import hashlib
import io
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
import uuid
from unittest.mock import patch

from catalog_fixture import inactive_catalog
from installer.engine import install, diagnose


class SkillsRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.private = Path.home() / ('.sdlc-skills-proof-' + uuid.uuid4().hex)
        self.addCleanup(lambda: shutil.rmtree(self.private, ignore_errors=True))
        private = patch('installer.lifecycle._private_root', return_value=self.private)
        private.start()
        self.addCleanup(private.stop)

    def catalog(self, count=15, unsafe=False):
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode='w:gz') as tar:
            files = {'source/LICENSE': b'MIT fixture'}
            files.update({f'source/skills/skill-{n}/SKILL.md': b'# Workflow fixture\n' for n in range(count)})
            if unsafe:
                files['source/skills/../../escaped'] = b'escape'
            for name, content in files.items():
                entry = tarfile.TarInfo(name)
                entry.size = len(content)
                tar.addfile(entry, io.BytesIO(content))
        data = payload.getvalue()
        catalog = inactive_catalog()
        tool = next(t for t in catalog if t['id'] == 'superpowers')
        tool.update(active=True, sha256=hashlib.sha256(data).hexdigest())
        tool['artifact'].update(sha256=tool['sha256'], bytes=len(data))
        tool['install'].update(executable=True, status='ready')
        class Runner:
            def fetch(self, *args, **kwargs): return data
            def run(self, *args, **kwargs): raise AssertionError('instruction assets must not launch a process')
        return catalog, Runner()

    def test_complete_framework_installs_resumes_and_diagnoses_without_processes(self):
        catalog, runner = self.catalog()
        for action in (install, install, diagnose):
            result = action(catalog, self.root, runner)
            record = next(t for t in result['tools'] if t['tool_id'] == 'superpowers')
            self.assertTrue(record['installed'] and record['smoke_tested'], record)

    def test_archive_traversal_is_rejected(self):
        catalog, runner = self.catalog(unsafe=True)
        result = install(catalog, self.root, runner)
        record = next(t for t in result['tools'] if t['tool_id'] == 'superpowers')
        self.assertIn(record['status'], ('failed', 'blocked'))
        self.assertFalse(record['installed'])
        self.assertFalse((self.root / 'escaped').exists())

    def test_incomplete_framework_cannot_be_called_installed(self):
        catalog, runner = self.catalog(count=14)
        result = install(catalog, self.root, runner)
        record = next(t for t in result['tools'] if t['tool_id'] == 'superpowers')
        self.assertEqual(record['status'], 'failed')

    def test_interrupted_runtime_is_preserved_and_rebuilt(self):
        from installer.lifecycle import begin_runtime, runtime_context
        catalog, runner = self.catalog()
        tool = next(t for t in catalog if t['id'] == 'superpowers')
        relative = runtime_context(tool)
        begin_runtime(self.root, tool, 'codex', 'project', relative)
        context = self.root / relative
        context.mkdir(parents=True)
        (context / 'unknown-user-file.txt').write_text('preserve this')
        result = install(catalog, self.root, runner)
        record = next(t for t in result['tools'] if t['tool_id'] == 'superpowers')
        self.assertTrue(record['installed'], record)
        preserved = list(context.parent.glob(context.name + '.interrupted-*'))
        self.assertEqual(len(preserved), 1)
        self.assertEqual((preserved[0] / 'unknown-user-file.txt').read_text(), 'preserve this')

    def test_runtime_can_be_reinstalled_after_uninstall(self):
        from installer.engine import uninstall
        catalog, runner = self.catalog()
        first = install(catalog, self.root, runner)
        self.assertTrue(next(t for t in first['tools'] if t['tool_id'] == 'superpowers')['installed'])
        self.assertEqual(uninstall(self.root)['status'], 'complete')
        second = install(catalog, self.root, runner)
        record = next(t for t in second['tools'] if t['tool_id'] == 'superpowers')
        self.assertTrue(record['installed'], record)

    def test_runtime_upgrade_and_rollback_select_verified_generations(self):
        import copy
        from installer.engine import diagnose
        from installer.lifecycle import update, rollback, runtime_context
        catalog, runner = self.catalog()
        original = next(t for t in catalog if t['id'] == 'superpowers')
        install(catalog, self.root, runner)
        upgraded = copy.deepcopy(catalog)
        new = next(t for t in upgraded if t['id'] == 'superpowers')
        new['version'] = 'test-next-version'
        self.assertNotEqual(runtime_context(original), runtime_context(new))
        result = update(upgraded, self.root, runner)
        self.assertEqual(result.get('assets_status'), 'updated', result)
        current = next(t for t in diagnose(upgraded, self.root, runner)['tools'] if t['tool_id'] == 'superpowers')
        self.assertEqual(current['version'], new['version'])
        result = rollback(upgraded, self.root, runner)
        self.assertEqual(result.get('assets_status'), 'rolled-back', result)
        previous = next(t for t in diagnose(upgraded, self.root, runner)['tools'] if t['tool_id'] == 'superpowers')
        self.assertEqual(previous['version'], original['version'])
        self.assertTrue(previous['smoke_tested'])

    def test_modified_runtime_receipt_is_preserved_and_reported(self):
        from installer.engine import uninstall
        catalog, runner = self.catalog()
        install(catalog, self.root, runner)
        relative = '.agentic-sdlc/runtime-receipts/codex/superpowers.json'
        receipt = self.root / relative
        receipt.write_bytes(receipt.read_bytes() + b'\nuser note')
        result = uninstall(self.root)
        self.assertEqual(result['status'], 'blocked', result.get('reason'))
        self.assertIn(relative, result['preserved'])
        self.assertTrue(receipt.read_bytes().endswith(b'user note'))
