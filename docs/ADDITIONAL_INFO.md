# Devpost additional-information answers

Draft `1271959-releaseproof` / project `releaseproof-yr8e0t`. Entrant ratings below were explicitly supplied by the user. Technical claims are based on recorded application evidence; no personal reasons or comparative benchmarks are invented.

## NVIDIA model variant and reason for choosing it

The working reviewed-drafts candidate uses `nvidia/nemotron-3-super-120b-a12b` through Nebius Token Factory's `https://api.tokenfactory.nebius.com/v1/chat/completions` endpoint. The model classifies synthetic software issues, selects a route, marks review requirements and writes an acknowledgement draft. Prompt v2 with the explicit policy that every draft requires human review passed 16/16 checks across two repetitions of eight public synthetic cases. This is a different, more supervised contract from the original policy; it is not autonomous-triage success.

We also exercised `nvidia/Nemotron-3_5-Lightning` and `nvidia/Nemotron-3-Ultra-550b-a55b`. All original-policy candidates failed the full-pass gate; those results are retained. Super was selected for the reviewed-drafts demonstration because that exact contract passed the bounded qualification. Passing these cases is not a general safety or correctness claim.

## Model quality rating — 1 to 10

**6/10 — entrant answer.** The recorded small-panel outcomes explain the limits: useful structured responses, but review-flag and policy-following failures under the original policy; some drafts invented product details. The all-drafts-reviewed contract passed its bounded checks. These observations are narrow and do not constitute a general model rating benchmark.

## Prompt engineering or fine-tuning

We used structured triage instructions, explicit label-to-route mappings and independent human-review rules. Issue content is untrusted and cannot grant authority. The prompt requests only the JSON fields `label`, `route`, `draft` and `needs_review`; declared settings were temperature zero, JSON-object response format, thinking disabled and a 768-token output bound. All recorded model calls accepted these settings. No fine-tuning was performed.

Prompt v1 remains preserved. Prompt v2 clarified the mapping, review triggers and restrictions on invented facts/actions; it did not inject corpus answers or repair output. The later policy v2 requires review for every draft and is recorded as a distinct contract with changed expected review flags. The label and route checks remain unchanged.

## Comparisons with other models

Under prompt v1/policy v1, the equal-panel comparison was Lightning 10/16 versus Super 11/16. Under prompt v2/policy v1 it was Lightning 13/16 versus Super 14/16. Each comparison used the same eight cases twice with matching prompt, tools, policy and sampling settings. Separate Lightning pilots are excluded from those denominators. A separate Ultra v2 diagnostic scored 13/16; it was not part of the planned Lightning/Super comparison. Every failure remains in the evidence report.

Super's 16/16 reviewed-drafts run uses policy v2, requiring human review for all drafts. It must not be presented as the same task or a direct model-only improvement. No controlled Ollama or Lambda benchmark was run for this project.

## Most valuable Nebius capabilities

The OpenAI-compatible Token Factory endpoint let a small CPU-hosted application exercise NVIDIA open models without downloading weights or installing a GPU runtime. The responses supplied usage fields and request identifiers that we retained alongside actual outputs. This supported observed-token cost estimates and traceable release evidence within the project's 4 GB limit. Nebius AI Cloud, Serverless Jobs and Serverless Endpoints were not used.

## Recommendation rating — 1 to 10

**6/10 — entrant answer.** No additional personal reason was supplied; do not invent one.

## Experience compared with prior cloud/local tools — 1 to 10

**7/10, compared with Ollama and Lambda — entrant answer.** This is the user's personal experience rating, not a measured cross-provider comparison.

## Improvements for Nebius or NVIDIA tooling

Our actual requests returned valid transport responses and usable usage data, but model task failures remained: forged authority was sometimes classified without required review, and benign credential questions sometimes received unnecessary review. More documented examples for structured policy-following, human-review flags and adversarial issue content would help builders understand and evaluate these tradeoffs.

The application had to implement a durable aggregate spending cap with worst-case reservations before dispatch and reconciliation afterward. An account-level hard spending limit with clear reservation/usage semantics would simplify this use case. For billing cleanup, the inspected card editor exposed replacement, but we did not find removal of the only saved card; clearer removal controls or documented prerequisites would help. These are observations and requests, not claims that undocumented capabilities cannot exist.

## What we hope to see next from Nemotron

Stronger consistency on explicit policy constraints, clearer revision-aware behavior information, and structured-output examples that distinguish formatting success from workflow correctness. Our own next steps include a larger independently authored test set and factuality checks for drafts, rather than assuming schema compliance makes the content true.

## AI tools used

Codex AI assistance was used for rules research, architecture discussion, implementation, synthetic fixture authoring, automated tests and documentation drafts. The entrant selected the project and remains responsible for the submission and its claims. The fixture dataset is labelled AI-authored synthetic content. No other tool usage is claimed here.

## Learning from participation — None / Moderate / Significant

**Significant — entrant answer.**

## Career value of AI — Yes / No

**Yes — entrant answer.**

## Awards and attendance

Track: **Best Apps and Agents**. No Tavily usage or IRL city attendance is claimed. Adult, US solo eligibility and no excluded conflicts were previously confirmed. Pollard, Hashrope and Epicormic are preexisting libraries; the integrated ReleaseProof application is new hackathon work, as detailed in `docs/NEW_WORK.md`.
