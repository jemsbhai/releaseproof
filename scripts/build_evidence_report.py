"""Build an offline, allowlisted report of recorded live observations.

No provider calls, approval actions, credentials, session capabilities, or operator
budget state are read or included. Original evaluation artifacts are preserved.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts" / "live-evaluation"
OUT = ROOT / "web" / "recorded-evidence"


def pick(value: dict, keys: tuple[str, ...]) -> dict:
    return {key: value[key] for key in keys if key in value}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def role_for(name: str) -> str:
    if "pilot" in name:
        return "pilot; excluded from equal-panel comparison"
    if "diagnostic" in name:
        return "separate diagnostic; excluded from planned Lightning/Super comparison"
    if "reviewed-drafts" in name:
        return "different policy: every draft requires human review; not autonomous triage"
    if "replication" in name:
        return "same reviewed-drafts contract, fresh qualification for live probe; separate replication"
    return "equal-panel comparison within its declared prompt and policy"


def render() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    runs = []
    seen_qualifications = set()
    for manifest_path in sorted(SOURCE.glob("*-calls.json")):
        name = manifest_path.stem.removesuffix("-calls")
        export_path = SOURCE / f"{name}.json"
        if not export_path.exists():
            continue
        original = json.loads(export_path.read_text(encoding="utf-8-sig"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        state = original.get("state", {})
        qualification = state.get("qualification")
        if not qualification or qualification.get("mode") != "live":
            continue
        # A manifest must describe this qualification, not an earlier run in its history.
        if manifest.get("qualification_id") != qualification.get("id"):
            raise ValueError(f"Mismatched qualification in {name}")
        # Contract mutations and workflow snapshots can retain the previous result.
        if qualification["id"] in seen_qualifications or not manifest.get("calls"):
            continue
        if len(manifest["calls"]) != qualification["total"]:
            raise ValueError(f"Incomplete qualification call manifest in {name}")
        seen_qualifications.add(qualification["id"])
        q = pick(qualification, ("id", "mode", "status", "passed", "total", "accuracy", "latency_ms", "tokens", "cost_usd", "created_at", "fingerprint", "suite", "repetitions"))
        q["cases"] = [pick(case, ("id", "title", "expected", "actual", "passed", "latency_ms", "input_tokens", "output_tokens", "cost_usd", "source", "error")) for case in qualification["cases"]]
        contract = pick(manifest.get("contract", {}), ("model_id", "prompt_version", "tool_version", "policy_version", "provider", "endpoint", "prompt", "policy", "tool_limits", "sampling", "registry_digest", "application_revision", "evidence_digest", "libraries"))
        calls = [pick(call, ("issue_id", "source", "result_digest", "selected_model", "provider_model", "provider_request_id", "finish_reason", "usage", "text", "latency_ms", "passed", "error")) for call in manifest.get("calls", [])]
        public = {
            "format": "releaseproof-public-recorded-observation-v1",
            "notice": "Recorded live NVIDIA calls on Nebius Token Factory. Reading this file makes no fresh calls and grants no approval. Small public synthetic panel; not a general benchmark or safety certification.",
            "source_artifact": str(export_path.relative_to(ROOT)).replace("\\", "/"),
            "captured_at": manifest.get("captured_at"),
            "role": role_for(name),
            "contract": contract,
            "qualification": q,
            "provider_calls": calls,
        }
        (OUT / f"{name}.json").write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        runs.append((name, public))

    rows, sections = [], []
    total_calls = 0
    total_cost = 0.0
    for name, run in runs:
        q, c = run["qualification"], run["contract"]
        total_calls += len(run["provider_calls"])
        total_cost += float(q["cost_usd"])
        link = f"recorded-evidence/{name}.json"
        rows.append(f'<tr><th><a href="#{esc(name)}">{esc(name)}</a></th><td>{esc(c.get("model_id"))}</td><td>prompt v{esc(c.get("prompt_version"))}<br>policy v{esc(c.get("policy_version"))}</td><td>{q["passed"]}/{q["total"]}</td><td>{esc(q["status"])}</td><td>{q["tokens"]:,}</td><td>${q["cost_usd"]:.6f}</td><td>{q["latency_ms"]/1000:.2f}s</td></tr>')
        details = []
        for idx, case in enumerate(q["cases"]):
            verdict = "PASS" if case["passed"] else "FAIL"
            details.append(f'<details><summary><strong class="{verdict.lower()}">{verdict}</strong> {idx+1}. {esc(case["id"])} — {esc(case["title"])}</summary><p>{esc(case.get("error") or "Passed the declared deterministic checks.")}</p><h4>Expected decision</h4><pre>{esc(json.dumps(case.get("expected"), indent=2))}</pre><h4>Actual model output</h4><pre>{esc(json.dumps(case.get("actual"), ensure_ascii=False, indent=2))}</pre><p>{esc(case.get("input_tokens", 0))} input tokens · {esc(case.get("output_tokens", 0))} output tokens · ${case.get("cost_usd", 0):.6f} estimated</p></details>')
        sections.append(f'<section id="{esc(name)}"><p class="eyebrow">Recorded live · {esc(run["role"])}</p><h2>{esc(name)}</h2><p><code>{esc(c.get("model_id"))}</code> · prompt v{esc(c.get("prompt_version"))} · policy v{esc(c.get("policy_version"))} · {esc(q.get("created_at"))}</p><p><strong>{q["passed"]}/{q["total"]} checks passed; qualification {esc(q["status"])}.</strong> <a href="{esc(link)}" download>Download sanitized observations and raw provider responses (JSON)</a></p><details><summary>Exact recorded contract and settings</summary><pre>{esc(json.dumps(c, ensure_ascii=False, indent=2))}</pre></details>{"".join(details)}</section>')

    workflow, workflow_html = [], []
    qualification_names = {name for name, _ in runs}
    for export_path in sorted(SOURCE.glob("*.json")):
        name = export_path.stem
        if name in qualification_names or name.endswith("-calls") or name.startswith("summary"):
            continue
        packet = json.loads(export_path.read_text(encoding="utf-8-sig"))
        if packet.get("format") == "releaseproof-operator-observation-v1":
            item = pick(packet, ("recorded_at", "action", "scenario", "http_status", "message", "provider_dispatched"))
            item["name"] = name
            workflow.append(item)
            workflow_html.append(f'<details><summary>{esc(name)} — refused before dispatch</summary><p>{esc(item.get("message"))}</p><pre>{esc(json.dumps(item, ensure_ascii=False, indent=2))}</pre></details>')
            continue
        state = packet.get("state")
        if not state:
            continue
        item = {"name": name, "status": state.get("status"), "mode": state.get("mode"),
                "candidate": state.get("candidate"), "active": state.get("active"),
                "governance": state.get("governance"), "drift": state.get("drift"),
                "latest_event": state.get("events", [])[-1:]}
        item["board"] = [pick(issue, ("id", "title", "labels", "route", "draft", "status", "source")) for issue in state.get("board", [])]
        manifest_path = SOURCE / f"{name}-calls.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            item["provider_calls"] = [pick(call, ("issue_id", "source", "result_digest", "selected_model", "provider_model", "provider_request_id", "finish_reason", "usage", "text", "latency_ms", "passed", "error")) for call in manifest.get("calls", [])]
        workflow.append(item)
        event = item["latest_event"][0] if item["latest_event"] else {}
        workflow_html.append(f'<details><summary>{esc(name)} — {esc(event.get("title", item["status"]))}</summary><p>{esc(event.get("detail", ""))}</p><pre>{esc(json.dumps(item, ensure_ascii=False, indent=2))}</pre></details>')
    (OUT / "workflow.json").write_text(json.dumps({"format": "releaseproof-public-workflow-observations-v1", "notice": "Saved workflow snapshots and refusals. No new inference or authorization. Board entries are synthetic, drafts are not sent, and every draft under policy v2 requires human review.", "snapshots": workflow}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_html = ""
    summary_path = SOURCE / "summary-v2.json"
    if summary_path.exists():
        summary = pick(json.loads(summary_path.read_text(encoding="utf-8-sig")), ("format", "captured_at", "scope", "source", "source_commits", "total_actual_calls", "qualification_calls", "heldout_execution_calls", "new_live_probe_calls", "all_request_ids_unique", "all_finish_reasons", "total_tokens", "total_estimated_cost_usd"))
        (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary_html = f'<p><strong>Complete archived local workflow: {summary["total_actual_calls"]} unique provider calls, {summary["total_tokens"]:,} tokens, ${summary["total_estimated_cost_usd"]:.6f} estimated.</strong> This includes all qualification calls plus one held-out board call and 16 fresh live-probe calls. The probe compared 16 new observations with 16 recorded baseline observations; it found no detected change on that small panel, not a general stability guarantee. Independent browser demonstrations are separate. <a href="recorded-evidence/summary.json" download>Download provenance and totals</a>.</p>'
    browser_html = ""
    browser_path = ROOT / "artifacts" / "video" / "public-live-complete57.json"
    if browser_path.exists():
        state = json.loads(browser_path.read_text(encoding="utf-8-sig"))["state"]
        history = []
        for qualification in state.get("qualification_history", []):
            q = pick(qualification, ("id", "mode", "status", "passed", "total", "accuracy", "latency_ms", "tokens", "cost_usd", "created_at", "fingerprint", "suite", "repetitions", "model_id", "model_label", "config_versions", "source_note"))
            q["cases"] = [pick(case, ("id", "title", "expected", "actual", "passed", "latency_ms", "input_tokens", "output_tokens", "cost_usd", "source", "error")) for case in qualification.get("cases", [])]
            history.append(q)
        browser = {"format": "releaseproof-public-browser-observations-v1", "notice": "Independent public-browser demonstration; not pooled into the planned local model comparison. Provider request IDs are absent from the application's normal public export. Saved observations, not fresh calls.", "qualification_history": history, "live_calls": state.get("metrics", {}).get("live_calls"), "estimated_cost_usd": state.get("budget", {}).get("spent_usd"), "board": [pick(issue, ("id", "title", "labels", "route", "draft", "status", "source")) for issue in state.get("board", [])], "drift": state.get("drift"), "governance": state.get("governance"), "latest_event": state.get("events", [])[-1:]}
        (OUT / "public-browser.json").write_text(json.dumps(browser, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        browser_rows = "".join(f'<li>{esc(q["model_label"])} · {esc(q["config_versions"])}: {q["passed"]}/{q["total"]}, {esc(q["status"])}.</li>' for q in history)
        browser_html = f'<section><p class="eyebrow">Independent public-browser demonstration</p><h2>A separately recorded UI session</h2><p>{browser["live_calls"]} actual calls, ${browser["estimated_cost_usd"]:.6f} estimated, including qualification, a held-out draft and fresh probes. These results are not pooled into the planned local comparisons above. The session also recorded a stale-approval refusal. Every failed case is retained in <a href="recorded-evidence/public-browser.json" download>the sanitized browser-session download</a>.</p><ul>{browser_rows}</ul><p>The reviewed-drafts policy requires human review for every draft. Its successful gate is a different task contract from the failed original-policy runs. The browser probe found no detected change on its small panel; the same limitations apply.</p></section>'

    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Recorded live evidence · ReleaseProof</title>
<style>body{{margin:0;background:#f5f4ee;color:#182521;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1180px;margin:auto;padding:32px 24px 80px}}a{{color:#145e48}}nav{{display:flex;gap:24px;margin-bottom:44px}}h1{{font-size:clamp(32px,5vw,54px);line-height:1.1;max-width:850px}}h2{{line-height:1.25}}.eyebrow{{text-transform:uppercase;font-size:12px;letter-spacing:.1em;font-weight:750;color:#566d62}}.intro{{max-width:880px;font-size:19px}}.notice{{border-left:4px solid #bf8b27;background:#fff8e9;padding:16px 20px}}section{{margin-top:32px;background:white;border:1px solid #d4ddd5;border-radius:16px;padding:24px}}.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #d4ddd5}}td code,code{{overflow-wrap:anywhere}}details{{border-top:1px solid #d4ddd5;padding:15px 0}}summary{{cursor:pointer}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7f3;padding:18px;border-radius:8px;font-size:13px}}.fail{{color:#9a362c}}.pass{{color:#126448}}footer{{margin-top:32px;color:#566d62}}</style></head>
<body><main><nav><a href="/">← Open workbench</a><a href="https://github.com/jemsbhai/releaseproof">Source and methods</a></nav>
<p class="eyebrow">ReleaseProof · archived observations · October 30, 2026</p><h1>Real calls. Every failure. A bounded release decision.</h1>
<p class="intro">These are saved results from NVIDIA Nemotron on Nebius Token Factory, using eight public synthetic issue-triage cases. This page works without an API key and does not make new inference calls or authorize a release.</p>
<p><strong>Future live availability:</strong> the tested Super serverless model is scheduled to retire November 9, 2026. These recorded observations and the fixture workflow remain inspectable without that model. No model migration was performed. <a href="https://docs.tokenfactory.nebius.com/model-deprecations-november-2026.md">Nebius retirement notice</a>.</p>
<p class="notice"><strong>Recorded evidence, not a live status dashboard.</strong> Passing a small panel is not a safety certification. Prompt v1 and v2 are different declared configurations; differences between them are not silent provider drift. Policy v2 requires human review for <em>every</em> draft and changes the expected review flag: its result is not autonomous triage success or the same task as policy v1. Pilots and the Ultra diagnostic are separate from planned equal-panel comparisons. All attempts below remain visible.</p>
<p><strong>{total_calls} recorded qualification calls · ${total_cost:.6f} estimated qualification cost.</strong> Costs use observed tokens and declared prices, exclude taxes, and are not invoices. Workflow/probe calls, when recorded separately, are not included in this qualification-only total.</p>
{summary_html}
<div class="table-wrap"><table><thead><tr><th>Run</th><th>Selected model</th><th>Contract</th><th>Passed</th><th>Result</th><th>Tokens</th><th>Est. USD</th><th>Suite time</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<p>Sequential suite times include local orchestration and spending-ledger overhead. They are not a controlled speed benchmark. The JSON downloads retain model-returned text, request identifiers, settings and per-case failures. Displayed drafts may contain unsupported claims: free-text truth is outside these deterministic checks.</p>
<section><p class="eyebrow">Separate workflow evidence</p><h2>Approval, draft board, probes and refusals</h2><p>These snapshots retain the actual release decisions, completed board state and refusals, including storage refusals before dispatch. A later hold does not undo a completed draft. <a href="recorded-evidence/workflow.json" download>Download sanitized workflow observations (JSON)</a>.</p>{"".join(workflow_html)}</section>
{browser_html}
{"".join(sections)}
<footer>Pollard 1.6.2 · Hashrope 0.2.2 · Epicormic 0.2.0. The integrated ReleaseProof application is new hackathon work; these three libraries predate it. No customer issues or external issue writes are used.</footer>
</main></body></html>'''
    (ROOT / "web" / "observations.html").write_text(document, encoding="utf-8")
    print(f"Built recorded evidence report: {len(runs)} runs, {total_calls} qualification calls, ${total_cost:.6f} estimated.")


if __name__ == "__main__":
    render()
