# Devpost submission copy

Project name: **ReleaseProof**
Tagline: **Know which agent release is allowed to act—and why.**
Track: **Best Apps and Agents**

This copy was prepared for the entrant's Devpost submission, confirmed at approximately 11:11 a.m. Eastern on October 30, 2026. The public video is published. Public live dispatch is now disabled; judges can use the fixture workbench and preserved actual live evidence.

## Inspiration

An agent can pass a test and still be running a different prompt, tool contract, or policy when it takes its next action. Switching models adds another decision: does the new configuration perform the actual workflow well enough, and what will qualification and monitoring cost?

I built ReleaseProof for that release decision. My existing work on Pollard, Hashrope, and Epicormic supplied the foundations. ReleaseProof brings them together in a new, runnable issue-triage application with a new interface and synthetic workload.

## What it does

ReleaseProof qualifies a candidate against eight public synthetic cases, records its exact model/prompt/tool/policy/evidence contract, and makes promotion explicit. An approved candidate can label, route, and save a draft response on an isolated four-issue demo board. The server checks approval again before each board action and refuses stale approval after the contract changes.

Its budget controller reserves worst-case call cost before dispatch, reconciles observed usage, and protects validation/recovery capacity. A shared durable ledger covers local and public instances. Pollard enforces execution policy; Hashrope preserves versioned content; Epicormic compares repeated behavioral observations and can hold future actions. A hold never claims to undo an action already completed.

## How I built it

A compact Python/FastAPI server serves a buildless JavaScript interface and persists session state in SQLite. Live inference uses NVIDIA open models through Nebius Token Factory's OpenAI-compatible chat-completions endpoint. Model weights stay remote; the project needs no GPU or local model download. Firestore provides the shared spending authority, and a free CPU Hugging Face Docker Space hosts the app.

Deterministic checks assess labels, routes, human-review requirements and output schema. Full-suite qualification is required: a four-case smoke test cannot authorize promotion. Canonical SHA-256 fingerprints bind approvals to the tested contract; Hashrope versions retain the underlying content. The UI distinguishes live calls, synthetic fixtures, recorded observations and injected faults.

## What actually happened

The gate refused real model outputs that looked plausible but violated the workflow. Under prompt v1, Lightning passed 10 of 16 checks and Super 11 of 16 in the equal-panel comparison. Under the revised v2 prompt, Lightning passed 13 of 16 and Super 14 of 16. Neither candidate met the full-pass threshold, and neither result was silently repaired or promoted. Separate one-repetition Lightning pilots and every failure are retained.

The failures were useful: invalid routing, missing review for forged authority, and unnecessary review for a benign credential question. Some fluent drafts also invented product details. That last problem is outside our current deterministic checks, and the evidence report says so. A separate Ultra diagnostic also failed, at 13/16.

I then tested one explicitly different policy: every draft requires human review. Super with prompt v2 and this reviewed-drafts policy passed 16/16. Label and route checks remained unchanged; the expected review flag became true for every case. This is a more supervised workflow, not autonomous-triage success or a repaired original score.

After explicit approval, a fresh held-out call saved a draft on the local board. Changing the tools contract invalidated approval; the next action was refused without changing the board or making a provider call. A fresh qualification under the same reviewed-drafts contract again passed 16/16. Its live probe compared 16 new calls with 16 recorded baseline observations and found no detected behavioral change (p = 1.0). With only two samples per issue, that is not a stability guarantee. Two earlier storage-headroom refusals before dispatch are also preserved.

The complete archived local evaluation contains 145 unique provider calls and 81,949 tokens at $0.031828 estimated token cost, including pilots, all failures, the diagnostic, qualification replication, board action and fresh probe calls. Independent browser demonstrations are recorded separately. This is a tiny public development panel, not a general model benchmark; token-cost estimates are not invoices.

The recorded-evidence page is available without credentials and makes no new inference calls. The labelled fixture mode demonstrates the complete approval, board action, stale-approval refusal, and controlled injected-drift workflow even when a live candidate fails qualification or live access is unavailable.

## Product feedback

Nebius Token Factory accepted the declared JSON-output requests, disabled-thinking setting, zero temperature and bounded output tokens in our recorded calls. Its hosted endpoint let a small CPU app exercise NVIDIA models without downloading weights. Returned usage and request identifiers helped us preserve auditable observations and estimate costs. These successful requests do not imply successful task decisions.

The NVIDIA models produced useful structured triage responses, but our small adversarial panel exposed review-flag and policy-following failures. We would value stronger, documented structured-policy examples and revision-aware behavior information. Prompt v2 improved the measured counts, but its declared prompt change cannot be described as silent provider drift or attributed solely to the model.

The entrant rates Nebius recommendation 6/10 and the experience versus Ollama and Lambda 7/10. These are personal ratings, not a measured cross-provider benchmark. Nebius AI Cloud and Tavily were not used.

## What I learned and what comes next

Behavioral consistency and correctness are different. An unchanged configuration can be wrong; a changed configuration needs current evidence before it acts. Small repeated probes have low statistical power and cannot establish general safety or the cause of a difference.

Next steps are a larger independently authored evaluation set, stronger draft-factuality checks, and better evidence for workflow-specific policy decisions. The current board uses known-answer synthetic cases and does not establish correctness on arbitrary real issues. All responses remain drafts; nothing is sent to a real customer or issue tracker.

## Existing foundations and new work

Pollard 1.6.2, Hashrope 0.2.2 and Epicormic 0.2.0 are my preexisting libraries, used as actual dependencies. New hackathon work includes ReleaseProof's server and provider integration, qualification/promotion workflow, budget ledger integration, contract binding, browser interface, synthetic dataset, board, tests, evidence report and documentation. Earlier Canopy team work inspired the problem; its frontend, benchmark and application code were not copied. Codex assisted with research, implementation, tests and drafts. The source is MIT licensed; dependencies retain their own licenses.

## Form links and technologies

- Public application: https://jemsbhai-releaseproof.hf.space
- Recorded live evidence: https://jemsbhai-releaseproof.hf.space/assets/observations.html
- Public source: https://github.com/jemsbhai/releaseproof
- Judge instructions: https://github.com/jemsbhai/releaseproof/blob/main/docs/JUDGE_GUIDE.md
- New-work disclosure: https://github.com/jemsbhai/releaseproof/blob/main/docs/NEW_WORK.md
- Public YouTube video (2:24): https://youtu.be/1ZAR8XT7tiA

Built With: Python, FastAPI, JavaScript, Nebius Token Factory, NVIDIA Nemotron, Pollard, Hashrope, Epicormic, SQLite, Google Cloud Firestore, Hugging Face.

Exact live model IDs: `nvidia/Nemotron-3_5-Lightning`, `nvidia/nemotron-3-super-120b-a12b`, and `nvidia/Nemotron-3-Ultra-550b-a55b`. The reviewed-drafts candidate is Super. Endpoint: `https://api.tokenfactory.nebius.com/v1/chat/completions`. Declared settings: `temperature=0`, JSON object response format, thinking disabled, `max_tokens=768` under the balanced strategy. No fine-tuning. Latest offline verification: 88 passing tests at source `823e4a6`; offline tests do not measure model quality.
