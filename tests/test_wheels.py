"""Protect bundled source-to-wheel provenance and portable archive bytes."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class WheelsTest(unittest.TestCase):
    def manifest(self):
        path = ROOT / 'toolkit/wheels/manifest.json'
        self.assertTrue(path.is_file(), 'reviewed wheel manifest missing')
        return json.loads(path.read_text(encoding='utf-8'))

    def test_exact_reviewed_sources_and_pure_wheels(self):
        records = self.manifest()['wheels']
        self.assertEqual({r['name'] for r in records}, {'fire', 'cuid', 'func-timeout', 'ibm-cos-sdk', 'ibm-cos-sdk-core', 'ibm-cos-sdk-s3transfer'})
        for record in records:
            for kind in ('source', 'wheel'):
                payload = record[kind]
                file = ROOT / payload['path']
                self.assertTrue(file.resolve().is_relative_to((ROOT / 'toolkit/wheels').resolve()))
                self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), payload['sha256'])
            with zipfile.ZipFile(ROOT / record['wheel']['path']) as wheel:
                metadata = next(n for n in wheel.namelist() if n.endswith('.dist-info/WHEEL'))
                self.assertIn('Root-Is-Purelib: true', wheel.read(metadata).decode())
                self.assertTrue(all(not n.endswith(('.exe', '.dll', '.so', '.pyd')) for n in wheel.namelist()))

    def test_copyleft_texts_source_and_replacement_guidance(self):
        record = next(r for r in self.manifest()['wheels'] if r['name'] == 'func-timeout')
        self.assertEqual(record['license'], 'LGPL-3.0-only (runtime); LGPL-2.1-only (setup.py); upstream metadata differs')
        for name in ('GPL-3.0.txt', 'LGPL-3.0.txt', 'LGPL-2.1.txt'):
            self.assertTrue((ROOT / 'toolkit/wheels/licenses' / name).is_file())
        guidance = (ROOT / 'toolkit/wheels/BUILD.md').read_text(encoding='utf-8')
        self.assertIn('modified', guidance)
        self.assertIn('SOURCE_DATE_EPOCH', guidance)

    def test_git_attributes_preserve_binary_payloads(self):
        records = self.manifest()['wheels']
        # Binary attributes prevent platform checkout from changing frozen bytes.
        for record in records:
            for kind in ('source', 'wheel'):
                payload = record[kind]
                result = subprocess.run(['git', 'check-attr', 'text', '--', payload['path']], cwd=ROOT, capture_output=True, text=True, check=True)
                self.assertTrue(result.stdout.rstrip().endswith(': unset'))
