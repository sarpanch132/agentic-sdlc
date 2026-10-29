import subprocess
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class InstallerCLI(unittest.TestCase):
    def test_configuration_cli_requires_explicit_selection_and_reports_missing_runtime(self):
        import json
        with tempfile.TemporaryDirectory(prefix='configure project ') as project:
            base = [sys.executable, '-m', 'installer', 'configure', '--host', 'codex',
                    '--scope', 'project', '--project', project]
            missing = subprocess.run(base, cwd=self.distribution, env=self.env, capture_output=True, text=True)
            self.assertEqual(missing.returncode, 2)
            self.assertIn('--tools', missing.stderr)
            blocked = subprocess.run(base + ['--tools', 'superpowers'], cwd=self.distribution,
                                     env=self.env, capture_output=True, text=True)
            self.assertEqual(blocked.returncode, 1)
            self.assertEqual(json.loads(blocked.stdout)['status'], 'blocked')

    @classmethod
    def setUpClass(cls):
        from catalog_fixture import inactive_distribution
        cls.source = tempfile.TemporaryDirectory(prefix='offline CLI source ')
        cls.addClassCleanup(cls.source.cleanup)
        cls.distribution = Path(cls.source.name)
        inactive_distribution(cls.distribution)

    def setUp(self):
        import shutil, uuid
        from installer.state import secure
        home = Path.home() / ('.sdlc-cli-profile-' + uuid.uuid4().hex)
        secure(home, create=True)
        self.addCleanup(lambda: shutil.rmtree(home, ignore_errors=True))
        self.env = {**os.environ, 'HOME': str(home), 'USERPROFILE': str(home)}

    def test_project_install_copies_workflow_and_reports_blocked(self):
        with tempfile.TemporaryDirectory(prefix='install & ') as project:
            result = subprocess.run([sys.executable, '-m', 'installer', 'install', '--host', 'codex', '--scope', 'project', '--project', project], cwd=self.distribution, env=self.env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertTrue((Path(project) / '.agents/skills/agentic-sdlc/workflow/WORKFLOW.md').is_file())
            self.assertIn('graphify', result.stdout.lower())

    def test_cli_reports_each_catalog_gate_and_graphify(self):
        import json
        with tempfile.TemporaryDirectory() as project:
            result = subprocess.run([sys.executable, '-m', 'installer', 'install', '--host', 'codex', '--scope', 'project', '--project', project], cwd=self.distribution, env=self.env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            records = {record['tool_id']: record for record in json.loads(result.stdout)['tools']}
            self.assertEqual(len(records), 17)
            self.assertEqual(records['promptfoo']['reason'], 'locked-candidate-unverified')
            self.assertEqual(records['spec-kit']['reason'], 'locked-candidate-unverified')
            self.assertEqual(records['graphify']['reason'], 'locked-candidate-unverified')
            self.assertTrue(all(not record['installed'] for record in records.values()))

    def test_disposable_cli_install_update_rollback_uninstall_cycle(self):
        import json
        with tempfile.TemporaryDirectory(prefix='cycle & ') as project:
            expected = {'install': 1, 'update': 1, 'rollback': 1, 'uninstall': 0}
            for action, exit_code in expected.items():
                result = subprocess.run([sys.executable, '-m', 'installer', action, '--host', 'codex', '--scope', 'project', '--project', project], cwd=self.distribution, env=self.env, capture_output=True, text=True)
                self.assertEqual(result.returncode, exit_code, action + ': ' + result.stderr)
                data = json.loads(result.stdout)
                self.assertNotEqual(data['status'], 'failed', data)
            self.assertFalse((Path(project) / '.agents/skills/agentic-sdlc/SKILL.md').exists())
            repeated = subprocess.run([sys.executable, '-m', 'installer', 'uninstall', '--host', 'codex', '--scope', 'project', '--project', project], cwd=self.distribution, env=self.env, capture_output=True, text=True)
            self.assertEqual(repeated.returncode, 0, repeated.stdout)
