# Stages and gates

Account for every stage as completed, pending, or not applicable with a reason. Prepared work is not a passed gate. Preserve distinct internal names; the source numbers Governance and After Delivery both 7 (After Delivery is also described as 8).

| Stage | Required outcome / next gate |
|---|---|
| planning (0) | User-confirmed brief; essential gaps resolved before design/build. |
| analysis (1) | Feasibility, requirements, success criteria, constraints, failure risks and authority understood. |
| design (2) | Smallest viable approach, contracts, test strategy, tradeoffs and rollout needs; obtain required design/plan approval before build. |
| simulation (3) | Test material uncertainties with safe realistic inputs; record actual baseline and go/no-go. Skip with reason when no proof is needed. |
| build (4) | Small reviewable slices; respect approved scope and validate immediately. |
| testing (5) | Actual focused/regression and acceptance evidence; applicable security, permission, recovery, performance and accessibility checks. |
| deployment (6) | Explicitly authorized rollout only after required gates; versions, thresholds, rollback and ownership. Otherwise prepared/pending or not applicable. |
| governance (7) | Reviewed feedback, privacy/access/retention and quality process; AI drift/cost/RAG freshness only when relevant. |
| after-delivery (8; also 7 in source) | Quality reports, upgrades evaluated against baseline, incident learning and cleanup ownership. No automatic monitoring job. |

Low: brief planning/analysis/design, smallest change, cheapest focused check. Medium: relevant specialist where available, short design and regression checks. High: verify current facts, convene council, implement only judge-approved approach, then separate QA, security, simplification, portability and release review ownership. Escalate architecture, authentication/permissions/security, API/database redesign, browser automation, deployment, breaking changes, major UI/UX and consequential ambiguity. Unavailable independent review leaves its gate pending.

Use project-native infrastructure first. All software is supported; models, agents, memory, RAG, model judges and AI evaluations are conditional. Only use relevant ready tools with authority. Catalog inclusion or installation does not imply invocation, readiness or project integration. Keep all 16 catalog identities; do not initialize competing specification workflows by default. Task 2 evidence permits safe source work only; full runtime/release remains no-go and inactive recipes stay inactive until independently cleared.
