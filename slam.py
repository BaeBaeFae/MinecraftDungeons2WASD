"""One bounded Jump Slam press per airborne movement, using the game's binding."""
import time

KEY_CODES = {chr(n): n for n in range(65, 91)}
KEY_CODES.update({name: 0x30+i for i, name in enumerate(
    ('Zero', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine'))})
KEY_CODES.update({'ThumbMouseButton': 5, 'ThumbMouseButton2': 6, 'MiddleMouseButton': 4})
BINDINGS = ('Auto', 'ThumbMouseButton', 'ThumbMouseButton2', 'MiddleMouseButton') + tuple(chr(n) for n in range(65, 91)) + tuple(
    ('Zero', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine'))


def select_binding(rows, preference='Auto', movement=()):
    """Never press an unrelated action or an ambiguous shared binding."""
    candidates = [key for action, key in rows if action == 'HeavyJumpAttack']
    if preference != 'Auto':
        candidates = [preference] if preference in candidates else []
    else:
        candidates.sort(key=lambda key: (not key.startswith('ThumbMouse'), key))
    for key in candidates:
        if key in KEY_CODES and key not in movement and not any(
                other == key and action != 'HeavyJumpAttack' for action, other in rows):
            return key, ''
    return None, 'Bind Jump Slam to an unused letter, number, middle mouse, or side button in the game. The companion selection must match.'


class SlamAssist:
    def __init__(self, io):
        self.io = io
        self.held = None
        self.release_at = 0.0
        self.armed = False
        self.since = None
        self.fired = False
        self.count = 0
        self.error = ''

    def release(self):
        if self.held:
            key = self.held
            # Keep ownership until Windows confirms release; stop can retry on failure.
            self.io.send(key, False)
            self.held = None

    def reset(self):
        self.release()
        self.armed, self.since, self.fired = False, None, False

    def update(self, now, eligible, grounded, airborne, left_down, key, delay_ms):
        if self.held and (now >= self.release_at or not eligible or not airborne or not left_down):
            self.release()
        if not eligible or not key or self.error:
            self.reset()
            return
        if grounded:
            self.armed, self.since, self.fired = True, None, False
            return
        if not airborne:
            self.reset()
            return
        if not self.armed:
            return
        if self.since is None:
            self.since = now
        if self.fired or not left_down or now-self.since < delay_ms/1000:
            return
        self.fired = True
        if self.io.down(KEY_CODES[key]):
            return  # The player already pressed the real binding; do not release it.
        self.held, self.release_at = key, now+0.08
        try:
            self.io.send(key, True)
        except Exception:
            self.release()
            raise
        self.count += 1


class WindowsInput:
    def __init__(self, pid):
        import ctypes as c
        from ctypes import wintypes as w
        self.c, self.w, self.pid = c, w, pid
        class Mouse(c.Structure):
            _fields_ = [('dx', w.LONG), ('dy', w.LONG), ('data', w.DWORD),
                        ('flags', w.DWORD), ('time', w.DWORD), ('extra', c.c_size_t)]
        class Keyboard(c.Structure):
            _fields_ = [('vk', w.WORD), ('scan', w.WORD), ('flags', w.DWORD),
                        ('time', w.DWORD), ('extra', c.c_size_t)]
        class Payload(c.Union):
            _fields_ = [('mouse', Mouse), ('keyboard', Keyboard)]
        class Input(c.Structure):
            _fields_ = [('type', w.DWORD), ('payload', Payload)]
        self.Input = Input
        self.api = c.WinDLL('user32', use_last_error=True)
        for name, args, result in [
            ('GetForegroundWindow', [], w.HWND),
            ('GetWindowThreadProcessId', [w.HWND, c.POINTER(w.DWORD)], w.DWORD),
            ('GetAsyncKeyState', [c.c_int], c.c_short),
            ('SendInput', [w.UINT, c.POINTER(Input), c.c_int], w.UINT),
        ]:
            fn = getattr(self.api, name)
            fn.argtypes, fn.restype = args, result

    def focused(self):
        pid = self.w.DWORD()
        self.api.GetWindowThreadProcessId(self.api.GetForegroundWindow(), self.c.byref(pid))
        return pid.value == self.pid

    def down(self, vk):
        return bool(self.api.GetAsyncKeyState(vk) & 0x8000)

    def send(self, key, down):
        event = self.Input()
        if key.startswith('ThumbMouse'):
            event.payload.mouse.data = 2 if key.endswith('2') else 1
            event.payload.mouse.flags = 0x80 if down else 0x100
        elif key == 'MiddleMouseButton':
            event.payload.mouse.flags = 0x20 if down else 0x40
        else:
            event.type = 1
            event.payload.keyboard.vk = KEY_CODES[key]
            event.payload.keyboard.flags = 0 if down else 2
        # Recheck focus at the actual press. Releases always clean up owned input.
        if down and not self.focused():
            raise RuntimeError('Game focus changed before the Jump Slam press. Apply settings to retry.')
        if self.api.SendInput(1, self.c.byref(event), self.c.sizeof(event)) != 1:
            raise RuntimeError('Windows blocked Jump Slam input. Run the game and companion at the same permission level, then Apply settings.')
