import hashlib
import io
import json
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import updater
from worker import Worker


def release(tag='v0.1.3-beta', **changes):
    name = f'MinecraftDungeons2WASD-{tag[1:]}-Windows-x64.zip'
    result = {'tag_name': tag, 'draft': False, 'prerelease': '-beta' in tag,
              'assets': [{'name': name, 'state': 'uploaded', 'digest': 'sha256:'+'a'*64,
                          'size': 100, 'browser_download_url': f'https://github.com/{updater.REPO}/releases/download/{tag}/{name}'}]}
    result.update(changes)
    return result


def zip_bytes(extra=()):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as archive:
        archive.writestr('DungeonsInputStudio/DungeonsInputStudio.exe', b'fixture executable')
        archive.writestr('DungeonsInputStudio/_internal/python312.dll', b'fixture runtime')
        for name, value in extra: archive.writestr(name, value)
    return data.getvalue()


class UpdaterTests(unittest.TestCase):
    def test_beta_order_drafts_and_no_downgrades(self):
        rows = [release('v0.1.2-beta'), release('v0.1.10-beta'), release('v1.0.0', draft=True)]
        self.assertEqual(updater.choose_release(rows, '0.1.3-beta')['version'], '0.1.10-beta')
        self.assertIsNone(updater.choose_release(rows, '0.1.10-beta'))
        self.assertIsNone(updater.choose_release(rows, '0.1.3'))
        self.assertGreater(updater.version('0.1.3'), updater.version('0.1.3-beta'))

    def test_require_complete_trusted_asset(self):
        for field, value in [('digest', None), ('size', 2**40), ('state', 'new'),
                             ('browser_download_url', 'https://github.com/other/release.zip')]:
            row = release()
            row['assets'][0][field] = value
            self.assertIsNone(updater.choose_release([row], '0.1.2-beta'))

    def test_redirects_require_https_and_known_hosts(self):
        for url in ['http://github.com/file', 'https://github.com.evil.example/file',
                    'https://user:secret@github.com/file', 'https://github.com:81/file']:
            with self.assertRaises(ValueError): updater.safe_url(url)
        self.assertEqual(updater.safe_url('https://release-assets.githubusercontent.com/a'),
                         'https://release-assets.githubusercontent.com/a')

    def test_reject_archive_traversal_links_and_duplicates(self):
        for name in ['../escape.exe', 'DungeonsInputStudio/../escape.exe',
                     'DungeonsInputStudio/C:/escape', 'DungeonsInputStudio/CON',
                     'DungeonsInputStudio/DUNGEONSINPUTSTUDIO.EXE']:
            with zipfile.ZipFile(io.BytesIO(zip_bytes([(name, b'bad')]))) as archive:
                with self.assertRaises(ValueError): updater.archive_paths(archive)
        link = zipfile.ZipInfo('DungeonsInputStudio/link')
        link.external_attr = 0o120777 << 16
        with zipfile.ZipFile(io.BytesIO(zip_bytes([(link, b'../outside')]))) as archive:
            with self.assertRaises(ValueError): updater.archive_paths(archive)

    def test_verified_stage_preserves_old_copy_and_validates_runtime_files(self):
        payload = zip_bytes()
        selected = updater.choose_release([release()], '0.1.2-beta')
        selected.update(size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        def fetch(url, limit, destination):
            destination.write(payload)
            return len(payload)
        with tempfile.TemporaryDirectory() as folder, patch('updater.fetch', side_effect=fetch):
            original = Path(folder)/'old.exe'
            original.write_bytes(b'old')
            record = updater.stage_update(selected, folder)
            exe = updater.installed_executable(record, folder, '0.1.2-beta')
            self.assertIsNotNone(exe)
            self.assertEqual(original.read_bytes(), b'old')
            self.assertFalse((Path(folder)/'updates/active.json').exists())
            with patch('updater.launch') as launch:
                updater.activate(record, folder, '0.1.2-beta')
                launch.assert_called_once_with(exe)
            self.assertEqual(updater.preferred_update(folder, '0.1.2-beta'), exe)
            self.assertIsNone(updater.preferred_update(folder, '0.1.3-beta'))
            (exe.parent/'_internal/python312.dll').write_bytes(b'changed')
            self.assertIsNone(updater.preferred_update(folder, '0.1.2-beta'))

    def test_bad_checksum_never_activates_or_leaves_partial_install(self):
        payload = zip_bytes()
        selected = updater.choose_release([release()], '0.1.2-beta')
        selected['size'] = len(payload)
        def fetch(url, limit, destination):
            destination.write(payload)
            return len(payload)
        with tempfile.TemporaryDirectory() as folder, patch('updater.fetch', side_effect=fetch):
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                updater.stage_update(selected, folder)
            self.assertEqual(list((Path(folder)/'updates').iterdir()), [])

    def test_network_failure_and_preference_do_not_change_game_settings(self):
        with patch('updater.fetch', side_effect=OSError('offline')):
            with self.assertRaises(OSError): updater.check('0.1.2-beta')
        with tempfile.TemporaryDirectory() as folder:
            self.assertTrue(updater.enabled(folder))
            updater.set_enabled(folder, False)
            self.assertFalse(updater.enabled(folder))
            self.assertFalse((Path(folder)/'settings.json').exists())

    def test_update_stop_acknowledges_even_when_already_stopped(self):
        with tempfile.TemporaryDirectory() as folder:
            worker = Worker(queue.Queue(), folder)
            worker.publish('stopped')
            worker.command('prepare_update', None, None, None, None)
            self.assertIn(('update_restored', ''), list(worker.events.queue))

    def test_update_stop_reports_restoration_failure(self):
        class Process:
            def alive(self): return True
            def close(self): pass
        class Engine:
            def stop(self): return 0, 2
        with tempfile.TemporaryDirectory() as folder:
            worker = Worker(queue.Queue(), folder)
            worker.process, worker.engine = Process(), Engine()
            worker.command('prepare_update', None, None, None, None)
            result = [v for k, v in worker.events.queue if k == 'update_restored']
            self.assertTrue(result[0])
            self.assertEqual(worker.last_guide.stage, 'restore_warning')
            self.assertFalse(worker.enabled)


if __name__ == '__main__': unittest.main()
