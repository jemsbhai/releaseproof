# Judge guide

ReleaseProof helps a developer decide whether an exact issue-triage agent release may act. It combines full-workflow qualification, a protected inference budget, explicit approval, and future-action holds. The board is isolated application state; it does not contact a real customer or modify GitHub issues.

- Application: [ReleaseProof demo](https://jemsbhai-releaseproof.hf.space)
- Source: [jemsbhai/releaseproof](https://github.com/jemsbhai/releaseproof)
- Track: **Best Apps and Agents**
- Recorded evidence: [actual model calls, failures and workflow decisions](https://jemsbhai-releaseproof.hf.space/assets/observations.html). This read-only page requires no account or inference access.
- Public video: [ReleaseProof walkthrough — 2:24](https://youtu.be/1ZAR8XT7tiA), using actual captured application states with shortened pauses and disclosed synthesized narration.

**Current judge path:** public live inference was disabled after the confirmed submission on October 30, 2026. The fixture walkthrough below, recorded live-evidence report and public video remain available without credentials. The recorded results preserve the actual Nebius calls, including failures; inspecting them does not make new calls. Local live reproduction requires the reader's own configured credentials and shared spending authority.

**Availability:** Nebius lists this Super model for serverless retirement on November 9, 2026, without automatic rerouting. No migration was performed. Use the preserved recorded evidence and fixture workflow during later judging; fresh Super calls cannot be promised. [Official notice](https://docs.tokenfactory.nebius.com/model-deprecations-november-2026.md).

## Reproducible fixture walkthrough

No account or API key is needed for the labelled fixture workflow. If a free host is waking up, allow it to finish loading. A browser receives an isolated session.

1. Keep **Synthetic fixture** selected. Open **Qualification**, choose **Full suite** and **1 repetition**, then run it. Expect eight synthetic checks, including security, forged-authority, instruction-injection, and clarification cases. These deterministic results do not measure an NVIDIA model. The quick four-case suite is a smoke test only and cannot authorize a release.
2. Inspect a case's expected decision, actual result, source and usage. Return to Overview and choose **Approve this candidate**. Approval is bound to the exact current contract and evidence.
3. Open the issue board and process the first issue. Its label becomes `bug`, its route `engineering`, and a draft is saved. Nothing is sent externally. These four board cases have known gold decisions that the server checks before applying a demo action.
4. Under governance, edit the prompt version. The old approval becomes invalid. On the board, choose **Try governed action** to inspect a real server refusal. The earlier board result remains; the next issue is not changed. Inspect the Pollard refusal in Evidence & activity.
5. Run the **Full suite** again and explicitly approve the new candidate. Compare the two recorded runs: both retain their source and configuration identity. Fixture comparisons demonstrate the workflow, not relative model quality.
6. Run **Inject a behavior shift** in the controlled canary selector. The repeated observations are synthetic fault injection. Inspect the hold, then try the next board action. The hold controls future actions and never claims to undo the completed issue.
7. Choose **Requalify**, inspect the new full result, and explicitly approve again. A fallback instead restores a previously approved configuration in the same source mode and still requires fresh qualification and approval.
8. Export evidence. To demonstrate budget refusal, lower the session allowance below the required call reservation and rerun a qualification. The decision log explains the refused dispatch. Restore a usable allowance before continuing.

## Live evaluation

The recorded live evaluation used NVIDIA Nemotron through Nebius Token Factory. Public live dispatch is currently off. For independent local reproduction, live inference requires provider credentials, explicit live enablement, and a configured, healthy shared Firestore spending authority. SQLite alone supports fixtures, with no live opt-in or fallback. A fixture approval cannot authorize a live call. In an enabled local deployment, select **Live Nebius**, run the full suite, and inspect actual observed outcomes before promotion; a failed result must remain a failed result.

For an optional live behavioral comparison, first qualify with **2 repetitions**. The live probe obtains fresh provider observations under that same contract and compares label, route, and human-review decisions with the original recorded calls. Draft wording is excluded. The analysis replays recorded observations without making extra inference requests. Two samples per case have low statistical power: no detected change is not proof of equivalence or safety. Failed/incomplete observations may hold the release independently of the statistical verdict.

Actual Lightning, Super and Ultra calls, including every failed run, are preserved in [Evaluation](EVALUATION.md#recorded-live-results--october-30-2026). Original-policy candidates failed the gate. The selected demonstration uses a different **reviewed-drafts policy** under which every draft requires human review. This changes expected review flags and is not autonomous triage success. [Recorded rates](EVALUATION.md#verified-catalog-and-price-assumptions) exclude applicable taxes. Token-based cost estimates include failed calls and qualification/probe overhead and are not authoritative invoices. Public live access may refuse work once the shared allowance is exhausted or the spending authority is unavailable.

### Reproduce the reviewed-drafts candidate

These reproduction steps require an enabled local deployment and model availability; the public host currently offers the fixture path and recorded evidence. Start with a fresh workspace. Under **Test a contract change**, click **Edit prompt** once (v2) and **Edit policy** once (v2). The policy requires review for every draft; the original policy's failed results remain separate. Select **Nemotron 3 Super**, **Live Nebius**, **Full suite** and **2 repetitions**. Run qualification and inspect every case. The recorded run passed 16/16, but a fresh run may differ; approve only if the current server result passes.

If qualified, click **Approve this candidate**, then process the first board issue. The recorded held-out action produced a `bug`/`engineering` draft marked for human review; no message was sent. A fresh live probe compares repeated observations under the same contract. The archived probe used 16 new calls against 16 baseline observations and found no detected change (p = 1.0); this small panel is not a stability guarantee. To inspect stale-approval refusal, choose **Edit tools**, then **Try governed action**. The previous draft remains and the next issue is unchanged. The server must refuse the changed contract.

The session evidence limit can refuse a large follow-up suite/probe before dispatch. The evaluation retained two such refusals and exported prior evidence, then used a fresh workspace with the same shared spending authority. A fresh workspace does not reset the global budget. Keep saved observations separate from any new reproduction and use the recorded report if live inference is unavailable.

## Boundaries and inspection

- Sessions are limited to 100 accepted actions and 2 MiB of stored state; conservative admission estimates can reject large suites before dispatch. Evidence stays exportable after quota refusal. An explicit reset does not renew the lifetime action count or global inference budget.
- Hashrope preserves versioned audit content; its fingerprint is noncryptographic. SHA-256 seals provide the recorded integrity checks. A fingerprint does not establish truth.
- Epicormic measures behavioral differences, not general task correctness, security, or the cause of a change. Declared configuration changes and injected faults are labelled separately from live observations.
- No Tavily integration or city-attendance award is claimed. Preexisting libraries and the new application work are disclosed in [New work](NEW_WORK.md); dependency license texts are in [Notices](../THIRD_PARTY_NOTICES.md).

For local reproduction, use the commands in [README](../README.md). The tests are offline and do not spend API credits.
