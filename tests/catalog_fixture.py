"""Offline fixtures keep unit tests separate from real runtime integration checks."""
import json
from pathlib import Path
import shutil

from installer.catalog import load_catalog

ROOT = Path(__file__).resolve().parents[1]


def disable_runtime_records(records):
    for tool in records:
        tool['active'] = False
        tool['install']['executable'] = False
        if tool['install']['status'] == 'ready':
            tool['install']['status'] = 'locked-candidate-unverified'


def inactive_catalog():
    records = load_catalog(ROOT / 'toolkit/manifest.json')
    disable_runtime_records(records)
    return records


def inactive_distribution(target):
    for name in ('installer', 'skills', 'adapters', 'toolkit'):
        shutil.copytree(ROOT / name, target / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    path = target / 'toolkit/manifest.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    disable_runtime_records(data['tools'] + data['runtime_dependencies'])
    data['active'] = False
    path.write_text(json.dumps(data), encoding='utf-8')
