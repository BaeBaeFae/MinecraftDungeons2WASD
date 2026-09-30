import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from journal import Journal
from control_backup import ControlBackup
from test_app import Memory


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'undo.json'
        self.p = Memory()
        self.p.alive = lambda: True
        self.session = {'session': 'pid-creation-time', 'hash': 'verified'}
        self.valid = True

    def guard(self, record=None):
        def check(): return self.valid
        check.record = record or {'identity': [1, 2, 3], 'checks': []}
        return check

    def journal(self):
        j = Journal(self.p)
        j.attach_store(self.path, self.session, self.guard)
        return j

    def test_saved_before_write_and_restore_after_reopen(self):
        self.p.write(100, b'old-name')
        j = self.journal()
        original_write = self.p.write
        def verify_backup_first(address, data):
            saved = json.loads(self.path.read_text())
            self.assertEqual(saved['entries'][0]['original'], b'old-name'.hex())
            original_write(address, data)
        with patch.object(self.p, 'write', side_effect=verify_backup_first):
            j.set(100, b'new-name', self.guard(), key=True)
        self.assertEqual(self.journal().restore_where(), (1, 0))
        self.assertEqual(self.p.read(100, 8), b'old-name')

    def test_new_process_never_uses_saved_addresses(self):
        self.journal().set(100, b'x', self.guard())
        with self.assertRaises(RuntimeError):
            Journal(self.p).attach_store(self.path, {'session': 'reused-pid-new-time'}, self.guard)
        self.assertEqual(self.p.read(100, 1), b'x')

    def test_expired_guards_and_external_remaps_are_not_overwritten(self):
        self.journal().set(100, b'x', self.guard())
        self.valid = False
        self.assertEqual(self.journal().restore_where(), (0, 0))
        self.assertEqual(self.p.read(100, 1), b'x')
        self.valid = True
        j = self.journal()
        j.set(200, b'y', self.guard())
        self.p.write(200, b'z')
        self.assertEqual(j.restore_where(), (0, 1))
        self.assertEqual(self.p.read(200, 1), b'z')

    def test_failed_backup_prevents_memory_write(self):
        j = self.journal()
        with patch.object(j, 'save', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError): j.set(100, b'x', self.guard())
        self.assertEqual(self.p.writes, [])

    def test_failed_restore_retains_entry_for_retry(self):
        j = self.journal()
        j.set(100, b'x', self.guard())
        with patch.object(self.p, 'write', side_effect=RuntimeError('write failed')):
            self.assertEqual(j.restore_where(), (0, 1))
        self.assertIn(100, j.entries)
        self.assertEqual(self.journal().restore_where(), (1, 0))

    def test_named_originals_survive_restart_without_overwriting_user_changes(self):
        path = Path(self.temp.name)/'controls.json'
        b = ControlBackup(path)
        b.capture([{'action': 'Root', 'key': 'LeftShift'}])
        b.record('profile_root', 'LeftShift', 'LeftMouseButton')
        b = ControlBackup(path)
        b.record('profile_root', 'LeftMouseButton', 'LeftMouseButton')
        self.assertEqual(b.wanted('profile_root', 'LeftMouseButton'), 'LeftShift')
        self.assertIsNone(b.wanted('profile_root', 'Z'))
        b.record('profile_root', 'Z', 'LeftMouseButton')
        self.assertEqual(b.wanted('profile_root', 'LeftMouseButton'), 'Z')
        b.restored('profile_root')
        self.assertIsNone(ControlBackup(path).wanted('profile_root', 'LeftMouseButton'))
        self.assertEqual(b.data['original_bindings'][0]['key'], 'LeftShift')


if __name__ == '__main__': unittest.main()
