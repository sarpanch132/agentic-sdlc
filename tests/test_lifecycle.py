import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import shutil
import uuid
from unittest.mock import patch

from installer.catalog import load_catalog
from catalog_fixture import inactive_catalog
from installer.engine import install, _payload

ROOT = Path(__file__).resolve().parents[1]


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lifecycle & ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'project'
        self.root.mkdir()
        self.private = Path.home() / ('.sdlc-private-test-' + uuid.uuid4().hex)
        self.addCleanup(lambda: shutil.rmtree(self.private, ignore_errors=True))
        self.catalog = inactive_catalog()
        self.assertIsNotNone(importlib.util.find_spec('installer.lifecycle'), 'lifecycle implementation is missing')
        self.state = patch('installer.lifecycle._private_root', return_value=self.private)
        self.state.start()
        self.addCleanup(self.state.stop)
        result = install(self.catalog, self.root, None)
        self.assertEqual(result['status'], 'blocked', result.get('reason'))
        self.assertTrue(self.private.is_dir())

    def test_update_and_rollback_restore_previous_generation(self):
        from installer.lifecycle import update, rollback
        assets = _payload('codex')
        relative = '.agents/skills/agentic-sdlc/workflow/WORKFLOW.md'
        original = (self.root / relative).read_bytes()
        assets[relative] = original + b'\nnew verified generation\n'
        with patch('installer.engine._payload', return_value=assets):
            changed = update(self.catalog, self.root, None)
        self.assertEqual(changed['assets_status'], 'updated', changed)
        self.assertEqual((self.root / relative).read_bytes(), assets[relative])
        restored = rollback(self.catalog, self.root, None)
        self.assertEqual(restored['assets_status'], 'rolled-back', restored)
        self.assertEqual((self.root / relative).read_bytes(), original)

    def test_clean_uninstall_allows_a_new_install(self):
        from installer.lifecycle import uninstall
        self.assertEqual(uninstall(self.root)['status'], 'complete')
        result = install(self.catalog, self.root, None)
        self.assertEqual(result['status'], 'blocked', result)
        self.assertTrue((self.root / '.agents/skills/agentic-sdlc/SKILL.md').is_file())

    def test_uninstall_preserves_unknown_and_modified_files_and_repeats(self):
        from installer.lifecycle import uninstall
        modified = self.root / '.agents/skills/agentic-sdlc/SKILL.md'
        modified.write_text('user modified')
        unknown = self.root / '.agents/skills/user-skill.txt'
        unknown.write_text('user data')
        result = uninstall(self.root)
        self.assertEqual(result['status'], 'blocked', result)
        self.assertTrue(result['preserved'])
        self.assertEqual(modified.read_text(), 'user modified')
        self.assertEqual(unknown.read_text(), 'user data')
        self.assertFalse((self.root / '.agents/skills/agentic-sdlc/workflow/WORKFLOW.md').exists())
        self.assertEqual(uninstall(self.root)['preserved'], result['preserved'])

    def test_update_failure_restores_all_original_assets(self):
        from installer.lifecycle import update
        from installer.files import write_owned
        assets = _payload('codex')
        keys = list(assets)[:2]
        original = {name: (self.root / name).read_bytes() for name in keys}
        for name in keys:
            assets[name] += b'\nchanged\n'
        calls = 0
        def failing(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('injected replacement failure')
            return write_owned(*args, **kwargs)
        with patch('installer.engine._payload', return_value=assets), patch('installer.lifecycle.write_owned', side_effect=failing):
            result = update(self.catalog, self.root, None)
        self.assertEqual(result['status'], 'failed', result)
        for name, content in original.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_wrong_identity_and_forged_unrelated_ownership_are_rejected(self):
        from installer.lifecycle import uninstall
        wrong = uninstall(self.root, host='claude')
        self.assertEqual(wrong['status'], 'failed')
        victim = self.root / 'README.md'
        victim.write_text('preserve')
        receipt = self.root / '.agentic-sdlc/receipt.json'
        data = json.loads(receipt.read_text())
        data['owned_files']['README.md'] = '0' * 64
        receipt.write_text(json.dumps(data))
        self.assertEqual(uninstall(self.root)['status'], 'failed')
        self.assertEqual(victim.read_text(), 'preserve')

    def test_modified_asset_blocks_update_without_partial_replacement(self):
        from installer.lifecycle import update
        target = self.root / '.agents/skills/agentic-sdlc/SKILL.md'
        target.write_text('edited')
        result = update(self.catalog, self.root, None)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(target.read_text(), 'edited')

    def test_interrupted_private_commit_can_recover_update(self):
        from installer.lifecycle import update
        from installer import state
        assets = _payload('codex')
        relative = next(iter(assets))
        assets[relative] += b'\nupdated\n'
        real_write = state.write
        def interrupted(base, name, value):
            if name.startswith('assets-') and value.get('previous') and value.get('pending') is None:
                raise OSError('interruption before private commit')
            return real_write(base, name, value)
        with patch('installer.engine._payload', return_value=assets), patch('installer.state.write', side_effect=interrupted):
            self.assertEqual(update(self.catalog, self.root, None)['status'], 'failed')
        with patch('installer.engine._payload', return_value=assets):
            result = update(self.catalog, self.root, None)
        self.assertEqual(result['assets_status'], 'updated', result)
        self.assertEqual((self.root / relative).read_bytes(), assets[relative])

    def test_private_store_overlap_and_corruption_fail_closed(self):
        from installer.lifecycle import update
        with patch('installer.lifecycle._private_root', return_value=self.root / 'private'):
            result = update(self.catalog, self.root, None)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('overlap', result['reason'])
        next(self.private.glob('assets-*.json')).write_text('{}')
        self.assertEqual(update(self.catalog, self.root, None)['status'], 'failed')

    def test_interrupted_uninstall_can_be_repeated(self):
        from installer.lifecycle import uninstall
        from installer import state
        real_write = state.write
        def interrupted(base, name, value):
            if name.startswith('assets-') and not value.get('current') and value.get('pending') is None:
                raise OSError('interruption before private commit')
            return real_write(base, name, value)
        with patch('installer.state.write', side_effect=interrupted):
            self.assertEqual(uninstall(self.root)['status'], 'failed')
        self.assertEqual(uninstall(self.root)['status'], 'complete')

    def test_failed_runtime_update_preserves_previous_asset_generation(self):
        import copy
        from installer.lifecycle import update
        catalog = copy.deepcopy(self.catalog)
        tool = next(t for t in catalog if t['id'] == 'spec-kit')
        tool['active'] = True
        tool['install'].update(executable=True, status='ready')
        assets = _payload('codex')
        relative = next(iter(assets))
        original = (self.root / relative).read_bytes()
        assets[relative] += b'\nupdated\n'
        class Corrupt:
            def fetch(self, url, timeout): return b'corrupt artifact'
        with patch('installer.engine._payload', return_value=assets):
            result = update(catalog, self.root, Corrupt())
        self.assertEqual(result['status'], 'failed', result)
        self.assertEqual((self.root / relative).read_bytes(), original)


class RuntimeWitnessTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='runtime-state-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.private = Path.home() / ('.sdlc-runtime-test-' + uuid.uuid4().hex)
        self.addCleanup(lambda: shutil.rmtree(self.private, ignore_errors=True))
        private = patch('installer.lifecycle._private_root', return_value=self.private)
        private.start()
        self.addCleanup(private.stop)
        self.tool = inactive_catalog()[1]

    def sealed(self):
        from installer.lifecycle import begin_runtime, seal_runtime, runtime_context
        relative = runtime_context(self.tool)
        ticket = begin_runtime(self.root, self.tool, 'codex', 'project', relative)
        context = self.root / relative
        context.mkdir(parents=True)
        (context / 'program.txt').write_text('verified fixture')
        (context / 'unchanged.txt').write_text('verified owned data')
        bindir = context / 'venv' / ('Scripts' if __import__('os').name == 'nt' else 'bin')
        bindir.mkdir(parents=True)
        (bindir / ('specify.exe' if __import__('os').name == 'nt' else 'specify')).write_text(self.tool['version'])
        seal_runtime(self.root, self.tool, 'codex', 'project', relative, ticket)
        return context

    def test_only_fresh_install_can_create_runtime_authority(self):
        import installer.lifecycle as lifecycle
        self.assertTrue(hasattr(lifecycle, 'begin_runtime'), 'fresh runtime authority missing')
        context = self.sealed()
        value = lifecycle.runtime_witness(self.root, self.tool, 'codex', 'project')
        self.assertEqual(value['status'], 'verified')
        with self.assertRaises(ValueError):
            lifecycle.begin_runtime(self.root, self.tool, 'codex', 'project', context.relative_to(self.root).as_posix())

    def test_changed_missing_and_extra_files_invalidate_witness(self):
        import installer.lifecycle as lifecycle
        self.assertTrue(hasattr(lifecycle, 'runtime_witness'), 'runtime validation missing')
        context = self.sealed()
        file = context / 'program.txt'
        file.write_text('changed')
        with self.assertRaises(ValueError): lifecycle.runtime_witness(self.root, self.tool, 'codex', 'project')
        file.write_text('verified fixture')
        extra = context / 'extra-directory'
        extra.mkdir()
        with self.assertRaises(ValueError): lifecycle.runtime_witness(self.root, self.tool, 'codex', 'project')
        extra.rmdir()
        file.unlink()
        with self.assertRaises(ValueError): lifecycle.runtime_witness(self.root, self.tool, 'codex', 'project')

    def test_forged_project_receipt_does_not_authorize_probe(self):
        import installer.lifecycle as lifecycle
        self.assertTrue(hasattr(lifecycle, 'runtime_witness'), 'runtime validation missing')
        relative = lifecycle.runtime_context(self.tool)
        context = self.root / relative
        context.mkdir(parents=True)
        (context / 'program.txt').write_text('forged')
        receipts = self.root / '.agentic-sdlc/runtime-receipts/codex'
        receipts.mkdir(parents=True)
        (receipts / 'spec-kit.json').write_text(json.dumps({'installed': True, 'smoke_tested': True}))
        with self.assertRaises(ValueError): lifecycle.runtime_witness(self.root, self.tool, 'codex', 'project')

    def test_identity_change_and_incomplete_publication_are_not_adopted(self):
        import copy
        import installer.lifecycle as lifecycle
        self.assertTrue(hasattr(lifecycle, 'begin_runtime'), 'fresh runtime authority missing')
        self.sealed()
        changed = copy.deepcopy(self.tool)
        changed['version'] = '999.0.0'
        with self.assertRaises(ValueError): lifecycle.runtime_witness(self.root, changed, 'codex', 'project')
        with self.assertRaises(ValueError): lifecycle.runtime_witness(self.root, self.tool, 'claude', 'project')
        next(self.private.glob('runtime-*.json')).write_text('{}')
        with self.assertRaises(ValueError): lifecycle.runtime_witness(self.root, self.tool, 'codex', 'project')

    def test_active_runtime_resumes_without_acquisition_and_doctor_rejects_changes(self):
        import copy, subprocess
        from installer.engine import diagnose
        catalog = copy.deepcopy(inactive_catalog())
        tool = next(t for t in catalog if t['id'] == 'openspec')
        artifact = b'verified node fixture'
        tool.update(active=True, sha256=__import__('hashlib').sha256(artifact).hexdigest())
        tool['artifact'].update(sha256=tool['sha256'], bytes=len(artifact))
        tool['install'].update(executable=True, status='ready')
        platform = self.root.parent / (self.root.name + '-platform')
        platform.mkdir()
        self.addCleanup(lambda: shutil.rmtree(platform, ignore_errors=True))
        node = platform / ('node.exe' if __import__('os').name == 'nt' else 'node')
        node.write_bytes(b'host node')
        npm = platform / 'node_modules/npm/bin/npm-cli.js'
        npm.parent.mkdir(parents=True)
        npm.write_text('host npm')
        calls, downloads = [], []
        class Controlled:
            def fetch(self, url, timeout):
                downloads.append(url)
                return artifact
            def run(self, argv, *, cwd, env, timeout):
                calls.append(argv)
                if argv == [str(node), '--version']:
                    return subprocess.CompletedProcess(argv, 0, 'v24.18.0', '')
                if argv == [str(node), str(npm), '--version']:
                    return subprocess.CompletedProcess(argv, 0, '11.0.0', '')
                if 'ci' in argv:
                    entry = Path(cwd) / 'node_modules/@fission-ai/openspec/bin/openspec.js'
                    entry.parent.mkdir(parents=True)
                    entry.write_text('verified fixture')
                return subprocess.CompletedProcess(argv, 0, tool['version'], '')
        with patch('shutil.which', return_value=str(node)):
            first = install(catalog, self.root, Controlled())
            self.assertTrue(next(t for t in first['tools'] if t['tool_id'] == 'openspec')['installed'], first['reason'])
            repeated = install(catalog, self.root, Controlled())
            self.assertTrue(next(t for t in repeated['tools'] if t['tool_id'] == 'openspec')['installed'], 'authenticated runtime must resume')
            self.assertEqual(len(downloads), 1)
            healthy = diagnose(catalog, self.root, Controlled())
            self.assertTrue(next(t for t in healthy['tools'] if t['tool_id'] == 'openspec')['smoke_tested'])
            runtime = next((self.root / '.agentic-sdlc/runtimes/openspec').iterdir())
            (runtime / 'injected.txt').write_text('untrusted')
            calls.clear()
            broken = diagnose(catalog, self.root, Controlled())
            self.assertFalse(next(t for t in broken['tools'] if t['tool_id'] == 'openspec')['installed'])
            self.assertEqual(calls, [], 'modified runtime must not execute even a prerequisite probe')

    def test_node_prerequisites_use_distinct_empty_owned_configurations(self):
        import subprocess
        from installer.engine import _node_prerequisites
        platform = self.root.parent / (self.root.name + '-platform')
        platform.mkdir()
        self.addCleanup(lambda: shutil.rmtree(platform, ignore_errors=True))
        node = platform / ('node.exe' if __import__('os').name == 'nt' else 'node')
        node.write_bytes(b'host')
        npm = platform / 'node_modules/npm/bin/npm-cli.js'
        npm.parent.mkdir(parents=True)
        npm.write_text('host npm')
        tool = next(t for t in inactive_catalog() if t['id'] == 'openspec')
        test = self
        class Controlled:
            def run(self, argv, *, cwd, env, timeout):
                test.assertNotEqual(Path(cwd), test.root, 'do not read project .npmrc')
                user, global_ = env.get('npm_config_userconfig'), env.get('npm_config_globalconfig')
                test.assertIsNotNone(user, 'explicit empty user configuration required')
                test.assertIsNotNone(global_, 'explicit empty global configuration required')
                test.assertNotEqual(user, global_)
                test.assertEqual(Path(user).read_bytes(), b'')
                test.assertEqual(Path(global_).read_bytes(), b'')
                return subprocess.CompletedProcess(argv, 0, 'v24.18.0' if len(argv) == 2 else '11.0.0', '')
        with patch('shutil.which', return_value=str(node)):
            _node_prerequisites(self.root, tool, Controlled(), 'project')

    def test_uninstall_removes_only_unchanged_runtime_files(self):
        from installer.lifecycle import uninstall
        install(inactive_catalog(), self.root, None)
        context = self.sealed()
        (context / 'program.txt').write_text('user edit')
        (context / 'unknown.txt').write_text('user data')
        result = uninstall(self.root)
        self.assertFalse((context / 'unchanged.txt').exists(), result)
        self.assertEqual((context / 'program.txt').read_text(), 'user edit')
        self.assertEqual((context / 'unknown.txt').read_text(), 'user data')
        self.assertEqual(result['status'], 'blocked')

    @unittest.skipUnless(__import__('os').name == 'nt', 'Windows executable suffix')
    def test_python_runtime_probe_uses_native_executable_suffix(self):
        import subprocess
        from installer.lifecycle import begin_runtime, seal_runtime, runtime_context, probe_runtime
        relative = runtime_context(self.tool)
        ticket = begin_runtime(self.root, self.tool, 'codex', 'project', relative)
        context = self.root / relative
        bindir = context / 'venv/Scripts'
        bindir.mkdir(parents=True)
        (bindir / 'specify.exe').write_bytes(b'controlled executable')
        seal_runtime(self.root, self.tool, 'codex', 'project', relative, ticket)
        test = self
        class Controlled:
            def run(self, argv, **kwargs):
                test.assertEqual(Path(argv[0]).suffix, '.exe', 'Windows probe must use a native executable path')
                return subprocess.CompletedProcess(argv, 0, test.tool['version'], '')
        record = {}
        probe_runtime(self.root, self.tool, 'codex', 'project', Controlled(), record)
        self.assertTrue(record['installed'])

    def test_runtime_rollback_selects_authenticated_previous_generation(self):
        import copy, subprocess
        import installer.lifecycle as lifecycle
        from installer.engine import diagnose
        self.assertTrue(hasattr(lifecycle, 'register_runtime_heads'), 'runtime generation commit missing')
        install(inactive_catalog(), self.root, None)
        self.tool = copy.deepcopy(self.tool)
        self.tool['active'] = True
        self.tool['install'].update(executable=True, status='ready')
        old = copy.deepcopy(self.tool)
        self.sealed()
        lifecycle.register_runtime_heads(self.root, [old], [{'tool_id': old['id'], 'installed': True}], 'codex', 'project')
        self.tool['version'] = '999.0.0'
        self.sealed()
        current = copy.deepcopy(self.tool)
        class Controlled:
            def run(self, argv, **kwargs):
                return subprocess.CompletedProcess(argv, 0, Path(argv[0]).read_text(), '')
        assets = _payload('codex')
        relative = next(iter(assets))
        assets[relative] += b'\nnew generation\n'
        with patch('installer.engine._payload', return_value=assets):
            changed = lifecycle.update([current], self.root, Controlled())
        self.assertEqual(changed['assets_status'], 'updated', changed.get('reason'))
        restored = lifecycle.rollback([current], self.root, Controlled())
        self.assertEqual(restored['assets_status'], 'rolled-back', restored.get('reason'))
        health = diagnose([current], self.root, Controlled())
        record = next(t for t in health['tools'] if t['tool_id'] == old['id'])
        self.assertEqual(record['version'], old['version'])
        self.assertTrue(record['smoke_tested'], record)
