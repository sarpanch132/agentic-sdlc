import json
from pathlib import Path
import unittest


class AssetsTest(unittest.TestCase):
    def test_required_phase_reference_exists(self):
        reference = Path('skills/agentic-sdlc/references/phases.md')
        self.assertTrue(reference.is_file())
        self.assertIn('after-delivery', reference.read_text(encoding='utf-8'))

    def test_scenarios_are_inert_and_complete(self):
        scenarios = json.loads(Path('evals/scenarios.json').read_text(encoding='utf-8'))
        self.assertEqual(len(scenarios), 10)
        self.assertEqual(len({s['id'] for s in scenarios}), 10)
        for scenario in scenarios:
            self.assertTrue(scenario['request'])
            self.assertTrue(scenario['expected'])
            self.assertTrue(scenario['must_not'])

    def test_coordinator_assets_and_relative_links(self):
        import re
        root = Path('skills/agentic-sdlc')
        required = ['SKILL.md', 'references/discovery.md', 'references/phases.md',
                    'references/delegation.md', 'templates/sdlc.md']
        for name in required:
            self.assertTrue((root / name).is_file(), name)
        skill = (root / 'SKILL.md').read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)]+)\)', skill):
            self.assertTrue((root / target).is_file(), target)
        stages = ['planning', 'analysis', 'design', 'simulation', 'build',
                  'testing', 'deployment', 'governance', 'after-delivery']
        for name in ['references/phases.md', 'templates/sdlc.md']:
            content = (root / name).read_text(encoding='utf-8')
            for stage in stages:
                self.assertIn('| ' + stage, content)
        self.assertTrue(Path('evals/rubric.md').is_file())

    def test_packaged_inventory(self):
        import hashlib
        for package in json.loads(Path('toolkit/skills.json').read_text(encoding='utf-8'))['skills']:
            root = Path('skills/dependencies') / ('agentic-sdlc-' + package['id'])
            manifest = json.loads((root / 'PROVENANCE.json').read_text(encoding='utf-8'))
            self.assertEqual({a['source'] for a in manifest['assets']}, {a['path'] for a in package['package_assets']})
            originals = {a['path']: a['sha256'] for a in package['package_assets']}
            for asset in manifest['assets']:
                self.assertEqual(asset['upstream_sha256'], originals[asset['source']])
            for asset in manifest['assets']:
                self.assertEqual(hashlib.sha256((root / asset['destination']).read_bytes()).hexdigest(), asset['shipped_sha256'])
            self.assertIn('active user-invoked SDLC workflow', (root / 'SKILL.md').read_text(encoding='utf-8'))
            for name in package['license_files']:
                expected = next(a['sha256'] for a in package['package_assets'] if a['path'] == name)
                self.assertEqual(hashlib.sha256((root / name).read_bytes()).hexdigest(), expected)
            self.assertFalse(any(p.suffix.lower() in {'.woff', '.woff2', '.ttf', '.svg', '.otf'} for p in root.rglob('*')))

    def test_native_adapters(self):
        import tomllib
        contracts = json.loads(Path('tests/fixtures/host-contracts.json').read_text(encoding='utf-8'))['hosts']
        self.assertEqual(len(list(Path('agents').glob('agentic-sdlc-*.md'))), 9)
        for host in contracts:
            folder = Path('adapters') / {'claude-code': 'claude'}.get(host['id'], host['id'])
            entry = (folder / 'skills/agentic-sdlc/SKILL.md').read_text(encoding='utf-8')
            self.assertIn('workflow/WORKFLOW.md', entry)
            if host['id'] == 'codex':
                self.assertEqual((folder / 'skills/agentic-sdlc/agents/openai.yaml').read_text(encoding='utf-8'), 'policy:\n  allow_implicit_invocation: false\n')
            else:
                self.assertIn('disable-model-invocation: true', entry)
            files = list((folder / 'agents').glob('*')); self.assertEqual(len(files), 10)
            for path in files:
                content = path.read_text(encoding='utf-8')
                if path.suffix == '.toml':
                    metadata = tomllib.loads(content)
                    self.assertEqual(set(metadata), set(host['specialist_fields']))
                else:
                    metadata = {}
                    for line in content.split('---', 2)[1].strip().splitlines():
                        key, value = line.split(':', 1)
                        self.assertNotIn(key, metadata); self.assertTrue(value.strip()); metadata[key] = value.strip()
                    self.assertTrue(set(host['specialist_fields']) <= metadata.keys())
                    self.assertTrue(metadata.keys() <= set(host['specialist_fields'] + host['optional_fields']))
                self.assertTrue(metadata['name'].startswith('agentic-sdlc'))
                self.assertIn('active user-invoked SDLC workflow', metadata['description'])
                self.assertNotIn('model', metadata)
                if not path.stem.endswith('-coordinator'):
                    canonical = (Path('agents') / (path.stem + '.md')).read_text(encoding='utf-8')
                    self.assertIn(canonical, metadata.get('developer_instructions', content))
                if path.stem.endswith('-reviewer') or path.stem.endswith(('-requirements-analyst', '-architect')):
                    if host['id'] == 'claude-code':
                        self.assertEqual(metadata['tools'], 'Read, Glob, Grep')
                    elif host['id'] == 'cursor':
                        self.assertEqual(metadata['readonly'], 'true')
                if host['id'] == 'claude-code' and path.stem.endswith(('-coordinator', '-researcher', '-implementer')):
                    self.assertNotIn('tools', metadata)
                self.assertIn('inherit', content.lower())
        self.assertEqual(len(json.loads(Path('adapters/layout.json').read_text(encoding='utf-8'))['hosts']), 3)

    def test_dependency_authority_and_runtime_boundary(self):
        graph = Path('skills/dependencies/agentic-sdlc-graphify/SKILL.md').read_text(encoding='utf-8')
        self.assertNotIn('pip install', graph)
        self.assertNotIn('os.environ', graph)
        self.assertIn('never authorizes an external service', graph)
        self.assertIn('Ponytail minimality never bypasses brainstorming design approval', graph)
        for root in Path('skills/dependencies').iterdir():
            text = (root / 'SKILL.md').read_text(encoding='utf-8')
            self.assertIn('name: ' + root.name, text)
            self.assertNotIn('CLAUDE_PLUGIN_ROOT', text)
            self.assertNotIn('C:/Users/', text)
        runtime = next(s for s in json.loads(Path('toolkit/skills.json').read_text())['skills'] if s['id'] == 'graphify')['runtime']
        self.assertEqual(runtime['version'], '0.9.97')
        self.assertEqual(runtime['status'], 'ready')
        self.assertFalse(runtime['blockers'])

    def test_helper_policy_allows_core_to_call_needed_helpers(self):
        layout = json.loads(Path('adapters/layout.json').read_text(encoding='utf-8'))
        for host in layout['hosts']:
            policy = host['dependency_policy']
            self.assertIsInstance(policy, dict)
            if host['id'] == 'codex':
                self.assertTrue(policy['openai_yaml']['policy']['allow_implicit_invocation'])
            else:
                self.assertFalse(policy['frontmatter']['disable-model-invocation'])
            self.assertEqual(layout['canonical_entry_mapping'], {'SKILL.md': 'WORKFLOW.md'})
        cases = json.loads(Path('adapters/evidence/helper-invocation-cases.json').read_text(encoding='utf-8'))
        self.assertEqual({c['helper'] for c in cases}, {'brainstorming', 'ui-ux-pro-max', 'graphify'})
        for case in cases:
            self.assertFalse(case['separate_user_helper_invocation'])
            self.assertEqual(case['real_host_status'], 'not-run')
            self.assertIn('unrelated', case['must_not'])

    def test_claude_orchestration_and_research_preserve_available_tools(self):
        for role in ['coordinator', 'researcher']:
            text = Path('adapters/claude/agents/agentic-sdlc-' + role + '.md').read_text(encoding='utf-8')
            self.assertNotIn('tools:', text.split('---', 2)[1])
            self.assertIn('active user-invoked SDLC workflow', text)
        for path in Path('agents').glob('*.md'):
            self.assertIn('when exposed by', path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
