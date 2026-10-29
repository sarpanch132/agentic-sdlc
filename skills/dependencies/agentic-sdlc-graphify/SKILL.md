---
name: agentic-sdlc-graphify
description: Supporting graphify helper only for an active user-invoked SDLC workflow when needed.
---

## SDLC distribution adaptation (2026-10-28)

Use only within an active user-invoked SDLC workflow when this helper is needed. The active coordinator may invoke this helper without a separate user invocation. If no user-invoked SDLC workflow is active, do not run this helper or activate SDLC; return control without performing its steps. Inherit the host model, established permissions and existing MCP. The canonical coordinator and user approvals govern conflicts. Missing user requirements must be asked, never guessed. Ponytail minimality never bypasses brainstorming design approval, validation, security or explicit requirements.

Resolve bundled paths from this installed skill directory, not the current project, a personal home, or an upstream checkout. Use the host's available Python executable (Python 3.11+); on Windows use PowerShell `&` with quoted paths, not Bash snippets. Shell examples below are reference syntax, not permission to execute blindly. Companion assets are bundled, not activated. Do not start services, hooks, watchers, installs, background jobs, inline MCP servers or external providers automatically. References to unbundled skills are optional upstream context; disclose unavailable capabilities and return to the coordinator instead of acquiring them.

Graphify: use project-local code-only extraction and local graph queries. A Gemini/API key never authorizes an external service, model call or upload. Do not read provider keys. Obtain separate explicit authority before any external extraction; otherwise keep the local fallback or report a blocker. Never auto-install Graphify on first use; the installer must provision its separately pinned runtime or report blocked. Preserve project data locally.

# Local Graphify SDLC helper

This adapted entry replaces upstream install, automatic provider detection, shell orchestration, settings changes and watcher flows. Supporting reference documents are retained as upstream context; their service/hook/install instructions require separate authority and do not override this entry.

1. Check a relevant project-local `graphify-out/graph.json`; query it before broad source exploration. Skip extraction for an empty or unrelated corpus.
2. Verify the installer-recorded Graphify runtime and interpreter. Missing or incompatible runtime is a blocker; do not install on first use.
3. For cross-file exploration, use local code-only structural extraction with the runtime Python `graphify.extract.collect_files` and `graphify.extract.extract`. Inspect the installed signatures before execution; runtime versions differ. Write graph output within the project and preserve existing data. Never invoke semantic extraction, backend auto-detection or provider APIs as part of this helper.
4. Query using `graphify query "question" --graph "<project>/graphify-out/graph.json"`; verify underlying source before editing. Use focused native source searches if Graphify fails or cannot represent the relationship, disclosing the limitation. Refresh affected local graph evidence after relevant changes.
5. Read bundled `references/query.md` for graph query concepts and `references/extraction-spec.md` for extraction concepts only when needed. No automatic hooks, services, cloud, global graph, configuration edits or additional helper fan-out.
