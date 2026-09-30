import ctypes
import unittest
import types
from dataclasses import replace
from unittest.mock import Mock, patch
from model import Settings
from slam import SlamAssist, WindowsInput, select_binding


class SlamTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.io = Mock()
        self.io.down.return_value = False
        self.io.send.side_effect = lambda key, down: self.events.append((key, down))
        self.s = SlamAssist(self.io)

    def tick(self, now, mode=3, left=True, eligible=True):
        self.s.update(now, eligible, mode in (1, 2), mode == 3, left, 'ThumbMouseButton', 80)

    def test_no_ground_attack_and_one_press_per_airborne_movement(self):
        self.tick(0, 1)
        self.assertEqual(self.events, [])
        self.tick(.1)
        self.tick(.15)
        self.assertEqual(self.events, [])
        self.tick(.19)
        self.tick(.29)
        self.tick(.8)
        self.assertEqual(self.events, [('ThumbMouseButton', True), ('ThumbMouseButton', False)])
        self.tick(.9, 1)
        self.tick(1)
        self.tick(1.1)
        self.assertEqual(self.s.count, 2)

    def test_click_after_jump_and_manual_binding(self):
        self.tick(0, 1, False)
        self.tick(.1, left=False)
        self.tick(.3)
        self.assertEqual(self.s.count, 1)
        self.s.reset()
        self.io.down.return_value = True
        self.tick(1, 1)
        self.tick(1.1)
        self.tick(1.3)
        self.assertEqual(self.s.count, 1)
        self.assertIsNone(self.s.held)

    def test_focus_pause_stop_or_release_cleans_up_and_does_not_rearm_midair(self):
        for reason in ('focus', 'pause', 'stop', 'landing', 'release'):
            with self.subTest(reason=reason):
                self.setUp()
                self.tick(0, 1)
                self.tick(.1)
                self.tick(.2)
                if reason == 'stop': self.s.reset()
                else: self.tick(.21, 1 if reason == 'landing' else 3,
                                reason != 'release', reason not in ('focus', 'pause'))
                self.assertEqual(self.events[-1], ('ThumbMouseButton', False))
                if reason != 'landing':
                    self.tick(.4)
                    self.assertEqual(self.s.count, 1)

    def test_attaching_airborne_does_not_trigger(self):
        self.tick(0)
        self.tick(.2)
        self.assertEqual(self.events, [])

    def test_binding_selection_excludes_conflicts_and_validates_override(self):
        rows = [('HeavyJumpAttack', 'Q'), ('HeavyJumpAttack', 'ThumbMouseButton')]
        self.assertEqual(select_binding(rows)[0], 'ThumbMouseButton')
        self.assertEqual(select_binding(rows, 'Q')[0], 'Q')
        self.assertIsNone(select_binding(rows, 'E')[0])
        rows.append(('Jump', 'ThumbMouseButton'))
        self.assertEqual(select_binding(rows)[0], 'Q')
        self.assertIsNone(select_binding(rows, movement=('Q',))[0])

    def test_old_settings_defaults_and_validation(self):
        self.assertFalse(Settings().jump_slam)
        for values in ({'jump_slam': 1}, {'slam_binding': 'LeftMouseButton'},
                       {'slam_delay': -1}, {'slam_delay': float('nan')}):
            with self.assertRaises(ValueError): replace(Settings(), **values).validate()

    def test_failed_press_attempts_release(self):
        def fail_down(key, down):
            self.events.append((key, down))
            if down: raise RuntimeError('blocked')
        self.io.send.side_effect = fail_down
        self.tick(0, 1)
        self.tick(.1)
        with self.assertRaises(RuntimeError): self.tick(.2)
        self.assertEqual(self.events, [('ThumbMouseButton', True), ('ThumbMouseButton', False)])

    def test_windows_input_layout_and_encoding_without_sending_input(self):
        io = WindowsInput(123)
        self.assertEqual(ctypes.sizeof(io.Input), 40)
        io.focused = lambda: True
        sent = []
        def capture(count, pointer, size):
            e = ctypes.cast(pointer, ctypes.POINTER(io.Input)).contents
            sent.append(bytes(e))
            return 1
        io.api = Mock()
        io.api.SendInput.side_effect = capture
        for key in ('ThumbMouseButton', 'ThumbMouseButton2', 'Q'):
            io.send(key, True)
            io.send(key, False)
        events = [io.Input.from_buffer_copy(data) for data in sent]
        self.assertEqual([(e.payload.mouse.data, e.payload.mouse.flags) for e in events[:4]],
                         [(1, 128), (1, 256), (2, 128), (2, 256)])
        self.assertEqual([(e.type, e.payload.keyboard.vk, e.payload.keyboard.flags) for e in events[4:]],
                         [(1, ord('Q'), 0), (1, ord('Q'), 2)])

    def test_engine_gates_pause_readonly_and_changed_binding(self):
        from engine import Engine
        e = Engine.__new__(Engine)
        e.slam = self.s
        e.settings = replace(Settings(), jump_slam=True)
        e.p = types.SimpleNamespace(writable=True)
        e.slam_key, e.slam_problem, e.slam_mode_offset = 'ThumbMouseButton', '', 561
        e.move, e.local = 100, 10
        state = {'mode': 1, 'paused': False, 'binding': True}
        e.slam_binding_guard = lambda: state['binding']
        e.u = types.SimpleNamespace(
            read=lambda a, n: bytes([state['mode']]),
            offset=lambda obj, prop: 2 if prop == 'PauserPlayerState' else 1,
            u64=lambda a: int(state['paused']) if a == 12 else 10)
        self.io.focused.return_value = True
        self.io.down.side_effect = lambda vk: vk == 1
        with patch('engine.time.monotonic', return_value=0) as clock:
            e.tick_slam()
            state['mode'] = 3
            clock.return_value = .1
            e.tick_slam()
            clock.return_value = .2
            e.tick_slam()
            self.assertEqual(self.s.count, 1)
            state['paused'] = True
            e.tick_slam()
            self.assertIsNone(self.s.held)
            self.assertFalse(self.s.armed)
            state.update(mode=1, paused=False)
            e.tick_slam()
            state['binding'] = False
            e.tick_slam()
            self.assertFalse(self.s.armed)
            state['binding'] = True
            e.p.writable = False
            e.tick_slam()
            self.assertFalse(self.s.armed)


if __name__ == '__main__':
    unittest.main()
