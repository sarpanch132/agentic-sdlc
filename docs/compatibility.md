> Current implementation and verification status: [runtime status](runtime-status.md), updated 2026-10-29. Earlier observations below are historical and do not describe the latest runtime gates. Publication status is in README; earlier deferral notes below are historical.

# Compatibility evidence — 2026-10-28

Targets are Windows, macOS and Linux, with native Claude Code, Cursor and Codex adapters. Windows temporary-project asset copying has passed for all three layouts. No combination has passed complete native workflow execution or full runtime installation. Registry wheel metadata and upstream instructions are candidate support evidence, not local compatibility results.

Task 2 bounded probes on 2026-10-28 confirmed installed CLI version/help only: Claude Code2.1.247 and Codex0.163.0-alpha.11.2. [Exact commands and exits](evidence/2026-10-28-task-2/commands.json), [observations](evidence/2026-10-28-task-2/observations.json), and [assessment](evidence/2026-10-28-task-2/assessment.md) distinguish these passes from asset loading, bounded delegation and MCP metadata, all not-run. Candidate host schemas are recorded in `tests/fixtures/host-contracts.json`; structural checks are not host behavior proof. The chief ruling is **go safe source; no-go full runtime/release**: safe implementation may proceed after review, while blocked runtime and lifecycle scripts remain unexecuted. No complete supported invocation route was proved for a constrained tool.

| OS | Claude Code | Cursor | Codex |
|---|---|---|---|
| Windows AMD64 | CLI2.1.247: native registration observed; provider retries prevented behavior verification | Asset layout tested; native client unavailable | CLI0.163.0-alpha.11.2: partial response; skill read blocked under test policy, loading unverified |
| macOS x64/arm64 | Not tested | Not tested | Not tested |
| Linux x64/arm64 | Not tested | Not tested | Not tested |

Controller preflight reports Python3.12.14, uv0.12.6, Node24.18.0; Docker, Cursor and agent were not on PATH. WSL executable presence does not prove a working distro/runtime. MetaGPT requires an additional Python3.11 environment. Docker/WSL prerequisites may be reported blocked until available. These are setup prerequisites, not evidence that the complete requirement is impossible. Record exact host versions and architectures when later probes run.

## Current official host contracts

- [Claude Code skills](https://code.claude.com/docs/en/skills): user/project skill directories with SKILL.md and support assets. `disable-model-invocation: true` provides explicit invocation. [Subagents](https://code.claude.com/docs/en/sub-agents) use Markdown/frontmatter under `.claude/agents` or user scope, with tool and permission fields. Existing MCP string references reuse parent connections; inline MCP has separate trust behavior. Do not add inline servers or bypass permissions. Current web documentation describes newer capabilities than installed2.1.247; nesting and permission details require version-specific proof.
- [Cursor skills](https://cursor.com/docs/skills): `disable-model-invocation: true` limits inclusion to explicit `/skill-name`. [Subagents](https://cursor.com/docs/subagents) use `.cursor/agents/*.md` or user scope, with name, description, model=inherit and optional readonly. Its current FAQ explicitly states local subagents inherit parent tools including configured MCP; cloud subagents instead use team-configured cloud MCP. [MCP approval](https://cursor.com/docs/mcp) follows host Run Mode and asks by default. Conditional descriptions must not activate SDLC for unrelated chats; never bypass host approvals. These documented mappings remain untested in an installed Cursor client here.
- [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents): standalone TOML agents require name, description and developer_instructions; parent permissions/provider/MCP remain controlling. [Skills](https://learn.chatgpt.com/docs/build-skills) documents `agents/openai.yaml` with `policy.allow_implicit_invocation: false`; explicit `$skill-name` invocation remains available. Use that native policy for the coordinator rather than Claude frontmatter. Current official mapping is established; installed-client parsing and behavior are still untested.

All defaults inherit the host model and preserve user/project trust controls. No automatic MCP installation, startup hook, global always-active instruction, watcher or background service is part of the approved adapter. If delegation is unavailable, report it and use the documented foreground fallback. Official docs establish candidate schemas only; syntactic parsing and actual native discovery are separate later checks.

## Later native smoke

An immutable asset snapshot and separate synthetic projects were used. Claude listed the skill but produced provider retries before its deadline. Codex returned one relevant question and disclosed inability to read the required skill; it also reported pre-existing global skill-budget overflow. Neither profile was a clean-device test. No complete workflow read, helper delegation, MCP operation or phase-runtime integration was proved. Current real catalog gates block all 16 tools plus Graphify; operational runtime diagnostics remain incomplete.
