"""Offline API boundaries, session isolation, and durable governance behavior."""
from __future__ import annotations

from copy import deepcopy
import json
import threading
import time

from fastapi.testclient import TestClient
import pytest

from releaseproof import engine, provider
from releaseproof.persistence import Store
from releaseproof.server import create_app


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "test-only-never-a-real-provider-key")
    monkeypatch.setenv("RELEASEPROOF_LIVE_ENABLED", "0")
    monkeypatch.setenv("RELEASEPROOF_LIVE_LIMIT_USD", "0")
    monkeypatch.delenv("RELEASEPROOF_FIRESTORE_PROJECT", raising=False)

    def prohibited(_request):
        raise AssertionError("API tests must never call a live provider.")

    monkeypatch.setattr(provider, "live", prohibited)


@pytest.fixture
def api(tmp_path):
    app = create_app(tmp_path / "api.sqlite3")
    with TestClient(app) as client:
        yield client, app


def create(client):
    response = client.post("/api/sessions")
    assert response.status_code == 201
    return response.json()


def settled(client, session_id, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/sessions/{session_id}")
        assert response.status_code == 200
        state = response.json()
        if not state["busy"]:
            return state
        time.sleep(0.01)
    pytest.fail("The offline action did not finish in time.")


def run(client, session_id, action, **payload):
    response = client.post(f"/api/sessions/{session_id}/actions", json={"action": action, "payload": payload})
    assert response.status_code == 202, response.text
    return settled(client, session_id)


def no_internal_fields(value):
    if isinstance(value, dict):
        assert all(not key.startswith("_") for key in value)
        for child in value.values():
            no_internal_fields(child)
    elif isinstance(value, list):
        for child in value:
            no_internal_fields(child)


def test_session_capabilities_are_distinct_and_board_actions_stay_isolated(api):
    client, _app = api
    first, second = create(client), create(client)
    assert first["session_id"] != second["session_id"]
    assert len(first["session_id"]) == 48
    baseline_second = deepcopy(second)

    state = run(client, first["session_id"], "qualify", mode="fixture", suite="full", repetitions=1)
    assert state["qualification"]["status"] == "passed"
    run(client, first["session_id"], "promote")
    changed = run(client, first["session_id"], "execute", issue_id="hold-01", mode="fixture")
    assert changed["board"][0]["status"] == "draft_ready"
    other = client.get(f"/api/sessions/{second['session_id']}").json()
    assert other == baseline_second

    assert client.get("/api/sessions/not-a-capability").status_code == 404
    assert client.get("/api/sessions/" + "f" * 48).status_code == 404


def test_snapshots_and_exports_strip_private_fields_and_session_capability(api):
    client, app = api
    created = create(client)
    sid = created["session_id"]
    state = app.state.store.get(sid)
    state["_credential"] = "DO-NOT-EXPORT"
    state["evidence"]["nested"] = [{"visible": "kept", "_secret": "DO-NOT-EXPORT"}]
    app.state.store.save(state)

    snapshot = client.get(f"/api/sessions/{sid}")
    exported = client.get(f"/api/sessions/{sid}/export")
    assert exported.status_code == 200
    assert "attachment" in exported.headers["content-disposition"]
    assert snapshot.headers["cache-control"] == "no-store"
    no_internal_fields(snapshot.json())
    no_internal_fields(exported.json())
    assert "DO-NOT-EXPORT" not in snapshot.text + exported.text
    assert sid not in exported.text
    assert exported.json()["state"]["evidence"]["nested"] == [{"visible": "kept"}]


def test_health_and_catalog_expose_capabilities_without_keys(api):
    client, _app = api
    health = client.get("/api/health")
    catalog = client.get("/api/catalog")
    assert health.status_code == catalog.status_code == 200
    assert health.json()["live_available"] is False
    assert health.json()["versions"].keys() >= {"pollard", "hashrope", "epicormic"}
    assert catalog.json()["models"]
    assert "test-only-never-a-real-provider-key" not in health.text + catalog.text
    assert health.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("body, status", [
    ({"action": "delete_everything", "payload": {}}, 400),
    ({"action": "promote", "payload": [], "approved": True}, 422),
    ({"action": "promote", "payload": {}, "_approval": {"passed": True}}, 422),
    ({"action": "promote", "payload": {"padding": "x" * 9000}}, 400),
])
def test_invalid_action_envelopes_are_rejected_without_state_changes(api, body, status):
    client, _app = api
    state = create(client)
    sid = state["session_id"]
    response = client.post(f"/api/sessions/{sid}/actions", json=body)
    assert response.status_code == status
    assert client.get(f"/api/sessions/{sid}").json() == state


def test_client_claimed_pass_cannot_promote_an_unqualified_release(api):
    client, _app = api
    created = create(client)
    state = run(client, created["session_id"], "promote", passed=True, accuracy=1,
                fingerprint=created["candidate"]["fingerprint"], approval_valid=True)
    assert not state["governance"]["approval_valid"]
    assert state["active"] is None
    assert state["qualification"] is None


@pytest.mark.parametrize("action, payload", [
    ("qualify", {"mode": "live"}),
    ("canary", {"scenario": "live_probe", "mode": "fixture"}),
])
def test_disabled_live_request_is_refused_without_claiming_or_spending(api, action, payload):
    client, app = api
    state = create(client)
    response = client.post(f"/api/sessions/{state['session_id']}/actions",
                           json={"action": action, "payload": payload})
    assert response.status_code == 409
    after = client.get(f"/api/sessions/{state['session_id']}").json()
    assert after["busy"] is False
    assert after["metrics"]["live_calls"] == 0
    assert app.state.ledger.totals()["committed_usd"] == 0


def test_requalification_cannot_disguise_live_session_as_fixture_in_payload(api):
    client, app = api
    created = create(client)
    sid = created["session_id"]
    state = app.state.store.get(sid)
    state["mode"] = "live"
    app.state.store.save(state)
    response = client.post(f"/api/sessions/{sid}/actions", json={
        "action": "mitigate", "payload": {"strategy": "requalify", "mode": "fixture"},
    })
    assert response.status_code == 409
    assert client.get(f"/api/sessions/{sid}").json()["busy"] is False
    assert app.state.ledger.totals()["committed_usd"] == 0


def test_busy_session_refuses_overlap_but_another_session_can_progress(api, monkeypatch):
    client, _app = api
    first, second = create(client), create(client)
    entered, release = threading.Event(), threading.Event()
    original = engine.perform

    def delayed(state, action, payload, **kwargs):
        if state["session_id"] == first["session_id"]:
            entered.set()
            assert release.wait(5), "Test failed to release its offline operation"
        return original(state, action, payload, **kwargs)

    monkeypatch.setattr(engine, "perform", delayed)
    try:
        response = client.post(f"/api/sessions/{first['session_id']}/actions",
                               json={"action": "mutate", "payload": {"change": "prompt"}})
        assert response.status_code == 202
        assert entered.wait(1)
        assert client.get(f"/api/sessions/{first['session_id']}").json()["busy"] is True
        overlapping = client.post(f"/api/sessions/{first['session_id']}/actions",
                                  json={"action": "reset", "payload": {}})
        assert overlapping.status_code == 409
        other = run(client, second["session_id"], "mutate", change="policy")
        assert other["candidate"]["policy_version"] == "v2"
    finally:
        release.set()
    final = settled(client, first["session_id"])
    assert final["candidate"]["prompt_version"] == "v2"


def test_action_errors_are_recorded_with_configured_key_redacted(api, monkeypatch):
    client, _app = api
    state = create(client)

    def fail(*_args, **_kwargs):
        raise RuntimeError("Failure with test-only-never-a-real-provider-key")

    monkeypatch.setattr(engine, "perform", fail)
    result = run(client, state["session_id"], "qualify", mode="fixture")
    assert result["last_error"] == "Failure with [redacted]"
    assert result["busy"] is False
    assert not result["governance"]["approval_valid"]


def test_cross_origin_mutation_is_rejected(api):
    client, _app = api
    response = client.post("/api/sessions", headers={"Origin": "https://unrelated.example"})
    assert response.status_code == 403


def test_atomic_claim_returns_the_current_persisted_version(tmp_path):
    store = Store(tmp_path / "claim.sqlite3")
    state = engine.new_state("a" * 48)
    store.create(state)
    claimed = store.claim_and_get(state["session_id"])
    assert claimed is not None
    assert store.claim_and_get(state["session_id"]) is None
    completed = engine.perform(claimed, "mutate", {"change": "prompt"})
    store.save(completed)
    next_claim = store.claim_and_get(state["session_id"])
    assert next_claim is not None
    assert next_claim["revision"] == completed["revision"]
    assert next_claim["candidate"]["fingerprint"] == completed["candidate"]["fingerprint"]
    assert next_claim["candidate"]["fingerprint"] != state["candidate"]["fingerprint"]


def test_restart_of_interrupted_approved_operation_requires_requalification(tmp_path):
    path = tmp_path / "restart.sqlite3"
    store = Store(path)
    sid = "b" * 48
    state = engine.perform(engine.new_state(sid), "qualify", {"mode": "fixture", "suite": "full"})
    state = engine.perform(state, "promote", {})
    assert state["governance"]["approval_valid"]
    store.create(state)
    assert store.claim_and_get(sid) is not None

    with TestClient(create_app(path)) as client:
        recovered = client.get(f"/api/sessions/{sid}").json()
        assert recovered["busy"] is False
        assert recovered["last_error"]
        assert not recovered["governance"]["approval_valid"]
        assert recovered["active"] is None
        before = deepcopy(recovered["board"])
        attempted = run(client, sid, "execute", issue_id="hold-01", mode="fixture")
        assert attempted["board"] == before
        assert not attempted["governance"]["approval_valid"]


@pytest.mark.parametrize("project_setting", [None, ""])
def test_live_key_and_enable_flag_require_durable_firestore(tmp_path, monkeypatch, project_setting):
    monkeypatch.setenv("RELEASEPROOF_LIVE_ENABLED", "1")
    monkeypatch.setenv("RELEASEPROOF_LIVE_LIMIT_USD", "5")
    if project_setting is None:
        monkeypatch.delenv("RELEASEPROOF_FIRESTORE_PROJECT", raising=False)
    else:
        monkeypatch.setenv("RELEASEPROOF_FIRESTORE_PROJECT", project_setting)

    dispatched = []
    monkeypatch.setattr(provider, "live", lambda request: dispatched.append(request))
    # A replacement ephemeral database must not grant a new live allowance either.
    for database in ("first.sqlite3", "replacement.sqlite3"):
        app = create_app(tmp_path / database)
        with TestClient(app) as client:
            health = client.get("/api/health").json()
            assert health["live_available"] is False
            assert health["spending_authority_available"] is False
            assert "requires the durable Firestore" in health["storage"]
            assert engine.LIVE_BILLING is None
            sid = create(client)["session_id"]
            response = client.post(f"/api/sessions/{sid}/actions", json={
                "action": "qualify", "payload": {"mode": "live", "suite": "quick"}})
            assert response.status_code == 409
            assert not client.get(f"/api/sessions/{sid}").json()["busy"]
            fixture = run(client, sid, "qualify", mode="fixture", suite="quick")
            assert fixture["qualification"]["status"] == "passed"
            assert fixture["metrics"]["live_calls"] == 0
    assert not dispatched


def test_configured_remote_authority_never_falls_back_to_local(tmp_path, monkeypatch):
    from releaseproof import server
    from releaseproof.cloud_ledger import FirestoreLedger

    monkeypatch.setenv("RELEASEPROOF_FIRESTORE_PROJECT", "test-project")
    monkeypatch.setenv("RELEASEPROOF_LIVE_ENABLED", "1")

    def broken_credentials(_limit):
        raise ValueError("private-service-account-details")

    def prohibited_local(*_args):
        raise AssertionError("A configured remote authority must not use SQLite fallback")

    monkeypatch.setattr(FirestoreLedger, "from_environment", broken_credentials)
    monkeypatch.setattr(server, "LiveLedger", prohibited_local)
    app = create_app(tmp_path / "remote-config-failure.sqlite3")
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["live_available"] is False
        assert health.json()["spending_authority_available"] is False
        assert "private-service-account-details" not in health.text
        assert "test-project" not in health.text
        assert app.state.ledger is None
        assert client.post("/api/sessions").status_code == 201


def test_remote_totals_failure_keeps_fixture_workbench_available(tmp_path, monkeypatch):
    from releaseproof.cloud_ledger import FirestoreLedger

    class UnavailableLedger:
        def totals(self):
            raise RuntimeError("private-remote-account-diagnostic")

    monkeypatch.setenv("RELEASEPROOF_FIRESTORE_PROJECT", "test-project")
    monkeypatch.setenv("RELEASEPROOF_LIVE_ENABLED", "1")
    monkeypatch.setattr(FirestoreLedger, "from_environment", lambda _limit: UnavailableLedger())
    with TestClient(create_app(tmp_path / "remote-offline.sqlite3")) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["live_available"] is False
        assert health.json()["live_budget"]["backend"] == "firestore"
        assert "private-remote-account-diagnostic" not in health.text
        created = create(client)
        result = run(client, created["session_id"], "mutate", change="prompt")
        assert result["candidate"]["prompt_version"] == "v2"


def test_remote_health_is_cached_and_only_reports_budget_fields(tmp_path, monkeypatch):
    from releaseproof.cloud_ledger import FirestoreLedger

    class HealthyLedger:
        calls = 0

        def totals(self):
            self.calls += 1
            return {"limit_usd": 0, "committed_usd": 0, "remaining_usd": 0,
                    "held_usd": 0, "backend": "firestore", "basis": "Test reservation ledger"}

    ledger = HealthyLedger()
    monkeypatch.setenv("RELEASEPROOF_FIRESTORE_PROJECT", "test-project")
    monkeypatch.setenv("RELEASEPROOF_LIVE_ENABLED", "1")
    monkeypatch.setattr(FirestoreLedger, "from_environment", lambda _limit: ledger)
    with TestClient(create_app(tmp_path / "remote-healthy.sqlite3")) as client:
        first = client.get("/api/health")
        second = client.get("/api/health")
        assert first.status_code == second.status_code == 200
        assert first.json()["spending_authority_available"] is True
        assert ledger.calls == 1
        assert "Firestore" in first.json()["storage"]
        assert "test-project" not in first.text
        assert "test-only-never-a-real-provider-key" not in first.text
