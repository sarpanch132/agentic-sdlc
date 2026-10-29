# Agentic SDLC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an explicitly invoked native SDLC coordinator, supporting skills and agents, and an honest full-tool installer for Claude Code, Cursor, and Codex.

**Architecture:** One canonical workflow feeds thin native adapters; the main host session owns interactive discovery and delegation. A Python standard-library installer consumes a pinned tool manifest and tracks acquisition, installation, checks, configuration, integration, and owned files separately. No separate AI runtime is introduced for the coordinator.

**Tech Stack:** Python 3.11+, standard-library unittest, JSON, TOML via tomllib for validation, Markdown/YAML host assets, PowerShell/POSIX launch instructions, Git. Upstream tools retain their documented runtimes in isolated environments.

**Spec:** [Approved design](../specs/2026-10-28-agentic-sdlc-design.md).

## Global Constraints

- "Target Windows, macOS, and Linux. Publish an explicit tested host/OS matrix, not a universal compatibility claim."
- "User-wide installation is the default; project-only installation is supported."
- "The default installation includes all 16 distinct tools ranked in the supplied research PDF, including alternatives."
- "Bundle brainstorming, Ponytail full mode, Graphify, and UI/UX Pro Max with their required supporting assets."
- "Ask for missing user requirements instead of guessing. Discover technical capabilities independently within existing access."
- "Use a small Python 3.11+ standard-library installer as the common controller, with PowerShell and POSIX entry instructions."
- "No external GitHub publication is authorized by these local design steps."
- Follow Agentic SDLC phases and Ponytail/token-efficiency throughout. Keep independent implementation, QA, security, simplification, portability, and release review ownership separate.
- No product files or dependencies are created until the user approves this written plan and selects execution method. Evidence collection is allowed; runtime installation belongs to approved execution.

## File ownership and interfaces

All paths below are relative to this dedicated repository, not the surrounding workspace or the ancestor Git repository.

| File/directory | Responsibility |
|---|---|
| `skills/agentic-sdlc/` | Canonical coordinator, discovery, phases, routing and checkpoint guidance |
| `skills/dependencies/` | Complete approved third-party skill assets with notices |
| `agents/` | Canonical focused specialist instructions |
| `adapters/{claude,cursor,codex}/` | Native agent/skill registration assets |
| `toolkit/manifest.json` | Exact versions, acquisition integrity, recipes, compatibility and probes |
| `toolkit/skills.json` | Skill provenance, asset list, license and local adaptations |
| `installer/catalog.py` | Manifest validation, statuses and platform selection |
| `installer/files.py` | Owned-file safety, staging, atomic receipt writes |
| `installer/engine.py` | Structured command execution and resumable install/update/uninstall |
| `installer/__main__.py` | User CLI and readiness report |
| `tests/` | Focused unittest suites and inert fixtures |
| `evals/` | Behavioral scenarios, rubric and actual result records |
| `docs/compatibility.md` | Tool/platform/host evidence and limitations |
| `docs/provenance.md`, `THIRD_PARTY_NOTICES.md` | Sources, attribution and redistribution decisions |
| `README.md` | Prerequisites, on-demand usage, setup and recovery instructions |

Avoid a generic plugin framework, installer SDK, unrelated agent catalog, hosted dashboard, and unrequested MCP server. Use a direct recipe table and standard library. Split a module only if distinct responsibilities demand it.

### Task 1: Resolve provenance, supported routes, and version candidates

**Files:** Create `docs/provenance.md`, `docs/compatibility.md`, `THIRD_PARTY_NOTICES.md`, `toolkit/manifest.json`, `toolkit/skills.json`; update `docs/sdlc.md`.

**Consumes:** Approved spec; original PDF tool identities; installed skill source material as reference only.
**Produces:** Frozen manifest records used by all following tasks. Each tool has `id`, `upstream`, `version`, `license`, `source`, `sha256`, `kind`, `platforms`, `requires`, `install`, `probe`, `configuration`, `integration`, `restrictions`, `evidence`. Recipe commands are arrays of arguments, never shell strings. Only installer-generated path tokens may be expanded.

- [ ] Check current official documentation and releases for all 16 repositories listed in the spec. Record URLs, retrieval date, release identifier and installation route, including native architecture support. Verify current host schemas, explicit invocation controls and inherited MCP permissions against official documentation rather than copying VoltAgent files blindly.
- [ ] Check redistribution licenses for brainstorming, Ponytail, Graphify, UI/UX Pro Max, including datasets, scripts and local modifications. Obtain pinned approved upstream assets; retain notices. Where downloading from upstream is required instead of redistribution, document and test that installation route.
- [ ] Resolve each runtime recipe from upstream evidence: Python packages/CLI entry points for Spec Kit, MetaGPT, DeepEval, Ragas, Aider, Agno, BentoML, MLflow, OpenLLMetry and Langflow where documented; Node or other documented routes for OpenSpec, Promptfoo and Cline; documented runnable service/CLI routes for OpenHands and Helicone; host-specific complete skill installation for Superpowers. Do not infer package names from repository names.
- [ ] Freeze exact artifact versions and checksums, dependency lock information where supported, platform prerequisites, probe arguments and successful probe criteria. Verify signatures when upstream supplies them. Audit candidate Promptfoo/OpenSpec dependency trees afresh; do not reuse the historical restricted environments.
- [ ] For every unsupported or unresolved route, record a blocker with evidence and halt the complete-bundle claim. Propose a scope change to the user if required; do not silently remove a tool.
- [ ] Commit the evidence and records: `git add docs toolkit THIRD_PARTY_NOTICES.md` then `git commit -m "docs: verify toolkit provenance and runtime routes"`.

**Gate:** All 16 identities have grounded recipes and license decisions before broad installer implementation. This is planned verification, not a compatibility claim made by this document.

### Task 2: Prove constrained tools and host contracts

**Files:** Create `tests/fixtures/host-contracts.json`; add dated evidence under `docs/evidence/`; update manifest and compatibility report.

**Consumes:** Task 1 frozen recipes.
**Produces:** Supported host schemas, tested asset-loading locations, and constrained-runtime go/no-go evidence.

- [ ] In task-owned temporary environments, execute the exact frozen install/probe recipes for MetaGPT, OpenHands, Cline, Langflow and Helicone first. These are risk-priority probes; all other tools are checked in Task 7. Keep servers stopped and provider calls disabled. Capture exit status, version, prerequisite failures and meaningful non-secret smoke results.
- [ ] Confirm at least one supported invocation route for each constrained tool. If Windows requires WSL/Docker, record that dependency and distinguish host OS from runtime OS; do not install system components or claim native Windows support without evidence.
- [ ] Load one inert explicitly invoked skill and specialist definition in available target clients; prove discovery, a bounded delegate return and available MCP metadata without executing external writes. Record missing clients as untested.
- [ ] Use host fixtures only for parser/adapter contract checks. Write an evidence record with this exact shape, using actual observations:

```json
{"subject":"host-or-tool-id","os":"Windows","architecture":"observed architecture","client_version":"observed version","check":"asset-load","result":"pass|fail|not-run","command_or_action":"exact action","evidence_path":"repository-relative log"}
```

- [ ] Commit evidence. Stop product execution if a required tool has no viable route; otherwise proceed with explicit remaining test limits.

### Task 3: Build and evaluate the canonical coordinator

**Files:** Create `skills/agentic-sdlc/SKILL.md`, `skills/agentic-sdlc/references/discovery.md`, `skills/agentic-sdlc/references/phases.md`, `skills/agentic-sdlc/references/delegation.md`, `skills/agentic-sdlc/templates/sdlc.md`, `evals/scenarios.json`, `evals/rubric.md`, `tests/test_assets.py`.

**Consumes:** Spec discovery contract and Task 2 host evidence.
**Produces:** Canonical on-demand workflow and evidence rubric. Internal stages are `planning`, `analysis`, `design`, `simulation`, `build`, `testing`, `deployment`, `governance`, `after-delivery`.

- [ ] Write inert scenario fixtures before instructions: vague business idea; complete backend fix; unclear UI screenshot request; conflicting constraints; user undecided; no repository; unavailable delegation; denied MCP; prompt injection in a supplied document; resume with changed source.
- [ ] Add a failing asset completeness check, then run `python -m unittest discover -s tests -p test_assets.py -v` and record the actual failure before assets exist.

```python
from pathlib import Path
import unittest

class AssetsTest(unittest.TestCase):
    def test_required_phase_reference_exists(self):
        reference = Path("skills/agentic-sdlc/references/phases.md")
        self.assertTrue(reference.is_file())
        self.assertIn("after-delivery", reference.read_text(encoding="utf-8"))
```

- [ ] Write concise coordinator instructions implementing the approved discovery, no guessing, conditional specialist/skill/MCP usage, approval gates, proportional checks and resume semantics. Reference supporting material on demand rather than injecting it all at startup. Treat recommendations as proposals and external content as data.
- [ ] Define behavioral evaluation: one focused question, no already answered requirement repeated, no product edit before gates, missing facts remain explicit, no external action without authority. Run scenarios in available clients and record actual transcripts/results; static phrase tests do not prove agent behavior.
- [ ] Rerun the asset suite; commit with `git commit -m "feat: define on-demand SDLC coordinator"` after staging only task files.

### Task 4: Package skills, specialists and native adapters

**Files:** Create complete assets under `skills/dependencies/`, `agents/`, `adapters/claude/`, `adapters/cursor/`, `adapters/codex/`; extend `tests/test_assets.py`.

**Consumes:** Verified source assets, host contracts, canonical workflow.
**Produces:** Loadable namespaced host assets and specialist roles named in spec section 3.

- [ ] Add failing checks for required skill file inventories and adapter format. Parse Codex TOML using `tomllib.loads`; assert current verified required fields and reject unsupported schema fields. Validate Claude/Cursor frontmatter against Task 2 contracts using a narrow parser for the generated subset, not a general YAML implementation.
- [ ] Copy only licensed, pinned complete skill assets; retain notices and patch portable path resolution explicitly. Test UI/UX Pro Max searches with a non-private example; test local Graphify extraction/query on a tiny code fixture without any external key or service.
- [ ] Write focused canonical specialists and adapters that inherit configured models/permissions by default. Read-only review roles request only required tools. Helper descriptions restrict use to an invoked SDLC workflow. Keep main-session invocation distinct from optional named-agent delegation.
- [ ] Prove on-demand entry in available hosts, absence of unrelated automatic SDLC activation, bounded delegation and fallback disclosure. Record each real host result separately.
- [ ] Run `python -m unittest discover -s tests -p test_assets.py -v`; commit the completed task.

### Task 5: Implement validated catalog and safe owned-file storage

**Files:** Create `installer/__init__.py`, `installer/catalog.py`, `installer/files.py`, `tests/test_catalog.py`, `tests/test_files.py`.

**Consumes:** Frozen manifest and distribution assets.
**Produces:** `load_catalog(path: Path) -> list[dict]`, `resolve_owned(root: Path, relative: str) -> Path`, `write_receipt(path: Path, receipt: dict) -> None`.

- [ ] Add failing tests for missing/duplicate tool IDs, wrong checksums, unpinned sources, shell-string commands, unsupported expansion tokens, and all 16 tools included by default. Use unittest and tempfile, with no network.
- [ ] Add failing filesystem safety tests for absolute/parent traversal, symlink or reparse-point escapes, modified owned files, and interrupted receipt writes. Include this independent trust-boundary check:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from installer.files import resolve_owned

class OwnedPathTest(unittest.TestCase):
    def test_parent_escape_is_rejected(self):
        with TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                resolve_owned(Path(temporary), "../outside")
```

- [ ] Implement JSON validation with explicit allowed kinds/statuses, supported token expansion and structured command arrays. Canonicalize destinations, reject escapes and unsafe links, stage validated files, write receipts with atomic replace, and record owned file hashes. Do not overwrite unknown existing files.
- [ ] Run `python -m unittest discover -s tests -p "test_*.py" -v`; commit only after the focused suites pass.

### Task 6: Implement resumable installation and diagnostics

**Files:** Create `installer/engine.py`, `installer/__main__.py`, `tests/test_engine.py`, `tests/test_cli.py`; update `README.md` with executable invocation.

**Consumes:** Catalog and safe storage APIs from Task 5.
**Produces:** `install(catalog: list[dict], root: Path, runner) -> dict`, `diagnose(catalog: list[dict], root: Path, runner) -> dict`, and `python -m installer install|doctor --host claude|cursor|codex --scope user|project [--project PATH]`.

- [ ] Add failing simulated-runner tests for all 16 attempted, prerequisite blocker, command failure, bounded transient retry, checksum mismatch, repeat install, interruption/resume, paths containing spaces, no shell interpolation and secret redaction.
- [ ] Define receipt fields `tool_id`, `version`, `acquired`, `installed`, `smoke_tested`, `configured`, `project_integrated`, `status`, `reason`, `owned_files`, `evidence`. Make status derived from observed evidence, not self-reported tool success.
- [ ] Implement sequential recipe execution with `subprocess.run(argv, shell=False, ...)`, per-command timeout, redacted bounded logs and verified state resume. Continue independent tools after failure. Do not treat version output or a downloaded archive as project integration. No server command or account provisioning runs as part of install.
- [ ] CLI defaults to user scope and the full catalog. Require explicit host selection rather than guessing; project scope requires a selected project path. Exit 0 only for completed installation with no failed/unsupported required component; exit 1 for required failures/blockers; exit 2 for invalid invocation. Clearly label missing credentials as needs setup, not operational success.
- [ ] Run `python -m unittest discover -s tests -v`; manually run CLI help and preflight against a temporary destination; commit.

### Task 7: Integrate and smoke-test all 16 recipes

**Files:** Update `toolkit/manifest.json`, `docs/compatibility.md`, `docs/evidence/`, `README.md`.

**Consumes:** Task 1 pinned recipes and Task 6 installer.
**Produces:** Actual per-tool installation/probe evidence in package-owned temporary destinations.

- [ ] Run the full default install on the available machine. Use the selected scope in a task-owned sandbox; do not write to the user's real coding-app settings for these checks. Capture all 16 outcomes.
- [ ] Run each manifest's frozen smoke probe. Python tools must import required modules; CLIs must complete a non-secret meaningful operation; services must validate runnable component/configuration without launching listeners; skill frameworks must expose required assets. Keep live provider and credential-dependent integration tests pending unless separately authorized.
- [ ] Confirm both Spec Kit and OpenSpec are installed while neither initializes arbitrary user projects. Confirm no monitoring backend, Docker service, MCP server or telemetry export was silently started.
- [ ] Fix demonstrated recipe defects, rerun only affected checks and their regression suites, and record actual disk usage, versions and outcomes. An unavailable system prerequisite is a visible blocker, not a passed test.
- [ ] Commit evidence and update the phase 3/4 checkpoint. Return to the user if full-tool feasibility fails.

### Task 8: Add safe update, rollback and uninstall

**Files:** Extend `installer/engine.py`, `installer/__main__.py`, `tests/test_engine.py`, `tests/test_cli.py`, `README.md`.

**Consumes:** Installed receipts and owned hashes.
**Produces:** `update(catalog, root, runner) -> dict`, `uninstall(root: Path) -> dict`, CLI `update` and `uninstall` with the same host/scope targeting.

- [ ] Add failing tests: changed user file preserved, unknown file preserved, shared runtime preserved, failed update retains previous usable assets, cross-scope target rejected, repeated uninstall harmless, and symlink substitution rejected.
- [ ] Implement update by staging verified replacement artifacts and committing receipts only after probes pass. Preserve previous owned asset generation for rollback. For third-party isolated environments, switch generation only after the replacement validates. Report modified/unknown files for manual resolution.
- [ ] Uninstall only matching recorded owned resources within the resolved root. Preserve modified files and report leftovers. Never recursively delete a user-selected directory merely because it contains a receipt.
- [ ] Run all installer suites and one real install/repeat/update/uninstall cycle in a disposable directory; commit.

### Task 9: Independent behavioral, security and portability verification

**Files:** Add `evals/results/`, `docs/evidence/`, update `docs/compatibility.md`, `docs/sdlc.md`.

**Consumes:** Completed toolkit and evaluator scenarios.
**Produces:** Separate QA/security/simplification/portability findings with fixes and actual retest evidence.

- [ ] QA reviewer runs Task 3 scenarios and an end-to-end small sample through discovery, brief confirmation, design/plan approval, implementation, tests, independent review and resume. Check sequential fallback labels and no independent-review claim without separate execution.
- [ ] Security reviewer inspects subprocess boundaries, download integrity, untrusted archive paths, symlink/reparse points, receipts, update/uninstall ownership, permissions, injection scenarios, credential handling and telemetry defaults. Scan dependency locks using appropriate current upstream/package-manager tooling; record exit codes and findings, not just tool execution.
- [ ] Simplification reviewer removes unnecessary frameworks, duplicated prompts, speculative options and repeated context without weakening requirements.
- [ ] Portability reviewer tests Windows/macOS/Linux with paths containing spaces and records actual architectures/runtime versions. Exercise every claimed host/OS pairing. Where machines or clients are unavailable, mark not run and leave corresponding release claims pending; mocked tests cannot close those gates.
- [ ] Implementer fixes actionable findings; relevant reviewers rerun failed checks. Record remaining blockers and commit verification evidence.

### Task 10: Prepare an honest distributable release

**Files:** Finalize `README.md`, `THIRD_PARTY_NOTICES.md`, `docs/compatibility.md`, `docs/maintenance.md`, `CHANGELOG.md`; create local distribution under `dist/` with license permitted assets only.

**Consumes:** Task 9 reviewed evidence and immutable pinned manifests.
**Produces:** Local archive and setup instructions with readiness limits. No external release is created.

- [ ] Document Python bootstrap, pinned runtime prerequisites, expected downloads, both installation scopes, all 16 tools, explicit invocation for each host, credentials/setup boundaries, diagnostics, retry/resume, update, uninstall and known compatibility gaps. Do not advertise complete cross-platform support until the matrix is verified.
- [ ] Add maintenance guidance for reviewed upstream upgrades, sanitized regression additions, telemetry opt-in/retention decisions, model-change evaluations and end-of-life cleanup. Do not create monitoring automations.
- [ ] Run `python -m unittest discover -s tests -v`, validate manifest integrity and notices, and inspect the distribution for absolute personal paths, credentials, accidental project data and missing skill assets.
- [ ] Release reviewer checks install and operational evidence separately. Package only if licensing/security gates permit; otherwise deliver source/evidence with explicit release blockers. Build the archive using standard-library `shutil.make_archive` with explicit approved distribution paths and exclude environments, logs containing private information and Git internals.
- [ ] Commit final documentation and checkpoint. Report changed behavior, actual checks, exact tested matrix, artifact location and remaining risks. Publishing to GitHub remains a separate authorized action.

## Coverage and execution handoff

Spec sections 1–2 map to Tasks 3–4; sections 3–4 to Tasks 2–4 and 9; section 5 to Tasks 1, 3 and 7; section 6 to Tasks 1–2 and 5–8; section 7 to Tasks 1, 5, 8–10; section 8 to Task 3 and checkpoint updates; section 9 to Tasks 2 and 7–10. User approval of this plan plus execution-method selection opens implementation.

Recommended execution: subagent-driven, one implementer per task with review between tasks and separate verification owners. Alternative: inline execution with checkpoints; independent reviews still use separate executions where required. Task dependencies are sequential except clearly independent review work. Never parallelize approval gates or overlapping file mutations.

No product tests have run while writing this plan. Research and proof-of-value steps are explicit tasks, not fabricated completed work.
