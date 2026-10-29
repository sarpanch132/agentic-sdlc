import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from installer.files import write_receipt


@unittest.skipUnless(os.name == 'nt', 'Windows sharing errors')
class WindowsReplaceTest(unittest.TestCase):
    def test_transient_sharing_error_retries_atomic_replace(self):
        original = os.replace
        calls = []
        def replace(source, target):
            calls.append(target)
            if len(calls) == 1:
                error = PermissionError('scanner temporarily owns file')
                error.winerror = 32
                raise error
            return original(source, target)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receipt.json'
            with patch('installer.files.os.replace', side_effect=replace):
                write_receipt(target, {'verified': True})
            self.assertEqual(len(calls), 2)
            self.assertIn('true', target.read_text())

    def test_persistent_permission_failure_stays_bounded_and_preserves_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'receipt.json'
            write_receipt(target, {'original': True})
            original = target.read_bytes()
            error = PermissionError('denied')
            error.winerror = 5
            with patch('installer.files.os.replace', side_effect=error) as replace:
                with self.assertRaises(PermissionError):
                    write_receipt(target, {'changed': True})
            self.assertLessEqual(replace.call_count, 5)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(list(Path(folder).glob('*.tmp')), [])
