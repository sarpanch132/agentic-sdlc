"""Structural evidence checks only; this does not launch or validate a host."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HostContractEvidence(unittest.TestCase):
    def test_evidence_is_complete_and_does_not_claim_runtime_proof(self):
        fixture = json.loads((ROOT / 'tests/fixtures/host-contracts.json').read_text())
        manifest = json.loads((ROOT / 'toolkit/manifest.json').read_text())
        observations = json.loads((ROOT / manifest['task2_proof']['observations']).read_text())
        commands = json.loads((ROOT / 'docs/evidence/2026-10-28-task-2/commands.json').read_text())
        self.assertEqual({h['id'] for h in fixture['hosts']}, {'claude-code', 'cursor', 'codex'})
        self.assertEqual(len(manifest['default_tool_ids']), 16)
        self.assertEqual(manifest['task2_proof']['decision'], 'go safe source; no-go full runtime/release')
        fields = {'subject', 'os', 'architecture', 'client_version', 'check', 'result', 'command_or_action', 'evidence_path'}
        for record in observations:
            self.assertEqual(set(record), fields)
            self.assertTrue((ROOT / record['evidence_path']).is_file())
            self.assertIn(record['result'], {'pass', 'fail', 'not-run'})
            if record['check'] != 'cli-help':
                self.assertEqual(record['result'], 'not-run')
        self.assertEqual(len(commands), 6)
        for command in commands:
            self.assertEqual(command['exit_code'], 0)
            self.assertIn(command['argv'][-1], {'--help', '--version'})
            self.assertTrue((ROOT / command['evidence_path']).is_file())
        codex = next(h for h in fixture['hosts'] if h['id'] == 'codex')
        self.assertFalse(codex['explicit_policy']['policy']['allow_implicit_invocation'])
        self.assertEqual(codex['specialist_fields'], ['name', 'description', 'developer_instructions'])


if __name__ == '__main__':
    unittest.main()
