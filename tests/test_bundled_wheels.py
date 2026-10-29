import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from installer import engine
from installer.catalog import load_catalog


class BundledWheelInstallTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tool = copy.deepcopy(next(t for t in load_catalog(engine.DIST / 'toolkit/manifest.json') if t['id'] == 'spec-kit'))
        manifest = json.loads((engine.DIST / 'toolkit/wheels/manifest.json').read_bytes())
        self.wheel = next(r['wheel'] for r in manifest['wheels'] if r['name'] == 'cuid')
        self.tool['install']['wheels'] = [copy.deepcopy(self.wheel)]

    def test_verified_wheelhouse_is_passed_to_hash_locked_install(self):
        owner = self
        class Runner:
            def run(self, argv, *, cwd, env, timeout):
                wheelhouse = Path(env.get('PIP_FIND_LINKS', 'missing'))
                owner.assertEqual(wheelhouse, cwd / 'wheels')
                copied = wheelhouse / Path(owner.wheel['path']).name
                owner.assertEqual(hashlib.sha256(copied.read_bytes()).hexdigest(), owner.wheel['sha256'])
                return subprocess.CompletedProcess(argv, 1, '', '')
        with patch('installer.lifecycle.begin_runtime', return_value='ticket'):
            engine._python_install(self.root, self.tool, b'artifact', Runner(), {}, 'codex', 'project')

    def test_changed_bundled_wheel_is_rejected_before_creating_runtime(self):
        self.tool['install']['wheels'][0]['sha256'] = '0' * 64
        class Runner:
            def run(self, argv, **kwargs):
                return subprocess.CompletedProcess(argv, 1, '', '')
        with patch('installer.lifecycle.begin_runtime') as begin:
            with self.assertRaisesRegex(ValueError, 'bundled wheel checksum'):
                engine._python_install(self.root, self.tool, b'artifact', Runner(), {}, 'codex', 'project')
            begin.assert_not_called()
