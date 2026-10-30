# New-work and ownership disclosure

ReleaseProof was created for the Nebius x NVIDIA Global AI Hackathon during its submission period. The application work began on October 30, 2026. This document separates the new application from preexisting foundations; it does not claim that its underlying libraries were invented during the hackathon.

## Preexisting foundations

- **Pollard 1.6.2:** the entrant's existing execution/control library, used as a dependency.
- **Hashrope 0.2.2:** the entrant's existing persistent content-version library, used as a dependency.
- **Epicormic 0.2.0:** the entrant's existing behavioral drift/probe library, used as a dependency.
- **Canopy:** prior team work informed the problem of governing agent actions. Its team-owned frontend, benchmark, and application code are not copied into ReleaseProof.
- FastAPI, Uvicorn, HTTPX, Pytest, and the other declared third-party dependencies retain their own licenses. NVIDIA models and Nebius services retain their own terms.

## New hackathon work

The new contribution is an end-to-end issue-triage release workflow: run a version-bound qualification, inspect task outcomes and spending, explicitly promote, invalidate a stale approval, and enforce a future-action hold when the current evidence or behavioral qualification is insufficient.

New work includes the server/session integration, release engine integration, Nebius provider adapter, budget reservation and reconciliation flow, configuration/evidence binding, local issue board, browser interface, synthetic eight-case qualification/four-case holdout workload, scenario tests, evidence export, and submission materials.

The novelty claimed is this concrete integrated workflow and its demonstrated behavior. We do not claim that evaluation dashboards, regression testing, cost tracking, model comparisons, or behavioral drift detection are new categories.

## Assistance and evidence

AI coding assistants helped with research, design, implementation, testing, and documentation. The entrant selected the project and is responsible for the submission, ownership, and claims. The issue fixtures are explicitly marked as AI-authored synthetic examples.

Before submission, retain a dated source commit, dependency versions, the final evaluation export, and the recorded demo. Publish actual observations and failures. Unfinished or unverified features must not be presented as completed work.
