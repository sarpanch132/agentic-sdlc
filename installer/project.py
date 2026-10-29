"""Selective project-local configuration using independently authenticated runtimes."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from . import engine, lifecycle, state
from .files import resolve_owned, write_owned
from .profiles import profile_files

PREFIX = '.agentic-sdlc/project-tools'
SUPPORTED = {'superpowers', 'spec-kit', 'openspec', 'promptfoo', 'deepeval',
             'agno', 'bentoml', 'mlflow', 'openllmetry', 'graphify'}


def _json(value):
    return (json.dumps(value, indent=2) + '\n').encode()


def _store(root, project, host, scope):
    base = state.store(lifecycle._private_root(), root, scope)
    identity = hashlib.sha256(_json([str(project), lifecycle._identity(root, host, scope)])).hexdigest()
    return base, f'project-{identity}.json', identity


def _validate_record(value, identity, root, project, host, scope):
    if (not isinstance(value, dict) or set(value) != {'identity', 'root', 'project', 'host', 'scope',
            'tools', 'source', 'files', 'pending', 'checked'}
            or any(value.get(k) != v for k, v in {'identity': identity, 'root': str(root),
                   'project': str(project), 'host': host, 'scope': scope}.items())
            or not isinstance(value['files'], dict) or not isinstance(value['checked'], dict)
            or not isinstance(value['tools'], list) or not set(value['tools']) <= SUPPORTED
            or value['pending'] is not None and not isinstance(value['pending'], dict)):
        raise ValueError('invalid private project configuration record')
    for mapping in (value['files'], value['pending'] or {}):
        for path, digest in mapping.items():
            if not path.startswith(PREFIX + '/') or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                raise ValueError('invalid project configuration ownership')
            resolve_owned(project, path)


def _unchanged(project, record):
    for path, before in record['files'].items():
        file = resolve_owned(project, path)
        allowed = {before, (record['pending'] or {}).get(path)}
        if not file.is_file() or file.stat().st_nlink != 1 or engine._digest(file.read_bytes()) not in allowed:
            raise ValueError('project configuration is missing or modified: ' + path)


def _environment(home):
    home.mkdir(parents=True, exist_ok=True)
    env = dict(engine.PROBE_ENV, HOME=str(home), USERPROFILE=str(home),
               APPDATA=str(home), LOCALAPPDATA=str(home), PYTHONNOUSERSITE='1',
               PYTHONDONTWRITEBYTECODE='1', PIP_CONFIG_FILE=os.devnull,
               TRACELOOP_TRACE_CONTENT='false', TRACELOOP_METRICS_ENABLED='false',
               TRACELOOP_LOGGING_ENABLED='false', TOKENIZERS_PARALLELISM='false')
    for key in ('SYSTEMROOT', 'WINDIR'):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _command(tool, context, root, runner, scope):
    if tool['kind'] == 'python':
        binary = context / 'venv' / ('Scripts' if os.name == 'nt' else 'bin')
        python = binary / ('python.exe' if os.name == 'nt' else 'python')
        if tool['id'] in ('spec-kit', 'graphify'):
            name = 'specify' if tool['id'] == 'spec-kit' else 'graphify'
            return [str(binary / (name + ('.exe' if os.name == 'nt' else '')))]
        return [str(python), '-B', '-I']
    node, _ = engine._node_prerequisites(root, tool, runner, scope)
    lock = json.loads((context / 'package-lock.json').read_text(encoding='utf-8'))
    package = next(iter(lock['packages']['']['dependencies']))
    binary = tool['probe']['argv'][0].removeprefix('{tool_bin}/')
    entry = lock['packages']['node_modules/' + package]['bin'][binary]
    executable = resolve_owned(context, 'node_modules/' + package + '/' + entry)
    return [str(node), str(executable)]


def _check(tool, context, root, project, runner, scope, source):
    identity = tool['id']
    folder = resolve_owned(project, PREFIX + '/' + identity)
    data = resolve_owned(project, PREFIX + '/' + identity + '/state')
    env = _environment(data)
    lifecycle._snapshot(project, PREFIX + '/' + identity)
    if identity == 'superpowers':
        engine._skills_check(context)
        return
    command = _command(tool, context, root, runner, scope)
    env['PATH'] = str(Path(command[0]).parent)
    if identity == 'mlflow':
        env.update(MLFLOW_TRACKING_URI='sqlite:///' + (data / 'tracking.db').as_posix(),
                   MLFLOW_DEFAULT_ARTIFACT_ROOT=(data / 'artifacts').as_uri())
    elif identity == 'bentoml':
        env['BENTOML_HOME'] = str(data)
    elif identity == 'openllmetry':
        env['OTEL_SDK_DISABLED'] = 'false'  # Explicit in-memory exporter only.
    def run(args, cwd=folder):
        result = runner.run(command + args, cwd=cwd, env=env, timeout=120)
        if result.returncode:
            raise ValueError(identity + ' local configuration check failed (exit ' + str(result.returncode) + ')')
        return result
    if identity == 'graphify':
        run(['extract', str(resolve_owned(project, source)), '--code-only',
             '--out', str(data)], cwd=data)
        graph = resolve_owned(data, 'graphify-out/graph.json')
        if not graph.is_file() or not json.loads(graph.read_text(encoding='utf-8')).get('nodes'):
            raise ValueError('Graphify did not produce a nonempty local source graph')
    elif identity == 'promptfoo':
        run(['eval', '--config', str(folder / 'promptfooconfig.json'), '--output',
             str(data / 'results.json'), '--no-cache'])
        results = json.loads((data / 'results.json').read_text(encoding='utf-8'))
        stats = results.get('results', {}).get('stats', {})
        if stats.get('successes') != 1 or stats.get('failures') != 0 or stats.get('errors', 0) != 0:
            raise ValueError('Promptfoo local echo evaluation did not pass')
    elif identity in ('spec-kit', 'openspec'):
        workspace = data / 'specification'
        marker = workspace / ('.specify' if identity == 'spec-kit' else 'openspec')
        if not marker.is_dir():
            if workspace.exists():
                raise ValueError('incomplete specification workspace preserved; inspect before retry')
            if identity == 'spec-kit':
                run(['init', str(workspace), '--integration', 'generic', '--integration-options',
                     '--commands-dir .sdlc-commands', '--script', 'py', '--ignore-agent-tools', '--non-interactive'])
            else:
                run(['init', str(workspace), '--tools', 'none', '--profile', 'core',
                     '--no-animation', '--no-copilot-cloud'])
        required = (['integration.json', 'templates/spec-template.md', 'templates/plan-template.md',
                     'templates/tasks-template.md'] if identity == 'spec-kit' else ['config.yaml'])
        if not marker.is_dir() or any(not (marker / path).is_file() or not (marker / path).stat().st_size for path in required):
            raise ValueError('specification framework did not create its project assets')
        if identity == 'openspec':
            run(['list', '--json'], cwd=workspace)
    else:
        result = run([str(folder / 'check.py')])
        if 'SDLC_LOCAL_CONFIGURATION_OK' not in result.stdout:
            raise ValueError(identity + ' local configuration marker missing')


def configure(catalog, root, runner=None, *, project=None, tools=(), source=None,
              host='codex', scope='project', check_only=False):
    root = Path(os.path.abspath(root))
    project = Path(os.path.abspath(project if project is not None else root))
    records = []
    try:
        if host not in engine.HOSTS or scope not in ('project', 'user') or not root.is_dir() or not project.is_dir():
            raise ValueError('valid existing runtime root, project, host and scope required')
        if {'spec-kit', 'openspec'} <= set(tools):
            raise ValueError('choose one specification workflow: spec-kit or openspec')
        if 'graphify' in tools and not source:
            raise ValueError('Graphify requires an explicit project-relative source directory or code file')
        with engine._lock(root):
            base, name, identity = _store(root, project, host, scope)
            prior = state.read(base, name)
            if prior is not None:
                _validate_record(prior, identity, root, project, host, scope)
                _unchanged(project, prior)
            if check_only:
                if not prior or prior['pending']:
                    raise ValueError('project configuration missing or interrupted; repeat configure first')
                tools, source = prior['tools'], prior['source']
            tools = sorted(set(tools))
            if not tools or not set(tools) <= SUPPORTED:
                raise ValueError('select one or more enabled tools explicitly after project discovery')
            if prior and not set(prior['tools']) <= set(tools):
                raise ValueError('preserve prior selections; adding tools is supported, implicit removal is not')
            if 'graphify' in tools:
                if not isinstance(source, str) or any(part in {'.agentic-sdlc', '.git', 'node_modules', 'venv', '.venv'} for part in source.split('/')):
                    raise ValueError('Graphify source must be an explicit application source path')
                if not resolve_owned(project, source).exists():
                    raise ValueError('selected Graphify source does not exist')
            runner = runner or engine.LocalRunner()
            selected, bindings = {}, {}
            available = {tool['id']: tool for tool in catalog}
            for tool_id in tools:
                records.append({'tool_id': tool_id, 'configured': False, 'project_integrated': False,
                                'configuration_mode': 'local-only', 'status': 'blocked'})
                tool = available.get(tool_id)
                if not tool or not tool['active'] or tool['install']['status'] != 'ready':
                    raise ValueError(tool_id + ' runtime is not enabled')
                tool = lifecycle.active_runtime_tool(root, tool, host, scope)
                witness = lifecycle.runtime_witness(root, tool, host, scope)
                selected[tool_id] = (tool, resolve_owned(root, witness['context']))
                bindings[tool_id] = witness['identity']
            manifest = json.loads((engine.DIST / 'toolkit/manifest.json').read_text(encoding='utf-8'))
            files = {PREFIX + '/routes.json': _json({'selected': tools, 'phases': manifest['phase_tools'],
                      'fallbacks': manifest['phase_fallbacks'], 'runtime_root': str(root),
                      'installer_source': str(engine.DIST), 'mode': 'local-only'})}
            for tool_id, (_, context) in selected.items():
                for relative, data in profile_files(tool_id).items():
                    if relative == 'config.json':
                        settings = json.loads(data)
                        settings.update(runtime_context=str(context), state_directory='state')
                        if tool_id == 'graphify': settings['source'] = source
                        if tool_id == 'superpowers': settings['instruction_root'] = str(context / 'skills')
                        data = _json(settings)
                    files[PREFIX + '/' + tool_id + '/' + relative] = data
            expected = {path: engine._digest(data) for path, data in files.items()}
            if check_only:
                if expected != prior['files'] or bindings != prior['checked']:
                    raise ValueError('project configuration or runtime generation changed; reconfigure selected tools')
            else:
                old = prior['files'] if prior else {}
                pending = prior['pending'] if prior else {}
                for tool_id in tools:
                    if (not prior or tool_id not in prior['tools']) and resolve_owned(project, PREFIX + '/' + tool_id).exists():
                        raise ValueError('unknown project tooling directory preserved: ' + tool_id)
                for path in files:
                    target = resolve_owned(project, path)
                    if target.exists() and path not in old and path not in (pending or {}):
                        raise ValueError('unknown project configuration preserved: ' + path)
                value = {'identity': identity, 'root': str(root), 'project': str(project), 'host': host,
                         'scope': scope, 'tools': tools, 'source': source, 'files': old,
                         'pending': expected, 'checked': {}}
                state.write(base, name, value)
                for path, data in files.items():
                    target = resolve_owned(project, path)
                    if not target.exists() or engine._digest(target.read_bytes()) != expected[path]:
                        write_owned(project, path, data, old.get(path))
                value.update(files=expected, pending=None)
                state.write(base, name, value)
            checked = {}
            for record in records:
                tool, context = selected[record['tool_id']]
                try:
                    _unchanged(project, prior if check_only else value)
                    _check(tool, context, root, project, runner, scope, source)
                    lifecycle.runtime_witness(root, tool, host, scope)
                    checked[record['tool_id']] = bindings[record['tool_id']]
                    record.update(configured=True, status='complete',
                                  reason='local tooling check passed; application acceptance and provider integration are separate')
                except (ValueError, OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
                    record.update(reason=str(exc))
            value = prior if check_only else value
            value['checked'] = checked
            state.write(base, name, value)
        complete = all(record['configured'] for record in records)
        return {'status': 'complete' if complete else 'blocked', 'mode': 'local-only', 'tools': records,
                'reason': 'selected local tooling configured and checked' if complete else 'some local configuration checks failed',
                'project_integrated': False, 'project_outputs': PREFIX,
                'requires_for_application_integration': ['project acceptance tests and data', 'provider/model and approved credential reference when required', 'deployment target when required']}
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired, RuntimeError) as exc:
        return {'status': 'blocked', 'reason': str(exc), 'tools': records, 'project_integrated': False}


def apply_status(catalog, root, project, host, scope, records):
    """Reflect prior verified local configuration without executing project code."""
    try:
        base, name, identity = _store(root, project, host, scope)
        value = state.read(base, name)
        if value is None:
            return
        _validate_record(value, identity, root, project, host, scope)
        _unchanged(project, value)
        if value['pending']:
            return
        available = {tool['id']: tool for tool in catalog}
        for record in records:
            tool_id = record['tool_id']
            if not record['installed'] or not record['smoke_tested'] or tool_id not in value['checked']:
                continue
            tool = lifecycle.active_runtime_tool(root, available[tool_id], host, scope)
            if lifecycle._runtime_identity(root, tool, host, scope) == value['checked'][tool_id]:
                record.update(configured=True, configuration_mode='local-only', project_integrated=False,
                              reason='local tooling configured; application/provider integration remains separate')
    except (ValueError, OSError, KeyError, TypeError):
        return
