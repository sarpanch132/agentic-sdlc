"""Command-line entry point for bundled assets."""
import argparse
import json
from pathlib import Path
from .catalog import load_catalog
from .engine import DIST, diagnose, install, update, rollback, uninstall


def main():
    parser = argparse.ArgumentParser(prog='python -m installer')
    parser.add_argument('action', choices=('install', 'doctor', 'update', 'rollback', 'uninstall', 'configure', 'project-doctor'))
    parser.add_argument('--host', required=True, choices=('claude', 'cursor', 'codex'))
    parser.add_argument('--scope', choices=('user', 'project'), default='user')
    parser.add_argument('--project', type=Path)
    parser.add_argument('--tools', nargs='+', help='tools explicitly selected after project discovery')
    parser.add_argument('--source', help='project-relative source directory or code file for Graphify')
    args = parser.parse_args()
    project_action = args.action in ('configure', 'project-doctor')
    if project_action and args.project is None:
        parser.error('project configuration requires --project')
    if args.action == 'configure' and not args.tools:
        parser.error('configure requires explicit --tools selection')
    if args.action != 'configure' and (args.tools or args.source):
        parser.error('--tools and --source are only valid for configure')
    if args.scope == 'project' and args.project is None:
        parser.error('project scope requires --project')
    if args.scope == 'user' and args.project is not None and not project_action:
        parser.error('--project requires project scope')
    try:
        catalog = load_catalog(DIST / 'toolkit/manifest.json')
        root = args.project if args.scope == 'project' else Path.home()
        if project_action:
            from .project import configure
            result = configure(catalog, root, project=args.project, host=args.host, scope=args.scope,
                               tools=args.tools or (), source=args.source, check_only=args.action == 'project-doctor')
        elif args.action == 'uninstall':
            result = uninstall(root, host=args.host, scope=args.scope)
        else:
            action = {'install': install, 'doctor': diagnose, 'update': update, 'rollback': rollback}[args.action]
            result = action(catalog, root, None, host=args.host, scope=args.scope)
    except (ValueError, OSError) as exc:
        result = {'status': 'failed', 'reason': str(exc)}
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
