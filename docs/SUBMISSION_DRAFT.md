# Devpost submission draft

Status: working draft. Replace the verification fields below with observed evidence before publication. Do not submit invented metrics or missing links.

**Project name:** ReleaseProof  
**Tagline:** Know which agent release is allowed to act—and why.  
**Track:** Best Apps and Agents

## Inspiration

An agent can pass a test and still be running a different prompt, tool contract, or policy when it takes its next action. Switching models adds another decision: does the new configuration perform the actual workflow well enough, and what will qualification and monitoring cost?

We built ReleaseProof for developers making that release decision. Our own work on Pollard, Hashrope, and Epicormic supplied the foundations, but the project focuses them on one useful workflow: an issue-triage agent.

## What it does

ReleaseProof tests a candidate against a small, clearly labelled synthetic workload, records exact configuration and evidence versions, and makes promotion an explicit decision. An approved agent can label, route, and draft responses on an isolated issue board. The server refuses stale approval after a contract change.

Smart budgeting reserves a worst-case call allowance before dispatch, reconciles observed usage, and protects validation/recovery capacity. Governance is enforced at the server before an action. Repeated behavioral probes can hold future actions, while mitigation requires appropriate current evidence rather than automatically reviving an old approval.

## How we built it

NVIDIA Nemotron performs live triage through Nebius Token Factory's inference API. A compact Python/FastAPI application serves a buildless browser interface and stores session state. Pollard provides execution controls, Hashrope preserves exact content versions, and Epicormic supplies behavioral probes. Deterministic task checks assess labels, routing, review requirements, and schema; model self-evaluation is not our source of truth.

The runnable fixture mode, live observations, replay, and controlled injected-drift demonstrations are labelled separately. A live call is required to demonstrate the Nebius integration; offline fixtures alone do not establish it.

## What we learned and limitations

Behavioral consistency is different from correctness. An unchanged configuration can be wrong, and a changed configuration needs evidence before it acts. The included public synthetic cases are a small demonstration, not a general safety certification. A hold affects future work; it cannot undo an action already completed.

The project uses preexisting libraries but introduces a new workflow, dataset, application, and interface during the hackathon. See `docs/NEW_WORK.md` for the precise disclosure.

## Verified results to fill before publication

- Final source commit and public repository: **pending**.
- Working public demo/test build and judge instructions: **pending**.
- Public YouTube video, duration below three minutes: **pending**.
- Exact live NVIDIA model and Nebius endpoint exercised: **pending live verification**.
- Evaluation count, repetitions, outcomes, errors, token usage, and estimated cost including qualification overhead: **pending actual evidence export**.
- Dependency versions and test result: **pending final verification**.

## Required product feedback — record actual experience

For each tool/model actually used, state its role, time to first successful call, one concrete strength, one reproducible rough edge or limitation, and whether we would use it again. Include the model identifier, relevant request settings, and sanitized error details where helpful. Do not describe onboarding or performance that has not been observed.

**Nebius Token Factory:** pending actual onboarding/inference experience.  
**NVIDIA Nemotron:** pending actual task outcomes and latency observations.  
**Nebius AI Cloud:** mark not used unless it is used in the final deployment.

**Built With:** Python, FastAPI, JavaScript, Nebius Token Factory, NVIDIA Nemotron, Pollard, Hashrope, Epicormic, SQLite. Remove or correct any item that differs from the final verified build.
