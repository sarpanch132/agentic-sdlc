# Agentic SDLC

An on-demand engineering coordinator for Claude Code, Cursor and Codex. It asks for missing requirements, discovers available capabilities, and calls skills, specialists and MCP tools only when needed.

**Experimental: the complete 16-tool plus Graphify automatic bundle is not finished.** See [runtime status](docs/runtime-status.md) for enabled recipes, actual checks and remaining blockers. Source is published at [sarpanch132/agentic-sdlc](https://github.com/sarpanch132/agentic-sdlc).

## Installation

A terminal-capable assistant can follow [INSTALL.md](INSTALL.md). To install, ask:

> Install https://github.com/sarpanch132/agentic-sdlc for this coding assistant.

From an inspected source checkout on Windows:

```powershell
python -m installer install --host codex --scope project --project 'C:\path to\project'
python -m installer doctor --host codex --scope project --project 'C:\path to\project'
```

Select `claude`, `cursor` or `codex` explicitly. User scope is the default; project scope requires an existing directory. The installer needs Python; current verified Python recipes use CPython 3.12. Native Node/npm and Docker are prerequisites for their respective recipes. The installer does not provision these system runtimes.

Invoke `/agentic-sdlc <request>` in Claude Code/Cursor or `$agentic-sdlc <request>` in Codex, using the skill picker if necessary. Complete native host behavior remains unverified.

## Lifecycle

`install`, `doctor`, `update`, `rollback` and `uninstall` are implemented. Use the same host, scope and project arguments for every operation. Recipes use isolated environments and verified artifacts/locks. Independently protected local state authenticates runtime contents before resume or execution. Unknown existing environments are rejected; interrupted environments are preserved before rebuilding.

Updates validate enabled runtimes before committing an asset generation; rollback selects the previous verified generation. Uninstall removes known unchanged files and preserves modified, unknown and shared resources. Keep the private ownership state at `~/.agentic-sdlc-state`; deleting it prevents authenticated cleanup or resume. These integrity checks are not a filesystem or network sandbox.

Windows native process-tree cleanup is implemented and tested. macOS/Linux execution and complete native application workflows are unverified. Exit 1 and JSON `blocked`/`failed` must be reported honestly: installation, smoke checks, provider configuration and project integration are separate fields. The complete bundle currently remains blocked.

Original code is MIT. Bundled third-party components retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Configure selected project tools

After confirming the project brief, select only the tools it needs. From the retained, inspected source checkout:

```powershell
python -m installer configure --host codex --scope project --project 'C:\path to\project' --tools superpowers openspec graphify --source src
python -m installer project-doctor --host codex --scope project --project 'C:\path to\project'
```

For user-wide runtimes omit `--scope project`, retaining `--project`. Setup authenticates the installed runtimes, writes project-local profiles and phase routes, and runs real local checks. Spec Kit and OpenSpec cannot be initialized together. Graphify needs an explicit relative source path. Modified files are preserved and blocked.

All ten enabled tools have local profiles. Successful setup reports `configured: true`, `configuration_mode: local-only`, and `project_integrated: false`; local tooling checks do not establish application acceptance or provider/deployment integration. Project outputs survive runtime uninstall. See [project setup and required inputs](skills/agentic-sdlc/references/project-setup.md).
