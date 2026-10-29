import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from installer.catalog import load_catalog
from installer.engine import _node_install

ROOT = Path(__file__).resolve().parents[1]


class ReviewedNodeManifestTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.dist = self.base / 'dist'
        self.root = self.base / 'project'
        self.root.mkdir()
        self.tool = copy.deepcopy(next(t for t in load_catalog(ROOT / 'toolkit/manifest.json') if t['id'] == 'openspec'))
        lock = ROOT / self.tool['install']['lock']['path']
        target = self.dist / self.tool['install']['lock']['path']
        target.parent.mkdir(parents=True)
        target.write_bytes(lock.read_bytes())
        self.manifest = json.loads(lock.read_bytes())['packages']['']
        self.manifest['overrides'] = {'basic-ftp': '6.2.3'}
        encoded = json.dumps(self.manifest).encode()
        file = target.parent / 'package.json'
        file.write_bytes(encoded)
        self.tool['install']['package'] = {'path': file.relative_to(self.dist).as_posix(), 'sha256': hashlib.sha256(encoded).hexdigest()}

    def test_preserves_hash_verified_overrides(self):
        expected = self.manifest
        owner = self
        class Runner:
            def run(self, argv, *, cwd, env, timeout):
                owner.assertEqual(json.loads((cwd / 'package.json').read_bytes()), expected)
                return subprocess.CompletedProcess(argv, 1, '', '')
        with patch('installer.engine.DIST', self.dist), patch('installer.lifecycle.begin_runtime', return_value='ticket'):
            _node_install(self.root, self.tool, b'artifact', Runner(), {}, Path('node.exe'), Path('npm.js'), 'codex', 'project')

    def test_tampered_package_manifest_fails_before_runtime_creation(self):
        self.tool['install']['package']['sha256'] = '0' * 64
        class Runner:
            def run(self, argv, **kwargs):
                return subprocess.CompletedProcess(argv, 1, '', '')
        with patch('installer.engine.DIST', self.dist), patch('installer.lifecycle.begin_runtime') as begin:
            with self.assertRaisesRegex(ValueError, 'package manifest checksum'):
                _node_install(self.root, self.tool, b'artifact', Runner(), {}, Path('node.exe'), Path('npm.js'), 'codex', 'project')
            begin.assert_not_called()

    def test_runtime_probe_disables_telemetry_and_exporters(self):
        owner = self
        class Runner:
            def run(self, argv, *, cwd, env, timeout):
                owner.assertEqual(env.get('PROMPTFOO_DISABLE_TELEMETRY'), '1')
                owner.assertEqual(env.get('OTEL_SDK_DISABLED'), 'true')
                return subprocess.CompletedProcess(argv, 1, '', '')
        with patch('installer.engine.DIST', self.dist), patch('installer.lifecycle.begin_runtime', return_value='ticket'):
            _node_install(self.root, self.tool, b'artifact', Runner(), {}, Path('node.exe'), Path('npm.js'), 'codex', 'project')
