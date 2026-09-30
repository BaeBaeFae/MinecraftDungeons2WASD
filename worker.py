"""Connection lifecycle; a loading screen must not terminate the command worker."""
from dataclasses import asdict
import os
from pathlib import Path
import queue
import threading
import time
from diagnostics import Recorder
from errors import TransientGameState, ProcessSelectionError
from guidance import guide, classify_error
from model import Settings, VERSION

DATA = Path(os.environ.get('LOCALAPPDATA', Path.home()))/'DungeonsInputStudio'


class Worker(threading.Thread):
    def __init__(self, events, data_dir=None):
        super().__init__(daemon=False)
        self.commands, self.events = queue.Queue(), events
        self.data_dir = Path(data_dir) if data_dir else DATA
        self.recorder = Recorder(self.data_dir/'diagnostics')
        self.engine = self.process = None
        self.enabled = self.configured = self.configuring = False
        self.reload_required = False
        self.settings = Settings()
        self.last_guide = self.last_notice = None
        self.selected_pid = None
        self.retries = 0
        self.recovering = False
        self.next_sync = self.next_attach = self.next_refresh = 0.0
        self.running = True
        self.last_snapshot = {}

    def publish(self, stage, detail='', checks=()):
        value = guide(stage, detail, checks, self.configured)
        if value != self.last_guide:
            self.events.put(('guide', value))
            self.last_guide = value
        notice = (value.stage, value.title, value.detail, value.next_action)
        if notice != self.last_notice:
            self.events.put(('notice', value.title+'\n'+value.detail+'\n'))
            self.recorder.event('status', stage=stage, detail=detail)
            self.last_notice = notice
            if stage in ('unknown_screen', 'select_process'):
                self.recorder.save(self.report())

    def report(self):
        details = {'app_version': VERSION, 'settings': asdict(self.settings),
                   'configured': self.configured, 'connection_enabled': self.enabled,
                   'selection': 'manual' if self.selected_pid else 'automatic',
                   'retry_attempts': self.retries,
                   'last_stage': self.last_guide.stage if self.last_guide else 'idle'}
        if self.process:
            details['build_sha256'] = getattr(self.process, 'hash', None)
            details['pid'] = self.process.pid
        if self.engine:
            for method, key in [('diagnostics', 'engine'), ('state_snapshot', 'game_state')]:
                try:
                    details[key] = getattr(self.engine, method)()
                except Exception as exc:
                    details[key] = {'snapshot_error': str(exc)}
            self.last_snapshot = {key: details[key] for key in ('engine', 'game_state')}
        elif self.last_snapshot:
            details['last_attached_snapshot'] = self.last_snapshot
        return self.recorder.report(**details)

    def show_engine_state(self):
        phase = self.engine.phase
        if phase == 'needs_reload':
            self.reload_required = True
        if phase == 'title':
            self.publish('load_character' if self.configured else 'apply')
        else:
            detail = 'Conflicting bindings: '+', '.join(self.engine.conflicts) if self.engine.conflicts else ''
            if phase == 'assist_warning': detail = self.engine.slam_problem
            self.publish(phase, detail, self.engine.checks)

    def detach(self, restore=True):
        warning = ''
        if self.engine:
            try:
                if not self.process.alive():
                    release = getattr(self.engine, 'release_inputs', None)
                    if release: release()
                elif not restore:
                    self.engine.leave_controls()
                    self.events.put(('log', 'Originals saved; leaving bindings and click settings. Smoothing and Jump Slam stop.'))
                else:
                    restored, skipped = self.engine.stop()
                    if skipped:
                        warning = f'{skipped} entries expired, changed externally, or could not be restored.'
                    self.events.put(('log', f'Restored {restored} owned changes; {skipped} unconfirmed entries.'))
            except Exception as exc:
                warning = str(exc)
                self.recorder.error(exc, 'restore')
        self.engine = None
        if self.process: self.process.close()
        self.process = None
        self.configured = self.configuring = self.reload_required = False
        return warning

    def recover(self, exc, operation):
        self.retries += 1
        self.recovering = True
        self.recorder.error(exc, operation)
        if self.engine:
            # Cleanup failures must not escape the recovery handler or erase the journal.
            self.engine.move = 0
            for name, args in [('release_inputs', ()), ('flag', (False,))]:
                try:
                    fn = getattr(self.engine, name, None)
                    if fn: fn(*args)
                except Exception as cleanup:
                    self.recorder.error(cleanup, 'recovery_cleanup')
        self.publish('recovering', str(exc))
        self.recorder.save(self.report())
        self.next_sync = time.monotonic()+min(2, .25*2**min(self.retries-1, 3))
        self.next_attach = self.next_sync

    def fail(self, exc, operation):
        self.recorder.error(exc, operation)
        self.recorder.save(self.report(), force=True)
        warning = self.detach()
        self.enabled = False
        self.publish('restore_warning' if warning else classify_error(exc), str(exc)+ ('\nRestore: '+warning if warning else ''))
        self.recorder.save(self.report(), force=True)

    def find_target(self, finder):
        return finder(self.selected_pid) if self.selected_pid else finder()

    def command(self, cmd, value, Engine, Process, finder):
        if cmd == 'processes':
            from winmem import list_processes
            self.events.put(('processes', list_processes()))
        elif cmd == 'select_process':
            if self.process:
                self.events.put(('log', 'Restore originals before changing the selected process.'))
                return
            self.enabled = False
            self.selected_pid = value
            self.publish('idle', 'Manual selection set for this session.' if value else 'Automatic detection selected.')
        elif cmd == 'start':
            self.settings = value.validate()
            self.enabled = True
            self.configured = False
            self.configuring = self.recovering = False
            self.retries = 0
            self.next_attach = self.next_sync = 0
            self.publish('connecting')
        elif cmd == 'settings':
            self.settings = value.validate()
            if not self.engine:
                self.publish('waiting_game' if self.enabled else 'idle')
                return
            if not self.configured:
                location = self.engine.location()
                if location != 'title' and not self.engine.can_resume():
                    self.publish('return_title' if location == 'gameplay' else location)
                    return
            self.configuring = True
            self.next_sync = 0
            self.publish('applying')
        elif cmd in ('stop', 'restore', 'close', 'close_keep'):
            self.enabled = False
            if cmd in ('restore', 'close') and self.engine is None:
                found = self.find_target(finder)
                if not found:
                    self.publish('stopped', 'No running game to restore; backups retained.')
                    if cmd == 'close': self.running = False
                    return
                self.process = Process(found, writable=True)
                self.engine = Engine(self.process, self.settings)
                self.engine.enable_backup(self.data_dir/'backups')
            warning = self.detach(restore=cmd != 'close_keep')
            self.publish('restore_warning' if warning else 'stopped', warning)
            if cmd in ('close', 'close_keep'):
                if warning: self.events.put(('close_failed', warning))
                else: self.running = False
        elif cmd == 'diagnostics':
            self.events.put(('diagnostics', (value, self.report())))

    def step(self, now, dt, Engine, Process, finder):
        if self.process and not self.process.alive():
            self.recorder.event('game_exited')
            self.recorder.save(self.report(), force=True)
            self.detach()
            self.selected_pid = None  # Never reuse a manually selected PID after game exit.
            self.events.put(('selection_reset', None))
            self.publish('waiting_game', 'The game closed. Automatic detection will check the next session.')
            self.next_attach = now+1
        if not self.enabled:
            return
        if not self.process and now >= self.next_attach:
            found = self.find_target(finder)
            if not found:
                self.publish('waiting_game')
                self.next_attach = now+2
                return
            self.publish('connecting')
            self.process = Process(found, writable=True)
        if self.process and not self.engine and now >= self.next_attach:
            self.engine = Engine(self.process, self.settings)
            self.engine.enable_backup(self.data_dir/'backups')
            self.recorder.event('attached', build_sha256=self.process.hash)
            self.events.put(('log', f'Attached to PID {self.process.pid}; verified build {self.process.hash[:12]}.'))
            self.next_sync = 0
        if not self.engine:
            return
        if self.recovering and now < self.next_sync:
            return
        if now >= self.next_sync:
            if self.recovering and now >= self.next_refresh:
                self.next_refresh = now+2
                self.engine.u.refresh()
                self.engine.last_refresh = now
            location = self.engine.location()
            if location == 'title' and self.reload_required:
                self.configured = False
                self.reload_required = False
            applied = False
            if self.configuring:
                self.engine.configure(self.settings)
                self.configuring = False
                self.configured = True
                applied = True
            if not self.configured and location != 'title':
                self.engine.flag(False)
                self.engine.move = 0
                ready = location == 'gameplay' and self.engine.can_resume()
                self.publish('resume' if ready else 'return_title' if location == 'gameplay' else location)
            else:
                self.engine.sync()
                self.show_engine_state()
                if applied or self.recovering and self.configured:
                    self.events.put(('applied', asdict(self.settings)))
            if self.recovering:
                self.recorder.event('recovered', attempts=self.retries)
                self.recorder.save(self.report(), force=True)
            self.recovering = False
            self.retries = 0
            self.next_sync = now+.25
        if self.configured:
            self.engine.tick(dt)

    def run(self):
        from engine import Engine
        from ue import StaleState
        from winmem import Process, find_game
        previous = time.monotonic()
        try:
            while self.running:
                while self.running:
                    try: cmd, value = self.commands.get_nowait()
                    except queue.Empty: break
                    try:
                        self.command(cmd, value, Engine, Process, find_game)
                    except (TransientGameState, StaleState) as exc:
                        if cmd in ('close', 'close_keep', 'restore', 'stop'):
                            self.fail(exc, cmd)
                            self.events.put(('close_failed', str(exc)))
                        else:
                            self.recover(exc, cmd)
                    except Exception as exc:
                        self.fail(exc, cmd)
                        if cmd in ('close', 'close_keep'): self.events.put(('close_failed', str(exc)))
                if not self.running: break
                now = time.monotonic()
                dt, previous = now-previous, now
                try:
                    self.step(now, dt, Engine, Process, find_game)
                except ProcessSelectionError as exc:
                    self.publish('select_process', str(exc))
                    self.next_attach = now+2
                except (TransientGameState, StaleState) as exc:
                    self.recover(exc, 'connection_update')
                except Exception as exc:
                    self.fail(exc, 'connection_update')
                time.sleep(1/120 if self.enabled and self.engine and not self.recovering else .05)
        finally:
            self.detach()
            self.events.put(('closed', None))
