import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from installer.catalog import load_catalog
from catalog_fixture import inactive_catalog

ROOT = Path(__file__).resolve().parents[1]

class AssetInstall(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='owned & ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = inactive_catalog()
        import shutil, uuid
        state_path = Path.home() / ('.sdlc-private-test-' + uuid.uuid4().hex)
        self.addCleanup(lambda: shutil.rmtree(state_path, ignore_errors=True))
        private = patch('installer.lifecycle._private_root', return_value=state_path)
        private.start()
        self.addCleanup(private.stop)
        self.assertIsNotNone(__import__('importlib.util', fromlist=['find_spec']).find_spec('installer.engine'))

    def test_unknown_file_is_preserved(self):
        self.assertIsNotNone(__import__("importlib.util", fromlist=["find_spec"]).find_spec("installer.engine"))
        from installer.engine import install
        target = self.root / '.agents/skills/agentic-sdlc/SKILL.md'
        target.parent.mkdir(parents=True)
        target.write_text('user data')
        result = install(self.catalog, self.root, None, host='codex', scope='project')
        self.assertEqual(target.read_text(), 'user data')
        self.assertNotEqual(result['status'], 'complete')

    def test_interrupted_write_can_resume_and_repeat(self):
        self.assertIsNotNone(__import__("importlib.util", fromlist=["find_spec"]).find_spec("installer.engine"))
        from installer.engine import install
        from installer.files import write_owned
        count = 0
        def interrupted(*args, **kwargs):
            nonlocal count
            count += 1
            result = write_owned(*args, **kwargs)
            if count == 2:
                raise InterruptedError('simulated interruption after write')
            return result
        with patch('installer.engine.write_owned', side_effect=interrupted):
            interrupted_result = install(self.catalog, self.root, None, host='codex', scope='project')
        self.assertEqual(interrupted_result['status'], 'failed')
        first = install(self.catalog, self.root, None, host='codex', scope='project')
        second = install(self.catalog, self.root, None, host='codex', scope='project')
        self.assertEqual(first['status'], 'blocked')
        self.assertEqual(second['status'], 'blocked')
        self.assertTrue((self.root / '.agents/skills/agentic-sdlc/workflow/WORKFLOW.md').is_file())

    def test_forged_receipt_cannot_claim_unrelated_file(self):
        self.assertIsNotNone(__import__("importlib.util", fromlist=["find_spec"]).find_spec("installer.engine"))
        from installer.engine import install
        victim = self.root / 'README.md'
        victim.write_text('preserve me')
        state = self.root / '.agentic-sdlc/receipt.json'
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps({'schema_version': 1, 'host': 'codex', 'scope': 'project', 'root': str(self.root.resolve()), 'owned_files': {'README.md': '0' * 64}, 'pending': None}))
        result = install(self.catalog, self.root, None, host='codex', scope='project')
        self.assertEqual(victim.read_text(), 'preserve me')
        self.assertNotEqual(result['status'], 'complete')



    def test_lock_contention_fails_and_release_allows_install(self):
        from installer.engine import _lock, install
        with _lock(self.root):
            blocked = install(self.catalog, self.root, None, host='codex', scope='project')
            self.assertEqual(blocked['status'], 'failed')
        result = install(self.catalog, self.root, None, host='codex', scope='project')
        self.assertEqual(result['status'], 'blocked')

    def test_host_overlays_and_diagnostics(self):
        from installer.engine import diagnose, install
        for host, prefix in [('claude', '.claude'), ('cursor', '.cursor'), ('codex', '.agents')]:
            with self.subTest(host=host), tempfile.TemporaryDirectory() as root:
                root = Path(root)
                result = install(self.catalog, root, None, host=host, scope='project')
                self.assertEqual(result['status'], 'blocked', result.get('reason'))
                self.assertEqual(len(result['tools']), 17)
                entry = root / prefix / 'skills/agentic-sdlc-brainstorming/SKILL.md'
                self.assertTrue(entry.is_file())
                if host == 'codex':
                    self.assertTrue((entry.parent / 'agents/openai.yaml').is_file())
                else:
                    self.assertIn('disable-model-invocation: false', entry.read_text(encoding='utf-8'))
                self.assertEqual(diagnose(self.catalog, root, None, host=host, scope='project')['status'], 'blocked')

    def test_missing_bundled_payload_is_reported_before_writes(self):
        from installer.engine import diagnose, install
        with tempfile.TemporaryDirectory() as source:
            source = Path(source)
            core = source / 'skills/agentic-sdlc'
            core.mkdir(parents=True)
            (core / 'SKILL.md').write_text('incomplete')
            (source / 'skills/dependencies').mkdir()
            with patch('installer.engine.DIST', source):
                result = install(self.catalog, self.root, None, host='codex', scope='project')
                diagnosis = diagnose(self.catalog, self.root, None, host='codex', scope='project')
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(diagnosis['status'], 'failed')
            self.assertIn('payload', diagnosis['reason'].lower())
            self.assertIn('payload', result['reason'].lower())
            self.assertFalse((self.root / '.agents').exists())

    def test_junction_at_workflow_root_is_rejected_before_writes(self):
        import os
        import shutil
        from installer.engine import install
        if os.name != 'nt':
            self.skipTest('Windows junction fixture')
        import _winapi
        with tempfile.TemporaryDirectory() as fixture:
            source = Path(fixture) / 'dist'
            source.mkdir()
            shutil.copytree(ROOT / 'skills', source / 'skills')
            shutil.copytree(ROOT / 'adapters', source / 'adapters')
            helper = source / 'skills/agentic-sdlc'
            real = source / 'held-helper'
            helper.rename(real)
            _winapi.CreateJunction(str(real), str(helper))
            with patch('installer.engine.DIST', source):
                result = install(self.catalog, self.root, None, host='codex', scope='project')
            self.assertEqual(result['status'], 'failed')
            self.assertIn('link', result['reason'].lower())
            self.assertFalse((self.root / '.agents').exists())

    def test_committed_archive_installs_without_integrity_error(self):
        import io
        import subprocess
        import tarfile
        from installer.engine import install
        archive = subprocess.run(['git', 'archive', 'HEAD'], cwd=ROOT, capture_output=True, check=True).stdout
        with tempfile.TemporaryDirectory() as source:
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                tar.extractall(source, filter='data')
            for relative in subprocess.check_output(['git', 'ls-files', 'skills/agentic-sdlc'], cwd=ROOT, text=True).splitlines():
                blob = subprocess.check_output(['git', 'show', 'HEAD:' + relative], cwd=ROOT)
                (Path(source) / relative).write_bytes(blob)
            with patch('installer.engine.DIST', Path(source)):
                result = install(self.catalog, self.root, None, host='codex', scope='project')
            self.assertEqual(result['status'], 'blocked', result['reason'])

    def test_inactive_catalog_reports_specific_gate_without_running(self):
        from installer.engine import install
        class NoRunner:
            def __getattr__(self, name):
                raise AssertionError('inactive catalog must not execute')
        result = install(self.catalog, self.root, NoRunner(), host='codex', scope='project')
        records = {record['tool_id']: record for record in result['tools']}
        self.assertEqual(len(records), 17)
        self.assertEqual(records['promptfoo']['reason'], 'locked-candidate-unverified')
        self.assertEqual(records['spec-kit']['reason'], 'locked-candidate-unverified')
        self.assertEqual(records['graphify']['reason'], 'locked-candidate-unverified')

    def test_active_checksum_mismatch_never_runs_recipe(self):
        import copy
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = catalog[1]
        tool['active'] = True
        tool['install']['executable'] = True
        tool['install']['status'] = 'ready'
        tool['install']['lock']['interpreter'] = f'Python{__import__("sys").version_info.major}.{__import__("sys").version_info.minor}'
        class CorruptRunner:
            def fetch(self, url, timeout):
                return b'wrong artifact'
            def run(self, *args, **kwargs):
                raise AssertionError('corrupt source must not run')
        result = install(catalog, self.root, CorruptRunner(), host='codex', scope='project')
        record = next(item for item in result['tools'] if item['tool_id'] == 'spec-kit')
        self.assertEqual(record['status'], 'failed')
        self.assertIn('checksum', record['reason'])
        self.assertFalse(record['acquired'])

    def test_active_transient_fetch_retries_only_once(self):
        import copy
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = catalog[1]
        tool['active'] = True
        tool['install']['executable'] = True
        tool['install']['status'] = 'ready'
        tool['install']['lock']['interpreter'] = f'Python{__import__("sys").version_info.major}.{__import__("sys").version_info.minor}'
        class Unavailable:
            def __init__(self): self.attempts = 0
            def fetch(self, url, timeout):
                self.attempts += 1
                raise TimeoutError('temporary')
        runner = Unavailable()
        result = install(catalog, self.root, runner, host='codex', scope='project')
        record = next(item for item in result['tools'] if item['tool_id'] == 'spec-kit')
        self.assertEqual(record['status'], 'failed')
        self.assertEqual(runner.attempts, 2)

    def test_transport_exception_never_exposes_secret(self):
        import copy
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        catalog[1]['active'] = True
        catalog[1]['install'].update(executable=True, status='ready')
        catalog[1]['install']['lock']['interpreter'] = f'Python{__import__("sys").version_info.major}.{__import__("sys").version_info.minor}'
        class Failing:
            def fetch(self, url, timeout):
                raise OSError('token=private-secret')
        result = install(catalog, self.root, Failing(), host='codex', scope='project')
        self.assertNotIn('private-secret', json.dumps(result))

    def test_fetch_holds_installer_lock(self):
        import copy
        from installer.engine import _lock, install
        catalog = copy.deepcopy(self.catalog)
        catalog[1]['active'] = True
        catalog[1]['install'].update(executable=True, status='ready')
        catalog[1]['install']['lock']['interpreter'] = f'Python{__import__("sys").version_info.major}.{__import__("sys").version_info.minor}'
        class CheckLock:
            def fetch(inner, url, timeout):
                with self.assertRaises(OSError):
                    with _lock(self.root): pass
                return b'bad'
        result = install(catalog, self.root, CheckLock(), host='codex', scope='project')
        self.assertEqual(next(t for t in result['tools'] if t['tool_id'] == 'spec-kit')['status'], 'failed')

    @unittest.skipIf(__import__('os').name not in ('nt', 'posix'), 'safe process isolation unavailable')
    def test_local_runner_uses_argv_and_filtered_environment(self):
        import os
        import sys
        import installer.engine
        self.assertTrue(hasattr(installer.engine, 'LocalRunner'))
        from installer.engine import LocalRunner
        os.environ['PROVIDER_PRIVATE_TOKEN'] = 'secret-value'
        self.addCleanup(os.environ.pop, 'PROVIDER_PRIVATE_TOKEN', None)
        result = LocalRunner().run([sys.executable, '-c', 'import os,sys; print(os.getenv("PROVIDER_PRIVATE_TOKEN", "absent")); print(sys.argv[1])', 'a & b'], cwd=self.root, env={'PATH': os.defpath}, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip().splitlines(), ['absent', 'a & b'])


    def test_local_fetch_rejects_oversized_artifact(self):
        import io
        from installer.engine import LocalRunner
        class Large:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size): return b'x' * size
        self.assertTrue(hasattr(LocalRunner, 'fetch'))
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = Large()
            with self.assertRaises(ValueError):
                LocalRunner().fetch('https://example.test/file', timeout=1)


    def test_graphify_record_uses_validated_runtime_catalog(self):
        from installer.engine import _records
        import copy
        catalog = copy.deepcopy(self.catalog)
        next(item for item in catalog if item['id'] == 'graphify')['version'] = '42.0'
        graphify = _records(catalog)[-1]
        self.assertEqual(graphify['version'], '42.0')

    @unittest.skipIf(__import__('os').name not in ('nt', 'posix'), 'safe process isolation unavailable')
    def test_active_install_uses_local_runner_when_unspecified(self):
        import copy
        from installer.engine import install, LocalRunner
        catalog = copy.deepcopy(self.catalog)
        catalog[1]['active'] = True
        catalog[1]['install'].update(executable=True, status='ready')
        catalog[1]['install']['lock']['interpreter'] = f'Python{__import__("sys").version_info.major}.{__import__("sys").version_info.minor}'
        with patch.object(LocalRunner, 'fetch', return_value=b'bad'):
            result = install(catalog, self.root, None, host='codex', scope='project')
        record = next(item for item in result['tools'] if item['tool_id'] == 'spec-kit')
        self.assertEqual(record['status'], 'failed')
        self.assertIn('checksum', record['reason'])

    def test_incompatible_python_is_blocked_without_fetch(self):
        import copy
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = catalog[1]
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        tool['install']['lock']['interpreter'] = 'Python0.0'
        class NoFetch:
            def fetch(self, *args, **kwargs):
                raise AssertionError('incompatible Python must not fetch')
        result = install(catalog, self.root, NoFetch(), host='codex', scope='project')
        record = next(item for item in result['tools'] if item['tool_id'] == 'spec-kit')
        self.assertEqual(record['status'], 'blocked')
        self.assertIn('Python0.0', record['reason'])

    def test_verified_python_recipe_failure_is_reported(self):
        import copy
        import hashlib
        import subprocess
        import sys
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = catalog[1]
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        tool['install']['lock']['interpreter'] = f'Python{sys.version_info.major}.{sys.version_info.minor}'
        content = b'verified test artifact'
        tool['sha256'] = hashlib.sha256(content).hexdigest()
        tool['artifact']['sha256'] = tool['sha256']
        tool['artifact']['bytes'] = len(content)
        class FailedRecipe:
            def fetch(self, url, timeout): return content
            def run(self, argv, *, cwd, env, timeout):
                if argv[1:3] == ['-m', 'ensurepip']:
                    return subprocess.CompletedProcess(argv, 0, '', '')
                self_test.assertEqual(argv[1:7], ['-m', 'pip', 'install', '--quiet', '--progress-bar', 'off'])
                self_test.assertIn('--require-hashes', argv)
                self_test.assertIn('--only-binary=:all:', argv)
                self_test.assertNotIn('PROVIDER_PRIVATE_TOKEN', env)
                return subprocess.CompletedProcess(argv, 1, '', '')
        self_test = self
        result = install(catalog, self.root, FailedRecipe(), host='codex', scope='project')
        record = next(item for item in result['tools'] if item['tool_id'] == 'spec-kit')
        self.assertEqual(record['status'], 'failed')
        self.assertFalse(record['installed'])

    def test_venv_bootstrap_uses_filtered_environment(self):
        import copy
        import hashlib
        import subprocess
        import sys
        import venv
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = catalog[1]
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        tool['install']['lock']['interpreter'] = f'Python{sys.version_info.major}.{sys.version_info.minor}'
        artifact = b'verified'
        tool['sha256'] = hashlib.sha256(artifact).hexdigest()
        tool['artifact'].update(sha256=tool['sha256'], bytes=len(artifact))
        commands = []
        class Runner:
            def fetch(self, url, timeout): return artifact
            def run(self, argv, *, cwd, env, timeout):
                commands.append(argv)
                return subprocess.CompletedProcess(argv, 1, '', '')
        with patch.object(venv, 'create') as create:
            install(catalog, self.root, Runner(), host='codex', scope='project')
        self.assertEqual(create.call_args.kwargs['with_pip'], False)
        self.assertEqual(commands[0][1:3], ['-m', 'ensurepip'])

    def test_verified_python_runtime_resumes_without_reinstalling(self):
        import copy
        import hashlib
        import subprocess
        import sys
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = catalog[1]
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        tool['install']['lock']['interpreter'] = f'Python{sys.version_info.major}.{sys.version_info.minor}'
        artifact = b'fixture artifact'
        tool['sha256'] = hashlib.sha256(artifact).hexdigest()
        tool['artifact'].update(sha256=tool['sha256'], bytes=len(artifact))
        class Runner:
            def __init__(self): self.installs = 0; self.fetches = 0
            def fetch(self, url, timeout): self.fetches += 1; return artifact
            def run(self, argv, *, cwd, env, timeout):
                if argv[1:3] == ['-m', 'pip']:
                    self.installs += 1
                    binary = Path(cwd) / 'venv' / ('Scripts' if __import__('os').name == 'nt' else 'bin') / ('specify.exe' if __import__('os').name == 'nt' else 'specify')
                    binary.write_bytes(b'fixture probe executable')
                return subprocess.CompletedProcess(argv, 0, 'specify ' + tool['version'], '')
        runner = Runner()
        first = install(catalog, self.root, runner, host='codex', scope='project')
        runtime_receipt = json.loads((self.root / '.agentic-sdlc/runtime-receipts/codex/spec-kit.json').read_text(encoding='utf-8'))
        self.assertIn('smoke_tested', runtime_receipt)
        self.assertTrue(runtime_receipt['smoke_tested'])
        self.assertFalse(runtime_receipt['project_integrated'])
        second = install(catalog, self.root, runner, host='codex', scope='project')
        record = next(item for item in second['tools'] if item['tool_id'] == 'spec-kit')
        self.assertEqual(runner.installs, 1)
        self.assertEqual(runner.fetches, 1)
        self.assertTrue(record['installed'])
        self.assertTrue(record['smoke_tested'])
        self.assertIn('independent private runtime inventory', record['evidence'])
        self.assertFalse(record['project_integrated'])

    def test_forged_runtime_receipt_never_executes_existing_probe(self):
        import copy, hashlib, os, subprocess, sys, venv
        from installer.engine import _runtime_hashes, install
        catalog = copy.deepcopy(self.catalog)
        tool = catalog[1]
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        tool['install']['lock']['interpreter'] = f'Python{sys.version_info.major}.{sys.version_info.minor}'
        artifact = b'fixture artifact'
        tool['sha256'] = hashlib.sha256(artifact).hexdigest()
        tool['artifact'].update(sha256=tool['sha256'], bytes=len(artifact))
        class Initial:
            def fetch(self, url, timeout): return artifact
            def run(self, argv, *, cwd, env, timeout):
                if argv[1:3] == ['-m', 'pip']:
                    binary = Path(cwd) / 'venv' / ('Scripts' if os.name == 'nt' else 'bin') / ('specify.exe' if os.name == 'nt' else 'specify')
                    binary.write_bytes(b'original probe')
                return subprocess.CompletedProcess(argv, 0, 'specify ' + tool['version'], '')
        def create(path, **kwargs):
            (Path(path) / ('Scripts' if os.name == 'nt' else 'bin')).mkdir(parents=True)
        with patch.object(venv, 'create', create):
            install(catalog, self.root, Initial(), host='codex', scope='project')
        receipt_path = self.root / '.agentic-sdlc/runtime-receipts/codex/spec-kit.json'
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        context = self.root / receipt['context']
        probe = context / 'venv' / ('Scripts' if os.name == 'nt' else 'bin') / ('specify.exe' if os.name == 'nt' else 'specify')
        probe.write_bytes(b'forged executable')
        receipt['files'] = _runtime_hashes(self.root, receipt['context'])
        receipt_path.write_text(json.dumps(receipt), encoding='utf-8')
        class NeverRun:
            def fetch(self, *args, **kwargs): raise AssertionError('must not fetch')
            def run(self, *args, **kwargs): raise AssertionError('must not execute forged probe')
        result = install(catalog, self.root, NeverRun(), host='codex', scope='project')
        record = next(item for item in result['tools'] if item['tool_id'] == 'spec-kit')
        self.assertEqual(record['status'], 'blocked')
        self.assertIn('authentication', record['reason'])

    def test_doctor_does_not_call_unverified_active_runtime_ready(self):
        import copy
        from installer.engine import diagnose, install
        install(self.catalog, self.root, None, host='codex', scope='project')
        catalog = copy.deepcopy(self.catalog)
        catalog[1]['active'] = True
        catalog[1]['install'].update(executable=True, status='ready')
        record = next(t for t in diagnose(catalog, self.root, None, host='codex', scope='project')['tools'] if t['tool_id'] == 'spec-kit')
        self.assertEqual(record['status'], 'blocked')
        self.assertNotEqual(record['reason'], 'ready')

    @unittest.skipIf(__import__('os').name not in ('nt', 'posix'), 'safe process isolation unavailable')
    def test_local_runner_redacts_secret_output(self):
        import sys
        from installer.engine import LocalRunner
        result = LocalRunner().run([sys.executable, '-c', 'print("token=secret-value")'], cwd=self.root, env={'PATH': __import__('os').defpath}, timeout=5)
        self.assertNotIn('secret-value', result.stdout)

    @unittest.skipIf(__import__('os').name not in ('nt', 'posix'), 'safe process isolation unavailable')
    def test_fresh_active_python_bootstraps_real_isolated_venv_offline(self):
        import copy, hashlib, subprocess, sys
        from installer.engine import install, LocalRunner
        catalog = copy.deepcopy(self.catalog)
        tool = catalog[1]
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        tool['install']['lock']['interpreter'] = f'Python{sys.version_info.major}.{sys.version_info.minor}'
        artifact = b'controlled artifact'
        tool['sha256'] = hashlib.sha256(artifact).hexdigest()
        tool['artifact'].update(sha256=tool['sha256'], bytes=len(artifact))
        class OfflineRunner(LocalRunner):
            def fetch(self, url, timeout): return artifact
            def run(self, argv, *, cwd, env, timeout):
                if argv[1:3] == ['-m', 'pip']:
                    self_test.assertTrue((Path(cwd) / 'venv' / 'pyvenv.cfg').is_file())
                    return subprocess.CompletedProcess(argv, 1, '', '')
                return super().run(argv, cwd=cwd, env=env, timeout=timeout)
        self_test = self
        result = install(catalog, self.root, OfflineRunner(), host='codex', scope='project')
        record = next(item for item in result['tools'] if item['tool_id'] == 'spec-kit')
        self.assertEqual(record['reason'], 'install command failed')
        self.assertFalse(record['installed'])

    def test_http_503_is_retried_once(self):
        import copy, sys
        from urllib.error import HTTPError
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = catalog[1]
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        tool['install']['lock']['interpreter'] = f'Python{sys.version_info.major}.{sys.version_info.minor}'
        class Transient:
            def __init__(self): self.calls = 0
            def fetch(self, url, timeout):
                self.calls += 1
                if self.calls == 1: raise HTTPError(url, 503, 'unavailable', {}, None)
                return b'bad checksum'
        runner = Transient()
        result = install(catalog, self.root, runner, host='codex', scope='project')
        record = next(t for t in result['tools'] if t['tool_id'] == 'spec-kit')
        self.assertEqual(runner.calls, 2)
        self.assertIn('checksum', record['reason'])

    def test_node_without_trusted_runtime_is_blocked_before_fetch(self):
        import copy, hashlib, subprocess
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = next(t for t in catalog if t['id'] == 'promptfoo')
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        artifact = b'node fixture'
        tool['sha256'] = hashlib.sha256(artifact).hexdigest()
        tool['artifact'].update(sha256=tool['sha256'], bytes=len(artifact))
        node = self.root / 'node.exe'
        node.write_bytes(b'native fixture')
        npm_cli = self.root / 'node_modules/npm/bin/npm-cli.js'
        npm_cli.parent.mkdir(parents=True)
        npm_cli.write_text('fixture')
        class Failing:
            def fetch(self, url, timeout): raise AssertionError('unverified node must not fetch')
            def run(self, argv, *, cwd, env, timeout):
                self_test.assertEqual(argv[:3], [str(node), str(npm_cli), 'ci'])
                self_test.assertIn('--ignore-scripts', argv)
                return subprocess.CompletedProcess(argv, 1, '', '')
        self_test = self
        with patch('shutil.which', return_value=str(node)):
            result = install(catalog, self.root, Failing(), host='codex', scope='project')
        record = next(t for t in result['tools'] if t['tool_id'] == 'promptfoo')
        self.assertEqual(record['status'], 'blocked')
        self.assertIn('verified Node', record['reason'])

    def test_node_platform_prerequisites_and_frozen_recipe(self):
        import copy, hashlib, subprocess
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = next(t for t in catalog if t['id'] == 'openspec')
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        artifact = b'controlled node artifact'
        tool['sha256'] = hashlib.sha256(artifact).hexdigest()
        tool['artifact'].update(sha256=tool['sha256'], bytes=len(artifact))
        with tempfile.TemporaryDirectory(prefix='platform-') as platform:
            node = Path(platform) / ('node.exe' if __import__('os').name == 'nt' else 'node')
            node.write_bytes(b'platform node')
            npm = node.parent / 'node_modules/npm/bin/npm-cli.js'
            npm.parent.mkdir(parents=True)
            npm.write_text('platform npm')
            class Controlled:
                def fetch(self, url, timeout): return artifact
                def run(self, argv, *, cwd, env, timeout):
                    if argv == [str(node), '--version']:
                        return subprocess.CompletedProcess(argv, 0, 'v20.19.0', '')
                    if argv == [str(node), str(npm), '--version']:
                        return subprocess.CompletedProcess(argv, 0, '10.0.0', '')
                    self_test.assertEqual(argv[:3], [str(node), str(npm), 'ci'])
                    self_test.assertIn('--ignore-scripts', argv)
                    return subprocess.CompletedProcess(argv, 1, '', '')
            self_test = self
            with patch('shutil.which', return_value=str(node)):
                result = install(catalog, self.root, Controlled(), host='codex', scope='project')
        record = next(t for t in result['tools'] if t['tool_id'] == 'openspec')
        self.assertEqual(record['status'], 'failed')
        self.assertEqual(record['reason'], 'install command failed')

    def test_active_oci_uses_native_docker_and_digest_only(self):
        import copy, subprocess
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = next(t for t in catalog if t['id'] == 'helicone')
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        with tempfile.TemporaryDirectory(prefix='platform-') as platform:
            docker = Path(platform) / ('docker.exe' if __import__('os').name == 'nt' else 'docker')
            docker.write_bytes(b'platform docker')
            class Controlled:
                def fetch(self, *args, **kwargs): raise AssertionError('OCI must not download archive')
                def run(self, argv, *, cwd, env, timeout):
                    if argv == [str(docker), '--version']:
                        return subprocess.CompletedProcess(argv, 0, 'Docker version 27.0.0', '')
                    self_test.assertEqual(argv[0:2], [str(docker), 'pull'])
                    self_test.assertIn('@sha256:', argv[2])
                    return subprocess.CompletedProcess(argv, 1, '', '')
            self_test = self
            with patch('shutil.which', return_value=str(docker)):
                result = install(catalog, self.root, Controlled(), host='codex', scope='project')
        record = next(t for t in result['tools'] if t['tool_id'] == 'helicone')
        self.assertEqual(record['status'], 'failed')
        self.assertEqual(record['reason'], 'image acquisition failed')

    def test_http_redirect_from_https_is_rejected(self):
        import installer.engine
        import urllib.request
        self.assertTrue(hasattr(installer.engine, '_HTTPSRedirect'))
        handler = installer.engine._HTTPSRedirect()
        with self.assertRaises(ValueError):
            handler.redirect_request(urllib.request.Request('https://example.test/a'), None, 302, 'redirect', {}, 'http://example.test/b')

    def test_node_install_probes_lockfile_declared_js_entry(self):
        import copy, hashlib, subprocess
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = next(t for t in catalog if t['id'] == 'openspec')
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        artifact = b'node controlled artifact'
        tool['sha256'] = hashlib.sha256(artifact).hexdigest()
        tool['artifact'].update(sha256=tool['sha256'], bytes=len(artifact))
        with tempfile.TemporaryDirectory(prefix='platform-') as platform:
            node = Path(platform) / ('node.exe' if __import__('os').name == 'nt' else 'node')
            node.write_bytes(b'node')
            npm = node.parent / 'node_modules/npm/bin/npm-cli.js'
            npm.parent.mkdir(parents=True)
            npm.write_text('npm')
            class Controlled:
                def fetch(self, url, timeout): return artifact
                def run(self, argv, *, cwd, env, timeout):
                    if argv == [str(node), '--version']: return subprocess.CompletedProcess(argv, 0, 'v20.19.0', '')
                    if argv == [str(node), str(npm), '--version']: return subprocess.CompletedProcess(argv, 0, '10.0.0', '')
                    entry = Path(cwd) / 'node_modules/@fission-ai/openspec/bin/openspec.js'
                    if argv[:3] == [str(node), str(npm), 'ci']:
                        entry.parent.mkdir(parents=True)
                        entry.write_text('fixture')
                    else:
                        self_test.assertEqual(argv, [str(node), str(entry), '--version'])
                    return subprocess.CompletedProcess(argv, 0, tool['version'], '')
            self_test = self
            with patch('shutil.which', return_value=str(node)):
                result = install(catalog, self.root, Controlled(), host='codex', scope='project')
        record = next(t for t in result['tools'] if t['tool_id'] == 'openspec')
        self.assertTrue(record['installed'])
        self.assertTrue(record['smoke_tested'])
        self.assertFalse(record['project_integrated'])

    def test_active_oci_inspects_exact_digest_before_claim(self):
        import copy, json, subprocess
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = next(t for t in catalog if t['id'] == 'helicone')
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        digest = tool['install']['commands'][0][2]
        with tempfile.TemporaryDirectory(prefix='platform-') as platform:
            docker = Path(platform) / ('docker.exe' if __import__('os').name == 'nt' else 'docker')
            docker.write_bytes(b'platform docker')
            class Controlled:
                def run(self, argv, *, cwd, env, timeout):
                    if argv[-1] == '--version': return subprocess.CompletedProcess(argv, 0, 'Docker version 27.0.0', '')
                    if argv[1] == 'pull': return subprocess.CompletedProcess(argv, 0, '', '')
                    self_test.assertEqual(argv[1:4], ['image', 'inspect', digest])
                    return subprocess.CompletedProcess(argv, 0, json.dumps([digest]), '')
            self_test = self
            with patch('shutil.which', return_value=str(docker)):
                result = install(catalog, self.root, Controlled(), host='codex', scope='project')
        record = next(t for t in result['tools'] if t['tool_id'] == 'helicone')
        self.assertTrue(record['installed'])
        self.assertTrue(record['smoke_tested'])
        self.assertFalse(record['project_integrated'])
        self.assertTrue((self.root / '.agentic-sdlc/runtime-receipts/codex/helicone.json').is_file())

    def test_failed_recipe_makes_overall_status_failed(self):
        import copy, sys
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        catalog[1]['active'] = True
        catalog[1]['install'].update(executable=True, status='ready')
        catalog[1]['install']['lock']['interpreter'] = f'Python{sys.version_info.major}.{sys.version_info.minor}'
        class Corrupt:
            def fetch(self, url, timeout): return b'wrong'
        result = install(catalog, self.root, Corrupt(), host='codex', scope='project')
        self.assertEqual(result['status'], 'failed')

    def test_node_floor_checks_minor_version(self):
        import subprocess
        from installer.engine import _node_prerequisites
        tool = next(t for t in self.catalog if t['id'] == 'openspec')
        with tempfile.TemporaryDirectory(prefix='platform-') as platform:
            node = Path(platform) / ('node.exe' if __import__('os').name == 'nt' else 'node')
            node.write_bytes(b'fixture')
            npm = node.parent / 'node_modules/npm/bin/npm-cli.js'
            npm.parent.mkdir(parents=True)
            npm.write_text('fixture')
            class OldNode:
                def run(self, argv, *, cwd, env, timeout):
                    return subprocess.CompletedProcess(argv, 0, 'v20.18.9' if len(argv) == 2 else '10.0.0', '')
            with patch('shutil.which', return_value=str(node)):
                with self.assertRaises(ValueError):
                    _node_prerequisites(self.root, tool, OldNode(), 'project')

    def test_windows_node_prerequisite_rejects_com_wrapper(self):
        import os, subprocess
        from installer.engine import _node_prerequisites
        if os.name != 'nt': self.skipTest('Windows executable type')
        tool = next(t for t in self.catalog if t['id'] == 'openspec')
        with tempfile.TemporaryDirectory(prefix='platform-') as platform:
            node = Path(platform) / 'node.com'
            node.write_bytes(b'not a native Node executable')
            npm = node.parent / 'node_modules/npm/bin/npm-cli.js'
            npm.parent.mkdir(parents=True)
            npm.write_text('fixture')
            class Fake:
                def run(self, argv, *, cwd, env, timeout):
                    return subprocess.CompletedProcess(argv, 0, 'v20.19.0' if len(argv) == 2 else '10.0.0', '')
            with patch('shutil.which', return_value=str(node)):
                with self.assertRaises(ValueError):
                    _node_prerequisites(self.root, tool, Fake(), 'project')

    def test_existing_oci_receipt_prevents_pull(self):
        import copy
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = next(t for t in catalog if t['id'] == 'helicone')
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        receipt = self.root / '.agentic-sdlc/runtime-receipts/codex/helicone.json'
        receipt.parent.mkdir(parents=True)
        receipt.write_text('{}')
        class NeverRun:
            def run(self, *args, **kwargs): raise AssertionError('existing receipt must prevent pull')
        with tempfile.TemporaryDirectory(prefix='platform-') as platform:
            docker = Path(platform) / ('docker.exe' if __import__('os').name == 'nt' else 'docker')
            docker.write_bytes(b'fixture')
            with patch('shutil.which', return_value=str(docker)):
                result = install(catalog, self.root, NeverRun(), host='codex', scope='project')
        record = next(t for t in result['tools'] if t['tool_id'] == 'helicone')
        self.assertEqual(record['status'], 'blocked')

    def test_changed_python_lock_reports_lock_integrity(self):
        import copy, hashlib, sys
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = catalog[1]
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        tool['install']['lock'].update(interpreter=f'Python{sys.version_info.major}.{sys.version_info.minor}', sha256='0' * 64)
        artifact = b'fixture'
        tool['sha256'] = hashlib.sha256(artifact).hexdigest()
        tool['artifact'].update(sha256=tool['sha256'], bytes=len(artifact))
        class Fetch:
            def fetch(self, url, timeout): return artifact
        result = install(catalog, self.root, Fetch(), host='codex', scope='project')
        record = next(t for t in result['tools'] if t['tool_id'] == 'spec-kit')
        self.assertEqual(record['status'], 'failed')
        self.assertIn('lock', record['reason'])

    def test_node_prerequisite_failure_does_not_expose_secret(self):
        import copy
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = next(t for t in catalog if t['id'] == 'openspec')
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        with tempfile.TemporaryDirectory(prefix='platform-') as platform:
            node = Path(platform) / ('node.exe' if __import__('os').name == 'nt' else 'node')
            node.write_bytes(b'node')
            npm = node.parent / 'node_modules/npm/bin/npm-cli.js'
            npm.parent.mkdir(parents=True)
            npm.write_text('npm')
            class Failing:
                def run(self, *args, **kwargs): raise OSError('token=private-secret')
            with patch('shutil.which', return_value=str(node)):
                result = install(catalog, self.root, Failing(), host='codex', scope='project')
        self.assertNotIn('private-secret', json.dumps(result))

    def test_windows_runner_uses_reviewed_job_lifetime(self):
        import os, sys
        from installer.engine import LocalRunner
        if os.name != 'nt': self.skipTest('Windows Job Object boundary')
        marker = self.root / 'started'
        try:
            result = LocalRunner().run([sys.executable, '-c', 'import pathlib,sys; pathlib.Path(sys.argv[1]).write_text("started")', str(marker)], cwd=self.root, env={'PATH': os.defpath}, timeout=5)
        except RuntimeError:
            self.fail('reviewed Windows process runner was not integrated')
        self.assertEqual(result.returncode, 0)
        self.assertTrue(marker.exists())

    def test_command_timeout_is_redacted_and_independent_tools_continue(self):
        import copy, hashlib, subprocess, sys
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        content = b'timeout fixture'
        for tool in catalog[1:3]:
            tool['active'] = True
            tool['install'].update(executable=True, status='ready')
            tool['kind'] = 'python'
            tool['install']['lock']['interpreter'] = f'Python{sys.version_info.major}.{sys.version_info.minor}'
            tool['sha256'] = hashlib.sha256(content).hexdigest()
            tool['artifact'].update(sha256=tool['sha256'], bytes=len(content))
        class TimedOut:
            def fetch(self, url, timeout): return content
            def run(self, argv, *, cwd, env, timeout):
                raise subprocess.TimeoutExpired('secret-command', timeout, output='private-secret')
        try:
            result = install(catalog, self.root, TimedOut(), host='codex', scope='project')
        except subprocess.TimeoutExpired:
            self.fail('command timeout escaped the per-tool boundary')
        records = {item['tool_id']: item for item in result['tools']}
        self.assertEqual(records['spec-kit']['status'], 'failed')
        self.assertEqual(records['openspec']['status'], 'failed')
        self.assertIn('timeout', records['spec-kit']['reason'])
        self.assertNotIn('private-secret', json.dumps(result))

    def test_windows_active_default_runner_reaches_integrity_gate(self):
        import copy, os
        from installer.engine import LocalRunner, install
        if os.name != 'nt': self.skipTest('Windows fail-closed boundary')
        catalog = copy.deepcopy(self.catalog)
        catalog[1]['active'] = True
        catalog[1]['install'].update(executable=True, status='ready')
        with patch.object(LocalRunner, 'fetch', return_value=b'corrupt artifact') as fetch:
            result = install(catalog, self.root, None, host='codex', scope='project')
        record = next(x for x in result['tools'] if x['tool_id'] == 'spec-kit')
        self.assertEqual(record['status'], 'failed')
        self.assertIn('checksum', record['reason'])
        fetch.assert_called_once()

    @unittest.skipIf(__import__('os').name != 'posix', 'POSIX process group required')
    def test_posix_timeout_terminates_descendant(self):
        import os, subprocess, sys, time
        from installer.engine import LocalRunner
        marker = self.root / 'descendant'
        child = 'import time,pathlib,sys; time.sleep(.7); pathlib.Path(sys.argv[1]).write_text("alive")'
        parent = 'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",sys.argv[1],sys.argv[2]]); time.sleep(5)'
        with self.assertRaises(subprocess.TimeoutExpired):
            LocalRunner().run([sys.executable, '-c', parent, child, str(marker)], cwd=self.root, env={'PATH': os.defpath}, timeout=.2)
        time.sleep(1)
        self.assertFalse(marker.exists())

    @unittest.skipIf(__import__('os').name != 'posix', 'POSIX process group required')
    def test_posix_large_output_stops_with_bounded_capture(self):
        import os, sys
        from installer.engine import LocalRunner
        with self.assertRaises(RuntimeError):
            LocalRunner().run([sys.executable, '-c', 'import sys; sys.stdout.write("x" * 1000000); sys.stdout.flush()'], cwd=self.root, env={'PATH': os.defpath}, timeout=5)

    def test_output_limit_is_reported_as_per_tool_failure(self):
        import copy, hashlib, sys
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        tool = catalog[1]
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        tool['install']['lock']['interpreter'] = f'Python{sys.version_info.major}.{sys.version_info.minor}'
        data = b'fixture'
        tool['sha256'] = hashlib.sha256(data).hexdigest()
        tool['artifact'].update(sha256=tool['sha256'], bytes=len(data))
        class OutputLimit:
            def fetch(self, url, timeout): return data
            def run(self, argv, *, cwd, env, timeout): raise RuntimeError('command output limit exceeded')
        result = install(catalog, self.root, OutputLimit(), host='codex', scope='project')
        record = next(item for item in result['tools'] if item['tool_id'] == 'spec-kit')
        self.assertEqual(record['status'], 'failed')
        self.assertIn('output limit', record['reason'])

    def test_node_and_oci_timeouts_are_structured(self):
        import copy, subprocess
        from installer.engine import install
        catalog = copy.deepcopy(self.catalog)
        for tool in catalog:
            if tool['id'] in ('openspec', 'helicone'):
                tool['active'] = True
                tool['install'].update(executable=True, status='ready')
        with tempfile.TemporaryDirectory(prefix='platform-') as platform:
            platform = Path(platform)
            node = platform / ('node.exe' if __import__('os').name == 'nt' else 'node')
            docker = platform / ('docker.exe' if __import__('os').name == 'nt' else 'docker')
            node.write_bytes(b'node'); docker.write_bytes(b'docker')
            npm = platform / 'node_modules/npm/bin/npm-cli.js'
            npm.parent.mkdir(parents=True); npm.write_text('npm')
            class TimedOut:
                def run(self, argv, *, cwd, env, timeout):
                    raise subprocess.TimeoutExpired('secret-command', timeout, output='private-secret')
            def which(name): return str(node if name == 'node' else docker)
            with patch('shutil.which', side_effect=which):
                result = install(catalog, self.root, TimedOut(), host='codex', scope='project')
        records = {item['tool_id']: item for item in result['tools']}
        for name in ('openspec', 'helicone'):
            self.assertEqual(records[name]['status'], 'failed')
            self.assertEqual(records[name]['reason'], 'command timeout')
        self.assertNotIn('private-secret', json.dumps(result))
