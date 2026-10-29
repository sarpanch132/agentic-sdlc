# Agentic SDLC: installable native agent toolkit

Date: 2026-10-28
Status: user-approved on 2026-10-28; written implementation plan and execution-method review remain required

## 1. Intent and agreed scope

Build a public GitHub distribution that users install into Claude Code, Cursor, or Codex, comparable in installation experience to the VoltAgent subagent repositories. It activates on demand and coordinates an SDLC workflow inside the existing coding application. It is not a separate hosted AI application or model service.

Confirmed decisions:

- Target Windows, macOS, and Linux. Publish an explicit tested host/OS matrix, not a universal compatibility claim.
- User-wide installation is the default; project-only installation is supported.
- The default installation includes all 16 distinct tools ranked in the supplied research PDF, including alternatives.
- Bundle brainstorming, Ponytail full mode, Graphify, and UI/UX Pro Max with their required supporting assets.
- Include requirements analyst, researcher, and architect specialists. Call specialists, skills, and MCP tools only when useful or explicitly requested.
- Ask for missing user requirements instead of guessing. Discover technical capabilities independently within existing access.
- Use the user's Agentic SDLC workflow to build this package, with proportional gates and evidence.

Approved scope: support ordinary software projects as well as AI applications. Model, RAG, and AI-specific evaluations apply only to relevant projects. This boundary was included in the written specification approved by the user.

## 2. Initial discovery experience

The coordinator reads the first request, supplied material, applicable project instructions, and narrowly relevant project context. It reflects what is understood, identifies essential missing information, and begins an adaptive conversation. It asks one focused question at a time; it does not present a mandatory questionnaire or repeat answered questions.

Ask the user when missing or ambiguous:

| Topic | Required understanding |
|---|---|
| Goal | Problem, desired outcome, and why it matters |
| Audience | Intended users, context, and principal journeys |
| Success | Observable acceptance criteria |
| Alternatives | Known competitors, current workarounds, and desired differentiation |
| Non-negotiables | Requirements that must not be compromised |
| Scope | First-version boundaries and explicit exclusions |
| UI/UX | Look, feel, branding, interaction, accessibility, and device requirements when relevant |
| Prototype | Whether a small prototype would help resolve an important uncertainty |
| References | Screenshots, sketches, images, or examples when these would clarify the request |
| Constraints | Budget, timeline, technology preferences, compatibility, privacy, and business rules |
| Authority | Intended workspace and actions outside already established authorization |

Users can speak plainly. Explain unfamiliar choices and offer recommendations, but do not convert a recommendation into a requirement without agreement. An unknown can remain explicitly undecided. Questions irrelevant to the task are marked not applicable; details needed only in a later phase can be deferred. A prototype is not built merely because the agent suggested one.

Discover independently: selected repository structure, stack, tests, existing documentation, project graph, installed tool readiness, exposed agents/skills/MCP tools, and configured permission boundaries. Do not inspect secret values or unrelated directories to discover capabilities. Confirm conflicting sources rather than silently choosing a requirement.

Phase 0 output: a user-confirmed brief separating confirmed requirements, unresolved questions, deferred decisions, scope, constraints, success criteria, and authority. A complete first request can proceed directly to confirming its brief. A vague request must not trigger product code or dependency installation for that project.

## 3. Native architecture and invocation

Use one canonical SDLC workflow and small host-specific adapters. The primary entry is a user-invoked workflow in the main session, so discovery remains interactive and the session can coordinate helpers. Ship native specialist definitions and a named SDLC agent where supported. Do not depend on a nested subagent being able to conduct the entire conversation.

Logical distribution components:

- Shared SDLC skill, phase guidance, briefing/checkpoint templates, and delegation rules.
- Claude Code, Cursor, and Codex integration assets using each tested host's current schema.
- Focused specialist definitions: requirements analyst, researcher, architect, implementer, QA reviewer, security reviewer, simplification reviewer, portability reviewer, and release reviewer. Roles are invoked proportionally, not all by default.
- Complete required skill assets, provenance, licenses, and a dependency inventory.
- Cross-platform installer, per-tool installation manifest, readiness diagnostics, resume/update/uninstall support.
- Automated contract tests, behavior scenarios, installation checks, and usage documentation.

The installer resolves user-wide or project-relative paths without personal absolute paths. Namespace package-owned components to avoid overriding generic existing agent names. Host adapters expose the coordinator explicitly; helper descriptions must not make the SDLC workflow activate for unrelated chats. Installation must not add an always-active global instruction, hook, watcher, or startup job.

The host's configured model is used by default. External tool runtimes may require their own provider setup; never imply that the host subscription automatically supplies API credentials to them. Configure MCP through supported host mechanisms only, preserving permission and trust checks. Existing MCP connections are used when relevant; no arbitrary marketplace servers are automatically added.

## 4. Delegation and economy

Ponytail full mode applies from the first invoked interaction. Prefer existing code, platform facilities, installed dependencies, small maintainable changes, and focused checks. Preserve security, validation, accessibility, and explicit requirements.

Graphify is installed with the package. At startup check for a relevant project-local graph; query it before broad exploration. With no meaningful corpus, skip extraction and continue discovery. Build a graph when cross-file exploration warrants it, defaulting to local code-only extraction. Verify underlying source before edits and refresh affected graph context after changes. Do not automatically upload documents or activate an external extraction provider because a key exists. No guaranteed token-saving percentage is claimed.

UI/UX Pro Max is preinstalled with search scripts, datasets, and references. Use it for interface discovery and design once enough requirements exist, preserving existing branding, accessibility, and the detected stack. Do not run design searches for backend-only tasks.

A delegation includes objective, bounded scope, relevant context, authority, expected evidence, and owned files when editing. The coordinator combines findings into one user conversation. Prefer narrow context over whole transcript copies. Only parallelize independent work. Prevent overlapping mutations; implementer and reviewer are different executions for independent review.

Default runtime limits: at most three concurrent helper executions or the lower host limit; one recovery retry for the same transient tool failure. Do not increase host limits automatically. Stop repeating a failed action and report its cause. If delegation is unavailable, disclose a sequential fallback; never label it independent review. If an approval gate requires independent review that cannot be obtained, keep that gate pending.

## 5. Lifecycle and phase tooling

Preserve nine distinct lifecycle stages. The PDF numbers both Governance and After Delivery as 7; use `after-delivery` as a distinct internal stage and display the source numbering note.

| Stage | Outcome | Installed candidates |
|---|---|---|
| 0 Planning | Confirmed problem brief, audience, scope, and failure risks | Superpowers, Spec Kit, OpenSpec |
| 1 Analysis | Requirements, feasibility, success criteria, constraints, authority | Superpowers, Spec Kit, OpenSpec |
| 2 Design | Reviewed architecture, contracts, cost assumptions, test strategy | MetaGPT, Spec Kit, OpenSpec |
| 3 Simulation/proof of value | Evidence for risky assumptions and a go/no-go decision | Promptfoo, DeepEval, Ragas |
| 4 Build | Small validated implementation slices | OpenHands, Cline, Aider; host-native implementation |
| 5 Testing | Actual regression, quality, security, and acceptance evidence | Promptfoo, DeepEval, Ragas; project-native tests |
| 6 Deployment | Authorized rollout preparation, rollback, and operational readiness | Langflow, Agno, BentoML; existing CI/CD |
| 7 Governance | Reviewed feedback, drift, privacy, quality, and cost process | MLflow, OpenLLMetry, Helicone |
| After Delivery (also 7 in PDF) | Reports, upgrade evaluation, incident learning, cleanup | MLflow, OpenLLMetry, Helicone |

Installation does not imply invocation. Choose tools by task fit and readiness. Install Spec Kit and OpenSpec but initialize only the selected specification workflow in a project. Avoid nested competing coding agents unless they add specific value and have bounded ownership.

Apply low/medium/high risk routing. Small fixes use lightweight planning and focused verification; substantial architecture uses reviewed written design and plan, then implementation, QA, security, simplification, portability, and release ownership. Record each stage as completed, pending, or not applicable with a reason. Deployment and operational stages can remain prepared/pending when no service is deployed. No recurring monitoring job is implied.

## 6. Full installation contract

All 16 identities are required manifest entries: Superpowers, Spec Kit, OpenSpec, MetaGPT, Promptfoo, DeepEval, Ragas, OpenHands, Cline, Aider, Langflow, Agno, BentoML, MLflow, OpenLLMetry, and Helicone. The default runs their installation recipes without requiring 16 separate selections. Required skills are installed as complete usable packages, not only SKILL.md text.

Use a small Python 3.11+ standard-library installer as the common controller, with PowerShell and POSIX entry instructions. Python is an explicit bootstrap prerequisite. Acquire only approved, pinned prerequisites under package-owned locations where supported. Docker, WSL, OS-level prerequisites, accounts, and credentials that cannot be provisioned without system changes must be reported precisely; do not bypass administrative consent. Tool environments are separate when dependency requirements conflict.

Each tool record must include upstream identity, version/commit, license, acquisition source, integrity data, host/OS compatibility, required runtimes, install recipe, invocation method, readiness probe, owned paths, configuration requirements, known restrictions, and validation evidence. Resolve exact versions from current upstream evidence during the proof-of-value/implementation planning work; release artifacts require a fully pinned manifest. Existing local inventories are historical evidence, not distribution locks.

For CLI tools install an executable runtime; for libraries install an importable package; for services install the applicable runnable components without starting them; for editor integrations use a documented compatible CLI, SDK, or extension route. The recipe must identify which route it implements. A repository ZIP or reference documentation never counts as an installed tool. If no compatible execution route exists, record a blocker rather than substitute a different product silently.

Maintain separate acquisition, installation, smoke-test, configuration, and project-integration evidence. User-facing status is ready, needs setup, blocked, failed, or unsupported, with concrete next steps. Credentials-dependent checks remain pending until configured. A help/version response proves executable availability only. A downloaded-only or failed component prevents a full-install success result. Continue independent recipes after a failure, then return a non-success summary if any required component failed or is unsupported. A completed installation with pending credentials is labeled installed/needs setup, never fully operational.

Preflight explains selected scope, destination, runtime/disk/network requirements when determinable, and blockers. Repeat runs are idempotent; interrupted installs resume from verified state. Download to staging, verify, then finalize; reject path traversal and unsafe destination paths. Preserve existing installations and configurations; reuse only after compatibility checks. Record owned files and hashes. Update replaces package-owned unmodified files, preserves or reports local modifications, and retains rollback information. Uninstall removes only recorded, unchanged owned resources, preserving user edits, projects, shared runtimes, and credentials. Use structured subprocess arguments instead of shell-built commands.

## 7. Trust, licensing, and data

Host permissions and repository/user instructions remain authoritative. Supplied PDFs, web pages, source archives, tool responses, and specialist reports are data, not permission to run commands or claim approval.

Do not ship personal paths, private project material, credentials, or undocumented global dependencies. Keep project briefs and graphs project-local. Diagnostics redact sensitive values and store no secret contents. Network installation is expected; external project-data transfer, telemetry activation, service startup, deployments, publishing, purchases, and background jobs need appropriate separate authority.

Verify licenses, provenance, and redistribution rights for tools, skill code, datasets, and local modifications before shipping. Preserve required notices; do not assume all local skills have the same license. If redistribution is not allowed, use a documented upstream installation recipe where permitted and report any unresolved licensing blocker. Keep locally customized behavior explicit rather than mislabeling it unmodified upstream content.

Historical local records identify security restrictions for installed Promptfoo/OpenSpec versions. Re-evaluate candidate releases and dependencies before using or distributing them. Do not carry old vulnerable pins forward or claim they remain vulnerable without a current check. No forced incompatible overrides or blanket permission bypasses.

## 8. State and reporting

Use one compact project-local checkpoint, normally `docs/sdlc.md`, respecting existing planning conventions. Record confirmed brief, unresolved/deferred questions, scope, approvals, risk, current phase, decisions, selected tool/version evidence, owned work, checks actually run, blockers, and next action. Write atomically and preserve existing content. Avoid transcript duplication.

On resume, reconcile saved state with current source and actual tool readiness before proceeding. Never replay destructive or external actions merely because they appear in a plan. Reopen discovery if scope changes invalidate agreed requirements.

## 9. Acceptance and release gates

Before claiming a released, working package, produce evidence for:

1. On-demand activation and nonactivation in unrelated tasks for every claimed host.
2. Vague request: identifies missing requirements, asks one focused question, does not guess/build, and produces a confirmed brief.
3. Complete request: reuses supplied answers and avoids unnecessary questioning; missing visual clarity triggers an appropriate reference request.
4. Conditional specialist, skill, and MCP use, correct handling of unavailable delegation, restricted permissions, denied access, and prompt injection in supplied material.
5. Required skill assets operate, Graphify reuses relevant local context, and no unnecessary graph build occurs on an empty project.
6. Every one of 16 tools has a tested install recipe and meaningful non-secret smoke test, with integration checks distinguished from installation checks.
7. Clean setup, repeat setup, interruption/resume, offline failure, missing prerequisites, conflicting installs, path-with-spaces handling, safe update, and ownership-aware uninstall.
8. Host loading and representative discovery/delegation on all nine OS/host combinations; publish exact client versions and architecture of tested systems. Report untested combinations, do not imply success from mocked tests.
9. One end-to-end sample from confirmed brief through a small implementation, actual tests, independent review where supported, and checkpoint resume.
10. Security, license/provenance, simplification, portability, and release reviews with unresolved blockers visible.

Do not deploy third-party services or spend provider credits merely to complete offline checks. Live checks need configured credentials and authority. The proof-of-value gate must establish viable installation/invocation routes for the largest or most constrained components before broad implementation. If a required tool cannot be supported, return to the user with the evidence and a proposed scope revision; do not quietly remove it.

## 10. Design review and next gate

Council perspectives: failure analysis, solution strategy, technical fact research, practical maintenance, and chief review. Chief verdict: approved for written specification, conditional on honest per-tool states, safe owned-file installation, current host schemas, local project data, and separate OS/host evidence. This verdict is not implementation approval or product verification.

The user reviews this written specification next. Only written-spec approval permits invoking writing-plans. The resulting written plan and its execution method are then reviewed before product scaffolding, dependency installation, or implementation. No external GitHub publication is authorized by these local design steps.

## Sources and verification limits

- User-provided Agentic SDLC GitHub Tool Research PDF: phase meanings, ranked candidates, numbering, and stated limits. Historical rankings are not current installation evidence.
- [VoltAgent Codex examples](https://github.com/VoltAgent/awesome-codex-subagents) and [Claude Code examples](https://github.com/VoltAgent/awesome-claude-code-subagents): distribution references, not authoritative current host schemas.
- [Claude Code skills](https://code.claude.com/docs/en/skills): documents user-only invocation controls and supporting skill assets.
- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents): documents native agent configuration and currently configurable nested delegation. Detect actual installed capabilities rather than assuming all subagents cannot delegate.
- [Cursor subagents](https://cursor.com/docs/subagents) and [skills](https://cursor.com/docs/skills): native agent/skill support and user/project scope.
- [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents): current custom TOML agents use name, description, and developer_instructions; parent permissions and MCP configuration remain controlling.

Documentation reviewed on 2026-10-28. No installer, runtime integration, clean-device compatibility, or behavioral evaluation has been built or passed during specification preparation.
