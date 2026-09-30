"""Minimal Windows process API. Does not change page protections or execute remote code."""
import ctypes as c
from ctypes import wintypes as w
import hashlib
from pathlib import Path
import struct
from model import BUILD_HASH

k = c.WinDLL('kernel32', use_last_error=True)
EXE = 'Dungeons-Win64-Shipping.exe'


class ProcessEntry(c.Structure):
    _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('pid', w.DWORD),
                ('heap', c.c_size_t), ('module', w.DWORD), ('threads', w.DWORD),
                ('parent', w.DWORD), ('priority', w.LONG), ('flags', w.DWORD), ('name', w.WCHAR * 260)]


class ModuleEntry(c.Structure):
    _fields_ = [('size', w.DWORD), ('module', w.DWORD), ('pid', w.DWORD),
                ('global_usage', w.DWORD), ('process_usage', w.DWORD), ('base', c.c_void_p),
                ('base_size', w.DWORD), ('handle', w.HMODULE), ('name', w.WCHAR * 256), ('path', w.WCHAR * 260)]


for name, args, result in [
    ('CreateToolhelp32Snapshot', [w.DWORD, w.DWORD], w.HANDLE),
    ('Process32FirstW', [w.HANDLE, c.POINTER(ProcessEntry)], w.BOOL),
    ('Process32NextW', [w.HANDLE, c.POINTER(ProcessEntry)], w.BOOL),
    ('Module32FirstW', [w.HANDLE, c.POINTER(ModuleEntry)], w.BOOL),
    ('Module32NextW', [w.HANDLE, c.POINTER(ModuleEntry)], w.BOOL),
    ('OpenProcess', [w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
    ('ReadProcessMemory', [w.HANDLE, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)], w.BOOL),
    ('WriteProcessMemory', [w.HANDLE, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)], w.BOOL),
    ('GetExitCodeProcess', [w.HANDLE, c.POINTER(w.DWORD)], w.BOOL),
    ('GetProcessTimes', [w.HANDLE, c.POINTER(w.FILETIME), c.POINTER(w.FILETIME), c.POINTER(w.FILETIME), c.POINTER(w.FILETIME)], w.BOOL),
    ('CreateMutexW', [c.c_void_p, w.BOOL, w.LPCWSTR], w.HANDLE),
    ('CloseHandle', [w.HANDLE], w.BOOL),
]:
    fn = getattr(k, name)
    fn.argtypes, fn.restype = args, result


def checked(ok, text):
    if not ok:
        raise RuntimeError(f'{text} (Windows error {c.get_last_error()}).')
    return ok


def snapshot(flags, pid=0):
    value = k.CreateToolhelp32Snapshot(flags, pid)
    if value == c.c_void_p(-1).value:
        raise RuntimeError('Unable to enumerate the game process.')
    return value


def find_game():
    matches = []
    snap = snapshot(2)
    entry = ProcessEntry(size=c.sizeof(ProcessEntry))
    try:
        ok = k.Process32FirstW(snap, c.byref(entry))
        while ok:
            if entry.name.lower() == EXE.lower():
                matches.append(entry.pid)
            ok = k.Process32NextW(snap, c.byref(entry))
    finally:
        k.CloseHandle(snap)
    if not matches:
        return None
    if len(matches) != 1:
        raise RuntimeError('Keep only one copy of the game running.')
    pid = matches[0]
    snap = snapshot(0x18, pid)
    entry = ModuleEntry(size=c.sizeof(ModuleEntry))
    try:
        ok = k.Module32FirstW(snap, c.byref(entry))
        while ok:
            if entry.name.lower() == EXE.lower():
                return pid, entry.base, Path(entry.path)
            ok = k.Module32NextW(snap, c.byref(entry))
    finally:
        k.CloseHandle(snap)
    raise RuntimeError('Game module is still loading. Try again at the title screen.')


class Process:
    def __init__(self, found, writable=False):
        self.pid, self.base, self.path = found
        with self.path.open('rb') as source:
            self.hash = hashlib.file_digest(source, 'sha256').hexdigest()
        if self.hash != BUILD_HASH:
            raise RuntimeError(f'Unsupported game build ({self.hash[:12]}). No changes made.')
        self.handle = checked(k.OpenProcess(0x438 if writable else 0x410, False, self.pid),
                              'Cannot open game; run both apps at the same permission level')
        self.writable = writable
        try:
            expected = b'EFeature::WASD_Inputs\0'
            if self.read(self.base + 0x9D6CD80, len(expected)) != expected:
                raise RuntimeError('Runtime build signature did not match.')
            if self.read(self.base + 0x63B936B, 9) != bytes.fromhex('80 3d 9e f2 ca 05 00 74 5a'):
                raise RuntimeError('Input code differs from the supported original build.')
        except Exception:
            self.close()
            raise

    def read(self, address, size):
        if not 0 < address < 0x7fffffffffff or not 0 <= size <= 16 * 1024 * 1024:
            raise RuntimeError('Invalid memory range.')
        buf, count = c.create_string_buffer(size), c.c_size_t()
        checked(k.ReadProcessMemory(self.handle, address, buf, size, c.byref(count)), 'Cannot read current game state')
        if count.value != size:
            raise RuntimeError('Game state changed during read.')
        return buf.raw

    def write(self, address, data):
        if not self.writable:
            raise RuntimeError('Read-only attachment.')
        count = c.c_size_t()
        checked(k.WriteProcessMemory(self.handle, address, data, len(data), c.byref(count)), 'Cannot update game data')
        if count.value != len(data):
            raise RuntimeError('Incomplete game-data update.')

    def u64(self, address):
        return struct.unpack('<Q', self.read(address, 8))[0]

    def alive(self):
        code = w.DWORD()
        return bool(self.handle and k.GetExitCodeProcess(self.handle, c.byref(code)) and code.value == 259)

    def session_id(self):
        created, exited, kernel, user = w.FILETIME(), w.FILETIME(), w.FILETIME(), w.FILETIME()
        checked(k.GetProcessTimes(self.handle, c.byref(created), c.byref(exited), c.byref(kernel), c.byref(user)), 'Cannot identify game session')
        return f'{self.pid}-{(created.dwHighDateTime << 32) | created.dwLowDateTime}'

    def close(self):
        if self.handle:
            k.CloseHandle(self.handle)
            self.handle = None
