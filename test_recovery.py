from dataclasses import replace
import json
import queue
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch, Mock
from diagnostics import Recorder, redact
from errors import TransientGameState, ProcessSelectionError
from model import Settings
from winmem import select_process, EXE
from worker import Worker


class RecoveryTests(unittest.TestCase):
    def test_error_frames_include_context_without_paths_or_source(self):
        with tempfile.TemporaryDirectory() as folder:
            recorder = Recorder(folder)
            try:
                raise TransientGameState('interrupted')
            except TransientGameState as exc:
                recorder.error(exc, 'connection_update')
            frames = recorder.report()['recent_errors'][0]['frames']
            self.assertEqual(frames[-1]['module'], 'test_recovery.py')
            self.assertEqual(frames[-1]['function'], 'test_error_frames_include_context_without_paths_or_source')
            self.assertEqual(set(frames[-1]), {'module', 'function', 'line'})
            self.assertNotIn(str(Path(__file__).parent), json.dumps(frames))

    def test_same_character_recovers_with_real_engine_and_slam(self):
        # Keep the character and its old guard valid, exactly as when a brief
        # input-tree interruption occurs without changing maps or respawning.
        import struct
        from engine import Engine
        for slam_enabled in (True, False):
            with self.subTest(jump_slam=slam_enabled), tempfile.TemporaryDirectory() as folder:
                e = Engine.__new__(Engine)
                e.settings = replace(Settings(), jump_slam=slam_enabled)
                e.local, e.pc, e.pawn, e.move = 10000, 20000, 30000, 40000
                e.local_guard = e.move_guard = lambda: True
                e.last_refresh = time.monotonic()
                e.conflicts = []
                e.slam = types.SimpleNamespace(error='', count=216)
                e.slam_key, e.slam_problem = 'ThumbMouseButton', ''
                e.journal = Mock()
                e.capture_controls = Mock()
                e.prepare_context = Mock()
                e.patch_profile = Mock()
                e.patch_tree = Mock()
                e.flag = Mock()
                e.release_inputs = Mock()
                e.location = lambda: 'gameplay'
                e.profile_rows = lambda: [('HeavyJumpAttack', 60000, lambda: True)]
                e.movement_keys = lambda *args: set('WASD')
                offsets = {'PlayerInput': 64, 'EnhancedActionMappings': 80,
                           'CharacterMovement': 96, 'RotationRate': 0x2d0,
                           'MovementMode': 128, 'Mappings': 144}
                def offset(obj, key):
                    if not obj:
                        raise TransientGameState('Cannot read current game state (Windows error 299).')
                    return offsets[key]
                e.u = Mock()
                e.u.offset.side_effect = offset
                e.u.u64.side_effect = {10048: 20000, 20000+0x2e8: 30000,
                                      20064: 50000, 30096: 40000}.__getitem__
                e.u.class_name.return_value = 'PlayerCharacterMovementComponent'
                e.u.read.side_effect = lambda address, size: struct.pack('<ddd', 0, 900, 0) if size == 24 else b'keybytes'
                e.u.guard.return_value = lambda: True
                e.u.name_at.return_value = 'ThumbMouseButton'
                w = Worker(queue.Queue(), folder)
                w.engine = e
                w.enabled = w.configured = True
                owner, settings = e.journal, e.settings
                for _ in range(3):
                    w.recover(TransientGameState('Object changed before write; update cancelled.'), 'connection_update')
                    e.sync()  # Production sync and sync_slam; no Apply/configure.
                    self.assertEqual(e.move, 40000)
                    self.assertEqual(e.phase, 'active')
                    self.assertTrue(e.move_guard())
                    self.assertIs(e.journal, owner)
                    self.assertIs(e.settings, settings)
                    self.assertTrue(w.configured)
                e.journal.restore_where.assert_not_called()
                if slam_enabled:
                    self.assertEqual(e.slam_mode_offset, 128)
                    self.assertTrue(e.slam_binding_guard())

    def test_repeated_travel_recovery_preserves_configuration_and_undo_owner(self):
        # Drive the production lifecycle with a simulated clock, without a game.
        world = {'location': 'gameplay', 'generation': 1, 'read_fault': False}
        class Process:
            pid, hash = 123, 'supported-hash'
            def alive(self): return True
        class Engine:
            def __init__(self):
                self.move, self.phase = 1, 'active'
                self.checks, self.conflicts = [], []
                self.journal = object()
                self.generations, self.ticks = [], 0
                self.u = types.SimpleNamespace(refresh=lambda: None)
            def location(self): return world['location']
            def sync(self):
                if world['read_fault']: raise TransientGameState('travel read interrupted')
                self.phase = 'active' if world['location'] == 'gameplay' else world['location']
                self.move = world['generation'] if self.phase == 'active' else 0
                if self.move: self.generations.append(self.move)
            def tick(self, dt):
                if self.move:
                    assert self.move == world['generation'], 'stale character used'
                    self.ticks += 1
            def release_inputs(self): pass
            def flag(self, enabled): pass
            def diagnostics(self): return {'phase': self.phase}
            def state_snapshot(self): return {}
        with tempfile.TemporaryDirectory() as folder:
            w = Worker(queue.Queue(), folder)
            e = Engine()
            w.engine, w.process = e, Process()
            w.enabled = w.configured = True
            undo_owner = e.journal
            now = 0.0
            for generation in range(2, 102):
                world.update(generation=generation, read_fault=True)
                now += 3
                with self.assertRaises(TransientGameState) as caught:
                    w.step(now, .01, None, None, None)
                with patch('worker.time.monotonic', return_value=now):
                    w.recover(caught.exception, 'connection_update')
                ticks = e.ticks
                w.step(now+.1, .01, None, None, None)
                self.assertEqual(e.ticks, ticks)  # No stale updates during retry delay.
                world.update(read_fault=False, location='loading')
                w.step(now+1, .01, None, None, None)
                self.assertEqual(w.last_guide.stage, 'loading')
                world['location'] = 'gameplay'
                w.step(now+2, .01, None, None, None)
                self.assertEqual(w.last_guide.stage, 'active')
                self.assertTrue(w.configured)
                self.assertIs(w.engine, e)
                self.assertIs(e.journal, undo_owner)
                self.assertFalse(w.recovering)
            self.assertEqual(e.generations, list(range(2, 102)))
            self.assertEqual(w.recorder.total_errors, 100)
            stages = [v.stage for k, v in w.events.queue if k == 'guide']
            self.assertNotIn('return_title', stages)
            self.assertNotIn('apply', stages)

    def test_persistent_failure_has_bounded_backoff_and_stop_still_works(self):
        with tempfile.TemporaryDirectory() as folder:
            w = Worker(queue.Queue(), folder)
            w.enabled = w.configured = True
            delays = []
            for _ in range(20):
                with patch('worker.time.monotonic', return_value=100):
                    w.recover(TransientGameState('objects unavailable'), 'connection_update')
                delays.append(w.next_sync-100)
                self.assertEqual(w.last_guide.stage, 'recovering')
            self.assertEqual(delays[:4], [.25, .5, 1, 2])
            self.assertTrue(all(v == 2 for v in delays[4:]))
            w.command('stop', None, None, None, None)
            self.assertFalse(w.enabled)
            self.assertEqual(w.last_guide.stage, 'stopped')

    def test_game_exit_discards_old_engine_and_does_not_reuse_selected_pid(self):
        calls = []
        class OldProcess:
            pid, hash = 1, 'supported-hash'
            def alive(self): return False
            def close(self): calls.append('closed')
        class OldEngine:
            def release_inputs(self): calls.append('released')
            def diagnostics(self): return {}
            def state_snapshot(self): return {}
        class NewProcess:
            pid, hash = 2, 'supported-hash'
            def __init__(self, found, writable): calls.append(('opened', found[0]))
            def alive(self): return True
        class NewEngine:
            def __init__(self, process, settings): self.move = 0
            def enable_backup(self, path): pass
            def location(self): return 'gameplay'
            def can_resume(self): return True
            def flag(self, enabled): pass
        with tempfile.TemporaryDirectory() as folder:
            w = Worker(queue.Queue(), folder)
            w.process, w.engine = OldProcess(), OldEngine()
            w.enabled = w.configured = True
            w.selected_pid = 1
            finder = lambda: (2, 0, 'game')
            w.step(10, .01, NewEngine, NewProcess, finder)
            self.assertIsNone(w.engine)
            self.assertIsNone(w.selected_pid)
            self.assertFalse(w.configured)
            w.step(11, .01, NewEngine, NewProcess, finder)
            self.assertIsInstance(w.engine, NewEngine)
            self.assertEqual(w.last_guide.stage, 'resume')
            self.assertEqual(calls, ['released', 'closed', ('opened', 2)])

    def test_transitions_cleanup_failure_and_export_after_fatal(self):
        world = {'location': 'title', 'reads': 0, 'cleanup': False, 'refresh': 0, 'fatal': False, 'stops': 0}
        class Process:
            pid, hash = 123, 'supported-hash'
            def __init__(self, *a, **kw): pass
            def alive(self): return True
            def close(self): pass
        class Engine:
            def __init__(self, p, settings):
                self.settings, self.phase = settings, 'loading'
                self.checks, self.conflicts = [], []
                self.move, self.last_refresh = 0, 0
                self.u = types.SimpleNamespace(refresh=self.refresh)
            def refresh(self):
                if world['refresh']:
                    world['refresh'] -= 1
                    raise TransientGameState('refresh interrupted')
            def location(self): return world['location']
            def can_resume(self): return True
            def enable_backup(self, path): pass
            def configure(self, settings): self.settings = settings
            def release_inputs(self): pass
            def flag(self, enabled):
                if not enabled and world['cleanup']:
                    world['cleanup'] = False
                    raise RuntimeError('cleanup interrupted')
            def sync(self):
                if world['fatal']:
                    world['fatal'] = False
                    raise RuntimeError('Unexpected unsupported layout')
                self.phase = 'title' if self.location() == 'title' else 'active'
            def tick(self, dt):
                if world['reads']:
                    world['reads'] -= 1
                    raise TransientGameState('partial memory read during travel')
            def stop(self):
                world['stops'] += 1
                return 0, 0
            def diagnostics(self): return {'phase': self.phase}
            def state_snapshot(self): return {'controller_class': 'GameplayController'}
        modules = {'engine': types.SimpleNamespace(Engine=Engine),
                   'ue': types.SimpleNamespace(StaleState=TransientGameState),
                   'winmem': types.SimpleNamespace(Process=Process, find_game=lambda: (123, 0, 'game'))}
        events = queue.Queue()
        seen = []
        def wait(kind, stage=None):
            end = time.monotonic()+6
            while time.monotonic() < end:
                try: k, v = events.get(timeout=.1)
                except queue.Empty: continue
                seen.append((k, v))
                if k == kind and (stage is None or v.stage == stage): return v
            self.fail(f'No {kind} {stage}')
        with tempfile.TemporaryDirectory() as folder, patch.dict('sys.modules', modules):
            w = Worker(events, folder)
            w.start()
            try:
                w.commands.put(('start', Settings()))
                wait('guide', 'apply')
                w.commands.put(('settings', Settings()))
                wait('guide', 'load_character')
                world['location'] = 'gameplay'
                wait('guide', 'active')
                world.update(reads=1, cleanup=True, refresh=1)
                wait('guide', 'recovering')
                wait('guide', 'active')
                self.assertTrue(w.is_alive())
                self.assertTrue(w.configured)
                self.assertEqual(world['stops'], 0)
                self.assertGreaterEqual(w.recorder.total_errors, 3)
                self.assertTrue((Path(folder)/'diagnostics/last-session.json').exists())
                self.assertFalse(any(k == 'guide' and v.stage == 'return_title' for k,v in seen))
                world['fatal'] = True
                wait('guide', 'error')
                self.assertTrue(w.is_alive())
                self.assertFalse(w.enabled)
                w.commands.put(('diagnostics', 'chosen.json'))
                path, report = wait('diagnostics')
                self.assertEqual(path, 'chosen.json')
                self.assertIn('last_attached_snapshot', report)
                self.assertTrue(any('unsupported layout' in e['message'] for e in report['recent_errors']))
                w.commands.put(('start', Settings()))
                wait('guide', 'resume')
            finally:
                w.commands.put(('stop', None))
                w.commands.put(('close_keep', None))
                w.join(6)
                self.assertFalse(w.is_alive())

    def test_process_selection_is_explicit_and_ambiguous_auto_does_not_guess(self):
        rows = [{'pid': 1, 'name': 'Launcher.exe'}, {'pid': 2, 'name': EXE}, {'pid': 3, 'name': EXE}]
        with self.assertRaises(ProcessSelectionError): select_process(rows)
        self.assertEqual(select_process(rows, 3)['pid'], 3)
        self.assertEqual(select_process(rows, 1)['name'], 'Launcher.exe')
        self.assertIsNone(select_process(rows, 99))
        self.assertEqual(select_process(rows[:2])['pid'], 2)

    def test_manual_selection_works_while_waiting_but_not_while_attached(self):
        with tempfile.TemporaryDirectory() as folder:
            w = Worker(queue.Queue(), folder)
            w.enabled = True
            w.command('select_process', 42, None, None, None)
            self.assertFalse(w.enabled)
            self.assertEqual(w.selected_pid, 42)
            w.process = object()
            w.command('select_process', 43, None, None, None)
            self.assertEqual(w.selected_pid, 42)

    def test_interaction_mode_overrides_clicks_only_and_keeps_preferences(self):
        selected = replace(Settings(), native_interactions=True, jump_slam=True, maximum=1234)
        effective = selected.effective()
        self.assertFalse(effective.attack_in_place)
        self.assertFalse(effective.block_ground_move)
        self.assertFalse(effective.block_interaction_approach)
        self.assertFalse(effective.jump_slam)
        self.assertTrue(effective.wasd)
        self.assertEqual(effective.maximum, 1234)
        self.assertTrue(selected.attack_in_place)
        self.assertTrue(replace(selected, native_interactions=False).effective().jump_slam)

    def test_recorder_is_bounded_redacted_and_disk_failure_is_nonfatal(self):
        with tempfile.TemporaryDirectory() as folder:
            r = Recorder(folder)
            for _ in range(250):
                r.error(RuntimeError('failure C:\\Users\\PrivateUser\\game.exe\nmail private@example.com address 0x12345678'), 'sync')
            report = r.report()
            text = json.dumps(report)
            for private in ('PrivateUser', 'private@example.com', '0x12345678'):
                self.assertNotIn(private, text)
            self.assertEqual(len(report['events']), 200)
            self.assertEqual(len(report['recent_errors']), 30)
            self.assertEqual(report['total_errors'], 250)
            with patch.object(Path, 'mkdir', side_effect=OSError('disk full')):
                r.save(report, force=True)
            self.assertIn('disk full', r.save_error)

    def test_controller_subclasses_are_recognized_without_broad_name_guessing(self):
        from ue import UE
        u = UE.__new__(UE)
        pointers = {116: 200, 264: 300, 364: 0}
        u.u64 = lambda a: pointers[a]
        u.name = lambda a: {200: 'PlatformMenuSubclass_C', 300: 'BP_MenuPlayerController_C'}[a]
        self.assertTrue(u.is_a(100, 'BP_MenuPlayerController_C'))
        self.assertFalse(u.is_a(100, 'BP_GameplayPlayerController_C'))

    def test_manual_process_cannot_bypass_executable_hash_check(self):
        from winmem import Process
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'different.exe'
            path.write_bytes(b'not the supported executable')
            with patch('winmem.k.OpenProcess') as opened:
                with self.assertRaisesRegex(RuntimeError, 'Unsupported game build'):
                    Process((123, 0, path), writable=True)
                opened.assert_not_called()

    def test_native_interactions_do_not_require_patched_input_tree(self):
        from engine import Engine
        e = Engine.__new__(Engine)
        e.settings = replace(Settings(), native_interactions=True).effective()
        e.patch_tree(0)  # No UE access required with both click blockers disabled.

    def test_interrupted_verification_keeps_latest_write_owned_for_restore(self):
        from journal import Journal
        from test_app import Memory
        memory = Memory()
        memory.write(100, b'a')
        journal = Journal(memory)
        journal.set(100, b'b', lambda: True)
        read = memory.read
        count = [0]
        def interrupted(address, size):
            count[0] += 1
            if count[0] == 2: raise TransientGameState('verification interrupted')
            return read(address, size)
        with patch.object(memory, 'read', side_effect=interrupted):
            with self.assertRaises(TransientGameState): journal.set(100, b'c', lambda: True)
        self.assertEqual(journal.restore_where(), (1, 0))
        self.assertEqual(memory.read(100, 1), b'a')


if __name__ == '__main__': unittest.main()
