import json
import math
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
import queue
import time
import types
from unittest.mock import patch
from model import Settings, PRESETS, angle_error, step
from journal import Journal
from guidance import guide, classify_error


class GuidanceTests(unittest.TestCase):
    def test_live_counters_refresh_without_repeating_notices(self):
        from app import Worker
        events = queue.Queue()
        worker = Worker(events)
        for n in range(6):
            worker.publish('active', checks=(f'Jump Slam: {n} presses sent',))
        received = list(events.queue)
        self.assertEqual(sum(kind == 'guide' for kind, value in received), 6)
        self.assertEqual(sum(kind == 'notice' for kind, value in received), 1)
        worker.publish('recovering', 'Waiting for character')
        worker.publish('active', checks=('Jump Slam: 6 presses sent',))
        self.assertEqual(sum(kind == 'notice' for kind, value in events.queue), 3)
        worker.publish('recovering', 'First error')
        worker.publish('recovering', 'Different error')
        self.assertEqual(sum(kind == 'notice' for kind, value in events.queue), 5)

    def test_no_success_until_verified_active(self):
        for stage in ('idle', 'waiting_game', 'connecting', 'return_title', 'apply',
                      'applying', 'load_character', 'loading', 'needs_reload',
                      'conflict', 'recovering', 'unsupported', 'error', 'stopped', 'restore_warning'):
            value = guide(stage)
            self.assertNotEqual(value.tone, 'success')
            self.assertTrue(value.next_action)
        self.assertEqual(guide('active').tone, 'success')
        self.assertEqual(guide('active').progress, 4)

    def test_apply_and_retry_availability(self):
        for stage in ('idle', 'waiting_game', 'connecting', 'return_title', 'applying', 'unsupported'):
            self.assertFalse(guide(stage).can_apply)
        for stage in ('apply', 'load_character', 'active', 'needs_reload', 'conflict'):
            self.assertTrue(guide(stage).can_apply)
        self.assertTrue(guide('error').can_start)
        self.assertEqual(classify_error(RuntimeError('Unsupported game build (abcd)')), 'unsupported')

    def test_full_worker_setup_and_new_session_require_apply(self):
        from app import Worker
        world = {'location': 'gameplay', 'alive': True, 'found': True, 'ticks': 0}
        class FakeProcess:
            pid, hash, writable = 123, 'verified', True
            def __init__(self, *args, **kwargs): pass
            def alive(self): return world['alive']
            def close(self): pass
        class FakeEngine:
            def __init__(self, p, settings):
                self.settings = settings
                self.phase, self.checks, self.conflicts = 'loading', [], []
                self.status, self.move, self.last_refresh = '', 0, time.monotonic()
                self.u = types.SimpleNamespace(refresh=lambda: None)
            def location(self): return world['location']
            def enable_backup(self, folder): pass
            def can_resume(self): return world.get('ready', False)
            def leave_controls(self): world['left_controls'] = True
            def sync(self):
                self.phase = 'title' if self.location() == 'title' else 'active'
                self.checks = ['Keyboard movement: 4/4 mappings ready']
            def tick(self, dt):
                if self.location() == 'gameplay':world['ticks'] += 1
            def flag(self, value): pass
            def stop(self):
                world['restores'] = world.get('restores', 0)+1
                return 9, world.get('skipped', 0)
            def configure(self, value): self.settings = value
        class Stale(RuntimeError): pass
        modules = {'engine': types.SimpleNamespace(Engine=FakeEngine),
                   'ue': types.SimpleNamespace(StaleState=Stale),
                   'winmem': types.SimpleNamespace(Process=FakeProcess, find_game=lambda: (123, 0, '') if world['found'] else None)}
        events = queue.Queue()
        def wait_stage(target):
            deadline = time.monotonic()+5
            while time.monotonic() < deadline:
                try:kind, value = events.get(timeout=.2)
                except queue.Empty:continue
                if kind == 'guide' and value.stage == target:return value
            self.fail('Missing stage: '+target)
        with patch.dict('sys.modules', modules):
            worker = Worker(events)
            worker.start()
            try:
                worker.commands.put(('start', Settings()))
                wait_stage('return_title')
                self.assertEqual(world['ticks'], 0)
                world['location'] = 'title'
                wait_stage('apply')
                self.assertFalse(worker.configured)
                worker.commands.put(('settings', Settings()))
                wait_stage('load_character')
                self.assertTrue(worker.configured)
                world['location'] = 'gameplay'
                wait_stage('active')
                self.assertGreater(world['ticks'], 0)
                world['ready'] = True
                worker.commands.put(('stop', None))
                wait_stage('stopped')
                worker.commands.put(('start', Settings()))
                wait_stage('resume')
                worker.commands.put(('settings', Settings()))
                wait_stage('active')
                world['alive'], world['found'] = False, False
                wait_stage('waiting_game')
                self.assertFalse(worker.configured)
                world.update(alive=True, found=True, location='title')
                wait_stage('apply')
                self.assertFalse(worker.configured)
                worker.commands.put(('stop', None))
                wait_stage('stopped')
                worker.commands.put(('start', Settings()))
                wait_stage('apply')
                world['skipped'] = 1
                worker.commands.put(('close', None))
                wait_stage('restore_warning')
                self.assertTrue(worker.is_alive())
                world['skipped'] = 0
                worker.commands.put(('start', Settings()))
                wait_stage('apply')
                restores = world['restores']
                worker.commands.put(('close_keep', None))
                worker.join(5)
                self.assertFalse(worker.is_alive())
                self.assertTrue(world['left_controls'])
                self.assertEqual(world['restores'], restores)
            finally:
                worker.commands.put(('close', None))
                worker.join(5)
                self.assertFalse(worker.is_alive())


class SettingsTests(unittest.TestCase):
    def test_roundtrip_and_unrecognized_profiles(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'profile.json'
            chosen = replace(Settings(), forward='Up', left='Left', back='Down', right='Right')
            chosen.save(path)
            self.assertEqual(Settings.load(path), chosen)
            path.write_text('{"schema": 999, "settings": {}}')
            with self.assertRaises(ValueError):
                Settings.load(path)

    def test_reject_invalid_settings_before_writes(self):
        for key, value in [('maximum', float('nan')), ('maximum', float('inf')), ('maximum', 0),
                           ('acceleration', -2), ('smooth', 'yes'), ('forward', 'S'), ('right', 'F99')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                replace(Settings(), **{key: value}).validate()


class TurningTests(unittest.TestCase):
    def test_wrap_uses_shortest_direction(self):
        self.assertEqual(angle_error(-179, 179), 2)
        self.assertEqual(angle_error(179, -179), -2)

    def test_converges_without_overshoot_at_different_frame_rates(self):
        for config in PRESETS.values():
            for fps in (30, 60, 120, 144):
                for initial in (1, 45, 90, 180):
                    error, speed = float(initial), 0.0
                    for _ in range(fps*4):
                        speed = step(speed, error, 1/fps, config)
                        self.assertGreaterEqual(speed, 0)
                        self.assertLessEqual(speed, config.maximum)
                        error -= min(error, speed/fps)
                    self.assertLess(error, 0.1)

    def test_initial_acceleration_and_long_stall_are_bounded(self):
        config = Settings()
        self.assertAlmostEqual(step(0, 180, 1/120, config), 50)
        self.assertLessEqual(step(0, 180, 10, config), config.acceleration*0.05)
        self.assertEqual(step(0, 90, .01, replace(config, smooth=False)), config.maximum)


class Memory:
    def __init__(self):
        self.data = bytearray(1000)
        self.writes = []
    def read(self, address, size):
        return bytes(self.data[address:address+size])
    def write(self, address, data):
        self.writes.append((address, bytes(data)))
        self.data[address:address+len(data)] = data


class RollbackTests(unittest.TestCase):
    def test_restore_original_after_multiple_updates(self):
        p = Memory()
        p.write(100, b'abc')
        journal = Journal(p)
        journal.set(100, b'def', lambda: True)
        journal.set(100, b'ghi', lambda: True)
        self.assertEqual(journal.restore_where(), (1, 0))
        self.assertEqual(p.read(100, 3), b'abc')

    def test_does_not_restore_into_expired_or_externally_changed_data(self):
        p = Memory()
        live = [True]
        journal = Journal(p)
        journal.set(100, b'A', lambda: live[0])
        journal.set(200, b'B', lambda: True)
        live[0] = False
        p.write(200, b'C')
        self.assertEqual(journal.restore_where(), (0, 2))
        self.assertEqual(p.read(100, 1), b'A')
        self.assertEqual(p.read(200, 1), b'C')

    def test_rejects_stale_write_and_resets_key_cache(self):
        p = Memory()
        journal = Journal(p)
        with self.assertRaises(RuntimeError):
            journal.set(100, b'A', lambda: False)
        self.assertEqual(p.writes, [])
        p.write(100, b'old-name' + b'cached-pointer!!')
        journal.set(100, b'new-name', lambda: True, key=True)
        self.assertEqual(p.read(108, 16), bytes(16))
        journal.restore_where()
        self.assertEqual(p.read(100, 8), b'old-name')
        self.assertEqual(p.read(108, 16), bytes(16))


if __name__ == '__main__':
    unittest.main()
