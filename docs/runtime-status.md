# Runtime status — 2026-10-29

**The complete automatic 16-tool plus Graphify bundle is incomplete.** Source publication: [GitHub](https://github.com/sarpanch132/agentic-sdlc); this is an experimental source distribution.

## Implemented and verified

- Installer actions: install, authenticated repeat/resume, doctor, update, rollback and uninstall.
- Private ownership state, immutable runtime inventory, recipe-specific generations, interrupted-install preservation and clean rebuild.
- Modified/unknown files are preserved; unknown environments are not adopted for execution. Shared Docker images are preserved.
- Windows native process-tree cleanup, bounded output and timeout handling. Transient Windows replacement errors receive bounded retries with safety revalidation.
- Full regression run: 147 tests, 144 passed and three platform/privilege skips, no failures (320.899 seconds). This preceded the final bytecode flag correction.
- Follow-up checks after that correction and catalog changes: 46 passed, covering catalog, assets, wheel integrity, bundled wheels and Python probes.
- Real Superpowers and OpenLLMetry lifecycle cycles passed. OpenLLMetry used an explicit pinned HTTPX dependency and bundled CUID wheel; probes disable bytecode to preserve immutable inventories.

## Tool inventory

All sixteen PDF tool identities remain in the default catalog. Graphify is an additional required runtime. Enabled means the installer can attempt its reviewed recipe; provider setup, native host behavior and project integration are separate.

| Tool | Version | Current gate |
|---|---|---|
| superpowers | v7.0.1 | Enabled; Windows local checks passed |
| spec-kit | 1.2.4 | Enabled; Windows local checks passed |
| openspec | 1.15.0 | Enabled; Windows local checks passed |
| metagpt | 0.8.2 | Python3.11 interpreter unavailable; source-only gitignore-parser0.1.9 still requires reviewed wheel and complete closure validation. |
| promptfoo | 0.125.1 | Enabled; Windows local checks passed |
| deepeval | 4.3.2 | Enabled; Windows local checks passed |
| ragas | 0.4.3 | Candidate audit matches direct multimodal SSRF and diskcache unsafe-pickle advisories; remediation and runtime proof pending. |
| openhands | 1.34.0 | Fresh npm audit findings: {'info': 0, 'low': 0, 'moderate': 1, 'high': 3, 'critical': 1, 'total': 5}; no forced downgrade or dependency override applied. |
| cline | 3.0.74 | Fresh npm audit findings: {'info': 0, 'low': 4, 'moderate': 11, 'high': 9, 'critical': 2, 'total': 26}; no forced downgrade or dependency override applied. |
| aider | 0.86.2 | Candidate audit matches direct and transitive advisories; exact dependency pins and unsafe application paths require reviewed fixes. |
| langflow | 1.13.0 | Candidate 469-package closure resolved with reviewed local wheels; filelock3.32.7, Pillow12.3.0 and setuptools83.0.0 advisory matches block execution. |
| agno | 3.1.11 | Enabled; Windows local checks passed |
| bentoml | 1.4.40 | Enabled; Windows local checks passed |
| mlflow | 3.17.2 | Enabled; Windows local checks passed |
| openllmetry | 0.62.4 | Enabled; Windows local checks passed |
| helicone | sha256:4da15718dd4936da63be8fbd5f8aedd2d396e25bffccbbfcd786d0b568d6b901 | Native Docker prerequisite unavailable; digest-pinned image pull and inspection unverified. |
| graphify | 0.9.97 | Enabled; Windows local checks passed |

## Scope of real checks

- Graphify: exact hash-locked environment, version and local code-only extraction; authenticated lifecycle resume/doctor and tamper rejection checked separately.
- Superpowers: all fifteen complete skill trees and root license, install/resume/doctor/update/rollback/uninstall; no hooks or native behavioral certification.
- OpenSpec: version, synthetic project initialization and list.
- Promptfoo: version and one providerless echo evaluation; exact FTP/Azure overrides audited with zero npm findings. Other integrations remain unverified.
- Spec Kit: installed version/features JSON; complete specification workflow unverified.
- Agno: model-free Agent/Message construction.
- DeepEval: deterministic tool-match metric with model calls forbidden.
- BentoML: local picklable model save/load/list.
- MLflow: local SQLite metric/parameter write/read. A combined managed install hit a 30-second CLI timeout; the corrected probe passed in 57.66 seconds with a 90-second bound. That complete combined cycle was not rerun.
- OpenLLMetry: isolated import/version and a local decorated function, followed by update/rollback/uninstall; no trace export initialized.

Exact artifact/lock hashes and compact check records are under [runtime evidence](evidence/2026-10-29-runtime/verification.json), [Graphify](evidence/2026-10-29-runtime/graphify.json), [Superpowers](evidence/2026-10-29-runtime/superpowers.json) and [OpenLLMetry](evidence/2026-10-29-runtime/openllmetry.json). No token-savings percentage was measured.

## Remaining release blockers

- Seven tools remain blocked; no audit bypass or forced dependency downgrade was used. OpenHands has an alternative Python SDK candidate, but that closure also has advisory matches and is not enabled.
- Python3.11 and Docker are not installed by this package. Compatible Node/npm must already exist for Node recipes.
- Claude Code/Cursor/Codex complete native loading, delegation and MCP behavior, fresh-device installation and macOS/Linux operation remain unverified. Earlier Claude/Codex observations did not establish complete skill loading.
- No production release, provider credentials, services or remote model calls. Experimental source is published on GitHub. Older experimental ZIPs are stale relative to this source.
- Implementation, regression verification and the final corrections in this turn were performed directly after the user requested no further delegation; these corrections have not received a fresh independent security/release review.

## Phase checkpoint

Planning, requirements and design remain approved. Build and focused Windows validation advanced as described above. Simulation covers structural/controlled scenarios; full native simulation is pending. Deployment/publication is deferred. Governance retains component licenses and private ownership state; after-delivery compatibility and complete runtime acceptance remain open.

## Project configuration update

Enabled tools now have selective local profiles. Run configure after project discovery and project-doctor to recheck local readiness; see [project setup](../skills/agentic-sdlc/references/project-setup.md). All nine phases have explicit catalog assignments, with a native-host Build fallback and cross-phase Graphify support.

Real profile operations passed for Spec Kit, OpenSpec, Promptfoo, DeepEval, Agno, BentoML, MLflow, Graphify and OpenLLMetry; the Superpowers instruction profile passed in the fresh managed proof. A fresh managed Superpowers/OpenSpec/Graphify install passed the public configure and project-doctor commands, ordinary doctor reporting, modified-configuration rejection and runtime uninstall while preserving project outputs. Scope and limits are recorded in [configuration evidence](evidence/2026-10-29-runtime/project-configuration.json).

Successful configuration means selected local tooling is ready. It does not establish the application's acceptance criteria, provider access, native application delegation or production deployment. Seven runtime gates and the existing host/OS limitations remain open. The earlier regression counts above describe the preceding build.

Final configuration build checks: **166 tests run, 163 passed, three skipped, no failures/errors**. An extracted source package passed **34 asset/catalog checks**, with **30 frozen runtime payloads and 116 instruction assets** verified against committed bytes. Code commit: `0319d7d`. These results do not close the seven runtime gates or native-host/non-Windows acceptance.
