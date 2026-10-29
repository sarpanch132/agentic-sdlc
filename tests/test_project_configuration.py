import importlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from installer import engine
from installer.catalog import load_catalog
import test_skills_runtime as skills_fixture


class ProjectConfigurationTest(unittest.TestCase):
    setUp = skills_fixture.SkillsRuntimeTest.setUp
    catalog = skills_fixture.SkillsRuntimeTest.catalog

    def configuration(self):
        self.assertIsNotNone(importlib.util.find_spec('installer.project'), 'project configuration is missing')
        return importlib.import_module('installer.project')

    def test_configures_only_selected_authenticated_instruction_runtime(self):
        module = self.configuration()
        catalog, runner = self.catalog()
        engine.install(catalog, self.root, runner)
        result = module.configure(catalog, self.root, runner, tools=['superpowers'])
        self.assertEqual(result['status'], 'complete', result)
        self.assertTrue(result['tools'][0]['configured'])
        self.assertFalse(result['tools'][0]['project_integrated'])
        routes = json.loads((self.root / '.agentic-sdlc/project-tools/routes.json').read_text())
        self.assertEqual(routes['selected'], ['superpowers'])
        self.assertEqual(len(routes['phases']), 9)
        self.assertFalse((self.root / '.agentic-sdlc/project-tools/mlflow').exists())

    def test_missing_runtime_is_not_configured_or_adopted(self):
        module = self.configuration()
        catalog, runner = self.catalog()
        result = module.configure(catalog, self.root, runner, tools=['superpowers'])
        self.assertEqual(result['status'], 'blocked', result)
        self.assertFalse(any(record['configured'] for record in result['tools']))
        self.assertFalse((self.root / '.agentic-sdlc/project-tools/routes.json').exists())

    def test_doctor_distinguishes_local_configuration_from_application_integration(self):
        module = self.configuration()
        catalog, runner = self.catalog()
        engine.install(catalog, self.root, runner)
        module.configure(catalog, self.root, runner, tools=['superpowers'])
        result = engine.diagnose(catalog, self.root, runner)
        record = next(item for item in result['tools'] if item['tool_id'] == 'superpowers')
        self.assertTrue(record['configured'], record)
        self.assertFalse(record['project_integrated'])

    def test_modified_configuration_is_preserved_and_diagnostics_fail_closed(self):
        module = self.configuration()
        catalog, runner = self.catalog()
        engine.install(catalog, self.root, runner)
        self.assertEqual(module.configure(catalog, self.root, runner, tools=['superpowers'])['status'], 'complete')
        path = self.root / '.agentic-sdlc/project-tools/superpowers/config.json'
        path.write_text('user modification')
        result = module.configure(catalog, self.root, runner, check_only=True)
        self.assertEqual(result['status'], 'blocked', result)
        self.assertEqual(path.read_text(), 'user modification')

    def test_unknown_configuration_cannot_be_adopted(self):
        module = self.configuration()
        catalog, runner = self.catalog()
        engine.install(catalog, self.root, runner)
        path = self.root / '.agentic-sdlc/project-tools/routes.json'
        path.parent.mkdir()
        path.write_text('{}')
        result = module.configure(catalog, self.root, runner, tools=['superpowers'])
        self.assertEqual(result['status'], 'blocked', result)
        self.assertEqual(path.read_text(), '{}')

    def test_competing_specification_workflows_require_a_choice(self):
        module = self.configuration()
        result = module.configure(load_catalog(engine.DIST / 'toolkit/manifest.json'), self.root,
                                  tools=['spec-kit', 'openspec'])
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('one specification workflow', result['reason'])
        self.assertFalse((self.root / '.agentic-sdlc/project-tools').exists())

    def test_graphify_requires_explicit_source_directory(self):
        module = self.configuration()
        result = module.configure(load_catalog(engine.DIST / 'toolkit/manifest.json'), self.root, tools=['graphify'])
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('source', result['reason'])

    def test_graphify_output_is_kept_in_project_tool_state(self):
        import subprocess
        module = self.configuration()
        folder = self.root / '.agentic-sdlc/project-tools/graphify'
        folder.mkdir(parents=True)
        (self.root / 'src').mkdir()
        tool = next(t for t in load_catalog(engine.DIST / 'toolkit/manifest.json') if t['id'] == 'graphify')
        self_test = self
        class Runner:
            def run(self, argv, **kwargs):
                self_test.assertIn('--out', argv)
                output = Path(argv[argv.index('--out') + 1])
                self_test.assertEqual(output, folder / 'state')
                graph = output / 'graphify-out'
                graph.mkdir(parents=True)
                (graph / 'graph.json').write_text('{"nodes":[{"id":"source"}]}')
                return subprocess.CompletedProcess(argv, 0, '', '')
        module._check(tool, self.root / 'runtime', self.root, self.root, Runner(), 'project', 'src')

    def test_every_phase_has_assigned_tools_and_build_has_native_fallback(self):
        self.configuration()
        data = json.loads((engine.DIST / 'toolkit/manifest.json').read_text(encoding='utf-8'))
        phases = data.get('phase_tools', {})
        self.assertEqual(set(phases), {'planning', 'analysis', 'design', 'simulation', 'build',
                                      'testing', 'deployment', 'governance', 'after-delivery'})
        self.assertTrue(all(phases.values()))
        self.assertEqual(data['phase_fallbacks']['build'], 'host-native coding agent')

    def test_installed_coordinator_includes_project_setup_instructions(self):
        payload = engine._payload('codex')
        path = '.agents/skills/agentic-sdlc/workflow/references/project-setup.md'
        self.assertTrue(path in payload, 'installed project setup instructions missing')
        self.assertIn(b'project-doctor', payload[path])

    def test_installed_metadata_preserves_source_location_without_project_secrets(self):
        payload = engine._payload('codex')
        path = '.agents/skills/agentic-sdlc/workflow/installer-location.json'
        self.assertTrue(path in payload, 'installer source locator missing')
        self.assertEqual(json.loads(payload[path]), {'source': str(engine.DIST), 'kind': 'location-hint'})

    def test_generated_python_checks_compile_without_provider_credentials(self):
        module = self.configuration()
        for identity in ('agno', 'deepeval', 'bentoml', 'mlflow', 'openllmetry'):
            files = module.profile_files(identity)
            self.assertIn('check.py', files)
            compile(files['check.py'], identity + '/check.py', 'exec')
            settings = json.loads(files['config.json'])
            self.assertEqual(settings['mode'], 'local-only')
            self.assertIsNone(settings['provider'])

    def test_catalog_rejects_missing_or_unknown_phase_routes(self):
        self.configuration()
        path = engine.DIST / 'toolkit/manifest.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['phase_tools']['build'] = []
        with patch('installer.catalog.json.loads', return_value=data):
            with self.assertRaisesRegex(ValueError, 'phase'):
                load_catalog(path)

    def test_linked_project_state_is_rejected_before_use(self):
        import os
        module = self.configuration()
        catalog, runner = self.catalog()
        engine.install(catalog, self.root, runner)
        module.configure(catalog, self.root, runner, tools=['superpowers'])
        original = self.root / 'preserve.txt'
        original.write_text('preserve')
        data = self.root / '.agentic-sdlc/project-tools/superpowers/state'
        os.link(original, data / 'unknown.txt')
        result = module.configure(catalog, self.root, runner, check_only=True)
        self.assertEqual(result['status'], 'blocked', result)
        self.assertEqual(original.read_text(), 'preserve')

    def test_project_configuration_survives_runtime_uninstall_as_project_output(self):
        module = self.configuration()
        catalog, runner = self.catalog()
        engine.install(catalog, self.root, runner)
        module.configure(catalog, self.root, runner, tools=['superpowers'])
        result = engine.uninstall(self.root)
        self.assertEqual(result['status'], 'complete', result)
        self.assertTrue((self.root / '.agentic-sdlc/project-tools/superpowers/config.json').exists())
        health = module.configure(catalog, self.root, runner, check_only=True)
        self.assertEqual(health['status'], 'blocked')

    def test_user_runtime_can_configure_a_separate_project(self):
        module = self.configuration()
        catalog, runner = self.catalog()
        engine.install(catalog, self.root, runner, scope='user')
        workspace = self.root / 'consumer'
        workspace.mkdir()
        result = module.configure(catalog, self.root, runner, project=workspace,
                                  tools=['superpowers'], scope='user')
        self.assertEqual(result['status'], 'complete', result)
        self.assertTrue((workspace / '.agentic-sdlc/project-tools/routes.json').is_file())
        check = module.configure(catalog, self.root, runner, project=workspace,
                                 scope='user', check_only=True)
        self.assertEqual(check['status'], 'complete', check)

    def test_empty_specification_marker_is_not_a_configured_workspace(self):
        module = self.configuration()
        marker = self.root / '.agentic-sdlc/project-tools/spec-kit/state/specification/.specify'
        marker.mkdir(parents=True)
        (marker / 'placeholder').write_text('incomplete')
        tool = next(t for t in load_catalog(engine.DIST / 'toolkit/manifest.json') if t['id'] == 'spec-kit')
        with self.assertRaisesRegex(ValueError, 'project assets'):
            module._check(tool, self.root / 'runtime', self.root, self.root, None, 'project', None)
