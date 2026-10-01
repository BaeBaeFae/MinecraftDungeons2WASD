import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from builds import BUILDS, select_build
from winmem import Process


class BuildTests(unittest.TestCase):
    def test_unknown_build_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Unsupported game build'):
            select_build('0' * 64)

    def test_each_gate_references_its_own_feature_flag(self):
        self.assertEqual(len(BUILDS), 2)
        for build in BUILDS.values():
            self.assertEqual(build.input_bytes[:2], b'\x80\x3d')
            displacement = struct.unpack_from('<i', build.input_bytes, 2)[0]
            self.assertEqual(build.input_gate + 7 + displacement, build.wasd_flag)

    def test_each_build_checks_its_own_runtime_signatures(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'game.exe'
            path.write_bytes(b'test fixture')
            for digest, build in BUILDS.items():
                with self.subTest(digest=digest), patch('winmem.hashlib.file_digest') as hashed, \
                     patch('winmem.k.OpenProcess', return_value=123), \
                     patch('winmem.k.CloseHandle'), patch.object(Process, 'read') as read:
                    hashed.return_value.hexdigest.return_value = digest
                    read.side_effect = [b'EFeature::WASD_Inputs\0', build.input_bytes]
                    process = Process((1, 0x10000000, path), writable=False)
                    self.assertIs(process.build, build)
                    self.assertEqual([call.args[0] for call in read.call_args_list],
                                     [process.base+build.feature_name, process.base+build.input_gate])
                    process.close()

    def test_runtime_mismatch_closes_handle(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'game.exe'
            path.write_bytes(b'test fixture')
            with patch('winmem.hashlib.file_digest') as hashed, \
                 patch('winmem.k.OpenProcess', return_value=123), \
                 patch('winmem.k.CloseHandle') as close, \
                 patch.object(Process, 'read', return_value=b'wrong signature'):
                hashed.return_value.hexdigest.return_value = next(iter(BUILDS))
                with self.assertRaisesRegex(RuntimeError, 'Runtime build signature'):
                    Process((1, 0x10000000, path), writable=False)
                close.assert_called_once_with(123)


if __name__ == '__main__': unittest.main()
