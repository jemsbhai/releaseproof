"""Operator helper: dispatch only through ReleaseProof; archive original observations.

Capability stays in an ignored private file. SQLite access below is read-only and
only retrieves recorded Pollard nodes omitted from the public evidence export.
"""
from __future__ import annotations

import argparse
import base64
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pollard import HashRopeStore

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:7860"
OUT = ROOT / "artifacts" / "live-evaluation"
SID = (ROOT / "artifacts/private/live-evaluation-session.txt").read_text().strip()


def request(path, body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Application HTTP {exc.code}: {exc.read().decode()}") from None
    except urllib.error.URLError:
        raise RuntimeError("Application unavailable; no direct-provider fallback.") from None


def state():
    return request(f"/api/sessions/{SID}")


def action(name, payload):
    request(f"/api/sessions/{SID}/actions", {"action": name, "payload": payload})
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        current = state()
        if not current["busy"]:
            if current.get("last_error"):
                raise RuntimeError(current["last_error"])
            return current
        time.sleep(0.5)
    raise RuntimeError("Application action still running; do not retry automatically.")


def save(name, role):
    packet = request(f"/api/sessions/{SID}/export")
    path = OUT / f"{name}.json"
    if path.exists():
        raise RuntimeError("Archive exists; refusing to overwrite evidence.")
    path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    with sqlite3.connect(f"file:{(ROOT / '.runtime/releaseproof.sqlite3').as_posix()}?mode=ro", uri=True) as db:
        private = json.loads(db.execute("SELECT state FROM sessions WHERE id=?", (SID,)).fetchone()[0])
    store = HashRopeStore(base64.b64decode(private["_runtime"]))
    public = packet["state"]
    qualification = public.get("qualification")
    cases = []
    if role == "qualification":
        cases = qualification["cases"]
    elif role == "execute":
        cases = [public["last_execution"]]
    elif role == "probe":
        cases = [dict(id=c["issue_id"], **c) for c in public["drift"].get("observation_records", []) if c["window"] == "current"]
    calls = []
    for case in cases:
        node = store.get(case["node_id"]) if case.get("node_id") else None
        result = node.result if node else {}
        calls.append({"issue_id": case["id"], "source": "live", "node_id": case.get("node_id"),
                      "result_digest": getattr(node, "result_digest", None),
                      "selected_model": public["candidate"]["model_id"],
                      "provider_model": result.get("model"), "provider_request_id": result.get("provider_request_id"),
                      "finish_reason": result.get("finish_reason"), "usage": result.get("usage"),
                      "text": result.get("text"), "latency_ms": case.get("latency_ms"),
                      "passed": case.get("passed"), "error": case.get("error")})
    manifest = {"format": "releaseproof-recorded-provider-manifest-v1", "source": "Recorded actual Pollard results; no new inference",
                "captured_at": datetime.now(timezone.utc).isoformat(), "role": role,
                "qualification_id": qualification["id"] if qualification else None,
                "qualification_created_at": qualification["created_at"] if qualification else None,
                "fingerprint": public["candidate"]["fingerprint"], "contract": public["evidence"]["contract"], "calls": calls}
    (OUT / f"{name}-calls.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return packet


def summary(public):
    q = public.get("qualification")
    return {"candidate": public["candidate"], "qualification": {k: q[k] for k in ("id", "passed", "total", "status", "tokens", "cost_usd", "latency_ms")} if q else None,
            "governance": public["governance"], "drift": {k: public["drift"].get(k) for k in ("mode", "status", "mitigation", "p_value", "observations", "task_failures")},
            "live_spent_usd": public["budget"]["live_spent_usd"], "metrics": public["metrics"], "last_error": public.get("last_error")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["health", "inspect", "mutate", "qualify", "promote", "execute", "probe", "archive"])
    parser.add_argument("--name")
    parser.add_argument("--model", default="nvidia/Nemotron-3_5-Lightning")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--change", default="prompt")
    parser.add_argument("--issue")
    args = parser.parse_args()
    if args.action == "health":
        print(json.dumps(request("/api/health"), indent=2)); return
    if args.action == "inspect":
        print(json.dumps(summary(state()), indent=2)); return
    health = request("/api/health")
    if not health["live_available"] or health["live_budget"].get("backend") != "firestore":
        raise RuntimeError("Healthy shared Firestore authority required.")
    current = state()
    before_live_calls = current["metrics"]["live_calls"]
    if current["budget"]["limit_usd"] > 0.25:
        raise RuntimeError("Evaluation allowance must not exceed 0.25 USD.")
    if args.action == "mutate": current = action("mutate", {"change": args.change})
    elif args.action == "qualify": current = action("qualify", {"mode": "live", "model_id": args.model, "repetitions": args.repetitions, "suite": "full"})
    elif args.action == "promote": current = action("promote", {})
    elif args.action == "execute": current = action("execute", {"mode": "live", **({"issue_id": args.issue} if args.issue else {})})
    elif args.action == "probe": current = action("canary", {"scenario": "live_probe"})
    if args.name:
        role = {"qualify": "qualification", "probe": "probe", "execute": "execute"}.get(args.action, args.action)
        if args.action == "execute" and current["metrics"]["live_calls"] == before_live_calls:
            role = "execute_refused_before_provider_dispatch"
        save(args.name, role)
    print(json.dumps(summary(current), indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(type(exc).__name__ + ": " + str(exc).replace(SID, "[session capability]"), file=sys.stderr)
        sys.exit(1)
