# Judge guide

ReleaseProof helps a developer decide whether an exact issue-triage agent release may act. It combines full-workflow qualification, a protected inference budget, explicit approval, and future-action holds. The board is isolated application state; it does not contact a real customer or modify GitHub issues.

- Application: [ReleaseProof demo](https://jemsbhai-releaseproof.hf.space)
- Source: [jemsbhai/releaseproof](https://github.com/jemsbhai/releaseproof)
- Track: **Best Apps and Agents**
- Publication status when this guide was drafted: local fixture verification and public source/MIT-license verification complete; final public-host workflow verification, live Nebius evidence, and public demo video **pending**. Those items must be verified before final submission.

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

Live inference uses NVIDIA Nemotron through Nebius Token Factory. It is enabled only when the server has provider credentials, explicit live enablement, and a configured, healthy shared Firestore spending authority. This also applies to local reproduction: SQLite alone supports fixtures, with no live opt-in or fallback. A fixture approval cannot authorize a live call. Select **Live Nebius** when available, run the full suite, and inspect actual observed outcomes before promotion; a failed result must remain a failed result.

For an optional live behavioral comparison, first qualify with **2 repetitions**. The live probe obtains fresh provider observations under that same contract and compares label, route, and human-review decisions with the original recorded calls. Draft wording is excluded. The analysis replays recorded observations without making extra inference requests. Two samples per case have low statistical power: no detected change is not proof of equivalence or safety. Failed/incomplete observations may hold the release independently of the statistical verdict.

Live metrics and video are **pending verification** at guide creation; fixture counts are not substitutes. Authenticated catalog and price checks confirmed the three candidate IDs and rates, but did not run inference. [Recorded rates](EVALUATION.md#verified-catalog-and-price-assumptions) exclude applicable taxes. Token-based cost estimates include qualification and probe overhead, and are not authoritative invoices. Public live access may refuse work once the shared allowance is exhausted or the spending authority is unavailable.

## Boundaries and inspection

- Sessions are limited to 100 accepted actions and 2 MiB of stored state; conservative admission estimates can reject large suites before dispatch. Evidence stays exportable after quota refusal. An explicit reset does not renew the lifetime action count or global inference budget.
- Hashrope preserves versioned audit content; its fingerprint is noncryptographic. SHA-256 seals provide the recorded integrity checks. A fingerprint does not establish truth.
- Epicormic measures behavioral differences, not general task correctness, security, or the cause of a change. Declared configuration changes and injected faults are labelled separately from live observations.
- No Tavily integration or city-attendance award is claimed. Preexisting libraries and the new application work are disclosed in [New work](NEW_WORK.md); dependency license texts are in [Notices](../THIRD_PARTY_NOTICES.md).

For local reproduction, use the commands in [README](../README.md). The tests are offline and do not spend API credits.
