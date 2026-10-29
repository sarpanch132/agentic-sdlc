# Installation guide

**Experimental. Full automatic installation of every phase tool remains incomplete.** Consult [runtime status](docs/runtime-status.md). Public source: [sarpanch132/agentic-sdlc](https://github.com/sarpanch132/agentic-sdlc).

## Assistant installation from a repository link

Give a terminal-capable coding assistant this request:

> Install https://github.com/sarpanch132/agentic-sdlc for this coding assistant.

The assistant should inspect this guide and source at a reviewed, pinned revision, identify the actual host and OS, and check Python and relevant native runtime prerequisites. Use ordinary host permissions, preserve existing files and settings, and never pipe a remote download directly into a shell. A chat-only app cannot install local software. A URL alone is not an execution instruction.

Select the actual host: `claude`, `cursor` or `codex`. Use user scope by default; use project scope only for an explicitly selected existing project. Do not guess the host when it cannot be detected.

From the inspected source directory on Windows PowerShell:

```powershell
python --version
python -m installer install --host codex
python -m installer doctor --host codex
```

For project scope append `--scope project --project 'C:\path to\project'` to each command. Replace `codex` with the detected host. On macOS/Linux the command name is normally `python3`, but those platforms have not been validated.

The installer installs enabled recipes automatically and reports disabled or unavailable recipes. Python recipes require the exact interpreter recorded in their lock, currently Python 3.12 for enabled Python tools. Node recipes need a compatible existing native Node/npm. Helicone needs Docker and remains unverified. Provider credentials, services, MCP connections and project integrations are not configured automatically.

Read the JSON fields `status`, `reason`, `installed`, `smoke_tested`, `configured` and `project_integrated`. Exit 0 means complete; exit 1 means incomplete/blocked/failed, and exit 2 is invalid command-line usage. The current full bundle returns exit 1 even when some tools and workflow assets install successfully. Do not report that as full success.

## On-demand use

Refresh skill discovery through the installed application's normal controls if required. Invoke `/agentic-sdlc <request>` in Claude Code/Cursor or `$agentic-sdlc <request>` in Codex. Native end-to-end loading and delegation are not yet proven for all three applications.

## Resume, diagnose, update, rollback and uninstall

Repeat `install` to resume only independently authenticated runtimes. An incomplete environment is preserved in an `.interrupted-*` directory and rebuilt from verified inputs. Unknown or modified verified environments are blocked before execution.

Use the same host/scope/project arguments throughout:

```powershell
python -m installer doctor --host codex
python -m installer update --host codex
python -m installer rollback --host codex
python -m installer uninstall --host codex
```

Update uses the current inspected checkout as the update source; it does not download an arbitrary latest version. Obtain and review the desired source revision first. Update validates enabled runtimes before committing assets; rollback requires an existing previous generation and checks its runtime inventory. Read `assets_status` separately from overall bundle readiness.

Uninstall preserves modified/unknown files, interrupted environments and shared Docker images, reporting their paths. An incomplete cleanup returns `blocked`. Keep `~/.agentic-sdlc-state` for ownership verification; do not copy private state between devices or trust a project receipt as execution authority. Native process cleanup is tested on Windows; these controls are not a security sandbox.

End-to-end assistant-driven installation, clean-device native host behavior and macOS/Linux compatibility remain unverified. This guide authorizes no publication, service startup, credential access or unattended jobs.

## Configure tools after discovery

Keep the inspected source checkout available. Its location is recorded as a hint in the installed coordinator's `workflow/installer-location.json`. Confirm the project brief, select the relevant tools, then run from that checkout:

```powershell
python -m installer configure --host codex --scope project --project 'C:\path to\project' --tools superpowers openspec graphify --source src
python -m installer project-doctor --host codex --scope project --project 'C:\path to\project'
```

This example assumes those runtimes were installed project-wide. If installed user-wide, omit `--scope project` but keep `--project`. Replace the host and selected tools with the actual choices. `--tools` is required; choose either `spec-kit` or `openspec`. Graphify's `--source` must identify a relative application source directory or code file, not a runtime/cache/private-state directory.

Configuration is local-only: native specification scaffolding, code-only graphs, local evaluation fixtures, model storage, SQLite tracking and in-memory tracing. It starts no server and configures no remote provider. `project-doctor` repeats the local checks and may add local check records or refresh graphs. Exit 0 means these selected local checks passed, not that all seventeen runtimes or the application are production-ready.

Generated files live under `.agentic-sdlc/project-tools/`. Protect their local state from accidental public commits. Unknown or modified settings are preserved and blocked; keep private ownership state for authenticated reuse. These files and data are retained as project outputs when runtimes are uninstalled. Tool selection can be expanded; implicit removal or switching an established specification workflow is blocked.

See [the project setup reference](skills/agentic-sdlc/references/project-setup.md) for each profile and the provider/model, credential-reference, acceptance-data and deployment questions to ask only when applicable.
