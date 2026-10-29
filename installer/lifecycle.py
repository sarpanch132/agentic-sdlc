"""Transactional owned-asset lifecycle with independent integrity authority."""
import hashlib
import json
import os
from pathlib import Path
import re

from .files import resolve_owned, write_owned, write_receipt
from . import state


def _private_root():
    return Path.home() / '.agentic-sdlc-state'


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _identity(root, host, scope):
    return _digest(json.dumps([os.path.normcase(str(Path(root).resolve())), host, scope], separators=(',', ':')).encode())


def _authority(root, host, scope, *, create=False, assets=None):
    from .engine import HOSTS
    if host not in HOSTS or scope not in ('user', 'project') or not Path(root).is_dir():
        raise ValueError('invalid host, scope or destination')
    identity = _identity(root, host, scope)
    base = state.store(_private_root(), root, scope)
    name = f'assets-{identity}.json'
    value = state.read(base, name)
    if value is None:
        if not create:
            raise ValueError('private installation authority missing')
        value = {'schema_version': 1, 'identity': identity, 'current': assets, 'previous': None, 'history': [], 'runtimes': {}, 'previous_runtimes': {}, 'pending': None}
        state.write(base, name, value)
    if not isinstance(value, dict) or set(value) != {'schema_version', 'identity', 'current', 'previous', 'history', 'runtimes', 'previous_runtimes', 'pending'} or type(value['schema_version']) is not int or value['schema_version'] != 1 or value['identity'] != identity or not isinstance(value['history'], list):
        raise ValueError('invalid private installation authority')
    for heads in (value['runtimes'], value['previous_runtimes']):
        if not isinstance(heads, dict) or any(not re.fullmatch('[a-z0-9-]+', key) or not isinstance(item, str) or not re.fullmatch('runtime-[0-9a-f]{64}\\.json', item) for key, item in heads.items()):
            raise ValueError('invalid runtime generation reference')
    for mapping in (value['current'], value['previous'], *value['history']):
        if mapping is None and mapping is value['previous']:
            continue
        if not isinstance(mapping, dict):
            raise ValueError('invalid generation inventory')
        for relative, digest in mapping.items():
            resolve_owned(root, relative)
            if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError('invalid generation hash')
            skill, agent = HOSTS[host]
            if not (relative.startswith(skill + '/agentic-sdlc/') or relative.startswith(skill + '/agentic-sdlc-') or relative.startswith(agent + '/agentic-sdlc')):
                raise ValueError('unexpected owned asset namespace')
    return base, name, value


def register_assets(root, host, scope, assets):
    """Attest only exact trusted distribution assets, never arbitrary historical bytes."""
    hashes = {relative: _digest(data) for relative, data in assets.items()}
    base, name, value = _authority(root, host, scope, create=True, assets=hashes)
    if not value['current'] and not value['pending']:
        value.update(current=hashes, previous=None, runtimes={}, previous_runtimes={})
        state.write(base, name, value)
    if value['current'] != hashes or value['pending']:
        raise ValueError('installed asset generation differs from private authority')


def _receipt(root, host, scope, owned):
    path = resolve_owned(root, '.agentic-sdlc/receipt.json')
    data = json.loads(path.read_text(encoding='utf-8'))
    if set(data) != {'schema_version', 'host', 'scope', 'root', 'owned_files', 'pending'} or any(data.get(key) != expected for key, expected in (('schema_version', 1), ('host', host), ('scope', scope), ('root', str(root)), ('owned_files', owned), ('pending', None))):
        raise ValueError('invalid receipt identity or ownership')
    return path, data


def _generation(mapping):
    return _digest(json.dumps(mapping, sort_keys=True, separators=(',', ':')).encode())


def _backup(root, mapping):
    generation = _generation(mapping)
    for relative, digest in mapping.items():
        path = resolve_owned(root, relative)
        data = path.read_bytes()
        if _digest(data) != digest:
            raise ValueError(f'modified asset: {relative}')
        backup = f'.agentic-sdlc/generations/{generation}/{relative}'
        saved = resolve_owned(root, backup)
        if saved.exists():
            if not saved.is_file() or _digest(saved.read_bytes()) != digest:
                raise ValueError('generation backup changed')
        else:
            write_owned(root, backup, data)
    return generation


def _saved(root, mapping):
    generation = _generation(mapping)
    result = {}
    for relative, digest in mapping.items():
        data = resolve_owned(root, f'.agentic-sdlc/generations/{generation}/{relative}').read_bytes()
        if _digest(data) != digest:
            raise ValueError('generation backup changed')
        result[relative] = data
    return result


def _replace(root, before, after, contents):
    for relative in set(before) | set(after):
        path = resolve_owned(root, relative)
        actual = _digest(path.read_bytes()) if path.is_file() else None
        if actual not in (before.get(relative), after.get(relative)):
            raise ValueError(f'modified asset during transaction: {relative}')
        if relative in after:
            if actual != after[relative]:
                write_owned(root, relative, contents[relative], actual)
        elif path.exists():
            path.unlink()


def _recover(root, base, name, authority):
    pending = authority['pending']
    if pending is None:
        return
    if isinstance(pending, dict) and pending.get('operation') == 'uninstall':
        _finish_uninstall(root, base, name, authority)
        return
    if not isinstance(pending, dict) or set(pending) != {'before', 'after'} or pending['before'] != authority['current']:
        raise ValueError('invalid private transaction')
    contents = _saved(root, pending['before'])
    _replace(root, pending['after'], pending['before'], contents)
    receipt = {'schema_version': 1, 'host': authority['_host'], 'scope': authority['_scope'], 'root': str(root), 'owned_files': pending['before'], 'pending': None}
    write_receipt(resolve_owned(root, '.agentic-sdlc/receipt.json'), receipt)
    authority['pending'] = None
    state.write(base, name, {k: v for k, v in authority.items() if not k.startswith('_')})


def _change(catalog, root, runner, host, scope, rolling_back):
    from . import engine
    root = Path(os.path.abspath(root))
    try:
        with engine._lock(root):
            base, name, authority = _authority(root, host, scope)
            authority.update(_host=host, _scope=scope)
            _recover(root, base, name, authority)
            before = authority['current']
            receipt_path, receipt = _receipt(root, host, scope, before)
            _backup(root, before)
            if before not in authority['history']:
                authority['history'].append(dict(before))
            if rolling_back:
                if authority['previous'] is None:
                    raise ValueError('previous generation unavailable')
                after = authority['previous']
                contents = _saved(root, after)
            else:
                contents = engine._payload(host)
                after = {relative: _digest(data) for relative, data in contents.items()}
            # Validate every destination before the first replacement.
            for relative in set(before) | set(after):
                path = resolve_owned(root, relative)
                if path.exists() and (not path.is_file() or relative not in before or _digest(path.read_bytes()) != before[relative]):
                    raise ValueError(f'unknown or modified asset: {relative}')
            records = engine._records(catalog)
            new_heads = dict(authority['runtimes'])
            if not rolling_back:
                engine._run_tools(catalog, root, host, scope, True, runner or engine.LocalRunner(), records)
                required = {tool['id'] for tool in catalog if tool['active'] and tool['install']['executable'] and tool['install']['status'] == 'ready'}
                if any(record['tool_id'] in required and (not record['installed'] or not record['smoke_tested']) for record in records):
                    raise ValueError('runtime update validation failed; previous generation retained')
                new_heads = _heads_from(root, base, catalog, records, host, scope, new_heads)
            else:
                new_heads = dict(authority['previous_runtimes'])
                allowed = {tool['id'] for tool in catalog if tool['active'] and tool['install']['executable'] and tool['install']['status'] == 'ready'}
                for identity, reference in new_heads.items():
                    old = _head_tool(root, base, reference, host, scope)
                    if identity in allowed:
                        record = {}
                        probe_runtime(root, old, host, scope, runner or engine.LocalRunner(), record)
                        if not record['smoke_tested']:
                            raise ValueError('previous runtime diagnostic failed; current generation retained')
                    else:
                        runtime_witness(root, old, host, scope)
            authority['pending'] = {'before': before, 'after': after}
            state.write(base, name, {k: v for k, v in authority.items() if not k.startswith('_')})
            try:
                _replace(root, before, after, contents)
                receipt['owned_files'] = after
                write_receipt(receipt_path, receipt)
            except (OSError, ValueError):
                _recover(root, base, name, authority)
                raise
            authority.update(current=after, previous=before, runtimes=new_heads, previous_runtimes=dict(authority['runtimes']), pending=None)
            state.write(base, name, {k: v for k, v in authority.items() if not k.startswith('_')})
        return {'status': 'blocked', 'assets_status': 'rolled-back' if rolling_back else 'updated', 'reason': 'asset generation committed; runtime readiness is reported separately', 'owned_files': after}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {'status': 'failed', 'assets_status': 'unchanged', 'reason': str(exc)}


def update(catalog, root, runner, *, host='codex', scope='project'):
    return _change(catalog, root, runner, host, scope, False)


def rollback(catalog, root, runner, *, host='codex', scope='project'):
    return _change(catalog, root, runner, host, scope, True)


def uninstall(root, *, host='codex', scope='project'):
    from . import engine
    root = Path(os.path.abspath(root))
    try:
        with engine._lock(root):
            base, name, authority = _authority(root, host, scope)
            authority.update(_host=host, _scope=scope)
            if authority['pending']:
                _recover(root, base, name, authority)
            owned = authority['current']
            receipt_path, receipt = _receipt(root, host, scope, owned)
            authority['pending'] = {'operation': 'uninstall', 'before': dict(owned)}
            state.write(base, name, {k: v for k, v in authority.items() if not k.startswith('_')})
            preserved, shared = _finish_uninstall(root, base, name, authority)
            return {'status': 'blocked' if preserved else 'complete', 'reason': 'modified or unknown resources preserved' if preserved else 'owned installation uninstalled', 'preserved': preserved, 'shared_resources': shared, 'owned_files': authority['current']}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {'status': 'failed', 'reason': str(exc), 'preserved': []}


def _remove_known(root, mapping):
    preserved = []
    for relative, digest in mapping.items():
        try:
            path = resolve_owned(root, relative)
        except ValueError:
            preserved.append(relative)
            continue
        if path.exists():
            if not path.is_file() or _digest(path.read_bytes()) != digest:
                preserved.append(relative)
                continue
            path.unlink()
    return preserved


def _remove_runtimes(root, base, host, scope):
    preserved, shared = [], []
    for path in base.glob('runtime-*.json'):
        value = state.read(base, path.name)
        if not isinstance(value, dict) or value.get('installation') != _identity(root, host, scope):
            continue
        tool = value.get('tool')
        if not isinstance(tool, dict) or value.get('identity') != _runtime_identity(root, tool, host, scope) or value.get('context') != runtime_context(tool):
            raise ValueError('invalid private runtime ownership')
        relative = value['context']
        context = resolve_owned(root, relative)
        if value.get('status') not in ('verified', 'uninstalled') or not isinstance(value.get('entries'), dict):
            if context.exists(): preserved.append(relative)
            continue
        files, directories = {}, []
        for entry, details in value['entries'].items():
            owned = relative + '/' + entry
            resolve_owned(root, owned)
            if details.get('kind') == 'file' and re.fullmatch('[0-9a-f]{64}', details.get('sha256', '')):
                files[owned] = details['sha256']
            elif details == {'kind': 'directory'}:
                directories.append(owned)
            else:
                raise ValueError('invalid runtime entry inventory')
        preserved.extend(_remove_known(root, files))
        for directory in sorted(directories, key=lambda item: item.count('/'), reverse=True) + [relative]:
            owned = resolve_owned(root, directory)
            if owned.is_dir():
                try: owned.rmdir()
                except OSError: pass
        if context.exists():
            preserved.append(relative)
            value['status'] = 'uninstalled'
            state.write(base, path.name, value)
        else:
            path.unlink()
        if tool['kind'] == 'oci-image':
            shared.append(tool['install']['commands'][0][2])
    return preserved, shared


def write_runtime_receipt(root, tool, host, scope, value):
    base = state.store(_private_root(), root, scope)
    installation = _identity(root, host, scope)
    relative = f'.agentic-sdlc/runtime-receipts/{host}/{tool["id"]}.json'
    name = f'receipt-{installation}-{tool["id"]}.json'
    prior = state.read(base, name)
    path = resolve_owned(root, relative)
    if prior is not None and (not isinstance(prior, dict) or set(prior) != {'installation', 'relative', 'sha256'}
            or prior['installation'] != installation or prior['relative'] != relative
            or not re.fullmatch('[0-9a-f]{64}', prior['sha256'])):
        raise ValueError('invalid private receipt ownership')
    if path.exists() and (prior is None or _digest(path.read_bytes()) != prior['sha256']):
        raise ValueError('runtime receipt is unknown or modified')
    write_receipt(path, value)
    state.write(base, name, {'installation': installation, 'relative': relative, 'sha256': _digest(path.read_bytes())})


def _remove_runtime_receipts(root, base, host, scope):
    installation = _identity(root, host, scope)
    prefix = f'.agentic-sdlc/runtime-receipts/{host}'
    preserved = []
    for private in base.glob(f'receipt-{installation}-*.json'):
        value = state.read(base, private.name)
        if (not isinstance(value, dict) or set(value) != {'installation', 'relative', 'sha256'}
                or value['installation'] != installation
                or not re.fullmatch(re.escape(prefix) + r'/[a-z0-9-]+\.json', value['relative'])
                or not re.fullmatch('[0-9a-f]{64}', value['sha256'])):
            raise ValueError('invalid private receipt ownership')
        remaining = _remove_known(root, {value['relative']: value['sha256']})
        preserved.extend(remaining)
        if not remaining:
            private.unlink()
    folder = resolve_owned(root, prefix)
    if folder.is_dir():
        preserved.extend(path.relative_to(root).as_posix() for path in folder.iterdir())
    for private in base.glob('interrupted-*.json'):
        value = state.read(base, private.name)
        if not isinstance(value, dict) or value.get('installation') != installation:
            continue
        context = runtime_context(value['tool'])
        quarantine = value.get('quarantine', '')
        if value.get('identity') != _runtime_identity(root, value['tool'], host, scope) or not re.fullmatch(re.escape(context) + r'\.interrupted-[0-9a-f]{32}', quarantine):
            raise ValueError('invalid interrupted runtime ownership')
        if resolve_owned(root, quarantine).exists():
            preserved.append(quarantine)
        else:
            private.unlink()
    return preserved


def _finish_uninstall(root, base, name, authority):
    pending = authority['pending']
    if not isinstance(pending, dict) or set(pending) != {'operation', 'before'} or pending['operation'] != 'uninstall' or pending['before'] != authority['current']:
        raise ValueError('invalid private uninstall intent')
    owned = pending['before']
    preserved = _remove_known(root, owned)
    remaining = {relative: digest for relative, digest in owned.items() if relative in preserved}
    runtime_preserved, shared = _remove_runtimes(root, base, authority['_host'], authority['_scope'])
    preserved.extend(runtime_preserved)
    preserved.extend(_remove_runtime_receipts(root, base, authority['_host'], authority['_scope']))
    for generation in [owned, authority['previous'] or {}, *authority['history']]:
        prefix = f'.agentic-sdlc/generations/{_generation(generation)}/'
        backups = {prefix + relative: digest for relative, digest in generation.items()}
        preserved.extend(_remove_known(root, backups))
    receipt = {'schema_version': 1, 'host': authority['_host'], 'scope': authority['_scope'], 'root': str(root), 'owned_files': remaining, 'pending': None}
    write_receipt(resolve_owned(root, '.agentic-sdlc/receipt.json'), receipt)
    authority.update(current=remaining, pending=None)
    state.write(base, name, {k: v for k, v in authority.items() if not k.startswith('_')})
    return sorted(set(preserved)), shared


def _recipe(tool):
    install = {key: tool['install'][key] for key in ('commands', 'lock', 'package', 'wheels') if key in tool['install']}
    for key in ('lock', 'package'):
        if key in install:
            install[key] = {field: install[key][field] for field in ('path', 'sha256', 'interpreter') if field in install[key]}
    return {**{key: tool.get(key) for key in ('id', 'version', 'kind', 'source', 'sha256', 'requires')},
            'recipe_schema': 1, 'install': install, 'probe': {'argv': tool['probe']['argv']}}


def runtime_context(tool):
    fingerprint = _digest(json.dumps(_recipe(tool), sort_keys=True, separators=(',', ':')).encode())[:16]
    return f'.agentic-sdlc/runtimes/{tool["id"]}/{fingerprint}'


def _head_tool(root, base, reference, host, scope):
    value = state.read(base, reference)
    if not isinstance(value, dict) or value.get('installation') != _identity(root, host, scope) or value.get('status') != 'verified' or not isinstance(value.get('tool'), dict):
        raise ValueError('runtime generation authority unavailable')
    if reference != 'runtime-' + _runtime_identity(root, value['tool'], host, scope) + '.json' or value.get('context') != runtime_context(value['tool']):
        raise ValueError('runtime generation identity mismatch')
    return value['tool']


def _heads_from(root, base, catalog, records, host, scope, existing):
    heads = dict(existing)
    installed = {record['tool_id'] for record in records if record.get('installed')}
    for tool in catalog:
        if tool['id'] in installed:
            reference = 'runtime-' + _runtime_identity(root, tool, host, scope) + '.json'
            _head_tool(root, base, reference, host, scope)
            heads[tool['id']] = reference
    return heads


def register_runtime_heads(root, catalog, records, host, scope):
    base, name, authority = _authority(root, host, scope)
    heads = _heads_from(root, base, catalog, records, host, scope, authority['runtimes'])
    if heads != authority['runtimes']:
        authority['runtimes'] = heads
        state.write(base, name, authority)


def active_runtime_tool(root, tool, host, scope):
    base, _, authority = _authority(root, host, scope)
    reference = authority['runtimes'].get(tool['id'])
    return _head_tool(root, base, reference, host, scope) if reference else tool


def _runtime_identity(root, tool, host, scope):
    recipe = _recipe(tool)
    return _digest(json.dumps([_identity(root, host, scope), recipe], sort_keys=True, separators=(',', ':')).encode())


def _snapshot(root, relative):
    import stat
    from pathlib import PureWindowsPath
    context = resolve_owned(root, relative)
    if not context.is_dir():
        raise ValueError('runtime directory unavailable')
    entries = {}
    def visit(directory):
        # Each ancestor is checked once; hostile concurrent replacement is excluded.
        with os.scandir(directory) as children:
            for child in children:
                piece = child.name
                if piece in ('', '.', '..') or piece.endswith((' ', '.')) or PureWindowsPath(piece).is_reserved() or re.search(r'[<>:"|?*\x00-\x1f\\]', piece):
                    raise ValueError('unsafe runtime entry name')
                metadata = child.stat(follow_symlinks=False)
                if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, 'st_file_attributes', 0) & 0x400:
                    raise ValueError('runtime contains a link or reparse point')
                safe = Path(child.path)
                name = safe.relative_to(context).as_posix()
                if stat.S_ISDIR(metadata.st_mode):
                    entries[name] = {'kind': 'directory'}
                    visit(safe)
                elif stat.S_ISREG(metadata.st_mode) and (metadata.st_nlink or safe.stat(follow_symlinks=False).st_nlink) == 1:
                    digest = hashlib.sha256()
                    with safe.open('rb') as stream:
                        while chunk := stream.read(1024 * 1024):
                            digest.update(chunk)
                    entries[name] = {'kind': 'file', 'sha256': digest.hexdigest()}
                else:
                    raise ValueError('runtime contains a special file or hardlink')
    visit(context)
    return entries


def begin_runtime(root, tool, host, scope, relative):
    expected = runtime_context(tool)
    if relative != expected or resolve_owned(root, relative).exists():
        raise ValueError('fresh runtime directory required')
    base = state.store(_private_root(), root, scope)
    identity = _runtime_identity(root, tool, host, scope)
    name = f'runtime-{identity}.json'
    if state.read(base, name) is not None:
        raise ValueError('existing runtime authority requires recovery')
    recipe = _recipe(tool)
    state.write(base, name, {'schema_version': 1, 'identity': identity, 'installation': _identity(root, host, scope), 'tool': recipe, 'status': 'pending', 'context': relative, 'entries': None})
    return name


def recover_pending_runtime(root, tool, host, scope):
    """Preserve an interrupted tree; rebuild it instead of adopting unknown bytes."""
    import uuid
    base = state.store(_private_root(), root, scope)
    identity = _runtime_identity(root, tool, host, scope)
    name = f'runtime-{identity}.json'
    pending = state.read(base, name)
    if not isinstance(pending, dict) or pending.get('status') != 'pending':
        return None
    relative = runtime_context(tool)
    expected = {'schema_version': 1, 'identity': identity, 'installation': _identity(root, host, scope),
                'tool': _recipe(tool), 'status': 'pending', 'context': relative, 'entries': None}
    if pending != expected:
        raise ValueError('interrupted runtime intent changed')
    context = resolve_owned(root, relative)
    quarantine = relative + '.interrupted-' + uuid.uuid4().hex
    target = resolve_owned(root, quarantine)
    if target.exists():
        raise ValueError('interruption preservation destination occupied')
    archived = {**pending, 'status': 'interrupted', 'quarantine': quarantine}
    state.write(base, 'interrupted-' + identity + '-' + uuid.uuid4().hex + '.json', archived)
    moved = context.exists()
    if moved:
        os.replace(context, target)
    resolve_owned(base, name).unlink()
    return quarantine if moved else ''


def seal_runtime(root, tool, host, scope, relative, ticket):
    base = state.store(_private_root(), root, scope)
    identity = _runtime_identity(root, tool, host, scope)
    if ticket != f'runtime-{identity}.json' or relative != runtime_context(tool):
        raise ValueError('runtime identity changed during installation')
    pending = state.read(base, ticket)
    recipe = _recipe(tool)
    expected = {'schema_version': 1, 'identity': identity, 'installation': _identity(root, host, scope), 'tool': recipe, 'status': 'pending', 'context': relative, 'entries': None}
    if pending != expected:
        raise ValueError('fresh runtime intent missing or changed')
    pending.update(status='verified', entries=_snapshot(root, relative))
    state.write(base, ticket, pending)


def runtime_witness(root, tool, host, scope):
    base = state.store(_private_root(), root, scope)
    identity = _runtime_identity(root, tool, host, scope)
    value = state.read(base, f'runtime-{identity}.json')
    if not isinstance(value, dict) or set(value) != {'schema_version', 'identity', 'installation', 'tool', 'status', 'context', 'entries'} or type(value['schema_version']) is not int or value['schema_version'] != 1 or value['identity'] != identity or value['installation'] != _identity(root, host, scope) or _runtime_identity(root, value['tool'], host, scope) != identity or value['status'] != 'verified' or value['context'] != runtime_context(tool) or not isinstance(value['entries'], dict):
        raise ValueError('runtime requires independent authentication before resume')
    if _snapshot(root, value['context']) != value['entries']:
        raise ValueError('runtime contents differ from private verification record')
    return value


def prior_runtime(root, tool, host, scope):
    base = state.store(_private_root(), root, scope)
    for path in base.glob('runtime-*.json'):
        value = state.read(base, path.name)
        if isinstance(value, dict) and value.get('installation') == _identity(root, host, scope) and value.get('tool', {}).get('id') == tool['id'] and value.get('status') == 'verified':
            runtime_witness(root, value['tool'], host, scope)
            return True
    return False


def probe_runtime(root, tool, host, scope, runner, record):
    import subprocess
    from . import engine
    witness = runtime_witness(root, tool, host, scope)
    context = resolve_owned(root, witness['context'])
    if tool['kind'] == 'skills':
        engine._skills_check(context)
        record.update(acquired=True, installed=True, smoke_tested=True,
                      reason='complete instruction runtime verified; native behavior is separate',
                      evidence=['fifteen complete skill trees and license', 'private instruction inventory'])
        return
    env = {'HOME': str(context), 'USERPROFILE': str(context), 'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1', 'PIP_CONFIG_FILE': os.devnull}
    env.update(engine.PROBE_ENV)
    if os.name == 'nt':
        for key in ('SYSTEMROOT', 'WINDIR'):
            if key in os.environ:
                env[key] = os.environ[key]
    if tool['kind'] == 'python':
        bindir = context / 'venv' / ('Scripts' if os.name == 'nt' else 'bin')
        argv = engine._python_probe_argv(tool, context)
        env['PATH'] = str(bindir)
    elif tool['kind'] == 'node':
        node, _ = engine._node_prerequisites(root, tool, runner, scope)
        lock = json.loads((context / 'package-lock.json').read_text(encoding='utf-8'))
        package = next(iter(lock['packages']['']['dependencies']))
        binary = tool['probe']['argv'][0].removeprefix('{tool_bin}/')
        entry = lock['packages']['node_modules/' + package]['bin'][binary]
        executable = resolve_owned(root, witness['context'] + '/node_modules/' + package + '/' + entry)
        argv = [str(node), str(executable), *tool['probe']['argv'][1:]]
        env.update(PATH=str(node.parent), npm_config_userconfig=str(context / 'npm-user.npmrc'), npm_config_globalconfig=str(context / 'npm-global.npmrc'))
    elif tool['kind'] == 'oci-image':
        import shutil
        found = shutil.which('docker')
        if not found:
            raise ValueError('native Docker prerequisite unavailable')
        docker = Path(found).resolve()
        forbidden = (engine.DIST, root if scope == 'project' else root / '.agentic-sdlc')
        if not docker.is_file() or docker.suffix.lower() in ('.cmd', '.bat', '.ps1') or any(docker.is_relative_to(base.resolve()) for base in forbidden):
            raise ValueError('unsafe Docker path')
        env.update(PATH=str(docker.parent), DOCKER_CONFIG=str(context))
        digest = tool['install']['commands'][0][2]
        argv = [str(docker), 'image', 'inspect', digest, '--format', '{{json .RepoDigests}}']
    else:
        raise ValueError('runtime diagnostics not implemented for recipe kind')
    result = runner.run(argv, cwd=context, env=env, timeout=engine.PROBE_TIMEOUT)
    if tool['kind'] == 'oci-image':
        healthy = not result.returncode and digest in json.loads(result.stdout)
    else:
        healthy = not result.returncode and tool['version'] in result.stdout
    runtime_witness(root, tool, host, scope)
    record.update(acquired=True, installed=True, smoke_tested=healthy,
                  reason='configuration and integration need setup' if healthy else 'runtime diagnostic probe failed',
                  evidence=['independent private runtime inventory', 'diagnostic probe' if healthy else 'failed diagnostic probe'])
    if not healthy:
        record['status'] = 'failed'
