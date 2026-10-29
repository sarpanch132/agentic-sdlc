import copy
from pathlib import Path
import tempfile
import unittest

from installer import engine
from installer.catalog import load_catalog


class PythonProbeTest(unittest.TestCase):
    def test_isolated_library_probe_prevents_bytecode_mutation(self):
        tool = next(t for t in load_catalog(engine.DIST / 'toolkit/manifest.json') if t['id'] == 'agno')
        with tempfile.TemporaryDirectory() as directory:
            argv = engine._python_probe_argv(tool, Path(directory))
            self.assertIn('-B', argv[1:argv.index('-c')])

    def test_runtime_probe_allows_bounded_cold_cli_startup(self):
        self.assertEqual(getattr(engine, 'PROBE_TIMEOUT', None), 90)

    def test_library_probe_uses_isolated_runtime_interpreter(self):
        self.assertTrue(callable(getattr(engine, '_python_probe_argv', None)), 'shared Python probe expansion missing')
        tool = copy.deepcopy(next(t for t in load_catalog(engine.DIST / 'toolkit/manifest.json') if t['id'] == 'agno'))
        tool['probe']['argv'] = ['{tool_python}', '-I', '-c', 'import agno; print("3.1.11")']
        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory)
            argv = engine._python_probe_argv(tool, context)
            self.assertEqual(Path(argv[0]).parent.parent, context / 'venv')
            self.assertEqual(argv[1:], ['-B', *tool['probe']['argv'][1:]])

    def test_cli_probe_expands_the_actual_entrypoint(self):
        self.assertTrue(callable(getattr(engine, '_python_probe_argv', None)), 'shared Python probe expansion missing')
        tool = next(t for t in load_catalog(engine.DIST / 'toolkit/manifest.json') if t['id'] == 'spec-kit')
        with tempfile.TemporaryDirectory() as directory:
            argv = engine._python_probe_argv(tool, Path(directory))
            self.assertEqual(Path(argv[0]).stem, 'specify')
            self.assertEqual(argv[1:], ['version'])

    def test_recipe_changes_create_a_new_runtime_generation(self):
        from installer.lifecycle import runtime_context
        tool = copy.deepcopy(next(t for t in load_catalog(engine.DIST / 'toolkit/manifest.json') if t['id'] == 'graphify'))
        original = runtime_context(tool)
        tool['probe']['argv'].append('changed')
        self.assertNotEqual(runtime_context(tool), original)

    def test_audit_text_does_not_invalidate_runtime_identity(self):
        from installer.lifecycle import _runtime_identity
        tool = copy.deepcopy(next(t for t in load_catalog(engine.DIST / 'toolkit/manifest.json') if t['id'] == 'graphify'))
        with tempfile.TemporaryDirectory() as directory:
            original = _runtime_identity(Path(directory), tool, 'codex', 'project')
            tool['install']['audit'] = 'same packages; refreshed advisory check'
            self.assertEqual(_runtime_identity(Path(directory), tool, 'codex', 'project'), original)

    def test_runtime_inventory_rejects_hardlinks(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'runtime').mkdir()
            original = root / 'outside.txt'
            original.write_text('outside runtime')
            try:
                os.link(original, root / 'runtime/linked.txt')
            except OSError:
                self.skipTest('hardlinks unavailable')
            with self.assertRaises(ValueError):
                engine._runtime_hashes(root, 'runtime')
