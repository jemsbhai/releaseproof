"""Bounded evidence storage must stop work before dispatch, never prune silently."""
from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient
import pytest

from releaseproof import engine, persistence
from releaseproof.persistence import StorageLimitError, Store
from releaseproof.server import create_app


@pytest.fixture(autouse=True)
def local_storage_only(monkeypatch):
    monkeypatch.delenv("RELEASEPROOF_FIRESTORE_PROJECT", raising=False)
    monkeypatch.setenv("RELEASEPROOF_LIVE_ENABLED", "0")


def test_session_capacity_preserves_existing_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "MAX_SESSIONS", 2)
    store = Store(tmp_path / "sessions.sqlite3")
    for number in range(2):
        store.create(engine.new_state(str(number) * 48))
    before = store.get("0" * 48)
    with pytest.raises(ValueError, match="capacity"):
        store.create(engine.new_state("2" * 48))
    assert store.get("0" * 48) == before
    assert store.storage_totals()["session_count"] == 2


def test_reset_does_not_renew_lifetime_action_allowance(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "MAX_SESSION_ACTIONS", 2)
    store = Store(tmp_path / "actions.sqlite3")
    sid = "a" * 48
    store.create(engine.new_state(sid))
    claimed = store.claim_and_get(sid, action="mutate", storage_estimator=lambda _: 65_536)
    store.save(engine.perform(claimed, "mutate", {"change": "prompt"}))
    reset = store.claim_and_get(sid, action="reset", storage_estimator=lambda _: 65_536)
    store.save(engine.perform(reset, "reset", {}))
    assert store.get(sid)["revision"] == 1
    assert store.get(sid)["storage"]["actions_used"] == 2
    with pytest.raises(StorageLimitError, match="lifetime limit"):
        store.claim_and_get(sid, action="reset", storage_estimator=lambda _: 0)
    assert store.get(sid)["busy"] is False


def test_snapshot_headroom_refuses_api_action_before_engine_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("RELEASEPROOF_LIVE_ENABLED", "0")
    monkeypatch.setattr(persistence, "MAX_SESSION_BYTES", 100_000)
    app = create_app(tmp_path / "snapshot.sqlite3")
    with TestClient(app) as client:
        created = client.post("/api/sessions").json()
        sid = created["session_id"]
        retained = app.state.store.get(sid)
        retained["_retained_evidence_padding"] = "x" * 80_000
        assert app.state.store.save(retained)
        monkeypatch.setattr(engine, "estimate_action_storage_bytes", lambda *_: 65_536)
        dispatched = []

        def record(*_args, **_kwargs):
            dispatched.append(True)
            raise AssertionError("Storage-denied work must not execute")

        monkeypatch.setattr(engine, "perform", record)
        response = client.post(f"/api/sessions/{sid}/actions",
                               json={"action": "mutate", "payload": {"change": "prompt"}})
        assert response.status_code == 409
        assert "nothing was dispatched" in response.text
        assert dispatched == []
        after = app.state.store.get(sid)
        assert after["_retained_evidence_padding"] == retained["_retained_evidence_padding"]
        assert after["busy"] is False
        assert after["storage"]["actions_used"] == 0
        assert client.get(f"/api/sessions/{sid}/export").status_code == 200


def test_database_headroom_counts_other_inflight_reservations(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "MAX_DATABASE_BYTES", 1_000_000)
    monkeypatch.setattr(persistence, "DATABASE_HEADROOM_BYTES", 10_000)
    store = Store(tmp_path / "global.sqlite3")
    first, second = "1" * 48, "2" * 48
    store.create(engine.new_state(first))
    store.create(engine.new_state(second))
    claimed = store.claim_and_get(first, action="qualify", storage_estimator=lambda _: 650_000)
    with pytest.raises(StorageLimitError, match="storage allowance"):
        store.claim_and_get(second, action="qualify", storage_estimator=lambda _: 650_000)
    assert store.get(second)["busy"] is False
    assert store.storage_totals()["reserved_growth_bytes"] == 650_000
    assert store.save(claimed)
    assert store.storage_totals()["reserved_growth_bytes"] == 0
    assert store.claim_and_get(second, action="qualify", storage_estimator=lambda _: 650_000)
    with store.connect() as db:
        pages = db.execute("PRAGMA max_page_count").fetchone()[0]
        page_bytes = db.execute("PRAGMA page_size").fetchone()[0]
        assert pages * page_bytes <= 1_000_000


@pytest.mark.parametrize("overrun", ["snapshot", "reservation"])
def test_unexpected_growth_retains_prior_evidence_and_holds_release(tmp_path, overrun):
    store = Store(tmp_path / f"overrun-{overrun}.sqlite3")
    sid = "c" * 48
    state = engine.perform(engine.new_state(sid), "qualify", {"mode": "fixture", "suite": "full"})
    state = engine.perform(state, "promote", {})
    assert state["governance"]["approval_valid"]
    store.create(state)
    before = deepcopy(store.get(sid))
    claim = store.claim_and_get(sid, action="execute", storage_estimator=lambda _: 1024)
    claim["_new_uncommitted_evidence"] = "x" * (persistence.MAX_SESSION_BYTES if overrun == "snapshot" else 2048)
    claim["board"][0]["labels"] = ["uncommitted"]

    assert store.save(claim) is False
    after = store.get(sid)
    assert after["_runtime"] == before["_runtime"]
    assert after["board"] == before["board"]
    assert "_new_uncommitted_evidence" not in after
    assert not after["governance"]["approval_valid"]
    assert after["status"] == "held"
    assert after["busy"] is False
    assert "not committed" in after["last_error"]
    assert "provider spend remains recorded" in after["last_error"]
    assert after["storage"]["reserved_growth_bytes"] == 0
