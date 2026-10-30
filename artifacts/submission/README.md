# ReleaseProof visual submission

Eight original 1800 × 1200 (3:2) gallery panels, prepared October 30, 2026 before the hackathon deadline. Every JPEG is below Devpost's 5 MB limit. HTML/CSS layouts are rendered through the browser screenshot API; embedded application images are unmodified genuine CUA captures from the completed demonstration. No UI state, outputs, or measurements were fabricated.

The simpler [project-card thumbnail](thumbnail.jpg) uses the same visual identity with larger text for gallery-card legibility. Devpost now includes all eight captioned images, this thumbnail, a revised pitch, and the story's two embedded diagrams. Public signed-out verification retained the submitted status.

1. [Cover: proof before permission](01-cover.jpg)
2. [Architecture and the three controls](02-architecture.jpg)
3. [Measured local model results](03-measured-results.jpg)
4. [Recorded public-browser qualification](04-qualification.jpg)
5. [Actual held-out draft](05-reviewed-draft.jpg)
6. [Stale-approval refusal](06-stale-approval.jpg)
7. [Budget reservation and reconciliation](07-budget.jpg)
8. [Controlled synthetic drift](08-drift.jpg)

The local results chart and public-browser screenshots describe separate runs. Original-policy results stay separate from the distinct policy requiring review of every draft. Live and synthetic provenance is labelled in each image and in the upload captions. The app's current public mode is fixture-only; screenshots preserve recorded live work from earlier the same day.

Source captures are copied in `screens/`. The original capture manifest is retained locally under `artifacts/video/raw/current/manifest.json`; the published video timeline and complete public-browser evidence export corroborate the workflow. Source measurements are in `artifacts/live-evaluation/summary-v2.json` and `artifacts/video/public-live-complete57.json`.

Rebuild layout HTML with `python artifacts/submission/build_gallery.py`, serve this directory locally, and capture each page with the browser's full-page screenshot API. `story.md` contains the revised Devpost story; `captions.json` contains gallery captions. All eight images were visually inspected for clipping, readability, provenance, and consistency with the evidence. No additional model calls or paid services were used.
