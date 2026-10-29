"""Read an inert, validated catalog. No commands run during catalog loading."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from .files import resolve_owned

# The approved research inventory is fixed; input defaults cannot redefine it.
_REQUIRED_IDS = frozenset({'superpowers', 'spec-kit', 'openspec', 'metagpt', 'promptfoo',
                           'deepeval', 'ragas', 'openhands', 'cline', 'aider', 'langflow',
                           'agno', 'bentoml', 'mlflow', 'openllmetry', 'helicone'})
_MOVING_REFS = {'latest', 'main', 'master', 'head', 'develop', 'development', 'dev', 'trunk', 'stable', 'nightly'}
_ALLOWED_TOKENS = {'{tool_python}', '{tool_root}', '{tool_bin}', '{npm}', '{node}', '{docker}', '{tool_state}', '{requirements_lock}'}
_ALLOWED_STATUSES = {'candidate-unverified', 'locked-candidate-unverified', 'security-blocked', 'source-build-review-blocked', 'ready'}
_PROBES = {
    'graphify': ['{tool_bin}/graphify', '--version'],
    'superpowers': [], 'spec-kit': ['{tool_bin}/specify', 'version'],
    'openspec': ['{tool_bin}/openspec', '--version'],
    'metagpt': ['{tool_python}', '-I', '-c', "import metagpt; import importlib.metadata as m; print(m.version('metagpt'))"],
    'promptfoo': ['{tool_bin}/promptfoo', '--version'],
    'deepeval': ['{tool_python}', '-I', '-c', "import deepeval; import importlib.metadata as m; print(m.version('deepeval'))"],
    'ragas': ['{tool_python}', '-I', '-c', "import ragas; import importlib.metadata as m; print(m.version('ragas'))"],
    'cline': ['{tool_bin}/cline', '--version'],
    'aider': ['{tool_bin}/aider', '--version'], 'langflow': ['{tool_bin}/langflow', '--version'],
    'agno': ['{tool_python}', '-I', '-c', "import agno; import importlib.metadata as m; print(m.version('agno'))"],
    'bentoml': ['{tool_bin}/bentoml', '--version'],
    'mlflow': ['{tool_bin}/mlflow', '--version'],
    'openhands': ['{node}', '{tool_root}/node_modules/@openhands/agent-canvas/bin/agent-canvas.mjs', '--version'],
    'openllmetry': ['{tool_python}', '-I', '-c', "import traceloop.sdk; import importlib.metadata as m; print(m.version('traceloop-sdk'))"],
    'helicone': ['{docker}', 'image', 'inspect', 'helicone/helicone-all-in-one@sha256:4da15718dd4936da63be8fbd5f8aedd2d396e25bffccbbfcd786d0b568d6b901', '--format', '{{json .RepoDigests}}'],
}
_RECIPES = {
    'python': ['{tool_python}', '-m', 'pip', 'install', '--quiet', '--progress-bar', 'off', '--no-compile', '--require-hashes', '--only-binary=:all:', '-r', '{requirements_lock}'],
    'node': ['{npm}', 'ci', '--prefix', '{tool_root}', '--ignore-scripts', '--no-audit', '--fund=false'],
}


def _check(condition, reason):
    if not condition:
        raise ValueError(reason)


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _object(pairs):
    result = {}
    for key, value in pairs:
        _check(key not in result, 'duplicate JSON member')
        result[key] = value
    return result


def _tokens(argv, declared):
    _check(isinstance(argv, list), 'command must be an argv array')
    for arg in argv:
        _check(isinstance(arg, str) and arg and not any(c in arg for c in '\x00\n\r'), 'invalid argv member')
        placeholders = re.findall(r'\{[^{}]*\}', arg)
        _check(all(p in _ALLOWED_TOKENS and p in declared for p in placeholders), 'unsupported path token')
        stripped = re.sub(r'\{[^{}]*\}', '', arg)
        _check('{' not in stripped and '}' not in stripped, 'malformed path token')


def _verify_local_metadata(value, root):
    if isinstance(value, list):
        for child in value:
            _verify_local_metadata(child, root)
    elif isinstance(value, dict):
        if 'path' in value and 'sha256' in value:
            _check(_sha(value['sha256']), 'invalid local checksum')
            file = resolve_owned(root, value['path'])
            _check(file.is_file(), f'missing local payload: {file}')
            _check(hashlib.sha256(file.read_bytes()).hexdigest() == value['sha256'], f'local checksum mismatch: {file}')
        for child in value.values():
            _verify_local_metadata(child, root)


def load_catalog(path: Path) -> list[dict]:
    """Return disabled and active records; validate local install payload bytes.

    Manifest placement is <distribution>/toolkit/manifest.json. Remote archive
    bytes must be hashed by the acquisition caller; loading performs no network IO.
    """
    catalog = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_object)
    _check(isinstance(catalog, dict) and type(catalog.get('schema_version')) is int and catalog['schema_version'] == 1, 'unsupported manifest schema')
    _check(type(catalog.get('active')) is bool, 'catalog active must be boolean')
    phases = catalog.get('phase_tools')
    required_phases = {'planning', 'analysis', 'design', 'simulation', 'build',
                       'testing', 'deployment', 'governance', 'after-delivery'}
    _check(isinstance(phases, dict) and set(phases) == required_phases, 'nine complete phase assignments required')
    for assigned in phases.values():
        _check(isinstance(assigned, list) and assigned
               and all(isinstance(tool, str) and tool in _REQUIRED_IDS for tool in assigned)
               and len(assigned) == len(set(assigned)), 'invalid phase tool assignment')
    _check(set().union(*map(set, phases.values())) == _REQUIRED_IDS, 'phase assignments must cover all sixteen tools')
    fallbacks = catalog.get('phase_fallbacks')
    _check(isinstance(fallbacks, dict) and fallbacks.get('build') == 'host-native coding agent', 'native build phase fallback required')
    _check(catalog.get('cross_phase_tools') == ['graphify'], 'cross-phase Graphify assignment required')
    tools = catalog.get('tools')
    _check(isinstance(tools, list) and tools, 'tools must be a nonempty list')
    dependencies = catalog.get('runtime_dependencies')
    _check(isinstance(dependencies, list) and len(dependencies) == 1
           and isinstance(dependencies[0], dict) and dependencies[0].get('id') == 'graphify',
           'Graphify runtime dependency required')
    _check(all(isinstance(tool, dict) and tool.get('id') != 'graphify' for tool in tools),
           'Graphify belongs in runtime dependencies')
    tools = tools + dependencies
    seen = set()
    for tool in tools:
        _check(isinstance(tool, dict), 'tool must be an object')
        identity = tool.get('id')
        _check(isinstance(identity, str) and identity in _PROBES and identity not in seen, 'missing, unsupported or duplicate tool ID')
        seen.add(identity)
        kind = tool.get('kind')
        _check(isinstance(kind, str) and kind in {'python', 'node', 'skills', 'oci-image'}, 'unsupported kind')
        install, probe = tool.get('install'), tool.get('probe')
        _check(isinstance(install, dict) and isinstance(probe, dict), 'install and probe objects required')
        status = install.get('status')
        _check(isinstance(status, str) and status in _ALLOWED_STATUSES, 'unsupported status')
        _check(type(tool.get('active')) is bool and type(install.get('executable')) is bool, 'active/executable must be booleans')
        blocked = not tool['active'] and not install['executable'] and status in {'security-blocked', 'source-build-review-blocked'}
        version = tool.get('version')
        _check(isinstance(version, str) and version and version.lower() not in _MOVING_REFS and not re.search(r'[\s*^~<>=]', version), 'version must be pinned')
        source = tool.get('source')
        _check(isinstance(source, str), 'source URL required')
        url = urlsplit(source)
        _check(url.scheme == 'https' and url.hostname and not url.username and not url.password and not url.fragment, 'unsafe source URL')
        artifact = tool.get('artifact')
        _check(isinstance(artifact, dict), 'artifact object required')
        digest = tool.get('sha256')
        _check(_sha(digest) or digest is None and blocked, 'source digest must be SHA-256 unless explicitly blocked')
        _check(artifact.get('sha256') == digest and artifact.get('url', artifact.get('source')) == source, 'artifact/source mismatch')
        _check(type(artifact.get('bytes')) is int and artifact['bytes'] > 0, 'positive artifact size required')
        declared = install.get('path_tokens')
        _check(isinstance(declared, list) and all(isinstance(p, str) and p in _ALLOWED_TOKENS for p in declared), 'unsupported path token declaration')
        commands = install.get('commands')
        _check(isinstance(commands, list), 'commands must be a list')
        for command in commands:
            _tokens(command, declared)
            recipe_matches = kind in _RECIPES and command == _RECIPES[kind]
            if kind == 'oci-image':
                recipe_matches = len(command) == 3 and command[:2] == ['{docker}', 'pull'] and re.fullmatch(r'[a-z0-9/._-]+@sha256:[0-9a-f]{64}', command[2])
            _check(recipe_matches, 'unsupported install recipe')
        if kind in _RECIPES and (commands or tool['active'] or install['executable'] or status == 'locked-candidate-unverified'):
            lock = install.get('lock')
            filename = 'requirements.lock' if kind == 'python' else 'package-lock.json'
            _check(isinstance(lock, dict) and lock.get('path') == f'toolkit/locks/{identity}/{filename}' and _sha(lock.get('sha256')), 'required kind-specific lock path/hash missing')
        _check(probe.get('argv') == _PROBES[identity], 'unsupported probe recipe')
        if identity in {'openllmetry', 'helicone'}:
            # Exact trusted Python/Docker literals above are not expansion templates.
            _check(probe['argv'][0] in declared, 'probe executable token not declared')
        else:
            _tokens(probe['argv'], declared)
        if tool['active'] or install['executable']:
            _check(catalog['active'], 'globally disabled catalog cannot enable a tool')
            _check(tool['active'] and install['executable'] and status == 'ready'
                   and (commands or kind == 'skills') and not tool.get('blockers'), 'active record has unresolved gates')
            snapshot = tool.get('upstream_snapshot')
            # Git sources use a full commit or the recorded release tag plus its snapshot.
            git_pin = (isinstance(snapshot, str) and re.fullmatch('[0-9a-f]{40}', snapshot)
                       and (version == snapshot or version == tool.get('upstream_release')))
            pinned_url = (url.hostname == 'files.pythonhosted.org' and re.fullmatch(r'/packages/[a-f0-9/]+/[^/]+', url.path)
                          or url.hostname == 'registry.npmjs.org' and url.path.endswith('-' + version + '.tgz')
                          or url.hostname == 'codeload.github.com' and git_pin and url.path.endswith('/tar.gz/' + version))
            _check(pinned_url and not url.query, 'active source URL must be pinned')
        _verify_local_metadata(install, path.parent.parent)
    defaults = catalog.get('default_tool_ids')
    _check(seen == _REQUIRED_IDS | {'graphify'}, 'catalog must contain all 16 approved tools and Graphify')
    _check(isinstance(defaults, list) and all(isinstance(i, str) for i in defaults) and len(defaults) == len(_REQUIRED_IDS) and set(defaults) == _REQUIRED_IDS, 'default inventory must include every distinct phase tool')
    return tools
