"""ReleaseProof's isolated browser sessions and hosted Python API."""
from __future__ import annotations

import importlib.metadata
import json
import os
import re
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from . import engine
from .persistence import LiveLedger, StorageLimitError, Store, public_state

ROOT = Path(__file__).resolve().parents[1]
SESSION_RE = re.compile(r"^[a-f0-9]{48}$")
ACTIONS = {"qualify", "mutate", "promote", "execute", "canary", "mitigate", "configure_budget", "reset"}


class ActionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(max_length=32)
    payload: dict[str, Any] = Field(default_factory=dict)


def create_app(db_path: str | Path | None = None) -> FastAPI:
    store = Store(db_path or os.environ.get("RELEASEPROOF_DB_PATH", str(ROOT / ".runtime" / "releaseproof.sqlite3")))
    limit = int(Decimal(os.environ.get("RELEASEPROOF_LIVE_LIMIT_USD", "5")) * 1_000_000)
    remote_ledger = bool(os.environ.get("RELEASEPROOF_FIRESTORE_PROJECT"))
    if remote_ledger:
        try:
            from .cloud_ledger import FirestoreLedger
            ledger = FirestoreLedger.from_environment(limit)
        except Exception:
            # A configured remote authority must never fall back to a fresh local budget.
            ledger = None
    else:
        ledger = LiveLedger(store, limit)
    ledger_probe_lock = threading.Lock()
    ledger_probe = {"checked_at": 0.0, "available": False, "totals": {}}
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="releaseproof")
    live_slot = threading.Lock()
    recent_actions: dict[str, list[float]] = {}
    rate_lock = threading.Lock()

    def ledger_status():
        with ledger_probe_lock:
            now = time.monotonic()
            if remote_ledger and now - ledger_probe["checked_at"] < 15:
                return ledger_probe["available"], ledger_probe["totals"]
            try:
                if ledger is None:
                    raise ValueError("Spending authority unavailable")
                totals = ledger.totals()
                ledger_probe.update(checked_at=now, available=True, totals=totals)
            except Exception:
                totals = {"available": False, "backend": "firestore" if remote_ledger else "sqlite",
                          "basis": "Shared spending authority is unavailable; live inference is disabled."}
                ledger_probe.update(checked_at=now, available=False, totals=totals)
            return ledger_probe["available"], ledger_probe["totals"]

    def live_available():
        enabled = bool(os.environ.get("NEBIUS_API_KEY")) and os.environ.get("RELEASEPROOF_LIVE_ENABLED") == "1"
        return bool(enabled and ledger_status()[0])

    @asynccontextmanager
    async def lifespan(_app):
        store.recover_interrupted()
        engine.LIVE_BILLING = ledger
        yield
        executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="ReleaseProof", version="0.1.0", lifespan=lifespan, docs_url="/api/docs", redoc_url=None)
    app.state.store = store
    app.state.ledger = ledger

    @app.middleware("http")
    async def guard_and_headers(request: Request, call_next):
        if request.method == "POST":
            try:
                body_size = int(request.headers.get("content-length", "0") or 0)
            except ValueError:
                return JSONResponse({"detail": "Invalid content length."}, status_code=400)
            if body_size > 32_768:
                return JSONResponse({"detail": "Request is too large."}, status_code=413)
            origin = request.headers.get("origin")
            if origin:
                from urllib.parse import urlsplit
                if urlsplit(origin).netloc != request.headers.get("host"):
                    return JSONResponse({"detail": "Use this application's own tab to make changes."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'self' https://huggingface.co; base-uri 'self'; form-action 'self'"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def get_state(session_id):
        if not SESSION_RE.fullmatch(session_id):
            raise HTTPException(404, "Session not found.")
        state = store.get(session_id)
        if state is None:
            raise HTTPException(404, "Session not found. Start a new workspace.")
        return state

    @app.get("/api/health")
    def health():
        ledger_ready, totals = ledger_status()
        return {"status": "ok", "live_available": live_available(), "provider": "Nebius Token Factory",
                "versions": {name: importlib.metadata.version(name) for name in ("pollard", "hashrope", "epicormic")},
                "storage_bytes": store.path.stat().st_size, "live_budget": totals,
                "spending_authority_available": ledger_ready,
                "storage_limits": store.storage_totals(),
                "storage": ("SQLite session state may be ephemeral; Firestore is the durable spending authority."
                            if remote_ledger else "SQLite; deployment must preserve runtime storage for live accounting.")}

    @app.get("/api/catalog")
    def catalog():
        models = getattr(engine, "MODEL_CATALOG", [])
        if isinstance(models, dict):
            models = [{"id": k, **v} for k, v in models.items()]
        return {"models": models, "workflows": [{"id": "issue-triage", "label": "Issue triage"}],
                "scenarios": [{"id": "stable", "label": "Unchanged synthetic behavior"},
                              {"id": "injected_drift", "label": "Injected behavior change"},
                              {"id": "live_probe", "label": "Live repeated probe after live qualification"}]}

    @app.post("/api/sessions", status_code=201)
    def create_session():
        state = engine.new_state(secrets.token_hex(24))
        try:
            store.create(state)
        except ValueError as exc:
            raise HTTPException(429, str(exc)) from exc
        return public_state(store.get(state["session_id"]))

    @app.get("/api/sessions/{session_id}")
    def session(session_id: str):
        return public_state(get_state(session_id))

    def run_action(state, action, payload, is_live):
        error = None
        try:
            result = engine.perform(state, action, payload, live_enabled=live_available())
            state = result if result is not None else state
        except Exception as exc:
            if isinstance(exc, (ValueError, RuntimeError)):
                error = str(exc)[:500]
                key = os.environ.get("NEBIUS_API_KEY", "")
                if key:
                    error = error.replace(key, "[redacted]")
            else:
                error = f"The operation stopped ({type(exc).__name__}). No new approval was granted. Review the evidence and retry."
        finally:
            try:
                store.save(state, error)
            finally:
                if is_live:
                    live_slot.release()

    @app.post("/api/sessions/{session_id}/actions", status_code=202)
    def action(session_id: str, body: ActionBody):
        get_state(session_id)  # Validate existence before claiming the authoritative snapshot.
        if body.action not in ACTIONS:
            raise HTTPException(400, "Unknown action.")
        if len(json.dumps(body.payload)) > 8_192:
            raise HTTPException(400, "Action settings are too large.")
        with rate_lock:
            now = time.monotonic()
            history = [t for t in recent_actions.get(session_id, []) if now - t < 60]
            if len(history) >= 30:
                raise HTTPException(429, "Please wait a moment before the next action.")
            recent_actions[session_id] = history + [now]
        try:
            state = store.claim_and_get(session_id, action=body.action,
                                       storage_estimator=lambda current: engine.estimate_action_storage_bytes(current, body.action, body.payload))
        except StorageLimitError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if state is None:
            raise HTTPException(409, "This workspace already has an operation running.")
        # Requalification uses the persisted source mode, not a client override.
        # Hold/fallback perform no inference and need no live dispatch slot.
        if body.action == "mitigate":
            is_live = body.payload.get("strategy") == "requalify" and state.get("mode") == "live"
        elif body.action == "canary":
            is_live = body.payload.get("scenario") == "live_probe"
        else:
            is_live = body.action in {"qualify", "execute"} and body.payload.get("mode", state.get("mode")) == "live"
        if is_live and not live_available():
            store.save(state)
            raise HTTPException(409, "Live Nebius inference is not enabled. The labelled fixture workflow remains available.")
        if is_live and not live_slot.acquire(blocking=False):
            store.save(state)
            raise HTTPException(409, "Another live run is finishing. Try again shortly.")
        executor.submit(run_action, state, body.action, body.payload, is_live)
        return {"accepted": True}

    @app.get("/api/sessions/{session_id}/export")
    def export(session_id: str):
        state = public_state(get_state(session_id))
        state.pop("session_id", None)
        packet = {"format": "releaseproof-evidence-v1", "exported_at": time.time(), "state": state,
                  "notice": "Evidence on a bounded synthetic issue-triage workload. Sources and injected faults are labelled; this is not a general safety certification."}
        return Response(json.dumps(packet, ensure_ascii=False, indent=2, allow_nan=False), media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="releaseproof-evidence.json"'})

    @app.get("/")
    def index():
        return FileResponse(ROOT / "web" / "index.html")

    if (ROOT / "web").exists():
        app.mount("/assets", StaticFiles(directory=ROOT / "web"), name="assets")
        @app.get("/{filename}")
        def asset(filename: str):
            if filename not in {"app.js", "styles.css", "favicon.svg"}:
                raise HTTPException(404, "Not found.")
            return FileResponse(ROOT / "web" / filename)
    return app


app = create_app()
