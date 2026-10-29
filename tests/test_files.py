import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
try:
    from installer.files import resolve_owned, write_owned, write_receipt
except ImportError:
    def missing_feature(*args, **kwargs):
        raise AssertionError("Task 5 implementation is absent; behavior must be implemented")
    resolve_owned = write_owned = write_receipt = missing_feature

class OwnedPathTest(unittest.TestCase):
    def test_parent_escape_is_rejected(self):
        with TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                resolve_owned(Path(temporary), '../outside')

    def test_cross_host_escapes_and_windows_aliases_rejected(self):
        with TemporaryDirectory() as temporary:
            for name in ['/outside', r'C:\outside', 'C:outside', r'\\server\share', r'..\outside',
                         'a/../b', '', '.', 'a:stream', 'NUL.txt', 'a. /b', 'a//b']:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    resolve_owned(Path(temporary), name)

    def test_spaces_are_supported(self):
        with TemporaryDirectory(prefix='install root ') as temporary:
            root = Path(temporary)
            self.assertEqual(resolve_owned(root, 'some folder/file.txt'), root.resolve() / 'some folder/file.txt')

    def test_symlink_escape_rejected(self):
        with TemporaryDirectory() as temporary, TemporaryDirectory() as outside:
            root = Path(temporary)
            try:
                (root / 'escape').symlink_to(outside, target_is_directory=True)
            except OSError as error:
                self.skipTest(f'symlink privilege unavailable: {error}')
            with self.assertRaises(ValueError):
                resolve_owned(root, 'escape/file')

    @unittest.skipUnless(os.name == 'nt', 'Windows junction check')
    def test_junction_escape_rejected(self):
        import subprocess
        with TemporaryDirectory() as temporary, TemporaryDirectory() as outside:
            root = Path(temporary)
            result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(root / 'escape'), outside], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            try:
                with self.assertRaises(ValueError):
                    resolve_owned(root, 'escape/file')
            finally:
                (root / 'escape').rmdir()

class OwnedWriteTest(unittest.TestCase):
    def test_unknown_file_preserved(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'file').write_bytes(b'user data')
            with self.assertRaises(ValueError):
                write_owned(root, 'file', b'replacement')
            self.assertEqual((root / 'file').read_bytes(), b'user data')

    def test_modified_owned_file_preserved(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'file').write_bytes(b'edited')
            with self.assertRaises(ValueError):
                write_owned(root, 'file', b'replacement', hashlib.sha256(b'original').hexdigest())
            self.assertEqual((root / 'file').read_bytes(), b'edited')

    def test_owned_write_returns_actual_hash_and_can_update(self):
        with TemporaryDirectory(prefix='install root ') as temporary:
            root = Path(temporary)
            digest = write_owned(root, 'folder/file', b'original')
            self.assertEqual(digest, '0682c5f2076f099c34cfdd15a9e063849ed437a49677e6fcc5b4198c76575be5')
            updated = write_owned(root, 'folder/file', b'next', digest)
            self.assertEqual(updated, hashlib.sha256(b'next').hexdigest())
            self.assertEqual((root / 'folder/file').read_bytes(), b'next')

    def test_interrupted_receipt_preserves_previous_bytes_and_cleans_stage(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / 'receipt.json'
            path.write_bytes(b'{"old": true}')
            with patch('os.replace', side_effect=OSError('interrupted')):
                with self.assertRaises(OSError):
                    write_receipt(path, {'new': True})
            self.assertEqual(path.read_bytes(), b'{"old": true}')
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_serialization_failure_preserves_receipt(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / 'receipt.json'
            path.write_bytes(b'{"old": true}')
            with self.assertRaises((TypeError, ValueError)):
                write_receipt(path, {'invalid': object()})
            self.assertEqual(path.read_bytes(), b'{"old": true}')

    def test_receipt_round_trip(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / 'receipt.json'
            write_receipt(path, {'owned_files': {'file': 'abc'}, 'label': 'spaces allowed'})
            self.assertEqual(json.loads(path.read_text()), {'owned_files': {'file': 'abc'}, 'label': 'spaces allowed'})

    def test_interrupted_owned_update_preserves_old_content(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            digest = write_owned(root, 'file', b'old')
            with patch('os.replace', side_effect=OSError('interrupted')):
                with self.assertRaises(OSError):
                    write_owned(root, 'file', b'new', digest)
            self.assertEqual((root / 'file').read_bytes(), b'old')
            self.assertEqual(list(root.iterdir()), [root / 'file'])

    def test_receipt_cannot_follow_a_directory_junction(self):
        if os.name != 'nt':
            self.skipTest('Windows junction check')
        import subprocess
        with TemporaryDirectory() as temporary, TemporaryDirectory() as outside:
            root = Path(temporary)
            result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(root / 'escape'), outside], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            try:
                with self.assertRaises(ValueError):
                    write_receipt(root / 'escape/receipt.json', {})
                self.assertFalse((Path(outside) / 'receipt.json').exists())
            finally:
                (root / 'escape').rmdir()

if __name__ == '__main__':
    unittest.main()
