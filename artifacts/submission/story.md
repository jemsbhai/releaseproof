## Proof before permission

**ReleaseProof is a release workbench for developers whose AI agents use tools.** It connects measured behavior, a spending budget, and explicit approval to the exact version that will act.

The demonstrated workflow is support triage: classify an issue, choose its route, and prepare a response draft. Before an agent can update the isolated demo board, it must pass the full qualification suite and earn approval. The server checks that approval again before every board action.

**The defining moment:** a live NVIDIA model produced an approved, reviewable draft. I then changed its tools contract. The server refused the next action, left the board unchanged, and made no new provider call. The old result could not authorize the changed release.

[Try the fixture workbench](https://jemsbhai-releaseproof.hf.space) · [Inspect the actual live evidence](https://jemsbhai-releaseproof.hf.space/assets/observations.html) · [Watch the 2:24 walkthrough](https://youtu.be/1ZAR8XT7tiA) · [Read the MIT source](https://github.com/jemsbhai/releaseproof)

## Inspiration: the gap between testing and acting

A model score does not answer the whole release question. The prompt may change, the agent may gain a tool, the review policy may differ, or repeated behavior may shift. Qualification and monitoring also consume a budget.

I built ReleaseProof for the developer making that decision: **which exact agent may act, on what evidence, and within what spending limit?** My work on Pollard, Hashrope, and Epicormic supplied the foundations; this hackathon brought them together in a new application and a concrete issue-triage workflow.

The intended impact is practical: make a release refusal, approval, and subsequent change inspectable in one place before connecting an agent to a real issue tracker. The working demonstration is deliberately bounded; it does not claim production adoption or measured business savings.

## How it works

![ReleaseProof architecture: exact-contract governance, reservation before inference, and behavioral monitoring](https://raw.githubusercontent.com/jemsbhai/releaseproof/main/artifacts/submission/02-architecture.jpg)

Three controls share the same release context:

- **Smart budgeting:** reserve conservative input and capped-output cost before dispatch, reconcile observed usage afterward, reject work that cannot fit, and preserve capacity for validation and recovery. Local and hosted instances share a durable Firestore spending authority.
- **Smart governance:** Pollard enforces execution policy. Approval binds the server's exact current contract and qualification evidence; changing the model, prompt, tools, or policy invalidates it. A smoke test cannot authorize promotion.
- **Drift mitigation:** Epicormic compares repeated behavioral observations. A hold blocks future actions, while fallback still needs fresh qualification and approval. Completed actions remain in the audit trail. Hashrope retains versioned content and evidence, with SHA-256 fingerprints binding the release decision.

Python/FastAPI serves a buildless JavaScript interface, with SQLite session persistence and free CPU hosting on Hugging Face. **NVIDIA Nemotron models run remotely through Nebius Token Factory.** The application needs no local weights or GPU. The interface distinguishes live calls, recorded observations, synthetic fixtures, and injected faults.

## What the real calls showed

![Measured local results: original-policy candidates stayed blocked; a separate review-all policy passed 16 of 16](https://raw.githubusercontent.com/jemsbhai/releaseproof/main/artifacts/submission/03-measured-results.jpg)

**The gate found useful failures.** On the original selective-review policy, the equal-panel prompt-v1 runs passed 10/16 for Lightning and 11/16 for Super. With prompt v2, Lightning reached 13/16 and Super 14/16; a separate Ultra diagnostic reached 13/16. All stayed blocked. Invalid routing, missed review for forged authority, and unnecessary review on a benign question remained visible in the evidence.

I then tested an explicitly different workflow: **every draft requires human review.** Super with prompt v2 and this policy passed 16/16. Label and route checks were unchanged; the expected review flag became true for every case. This supports a more supervised workflow, not a better score on the original task. A later fresh qualification replicated 16/16.

After explicit approval, a held-out live call produced a draft marked for review. The tools edit and subsequent server refusal demonstrated that approval remains tied to current evidence. A live probe compared 16 fresh calls with 16 recorded baseline observations and detected no behavioral change (p = 1.0). Separately, an injected synthetic shift produced 80 observations, p = 0.001, and a hold. These are different experiments; the synthetic result is not provider drift.

**202 actual NVIDIA calls are accounted for:** 145 archived local evaluation calls and 57 in the independent public-browser demonstration. All pilots, failures, diagnostics, replications, board actions, and probes are retained. Total estimated token cost was $0.040669, covered by promotional credit. This is observed usage multiplied by recorded prices, not an invoice or a savings claim.

## Challenges and what I learned

Fluent output can still violate a workflow. Some drafts also invented product details that our deterministic label, route, schema, and review checks do not score. That limitation is visible, not repaired away. The eight-case public development panel is small; two samples per case cannot establish general safety, stability, or the cause of behavioral differences.

The engineering challenge was making the controls agree: preserve the recovery reserve while qualifying, bind approval to the exact evidence, refuse stale actions on the server, and retain every failure. The repository's **88 passing offline tests** check implementation behavior; they are separate from model-quality measurements.

Nebius's hosted endpoint let a CPU-only application exercise NVIDIA models, with usage and request identifiers supporting an inspectable record. Stronger structured-policy examples and revision-aware behavior information would make release decisions easier. Next steps are independently authored evaluation cases, draft-factuality checks, and a reviewed integration with a real issue tracker.

## Try it and inspect it

The public app currently runs the clearly labelled **fixture workflow**; live dispatch is off. Run the full suite, approve, process an issue, edit the tools, and try another governed action. Use the recorded-evidence link for actual Nebius outcomes and failures. No account or API key is needed for either path. The gallery and video show genuine captured application states, with live versus synthetic provenance labelled.

## Existing foundations and new work

Pollard 1.6.2, Hashrope 0.2.2, and Epicormic 0.2.0 are my preexisting libraries, used as actual dependencies. New hackathon work includes the server/provider integration, release workflow, shared budget integration, contract binding, interface, synthetic dataset, demo board, tests, evidence report, and presentation materials. Earlier Canopy team work inspired the problem; its frontend, benchmark, and application code were not copied. Codex assisted with research, implementation, tests, and drafts. The source is MIT licensed; dependencies retain their licenses.
