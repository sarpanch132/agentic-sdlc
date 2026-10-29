> Current implementation and verification status: [runtime status](runtime-status.md), updated 2026-10-29. Earlier observations below are historical and do not describe the latest runtime gates. Publication status is in README; earlier deferral notes below are historical.

# Provenance gate — 2026-10-28, fix round 1

All16 required identities remain in the default catalog. Exact acquisition records, seven Python hash locks, four npm integrity locks/audits and selected skill rights decisions are delivered. **All records remain inactive/non-executable**. Blocked tools must be reported as blocked, not skipped or counted installed. Safe installer/coordinator source work can continue without operational use of affected runtimes.

Registry package version, GitHub latest-release label, separately retrieved HEAD snapshot and artifact digest are distinct fields. Aider/MetaGPT/DeepEval package versions exceed latest-release labels; Cline CLI differs from its extension version. Documentation establishes a route, not a matching package commit. Frozen payload hashes control acquisition; publisher signatures/attestations were not verified.

## Acquisition routes

| Tool | Exact candidate and documented route |
|---|---|
| Superpowers | 7.0.1 archive; complete licensed assets in namespaced on-demand adapters, without startup hooks/plugin auto activation. |
| Spec Kit | specify-cli1.2.4, Python>=3.11, published `specify` entry point; hash lock resolved. |
| OpenSpec | @fission-ai/openspec1.15.0, Node>=20.19.0; npm lock resolved, audit0 findings. |
| MetaGPT | metagpt0.8.2; separate Python3.11 required. No-build resolution blocked by source-only fire0.4.0. |
| Promptfoo | promptfoo0.125.1, Node>=22.22.0; exact npm tree frozen, seven high findings block operational use. |
| DeepEval | deepeval4.3.2; Python package/console entry point; hash lock resolved. |
| Ragas | ragas0.4.3; Python package/CLI; hash lock resolved, provider evaluation remains separate. |
| OpenHands | @openhands/agent-canvas1.34.0 full npm payload hash/integrity verified. Node24+; defaults pin agent-server1.58.1 and automation1.26.0 through uvx. `--version` exits before service startup. Npm lock has five findings including one critical; operational use blocked. Secondary Python runtime locks remain a gate. |
| Cline | cline3.0.74 wrapper plus all six Windows/macOS/Linux x64/arm64 native tarballs hashed/integrity-verified. Select exactly one platform package. Npm tree has26 findings including two critical; operational use blocked. Disable postinstall, which mutates user hub discovery. |
| Aider | aider-chat0.86.2, Python>=3.10,<3.13; published `aider` entry point, hash lock resolved. Convenience installer not run. |
| Langflow | langflow1.13.0 delegates to langflow-base; broad and Python3.12-only no-build locks fail on source-only IBM packages. No complete dependency lock claimed. |
| Agno | agno3.1.11, Python package/CLI, hash lock resolved. |
| BentoML | bentoml1.4.40, Python>=3.9; hash lock resolved. Container build remains separate. |
| MLflow | mlflow3.17.2, Python>=3.10; hash lock resolved; direct payload digest from publisher metadata. |
| OpenLLMetry | traceloop-sdk0.62.4 library, not fabricated CLI; version probe proposed. No-build lock blocked by source-only cuid0.4. |
| Helicone | Official all-in-one OCI index sha256:4da15718dd4936da63be8fbd5f8aedd2d396e25bffccbbfcd786d0b568d6b901; Linux amd64/arm64 manifests/configs frozen. Pull-by-digest candidate only. Supplementary source215MB archive and legacy Compose assets hashed. Selected current official image route avoids legacy local Dockerfile/Compose builds. |

Each manifest entry retains official upstream/release/registry/source URLs, retrieval date, exact artifacts, prerequisites, argv/probe criteria and restrictions. [Helicone official Docker instructions](https://docs.helicone.ai/getting-started/self-host/docker) support the selected image route. Docker Linux-container mode is required on every host. The image has no Helicone VCS-revision label, so supplementary release source is not claimed to reproduce it. Layers are approximately3.5GB/platform compressed; none were downloaded. Acquire official image by digest only, do not redistribute image layers; embedded OS/database software retains its separate licenses. Later explicit local start requires loopback ports and owned persistent volumes. Jawn's documented healthcheck does not prove account setup, model integration, gateway operation or production hardening.

Recipe commands are argument arrays and reserved installer-owned tokens only. Locks must be copied into owned tool roots before replay. No normal application launch, provider credential access or service start is part of provenance collection or a version probe.

## Locks, audits and lifecycle review

npm11.16.0/Node24.18.0 resolved four fresh trees with `install --package-lock-only --ignore-scripts --no-audit --fund=false`, then `audit --json`. Owned distinct empty user/global config files and owned cache avoided user configuration. Initial same-path config attempt failed; separate paths fixed it. No node_modules directories were created.

| Tree | Resolve exit | Audit exit | Fresh reported findings |
|---|---|---|---|
| OpenSpec1.15.0 | 0 | 0 | 0 |
| Promptfoo0.125.1 | 0 | 1 | 7 high |
| Cline3.0.74 | 0 | 1 | 2critical,9high,11moderate,4low |
| OpenHands Canvas1.34.0 | 0 | 1 | 1critical,3high,1moderate |

Full artifact integrity locks, current advisory URLs and decisions are in `toolkit/locks/`. Promptfoo includes MSAL and basic-ftp chains; npm proposes a breaking downgrade for part of its tree. No downgrade, force fix, override or historical-vulnerability assumption was applied. Promptfoo, Cline and OpenHands remain blocked from operational installation/use pending compatible remediation or independent security/reachability review. Audit output is registry evidence, not proof that every advisory is reachable or absent findings imply safety.

`lifecycle-review.json` records script commands and inspected source hashes. Esbuild may download/execute native binaries; fsevents invokes node-gyp; Cline mutates discovery/cache state; protobufjs inspects version metadata. Other declared scripts perform notifications/type checks. Suppress all with `--ignore-scripts`; no script ran, and no claim is made that script suppression preserves full native behavior without later tests.

uv0.12.6 ran metadata-only `pip compile --generate-hashes --universal --python-version3.12 --no-build --no-python-downloads` (3.11 for MetaGPT), official PyPI index, system TLS and owned cache. Seven locks succeeded. MetaGPT/fire, OpenLLMetry/cuid and Langflow/IBM locks failed; diagnostics are in `python-evidence.json`. Restricted Python3.12 Langflow retry also failed. Source-only failures are build-review gates, not proof upstream cannot run. No arbitrary backend executed for metadata. Python vulnerability audits and native install/probes have not run.

## Selected required-skill rights

The independent [selected-asset rights review](rights-audit.md) reviewed actual selected content and found no restrictive exception preventing scoped unchanged redistribution or pinned acquisition with notices. `toolkit/skills.json` inventories only selected usable assets; unrelated full archive inventories remain scratch evidence.

- Brainstorming: complete8-file skill subtree plus MIT LICENSE.
- Ponytail: one skill plus MIT LICENSE; full-mode coordinator policy retained.
- Graphify: Codex skill template, eight references, Apache LICENSE, legacy LICENSE-MIT and NOTICE. Rename template to SKILL.md and place references beside it. Separate runtime acquisition; no cloud/hooks/watchers.
- UI/UX Pro Max: SKILL.md, complete data directory, two references, five required Python scripts, MIT LICENSE. Retain catalog provenance, Google font license metadata, Phosphor metadata and unresolved-family exclusions. Catalogs contain metadata, not font binaries/SVG/icon implementations. Separately acquired implementations require their own rights.

No unmatched local modifications are redistributed. Verify archive and selected-file SHA256s; retain exact notices from `THIRD_PARTY_NOTICES.md` and mark adapter modifications. Acquisition does not erase notice obligations. Root project licensing must not relabel Graphify or external assets.

Official host invocation and MCP permission mappings are in `docs/compatibility.md`. Native client/OS tests remain later work; no16-tool runtime completion or universal compatibility is claimed.

## Public evidence scope

Executable locations in Task 2 commands and Python resolver records are redacted as `<local ... executable>` placeholders. Arguments, observed versions and exits are retained; placeholders are not verbatim executable paths. Development downloads and raw logs are not distributed. Official acquisition URLs, hashes and resolver outcomes remain in the catalog. Recorded synthetic fixture paths identify past checks, not files included in this checkout.
