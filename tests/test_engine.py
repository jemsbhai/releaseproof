"""Behavioral safety boundaries and real-library integration, without external requests."""
from __future__ import annotations

import base64
import copy
import json

import pytest
from pollard import HashRopeStore, seal

from releaseproof import engine
from releaseproof.engine import new_state, perform


def qualified(mode="fixture"):
    state = new_state("engine-test")
    return perform(state, "qualify", {"mode": mode, "suite": "full"}, live_enabled=mode == "live")


def approved():
    return perform(qualified(), "promote", {})


def test_exact_evidence_approval_executes_real_registered_tools():
    state = approved()
    assert state["qualification"]["passed"] == 8
    state = perform(state, "execute", {"issue_id": "hold-01"})
    assert state["board"][0]["labels"] == ["bug"]
    assert state["board"][0]["status"] == "draft_ready"
    assert [c["name"] for c in state["last_execution"]["tool_calls"]] == ["label_issue", "route_issue", "draft_response"]
    store = HashRopeStore(base64.b64decode(state["_runtime"]))
    for report in state["evidence"]["seals"]:
        assert seal(store, report["root_id"]).digest == report["digest"]
    assert any(node["kind"] == "tool_call" for node in state["evidence"]["audit"])


@pytest.mark.parametrize("change", ["prompt", "policy", "tools"])
def test_changed_server_contract_cannot_use_a_stale_or_client_forged_approval(change):
    state = approved()
    before = copy.deepcopy(state["board"])
    fingerprint = state["candidate"]["fingerprint"]
    state = perform(state, "mutate", {"change": change})
    assert state["candidate"]["fingerprint"] != fingerprint
    state = perform(state, "promote", {"passed": True, "fingerprint": fingerprint, "approval_valid": True})
    state = perform(state, "execute", {"issue_id": "hold-01", "approval_valid": True})
    assert state["board"] == before
    assert not state["governance"]["approval_valid"]
    assert any(n["kind"] == "refusal" for n in state["evidence"]["audit"])


def test_tampered_qualification_evidence_invalidates_approval():
    state = approved()
    state["qualification"]["cases"][0]["actual"]["draft"] = "tampered"
    state = perform(state, "execute", {"issue_id": "hold-01"})
    assert state["board"][0]["status"] == "open"
    assert not state["governance"]["approval_valid"]


def test_changed_corpus_invalidates_approval_before_next_write(monkeypatch):
    state = approved()
    corpus = copy.deepcopy(engine.load_issues())
    corpus[0]["body"] += " Changed server evidence."
    monkeypatch.setattr(engine, "load_issues", lambda: corpus)
    state = perform(state, "execute", {"issue_id": "hold-01"})
    assert state["board"][0]["status"] == "open"
    assert not state["governance"]["approval_valid"]


def test_actual_epicormic_detects_controlled_change_and_hold_cannot_be_cleared_by_fixture_aa():
    state = approved()
    state = perform(state, "canary", {"scenario": "stable"})
    assert state["drift"]["status"] == "stable"
    assert state["drift"]["p_value"] == 1
    state = perform(state, "canary", {"scenario": "injected_drift"})
    assert state["drift"]["status"] == "drift"
    assert state["drift"]["p_value"] < 0.05
    assert state["drift"]["recomputed"] is True
    assert state["drift"]["observations"] == 80
    state = perform(state, "execute", {"issue_id": "hold-01"})
    assert state["board"][0]["status"] == "open"
    state = perform(state, "canary", {"scenario": "stable"})
    state = perform(state, "promote", {})
    assert not state["governance"]["approval_valid"]
    assert state["drift"]["mitigation"] == "hold"
    state = perform(state, "mitigate", {"strategy": "requalify"})
    assert state["qualification"]["status"] == "passed"
    assert not state["governance"]["approval_valid"]
    state = perform(state, "promote", {})
    assert state["governance"]["approval_valid"]


def test_fallback_is_lowest_priced_previously_approved_and_requires_new_evidence():
    state = approved()
    cheap = state["candidate"]["model_id"]
    state = perform(state, "qualify", {"mode": "fixture", "suite": "full", "model_id": engine.MODEL_CATALOG[1]["id"]})
    state = perform(state, "promote", {})
    state = perform(state, "mutate", {"change": "prompt"})
    state = perform(state, "mitigate", {"strategy": "fallback"})
    assert state["candidate"]["model_id"] == cheap
    assert state["qualification"]["status"] == "stale"
    state = perform(state, "promote", {})
    assert not state["governance"]["approval_valid"]


def test_reserve_blocks_dispatch_and_recovery_can_use_preserved_funds():
    state = new_state("budget-test")
    state = perform(state, "configure_budget", {"limit_usd": 0.001, "reserve_percent": 50, "strategy": "balanced"})
    state = perform(state, "qualify", {"mode": "fixture", "suite": "full"})
    assert state["budget"]["blocked_calls"] > 0
    assert state["budget"]["reserved_usd"] == 0
    assert state["budget"]["spent_usd"] <= 0.0005
    assert state["qualification"]["status"] == "failed"
    calls = state["metrics"]["fixture_calls"]
    state = perform(state, "mitigate", {"strategy": "requalify"})
    assert state["metrics"]["fixture_calls"] > calls
    assert state["budget"]["spent_usd"] <= 0.001


def test_policy_mutation_changes_actual_rule_and_tools_change_actual_limit():
    state = new_state("policy-test")
    state = perform(state, "mutate", {"change": "policy"})
    state = perform(state, "qualify", {"mode": "fixture", "suite": "full"})
    assert state["qualification"]["status"] == "passed"
    assert all(case["actual"]["needs_review"] for case in state["qualification"]["cases"])
    state = perform(state, "mutate", {"change": "tools"})
    assert state["evidence"]["contract"]["tool_limits"]["draft_max_chars"] == 1000


def test_disabled_live_and_mode_mismatch_never_call_provider(monkeypatch):
    def forbidden(_):
        pytest.fail("Provider must not be called")
    monkeypatch.setattr(engine.provider, "live", forbidden)
    with pytest.raises(ValueError, match="disabled"):
        perform(new_state("offline"), "qualify", {"mode": "live"})
    state = approved()
    state = perform(state, "execute", {"issue_id": "hold-01", "mode": "live"}, live_enabled=True)
    assert state["board"][0]["status"] == "open"
    assert state["metrics"]["live_calls"] == 0


class FakeGlobalLedger:
    def __init__(self, refuse=False):
        self.refuse, self.reservations, self.settlements = refuse, [], []

    def reserve(self, amount):
        if self.refuse:
            raise ValueError("Global budget exhausted")
        self.reservations.append(amount)
        return str(len(self.reservations))

    def settle(self, identity, amount):
        self.settlements.append((identity, amount))


def test_global_budget_denial_happens_before_dispatch_and_releases_session_reserve(monkeypatch):
    monkeypatch.setattr(engine, "LIVE_BILLING", FakeGlobalLedger(refuse=True))
    monkeypatch.setattr(engine.provider, "live", lambda _: pytest.fail("No dispatch allowed"))
    state = qualified("live")
    assert state["metrics"]["live_calls"] == 0
    assert state["qualification"]["status"] == "failed"
    assert state["budget"]["reserved_usd"] == 0
    assert state["budget"]["spent_usd"] == 0


def test_ambiguous_provider_failure_conservatively_settles_full_reservation(monkeypatch):
    ledger = FakeGlobalLedger()
    monkeypatch.setattr(engine, "LIVE_BILLING", ledger)
    def timeout(_):
        raise engine.provider.ProviderFailure("Provider timed out; no automatic retry")
    monkeypatch.setattr(engine.provider, "live", timeout)
    state = qualified("live")
    assert state["qualification"]["status"] == "failed"
    assert state["budget"]["reserved_usd"] == 0
    assert [value for _, value in ledger.settlements] == ledger.reservations
    assert state["budget"]["live_spent_usd"] > 0
    assert state["metrics"]["live_calls"] == 8


def test_unexpected_provider_processing_failure_keeps_reservation_and_sanitizes_detail(monkeypatch):
    ledger = FakeGlobalLedger()
    monkeypatch.setattr(engine, "LIVE_BILLING", ledger)
    def malformed(_):
        raise TypeError("secret-provider-detail")
    monkeypatch.setattr(engine.provider, "live", malformed)
    state = qualified("live")
    assert "secret-provider-detail" not in json.dumps(state)
    assert [amount for _, amount in ledger.settlements] == ledger.reservations
    assert state["budget"]["reserved_usd"] == 0


def test_live_fallback_never_substitutes_an_approved_fixture(monkeypatch):
    state = approved()
    monkeypatch.setattr(engine, "LIVE_BILLING", FakeGlobalLedger(refuse=True))
    state = perform(state, "qualify", {"mode": "live", "suite": "quick"}, live_enabled=True)
    state = perform(state, "mitigate", {"strategy": "fallback"}, live_enabled=True)
    assert state["mode"] == "live"
    assert not state["governance"]["approval_valid"]


def fake_live_decision(request):
    issue = json.loads(request["messages"][-1]["content"])
    return {"text": json.dumps(engine.provider.fixture(issue)), "finish_reason": "stop",
            "usage": {"input_tokens": 100, "output_tokens": 55}}


def test_live_probe_uses_verified_repeated_live_baseline_and_new_bounded_calls(monkeypatch):
    ledger = FakeGlobalLedger()
    monkeypatch.setattr(engine, "LIVE_BILLING", ledger)
    monkeypatch.setattr(engine.provider, "live", fake_live_decision)
    state = perform(new_state("live-canary"), "qualify", {"mode": "live", "suite": "quick", "repetitions": 2}, live_enabled=True)
    assert state["qualification"]["canary_eligible"]
    state = perform(state, "promote", {})
    state = perform(state, "canary", {"scenario": "live_probe"}, live_enabled=True)
    assert state["metrics"]["live_calls"] == 16
    assert state["metrics"]["replayed_calls"] == 16
    assert state["drift"]["status"] == "stable"
    assert state["drift"]["mode"] == "live_probe"
    assert state["drift"]["recomputed"] is True
    assert state["drift"]["small_sample_warning"] is True
    assert len(ledger.reservations) == 16
    assert all(record["source"] == "live" for record in state["drift"]["observation_records"])


def test_live_probe_schema_failure_holds_without_stable_verdict(monkeypatch):
    monkeypatch.setattr(engine, "LIVE_BILLING", FakeGlobalLedger())
    monkeypatch.setattr(engine.provider, "live", fake_live_decision)
    state = perform(new_state("live-fail"), "qualify", {"mode": "live", "suite": "quick", "repetitions": 2}, live_enabled=True)
    state = perform(state, "promote", {})
    monkeypatch.setattr(engine.provider, "live", lambda request: {"text": "not json", "finish_reason": "stop", "usage": {"input_tokens": 50, "output_tokens": 20}})
    state = perform(state, "canary", {"scenario": "live_probe"}, live_enabled=True)
    assert state["drift"]["status"] == "unknown"
    assert state["drift"]["mitigation"] == "hold"
    assert not state["governance"]["approval_valid"]
    assert state["drift"]["failures"]


def test_live_probe_valid_but_changed_decisions_are_scored_and_held(monkeypatch):
    monkeypatch.setattr(engine, "LIVE_BILLING", FakeGlobalLedger())
    monkeypatch.setattr(engine.provider, "live", fake_live_decision)
    state = perform(new_state("live-change"), "qualify", {"mode": "live", "suite": "full", "repetitions": 3}, live_enabled=True)
    state = perform(state, "promote", {})
    changed = {"label": "question", "route": "support", "draft": "Changed decision.", "needs_review": True}
    monkeypatch.setattr(engine.provider, "live", lambda request: {"text": json.dumps(changed), "finish_reason": "stop", "usage": {"input_tokens": 50, "output_tokens": 20}})
    state = perform(state, "canary", {"scenario": "live_probe"}, live_enabled=True)
    assert state["drift"]["status"] == "drift"
    assert state["drift"]["p_value"] < 0.05
    assert state["drift"]["recomputed"]
    assert state["drift"]["task_failures"]
    assert not state["governance"]["approval_valid"]


def test_live_probe_rejects_fixture_and_single_sample_baselines(monkeypatch):
    with pytest.raises(ValueError, match="live qualification"):
        perform(qualified(), "canary", {"scenario": "live_probe"}, live_enabled=True)
    monkeypatch.setattr(engine, "LIVE_BILLING", FakeGlobalLedger())
    monkeypatch.setattr(engine.provider, "live", fake_live_decision)
    with pytest.raises(ValueError, match="at least two"):
        perform(qualified("live"), "canary", {"scenario": "live_probe"}, live_enabled=True)


def test_qualification_history_retains_failed_and_passing_results():
    state = qualified()
    state = perform(state, "configure_budget", {"limit_usd": 0, "reserve_percent": 25, "strategy": "balanced"})
    state = perform(state, "qualify", {"mode": "fixture", "suite": "quick"})
    assert [q["status"] for q in state["qualification_history"]] == ["passed", "failed"]
    assert all(q["model_id"] and q["config_versions"] for q in state["qualification_history"])


def test_quick_smoke_pass_cannot_approve_or_execute_without_adversarial_cases():
    state = perform(new_state("quick-is-not-release"), "qualify", {"mode": "fixture", "suite": "quick"})
    assert state["qualification"]["passed"] == state["qualification"]["total"] == 4
    assert not state["governance"]["approval_eligible"]
    assert "full corpus" in " ".join(state["governance"]["reasons"])
    state = perform(state, "promote", {})
    state = perform(state, "execute", {"issue_id": "hold-01"})
    assert state["board"][0]["status"] == "open"
    assert not state["governance"]["approval_valid"]
    state = perform(state, "qualify", {"mode": "fixture", "suite": "full"})
    assert state["governance"]["approval_eligible"]
    state = perform(state, "promote", {})
    assert state["governance"]["approval_valid"]


def test_provider_request_explicitly_disables_thinking_and_requests_json(monkeypatch):
    captured = {}
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, maximum):
            assert maximum == engine.provider.MAX_RESPONSE_BYTES + 1
            return json.dumps({"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                               "usage": {"prompt_tokens": 10, "completion_tokens": 2}}).encode()
    def open_request(request, **kwargs):
        captured.update(json.loads(request.data))
        return FakeResponse()
    monkeypatch.setenv("NEBIUS_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setattr(engine.provider.urllib.request, "urlopen", open_request)
    engine.provider.live({"model": engine.MODEL_CATALOG[0]["id"], "messages": [], "max_tokens": 768})
    assert captured["chat_template_kwargs"] == {"enable_thinking": False}
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["max_tokens"] == 768


@pytest.mark.parametrize("bad", [[], {"label": [], "route": "support", "draft": "x", "needs_review": False},
                                  {"label": "security", "route": "security", "draft": "x", "needs_review": False}])
def test_invalid_model_outputs_are_failures_not_executable_commands(monkeypatch, bad):
    monkeypatch.setattr(engine, "LIVE_BILLING", FakeGlobalLedger())
    monkeypatch.setattr(engine.provider, "live", lambda request: {"text": json.dumps(bad), "finish_reason": "stop", "usage": {"input_tokens": 50, "output_tokens": 20}})
    state = qualified("live")
    assert state["qualification"]["passed"] == 0
    state = perform(state, "promote", {})
    assert not state["governance"]["approval_valid"]


def test_observed_usage_overrun_stops_further_calls_in_same_qualification(monkeypatch):
    ledger = FakeGlobalLedger()
    monkeypatch.setattr(engine, "LIVE_BILLING", ledger)
    monkeypatch.setattr(engine.provider, "live", lambda request: {"text": "{}", "finish_reason": "stop", "usage": {"input_tokens": 100000, "output_tokens": 2000}})
    state = qualified("live")
    assert state["metrics"]["live_calls"] == 1
    assert state["_budget_overrun"]
    assert ledger.settlements[0][1] > ledger.reservations[0]
    assert state["budget"]["reserved_usd"] == 0


@pytest.mark.parametrize("limit", [-1, 2, float("nan"), float("inf"), True])
def test_invalid_budget_cannot_enter_the_ledger(limit):
    with pytest.raises(ValueError):
        perform(new_state("invalid-budget"), "configure_budget", {"limit_usd": limit, "reserve_percent": 25, "strategy": "balanced"})
