import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
try:
    from installer.catalog import load_catalog
except ImportError:
    def missing_feature(*args, **kwargs):
        raise AssertionError("Task 5 implementation is absent; behavior must be implemented")
    load_catalog = missing_feature

ROOT = Path(__file__).resolve().parents[1]

class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'toolkit/manifest.json').read_text(encoding='utf-8'))

    def load(self):
        # Keep local lock references relative to the actual distribution root.
        with TemporaryDirectory(dir=ROOT) as temporary:
            path = Path(temporary) / 'manifest.json'
            path.write_text(json.dumps(self.catalog), encoding='utf-8')
            return load_catalog(path)

    def rejects(self, change):
        change(self.catalog)
        with self.assertRaises(ValueError):
            self.load()

    def test_all_sixteen_phase_tools_remain_visible(self):
        tools = load_catalog(ROOT / 'toolkit/manifest.json')
        self.assertEqual(len([t for t in tools if t['id'] != 'graphify']), 16)
        self.assertEqual({t['id'] for t in tools if t['id'] != 'graphify'}, set(self.catalog['default_tool_ids']))
        self.assertTrue(all(t['install']['executable'] and t['install']['status'] == 'ready' for t in tools if t['active']))

    def test_graphify_runtime_is_validated_and_returned(self):
        tools = load_catalog(ROOT / 'toolkit/manifest.json')
        self.assertEqual(len(tools), 17)
        self.assertEqual([t['id'] for t in tools if t['id'] == 'graphify'], ['graphify'])

    def test_graphify_cannot_be_silently_removed(self):
        self.catalog['runtime_dependencies'] = []
        with self.assertRaises(ValueError):
            self.load()

    def test_arbitrary_supplemental_runtime_is_rejected(self):
        self.catalog['runtime_dependencies'] = [copy.deepcopy(self.catalog['tools'][1])]
        with self.assertRaises(ValueError):
            self.load()

    def test_missing_id_rejected(self):
        self.rejects(lambda m: m['tools'][0].pop('id'))

    def test_duplicate_id_rejected(self):
        self.rejects(lambda m: m['tools'].append(copy.deepcopy(m['tools'][0])))

    def test_wrong_artifact_checksum_rejected(self):
        self.rejects(lambda m: m['tools'][0]['artifact'].update(sha256='0' * 64))

    def test_unpinned_active_source_rejected(self):
        def change(m):
            m['tools'][0].update(active=True, version='latest', source='https://example.org/main.tar.gz')
            m['tools'][0]['install'].update(executable=True, status='ready')
        self.rejects(change)

    def test_shell_string_rejected(self):
        self.rejects(lambda m: m['tools'][1]['install'].update(commands=['echo unsafe']))

    def test_shell_argv_rejected(self):
        self.rejects(lambda m: m['tools'][1]['install'].update(commands=[['powershell', '-Command', 'echo unsafe']]))

    def test_unsupported_token_rejected_even_when_declared(self):
        def change(m):
            m['tools'][1]['install']['path_tokens'].append('{anything}')
            m['tools'][1]['probe']['argv'] = ['{anything}', '--help']
        self.rejects(change)

    def test_unknown_kind_and_status_rejected(self):
        for field, value in [('kind', 'shell'), ('status', 'trust-me')]:
            with self.subTest(field=field):
                self.setUp()
                if field == 'kind':
                    self.rejects(lambda m: m['tools'][0].update(kind=value))
                else:
                    self.rejects(lambda m: m['tools'][0]['install'].update(status=value))

    def test_invalid_hash_and_missing_active_hash_rejected(self):
        for value in ['garbage', None]:
            with self.subTest(value=value):
                self.setUp()
                self.rejects(lambda m: m['tools'][0].update(sha256=value))

    def test_default_inventory_cannot_silently_omit_tool(self):
        self.rejects(lambda m: m['default_tool_ids'].pop())

    def test_corrupted_local_lock_rejected(self):
        self.rejects(lambda m: m['tools'][1]['install']['lock'].update(sha256='0' * 64))

    def test_explicitly_blocked_missing_payload_hash_is_represented(self):
        tool = self.catalog['tools'][3]
        tool['sha256'] = None
        tool['artifact']['sha256'] = None
        self.assertIsNone(self.load()[3]['sha256'])

    def test_active_source_cannot_use_mutable_branch_with_plausible_version(self):
        def change(m):
            tool = m['tools'][1]
            tool['source'] = 'https://codeload.github.com/example/tool/tar.gz/main'
            tool['artifact']['url'] = tool['source']
            tool['active'] = True
            tool['blockers'] = []
            tool['install'].update(executable=True, status='ready')
        self.rejects(change)

    def test_arbitrary_python_probe_is_rejected(self):
        self.rejects(lambda m: m['tools'][14]['probe'].update(argv=['{tool_python}', '-c', 'print(123)']))

    def test_absolute_local_payload_is_rejected(self):
        self.rejects(lambda m: m['tools'][1]['install']['lock'].update(path='C:/outside/lock'))

    def activate(self, index=1):
        self.catalog['active'] = True
        tool = self.catalog['tools'][index]
        tool['active'] = True
        tool['blockers'] = []
        tool['install'].update(executable=True, status='ready')
        return tool

    def test_global_disable_rejects_active_records(self):
        self.activate()
        self.catalog['active'] = False
        with self.assertRaises(ValueError):
            self.load()

    def test_global_active_flag_requires_boolean(self):
        self.catalog['active'] = 'false'
        with self.assertRaises(ValueError):
            self.load()

    def test_active_python_requires_lock_metadata(self):
        for missing in ('lock', 'path', 'sha256'):
            with self.subTest(missing=missing):
                self.setUp()
                tool = self.activate()
                if missing == 'lock':
                    tool['install'].pop('lock')
                else:
                    tool['install']['lock'].pop(missing)
                with self.assertRaises(ValueError):
                    self.load()

    def test_active_node_requires_lock_metadata(self):
        tool = self.activate(2)
        tool['install'].pop('lock')
        with self.assertRaises(ValueError):
            self.load()

    def test_moving_develop_ref_cannot_be_active(self):
        tool = self.activate()
        tool.update(version='develop', upstream_release='develop', source='https://codeload.github.com/example/tool/tar.gz/develop')
        tool['artifact']['url'] = tool['source']
        with self.assertRaises(ValueError):
            self.load()

    def test_tool_and_default_id_cannot_both_disappear(self):
        self.catalog['tools'].pop()
        self.catalog['default_tool_ids'].remove('helicone')
        with self.assertRaises(ValueError):
            self.load()

    def test_enabled_catalog_can_represent_locked_ready_record(self):
        self.activate()
        self.assertTrue(self.load()[1]['active'])

if __name__ == '__main__':
    unittest.main()
