"""Install host assets and run explicitly enabled, gated runtime recipes."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.request import HTTPRedirectHandler

from .files import resolve_owned, write_owned, write_receipt

DIST = Path(__file__).resolve().parents[1]
INVENTORY = Path(__file__).with_name('asset-inventory.json')
HOSTS = {'claude': ('.claude/skills', '.claude/agents'),
         'cursor': ('.cursor/skills', '.cursor/agents'),
         'codex': ('.agents/skills', '.codex/agents')}
PROBE_TIMEOUT = 90

PROBE_ENV = {'DO_NOT_TRACK': '1', 'AGNO_TELEMETRY': 'false', 'DEEPEVAL_TELEMETRY_OPT_OUT': '1',
             'BENTOML_DO_NOT_TRACK': 'true', 'MLFLOW_DISABLE_TELEMETRY': 'true',
             'PROMPTFOO_DISABLE_TELEMETRY': '1', 'PROMPTFOO_DISABLE_UPDATE': '1',
             'OTEL_SDK_DISABLED': 'true', 'OTEL_TRACES_EXPORTER': 'none',
             'OTEL_METRICS_EXPORTER': 'none', 'OTEL_LOGS_EXPORTER': 'none'}


def _digest(content):
    return hashlib.sha256(content).hexdigest()


def _payload(host):
    skill_root, agent_root = HOSTS[host]
    inventory = json.loads(INVENTORY.read_text(encoding='utf-8'))
    if not isinstance(inventory, dict) or not inventory:
        raise ValueError('incomplete payload inventory')
    contents = {}
    for source, expected in inventory.items():
        if source.startswith('skills/agentic-sdlc/'):
            suffix = source.removeprefix('skills/agentic-sdlc/')
            if suffix == 'SKILL.md':
                suffix = 'WORKFLOW.md'
            dest = f'{skill_root}/agentic-sdlc/workflow/{suffix}'
        elif source.startswith('skills/dependencies/'):
            dest = f'{skill_root}/{source.removeprefix("skills/dependencies/")}'
        elif source.startswith(f'adapters/{host}/skills/'):
            dest = f'{skill_root}/{source.removeprefix(f"adapters/{host}/skills/")}'
        elif source.startswith(f'adapters/{host}/agents/'):
            dest = f'{agent_root}/{source.removeprefix(f"adapters/{host}/agents/")}'
        else:
            continue
        path = resolve_owned(DIST, source)
        if not path.is_file():
            raise ValueError(f'incomplete payload: missing {source}')
        data = path.read_bytes()
        if not isinstance(expected, str) or _digest(data) != expected:
            raise ValueError(f'payload integrity mismatch: {source}')
        if dest in contents:
            raise ValueError('duplicate payload destination')
        contents[dest] = data
    for helper in ('brainstorming', 'graphify', 'ponytail', 'ui-ux-pro-max'):
        entry = f'{skill_root}/agentic-sdlc-{helper}/SKILL.md'
        if entry not in contents:
            raise ValueError('incomplete payload: missing helper')
        if host == 'codex':
            contents[entry.removesuffix('SKILL.md') + 'agents/openai.yaml'] = b'policy:\n  allow_implicit_invocation: true\n'
        else:
            data = contents[entry]
            newline = b'\r\n' if data.startswith(b'---\r\n') else b'\n'
            if not data.startswith(b'---' + newline):
                raise ValueError('invalid helper frontmatter')
            contents[entry] = b'---' + newline + b'disable-model-invocation: false' + newline + data[3 + len(newline):]
    contents[f'{skill_root}/agentic-sdlc/workflow/installer-location.json'] = (json.dumps(
        {'source': str(DIST), 'kind': 'location-hint'}, indent=2) + '\n').encode()
    return contents


@contextmanager
def _lock(root):
    path = resolve_owned(root, '.agentic-sdlc/install.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as file:
        file.seek(0, 2)
        if file.tell() == 0:
            file.write(b'0')
            file.flush()
        file.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            file.seek(0)
            if os.name == 'nt':
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(file, fcntl.LOCK_UN)


def _receipt(root, host, scope, assets):
    path = resolve_owned(root, '.agentic-sdlc/receipt.json')
    empty = {'schema_version': 1, 'host': host, 'scope': scope, 'root': str(root), 'owned_files': {}, 'pending': None}
    if not path.exists():
        return path, empty
    receipt = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(receipt, dict) or set(receipt) != set(empty) or type(receipt['schema_version']) is not int or any(receipt[k] != empty[k] for k in ('schema_version', 'host', 'scope', 'root')):
        raise ValueError('invalid receipt identity')
    owned, pending = receipt['owned_files'], receipt['pending']
    if not isinstance(owned, dict) or any(k not in assets or not isinstance(v, str) or not re.fullmatch('[0-9a-f]{64}', v) or v != _digest(assets[k]) for k, v in owned.items()):
        raise ValueError('invalid receipt ownership')
    if pending is not None and (not isinstance(pending, dict) or set(pending) != {'path', 'sha256'} or not isinstance(pending['path'], str) or pending['path'] not in assets or pending['sha256'] != _digest(assets[pending['path']])):
        raise ValueError('invalid pending write')
    return path, receipt


def _records(catalog):
    records = []
    skills = json.loads((Path(__file__).resolve().parents[1] / 'toolkit/skills.json').read_text(encoding='utf-8'))
    runtime = next(item['runtime'] for item in skills['skills'] if item['id'] == 'graphify')
    graphify = {'id': 'graphify', 'version': runtime['version'], 'install': {'status': '; '.join(runtime['blockers'])}}
    for item in catalog + ([] if any(item['id'] == 'graphify' for item in catalog) else [graphify]):
        identity, version = item['id'], item['version']
        records.append({'tool_id': identity, 'version': version, 'acquired': False, 'installed': False,
                        'smoke_tested': False, 'configured': False, 'project_integrated': False,
                        'status': 'blocked', 'reason': ('runtime not yet verified' if item['install']['status'] == 'ready' else item['install']['status']),
                        'owned_files': {}, 'evidence': []})
    return records


def _operate(catalog, root, host, scope, installing, runner):
    root = Path(os.path.abspath(root))
    records = _records(catalog)
    if runner is None:
        runner = LocalRunner()
    try:
        if host not in HOSTS or scope not in ('user', 'project') or not root.is_dir():
            raise ValueError('invalid host, scope or destination')
        assets = _payload(host)
        with _lock(root):
            path, receipt = _receipt(root, host, scope, assets)
            pending = receipt['pending']
            if installing and pending:
                target = resolve_owned(root, pending['path'])
                if target.exists():
                    if not target.is_file() or _digest(target.read_bytes()) != pending['sha256']:
                        raise ValueError('pending file changed')
                    receipt['owned_files'][pending['path']] = pending['sha256']
                receipt['pending'] = None
                write_receipt(path, receipt)
            for relative, content in assets.items():
                target = resolve_owned(root, relative)
                prior = receipt['owned_files'].get(relative)
                if target.exists():
                    if not target.is_file() or prior != _digest(content) or _digest(target.read_bytes()) != prior:
                        raise ValueError(f'unknown or modified asset: {relative}')
                elif installing:
                    receipt['pending'] = {'path': relative, 'sha256': _digest(content)}
                    write_receipt(path, receipt)
                    write_owned(root, relative, content)
                    receipt['owned_files'][relative] = _digest(content)
                    receipt['pending'] = None
                    write_receipt(path, receipt)
                else:
                    raise ValueError(f'asset installation incomplete: {relative}')
            if not path.exists() or receipt['pending'] or set(receipt['owned_files']) != set(assets):
                raise ValueError('asset installation incomplete')
            if installing:
                from .lifecycle import register_assets
                register_assets(root, host, scope, assets)
            _run_tools(catalog, root, host, scope, installing, runner, records)
            if installing:
                from .lifecycle import register_runtime_heads
                register_runtime_heads(root, catalog, records, host, scope)
            if scope == 'project':
                from .project import apply_status
                apply_status(catalog, root, root, host, scope, records)
        status = 'failed' if any(record['status'] == 'failed' for record in records) else 'blocked'
        return {'status': status, 'reason': 'runtime provisioning and diagnostics incomplete', 'tools': records, 'owned_files': receipt['owned_files']}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {'status': 'failed', 'reason': str(exc), 'tools': records, 'owned_files': {}}


def _run_tools(catalog, root, host, scope, installing, runner, records):
    for tool, record in zip(catalog, records):
        if not installing:
            if tool['active'] and tool['install']['executable'] and tool['install']['status'] == 'ready':
                try:
                    from .lifecycle import active_runtime_tool
                    selected = active_runtime_tool(root, tool, host, scope)
                    record.update(version=selected['version'], requested_version=tool['version'])
                    if not _resume_python(root, selected, host, scope, runner, record):
                        record['reason'] = 'runtime not installed'
                except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired, RuntimeError):
                    record.update(status='failed', reason='runtime diagnostics failed safely')
            continue
        if installing and tool['active'] and tool['install']['executable'] and tool['install']['status'] == 'ready' and runner is not None:
            import sys
            try:
                if _resume_python(root, tool, host, scope, runner, record):
                    continue
            except subprocess.TimeoutExpired:
                record.update(status='failed', reason='command timeout')
                continue
            except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                record.update(status='failed', reason='authenticated runtime probe failed safely')
                continue
            if tool['kind'] == 'oci-image':
                try:
                    _oci_install(root, tool, runner, record, host, scope)
                except subprocess.TimeoutExpired:
                    record.update(status='failed', reason='command timeout')
                except RuntimeError as exc:
                    _runtime_error(record, exc)
                except (OSError, ValueError):
                    record['reason'] = 'native Docker prerequisite or isolated state unavailable'
                continue
            if tool['kind'] not in ('python', 'node', 'skills'):
                record['reason'] = 'runtime recipe not supported'
                continue
            node = npm = None
            if tool['kind'] == 'node':
                try:
                    node, npm = _node_prerequisites(root, tool, runner, scope)
                except subprocess.TimeoutExpired:
                    record.update(status='failed', reason='command timeout')
                    continue
                except RuntimeError as exc:
                    _runtime_error(record, exc)
                    continue
                except (ValueError, OSError) as exc:
                    allowed = {'verified Node compatibility range required', 'native Node prerequisite unavailable', 'verified Node must be outside project and distribution', 'verified Node and npm runtime required', 'incompatible Node or npm prerequisite'}
                    record['reason'] = str(exc) if str(exc) in allowed else 'Node prerequisite check failed'
                    continue
            required = tool.get('install', {}).get('lock', {}).get('interpreter')
            if tool['kind'] == 'python' and required != f'Python{sys.version_info.major}.{sys.version_info.minor}':
                record['reason'] = f'requires {required}'
                continue
            try:
                from urllib.error import HTTPError
                try:
                    artifact = runner.fetch(tool['source'], timeout=30)
                except (TimeoutError, HTTPError) as exc:
                    if isinstance(exc, HTTPError) and exc.code not in (429, 503):
                        raise
                    artifact = runner.fetch(tool['source'], timeout=30)
                if not isinstance(artifact, bytes) or _digest(artifact) != tool['sha256'] or len(artifact) != tool['artifact']['bytes']:
                    raise ValueError('artifact checksum or length mismatch')
                record['acquired'] = True
                if tool['kind'] == 'python':
                    _python_install(root, tool, artifact, runner, record, host, scope)
                elif tool['kind'] == 'skills':
                    _skills_install(root, tool, artifact, record, host, scope)
                else:
                    _node_install(root, tool, artifact, runner, record, node, npm, host, scope)
            except subprocess.TimeoutExpired:
                record.update(status='failed', reason='command timeout')
            except RuntimeError as exc:
                _runtime_error(record, exc)
            except ValueError as exc:
                record['status'] = 'failed'
                record['reason'] = ('lock checksum mismatch' if str(exc) in ('requirements lock checksum mismatch', 'package lock checksum mismatch') else 'artifact checksum or length mismatch')
            except OSError:
                record['status'] = 'failed'
                record['reason'] = 'artifact transport failed'


def _runtime_error(record, exc):
    if str(exc) == 'command output limit exceeded':
        record.update(status='failed', reason='command output limit exceeded')
    else:
        record['reason'] = 'safe process isolation unavailable'


def _oci_install(root, tool, runner, record, host, scope):
    import shutil
    found = shutil.which('docker')
    if not found:
        raise ValueError('Docker unavailable')
    docker = Path(found).resolve()
    forbidden = (DIST, root if scope == 'project' else root / '.agentic-sdlc')
    if not docker.is_file() or docker.suffix.lower() in ('.cmd', '.bat', '.ps1') or (os.name == 'nt' and docker.suffix.lower() != '.exe') or any(docker.is_relative_to(base.resolve()) for base in forbidden):
        raise ValueError('unsafe Docker path')
    command = tool['install']['commands'][0]
    if len(command) != 3 or command[:2] != ['{docker}', 'pull'] or not re.fullmatch(r'[a-z0-9/._-]+@sha256:[0-9a-f]{64}', command[2]):
        raise ValueError('unapproved image digest')
    from .lifecycle import runtime_context
    relative = runtime_context(tool)
    path = resolve_owned(root, f'.agentic-sdlc/runtime-receipts/{host}/{tool["id"]}.json')
    context = resolve_owned(root, relative)
    from .lifecycle import begin_runtime, seal_runtime
    ticket = begin_runtime(root, tool, host, scope, relative)
    context.mkdir(parents=True, exist_ok=False)
    env = {'PATH': str(docker.parent), 'HOME': str(context), 'USERPROFILE': str(context), 'DOCKER_CONFIG': str(context)}
    if os.name == 'nt':
        for key in ('SYSTEMROOT', 'WINDIR'):
            if key in os.environ: env[key] = os.environ[key]
    version = runner.run([str(docker), '--version'], cwd=context, env=env, timeout=15)
    if version.returncode or not version.stdout.lower().startswith('docker version'):
        raise ValueError('Docker unavailable')
    result = runner.run([str(docker), 'pull', command[2]], cwd=context, env=env, timeout=600)
    if result.returncode:
        record.update(status='failed', reason='image acquisition failed')
        return
    inspected = runner.run([str(docker), 'image', 'inspect', command[2], '--format', '{{json .RepoDigests}}'], cwd=context, env=env, timeout=30)
    try:
        digests = json.loads(inspected.stdout)
    except (ValueError, TypeError):
        digests = []
    if inspected.returncode or not isinstance(digests, list) or command[2] not in digests:
        record['reason'] = 'image digest inspection failed'
        return
    path = resolve_owned(root, f'.agentic-sdlc/runtime-receipts/{host}/{tool["id"]}.json')
    if path.exists():
        raise ValueError('runtime receipt already exists')
    seal_runtime(root, tool, host, scope, relative, ticket)
    from .lifecycle import write_runtime_receipt
    write_runtime_receipt(root, tool, host, scope, {'schema_version': 1, 'host': host, 'scope': scope, 'root': str(root),
                         'tool_id': tool['id'], 'version': tool['version'], 'artifact': command[2],
                         'acquired': True, 'installed': True, 'smoke_tested': True,
                         'configured': False, 'project_integrated': False, 'status': 'blocked',
                         'reason': 'configuration and integration need setup', 'owned_files': {},
                         'evidence': ['image digest inspection']})
    record.update(acquired=True, installed=True, smoke_tested=True, reason='configuration and integration need setup')


def _node_prerequisites(root, tool, runner, scope):
    import shutil
    requirement = tool.get('requires', {}).get('node')
    match = re.fullmatch(r'>=(\d+)(?:\.(\d+))?(?:\.(\d+))?', requirement or '')
    if not match:
        raise ValueError('verified Node compatibility range required')
    found = shutil.which('node')
    if not found:
        raise ValueError('native Node prerequisite unavailable')
    node = Path(found).resolve()
    forbidden = (DIST, root if scope == 'project' else root / '.agentic-sdlc')
    if not node.is_file() or node.suffix.lower() in ('.cmd', '.bat', '.ps1') or (os.name == 'nt' and node.suffix.lower() != '.exe') or any(node.is_relative_to(base.resolve()) for base in forbidden):
        raise ValueError('verified Node must be outside project and distribution')
    npm = (node.parent / 'node_modules/npm/bin/npm-cli.js').resolve()
    if not npm.is_file() or not npm.is_relative_to(node.parent.resolve()) or any(npm.is_relative_to(base.resolve()) for base in forbidden):
        raise ValueError('verified Node and npm runtime required')
    import tempfile
    from .lifecycle import _private_root
    from .state import store
    base = store(_private_root(), root, scope)
    with tempfile.TemporaryDirectory(prefix='node-check-', dir=base) as temporary:
        context = Path(temporary)
        user_config, global_config = context / 'npm-user.npmrc', context / 'npm-global.npmrc'
        user_config.write_bytes(b'')
        global_config.write_bytes(b'')
        env = {'PATH': str(node.parent), 'HOME': str(context), 'USERPROFILE': str(context),
               'npm_config_userconfig': str(user_config), 'npm_config_globalconfig': str(global_config),
               'npm_config_cache': str(context / 'cache')}
        if os.name == 'nt':
            for key in ('SYSTEMROOT', 'WINDIR'):
                if key in os.environ: env[key] = os.environ[key]
        node_version = runner.run([str(node), '--version'], cwd=context, env=env, timeout=15)
        npm_version = runner.run([str(node), str(npm), '--version'], cwd=context, env=env, timeout=15)
    nv = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)\s*', node_version.stdout)
    pv = re.fullmatch(r'(\d+)\.\d+\.\d+\s*', npm_version.stdout)
    if node_version.returncode or npm_version.returncode or not nv or not pv or tuple(map(int, nv.groups())) < tuple(int(x or 0) for x in match.groups()) or int(pv[1]) < 9:
        raise ValueError('incompatible Node or npm prerequisite')
    return node, npm


def _node_install(root, tool, artifact, runner, record, node, npm, host, scope):
    lock = tool['install']['lock']
    lock_bytes = resolve_owned(DIST, lock['path']).read_bytes()
    if _digest(lock_bytes) != lock['sha256']:
        raise ValueError('package lock checksum mismatch')
    parsed = json.loads(lock_bytes)
    if parsed.get('lockfileVersion') != 3:
        raise ValueError('unsupported package lock')
    package = parsed['packages']['']
    manifest = {key: package[key] for key in ('name', 'version', 'dependencies') if key in package}
    reviewed = tool['install'].get('package')
    if reviewed is not None:
        payload = resolve_owned(DIST, reviewed['path']).read_bytes()
        if _digest(payload) != reviewed['sha256']:
            raise ValueError('package manifest checksum mismatch')
        candidate = json.loads(payload)
        if (not isinstance(candidate, dict)
                or not set(candidate) <= {'name', 'version', 'private', 'dependencies', 'overrides'}
                or any(candidate.get(key) != package.get(key) for key in ('name', 'version', 'dependencies'))):
            raise ValueError('package manifest disagrees with lock')
        overrides = candidate.get('overrides', {})
        if not isinstance(overrides, dict) or any(not isinstance(key, str) or not isinstance(value, str)
                or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?', value) for key, value in overrides.items()):
            raise ValueError('package overrides must use exact reviewed versions')
        manifest = candidate
    from .lifecycle import runtime_context
    relative = runtime_context(tool)
    context = resolve_owned(root, relative)
    from .lifecycle import begin_runtime, seal_runtime
    ticket = begin_runtime(root, tool, host, scope, relative)
    context.mkdir(parents=True, exist_ok=False)
    write_owned(root, relative + '/artifact', artifact)
    write_owned(root, relative + '/package-lock.json', lock_bytes)
    write_owned(root, relative + '/package.json', json.dumps(manifest).encode('utf-8'))
    write_owned(root, relative + '/npm-user.npmrc', b'')
    write_owned(root, relative + '/npm-global.npmrc', b'')
    env = {'PATH': str(node.parent), 'HOME': str(context), 'USERPROFILE': str(context),
           'npm_config_userconfig': str(context / 'npm-user.npmrc'), 'npm_config_globalconfig': str(context / 'npm-global.npmrc'),
           'npm_config_cache': str(context / 'cache')}
    env.update(PROBE_ENV)
    if os.name == 'nt':
        for key in ('SYSTEMROOT', 'WINDIR'):
            if key in os.environ: env[key] = os.environ[key]
    result = runner.run([str(node), str(npm), 'ci', '--prefix', str(context), '--ignore-scripts', '--no-audit', '--fund=false'], cwd=context, env=env, timeout=600)
    if result.returncode:
        record['status'] = 'failed'
        record['reason'] = 'install command failed'
    else:
        dependencies = package.get('dependencies', {})
        if len(dependencies) != 1:
            record['reason'] = 'ambiguous lockfile entrypoint'
            return
        package_name = next(iter(dependencies))
        package_info = parsed['packages'].get('node_modules/' + package_name, {})
        name = tool['probe']['argv'][0].removeprefix('{tool_bin}/')
        entry = package_info.get('bin', {}).get(name)
        if not isinstance(entry, str) or Path(entry).suffix not in ('.js', '.mjs', '.cjs'):
            record['reason'] = 'lockfile entrypoint unavailable'
            return
        executable = resolve_owned(root, relative + '/node_modules/' + package_name + '/' + entry)
        if not executable.is_file():
            record['reason'] = 'installed entrypoint missing'
            return
        probe = runner.run([str(node), str(executable), *tool['probe']['argv'][1:]], cwd=context, env=env, timeout=PROBE_TIMEOUT)
        if probe.returncode or tool['version'] not in probe.stdout:
            record['reason'] = 'version probe failed'
            return
        files = _runtime_hashes(root, relative)
        receipt_path = resolve_owned(root, f'.agentic-sdlc/runtime-receipts/{host}/{tool["id"]}.json')
        receipt = {'schema_version': 1, 'host': host, 'scope': scope, 'root': str(root),
                   'id': tool['id'], 'version': tool['version'], 'artifact': tool['sha256'],
                   'lock': lock['sha256'], 'context': relative, 'files': files,
                   'acquired': True, 'installed': True, 'smoke_tested': True,
                   'configured': False, 'project_integrated': False, 'status': 'blocked',
                   'reason': 'configuration and integration need setup', 'owned_files': files,
                   'evidence': ['verified artifact and lock', 'version probe']}
        seal_runtime(root, tool, host, scope, relative, ticket)
        from .lifecycle import write_runtime_receipt
        write_runtime_receipt(root, tool, host, scope, receipt)
        record.update(installed=True, smoke_tested=True, reason='configuration and integration need setup')


def _skills_check(context):
    skills = list((context / 'skills').glob('*/SKILL.md'))
    if not (context / 'LICENSE').is_file() or len(skills) != 15 or any(not file.read_text(encoding='utf-8').strip() for file in skills):
        raise ValueError('complete fifteen-skill framework and license required')


def _skills_install(root, tool, artifact, record, host, scope):
    import io
    import tarfile
    from pathlib import PurePosixPath
    from .lifecycle import begin_runtime, seal_runtime, runtime_context
    selected = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(artifact)) as archive:
            for member in archive:
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or '\\' in member.name:
                    raise ValueError('unsafe instruction archive path')
                relative = '/'.join(path.parts[1:])
                if member.isdir() or not (relative == 'LICENSE' or relative.startswith('skills/')):
                    continue
                if not member.isfile() or relative in selected or member.size > 512 * 1024:
                    raise ValueError('unsafe instruction archive member')
                selected[relative] = archive.extractfile(member).read()
                if sum(map(len, selected.values())) > 8 * 1024 * 1024:
                    raise ValueError('instruction asset budget exceeded')
    except tarfile.TarError as exc:
        raise ValueError('invalid instruction archive') from exc
    if 'LICENSE' not in selected or len([name for name in selected if len(PurePosixPath(name).parts) == 3 and name.endswith('/SKILL.md')]) != 15:
        raise ValueError('complete fifteen-skill framework required')
    relative = runtime_context(tool)
    ticket = begin_runtime(root, tool, host, scope, relative)
    context = resolve_owned(root, relative)
    context.mkdir(parents=True, exist_ok=False)
    for name, data in selected.items():
        write_owned(root, relative + '/' + name, data)
    _skills_check(context)
    seal_runtime(root, tool, host, scope, relative, ticket)
    from .lifecycle import write_runtime_receipt
    write_runtime_receipt(root, tool, host, scope,
                  {'schema_version': 1, 'host': host, 'scope': scope, 'root': str(root),
                   'id': tool['id'], 'version': tool['version'], 'artifact': tool['sha256'],
                   'context': relative, 'owned_files': _runtime_hashes(root, relative)})
    record.update(installed=True, smoke_tested=True, reason='complete instruction runtime verified; native behavior is separate',
                  evidence=['fifteen complete skill trees and license', 'private instruction inventory'])


def _python_probe_argv(tool, context):
    bindir = context / 'venv' / ('Scripts' if os.name == 'nt' else 'bin')
    python = bindir / ('python.exe' if os.name == 'nt' else 'python')
    argv = [part.replace('{tool_bin}', str(bindir)).replace('{tool_python}', str(python))
            .replace('{tool_root}', str(context)) for part in tool['probe']['argv']]
    if os.name == 'nt' and Path(argv[0]).suffix.lower() != '.exe':
        argv[0] += '.exe'
    if tool['probe']['argv'][0] == '{tool_python}' and '-B' not in argv[1:]:
        # Isolated Python ignores PYTHONDONTWRITEBYTECODE from the environment.
        argv.insert(1, '-B')
    return argv


def _python_install(root, tool, artifact, runner, record, host, scope):
    import sys
    import venv
    lock = tool['install']['lock']
    lock_bytes = resolve_owned(DIST, lock['path']).read_bytes()
    if _digest(lock_bytes) != lock['sha256']:
        raise ValueError('requirements lock checksum mismatch')
    wheels = {}
    for payload in tool['install'].get('wheels', []):
        path = payload['path']
        if not path.startswith('toolkit/wheels/') or not path.endswith('.whl') or Path(path).name in wheels:
            raise ValueError('invalid bundled wheel identity')
        data = resolve_owned(DIST, path).read_bytes()
        if _digest(data) != payload['sha256']:
            raise ValueError('bundled wheel checksum mismatch')
        wheels[Path(path).name] = data
    from .lifecycle import runtime_context
    relative = runtime_context(tool)
    context = resolve_owned(root, relative)
    from .lifecycle import begin_runtime, seal_runtime
    ticket = begin_runtime(root, tool, host, scope, relative)
    context.mkdir(parents=True, exist_ok=False)
    write_owned(root, relative + '/artifact', artifact)
    write_owned(root, relative + '/requirements.lock', lock_bytes)
    for name, data in wheels.items():
        write_owned(root, relative + '/wheels/' + name, data)
    venv.create(context / 'venv', with_pip=False, symlinks=False)
    bindir = context / 'venv' / ('Scripts' if os.name == 'nt' else 'bin')
    python = bindir / ('python.exe' if os.name == 'nt' else 'python')
    env = {'PATH': str(bindir), 'HOME': str(context), 'USERPROFILE': str(context),
           'PIP_CONFIG_FILE': os.devnull, 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
           'PIP_NO_INPUT': '1', 'PIP_NO_CACHE_DIR': '1', 'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    env.update(PROBE_ENV)
    if wheels:
        env['PIP_FIND_LINKS'] = str(context / 'wheels')
    if os.name == 'nt':
        for key in ('SYSTEMROOT', 'WINDIR'):
            if key in os.environ:
                env[key] = os.environ[key]
    bootstrap = runner.run([str(python), '-m', 'ensurepip'], cwd=context, env=env, timeout=120)
    if bootstrap.returncode:
        record['status'] = 'failed'
        record['reason'] = 'environment bootstrap failed'
        return
    argv = [str(python), '-m', 'pip', 'install', '--quiet', '--progress-bar', 'off', '--no-compile',
            '--require-hashes', '--only-binary=:all:', '-r', str(context / 'requirements.lock')]
    result = runner.run(argv, cwd=context, env=env, timeout=600)
    if result.returncode:
        record['status'] = 'failed'
        record['reason'] = 'install command failed'
    else:
        probe_argv = _python_probe_argv(tool, context)
        probe = Path(probe_argv[0])
        if not probe.is_file():
            record['reason'] = 'installed executable not found'
            return
        output = runner.run(probe_argv, cwd=context, env=env, timeout=PROBE_TIMEOUT)
        if output.returncode or tool['version'] not in output.stdout:
            record['reason'] = 'version probe failed'
            return
        files = _runtime_hashes(root, relative)
        receipt_path = resolve_owned(root, f'.agentic-sdlc/runtime-receipts/{host}/{tool["id"]}.json')
        receipt = {'schema_version': 1, 'host': host, 'scope': scope, 'root': str(root),
                   'id': tool['id'], 'version': tool['version'], 'artifact': tool['sha256'],
                   'lock': lock['sha256'], 'context': relative, 'files': files,
                   'acquired': True, 'installed': True, 'smoke_tested': True,
                   'configured': False, 'project_integrated': False, 'status': 'blocked',
                   'reason': 'configuration and integration need setup', 'owned_files': files,
                   'evidence': ['verified artifact and lock', 'version probe']}
        seal_runtime(root, tool, host, scope, relative, ticket)
        from .lifecycle import write_runtime_receipt
        write_runtime_receipt(root, tool, host, scope, receipt)
        record.update(installed=True, smoke_tested=True, reason='configuration and integration need setup')


def _runtime_hashes(root, relative):
    from .lifecycle import _snapshot
    return {relative + '/' + name: item['sha256']
            for name, item in _snapshot(root, relative).items() if item['kind'] == 'file'}


def _resume_python(root, tool, host, scope, runner, record):
    from .lifecycle import runtime_context, runtime_witness, probe_runtime, prior_runtime, recover_pending_runtime
    context = resolve_owned(root, runtime_context(tool))
    receipt = resolve_owned(root, f'.agentic-sdlc/runtime-receipts/{host}/{tool["id"]}.json')
    preserved = recover_pending_runtime(root, tool, host, scope)
    if preserved is not None:
        if preserved:
            record.setdefault('preserved', []).append(preserved)
        record['evidence'].append('interrupted runtime preserved; clean verified restart')
        return False
    if context.exists():
        try:
            probe_runtime(root, tool, host, scope, runner, record)
        except (OSError, ValueError, KeyError, TypeError):
            record['reason'] = 'existing runtime requires independent authentication before resume'
            return True
        return True
    if receipt.exists() and not prior_runtime(root, tool, host, scope):
        record['reason'] = 'existing runtime receipt requires independent authentication before resume'
        return True
    return False


def install(catalog, root, runner, *, host='codex', scope='project'):
    return _operate(catalog, root, host, scope, True, runner)


def diagnose(catalog, root, runner, *, host='codex', scope='project'):
    return _operate(catalog, root, host, scope, False, runner)


from .lifecycle import update, rollback, uninstall


class _HTTPSRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith('https://'):
            raise ValueError('insecure redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class LocalRunner:
    """Run local commands without a shell or inherited environment; process groups are not a sandbox."""
    def fetch(self, url, timeout):
        from urllib.request import ProxyHandler, build_opener
        if not url.startswith('https://'):
            raise ValueError('HTTPS required')
        with build_opener(ProxyHandler({}), _HTTPSRedirect()).open(url, timeout=timeout) as response:
            content = response.read(256 * 1024 * 1024 + 1)
        if len(content) > 256 * 1024 * 1024:
            raise ValueError('artifact exceeds 256 MiB')
        return content

    def run(self, argv, *, cwd, env, timeout):
        import signal
        import threading
        if not argv or Path(argv[0]).suffix.lower() in ('.cmd', '.bat', '.ps1'):
            raise ValueError('unsafe executable')
        def clean(data):
            text = data.decode('utf-8', errors='replace') if isinstance(data, bytes) else data
            text = re.sub(r'(?i)(token|password|secret|api[_-]?key)(\s*[:=]\s*)[^\s,;]+', r'\1\2[redacted]', text)
            return re.sub(r'(?i)(bearer\s+)\S+', r'\1[redacted]', text)
        if os.name == 'nt':
            from .process import run
            result = run(argv, cwd=cwd, env=env, timeout=timeout)
            return subprocess.CompletedProcess(argv, result.returncode, clean(result.stdout), clean(result.stderr))
        if os.name != 'posix':
            raise RuntimeError('safe process isolation unavailable')
        process = subprocess.Popen(argv, cwd=cwd, env=env, shell=False,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        output = [bytearray(), bytearray()]
        guard = threading.Lock()
        total = [0]
        overflow = threading.Event()
        def terminate():
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        def drain(stream, buffer):
            try:
                while chunk := stream.read(4096):
                    with guard:
                        total[0] += len(chunk)
                        buffer.extend(chunk[:max(0, 4096 - len(buffer))])
                        if total[0] > 65536:
                            overflow.set()
                            terminate()
            finally:
                stream.close()
        readers = [threading.Thread(target=drain, args=(stream, buffer), daemon=True)
                   for stream, buffer in zip((process.stdout, process.stderr), output)]
        for reader in readers:
            reader.start()
        try:
            process.wait(timeout=timeout)
        except BaseException:
            terminate()
            process.wait()
            raise
        finally:
            terminate()
            for reader in readers:
                reader.join()
        if overflow.is_set():
            raise RuntimeError('command output limit exceeded')
        return subprocess.CompletedProcess(argv, process.returncode, clean(output[0]), clean(output[1]))
