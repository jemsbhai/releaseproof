"""Product-level release stories; all inference is explicitly synthetic and offline."""
from __future__ import annotations

from copy import deepcopy

import pytest

from releaseproof import engine, provider


@pytest.fixture(autouse=True)
def no_live_provider_calls(monkeypatch):
    def prohibited(_request):
        raise AssertionError("Scenario tests must never dispatch live inference.")

    monkeypatch.setattr(provider, "live", prohibited)


def act(state, action, **payload):
    return engine.perform(state, action, payload, live_enabled=False)


def approved_session(name="scenario"):
    state = act(engine.new_state(name), "qualify", mode="fixture", suite="full", repetitions=1)
    assert state["qualification"]["status"] == "passed", state["qualification"]["cases"]
    state = act(state, "promote")
    assert state["governance"]["approval_valid"]
    return state


@pytest.mark.parametrize("change", ["prompt", "policy", "tools"])
def test_a_changed_release_cannot_reuse_approval_or_touch_the_board(change):
    state = approved_session("stale-" + change)
    state = act(state, "execute", issue_id="hold-01", mode="fixture")
    assert state["board"][0]["status"] == "draft_ready"
    completed_board = deepcopy(state["board"])
    old_fingerprint = state["candidate"]["fingerprint"]
    calls_before = state["metrics"]["fixture_calls"]

    state = act(state, "mutate", change=change)
    state = act(state, "promote", fingerprint=old_fingerprint, passed=True)
    state = act(state, "execute", issue_id="hold-02", mode="fixture")

    assert state["candidate"]["fingerprint"] != old_fingerprint
    assert not state["governance"]["approval_valid"]
    assert state["board"] == completed_board
    assert state["metrics"]["fixture_calls"] == calls_before
    assert state["governance"]["blocked_actions"] >= 2
    assert any(node["kind"] == "refusal" for node in state["evidence"]["audit"])


def test_validation_reserve_blocks_work_before_any_provider_dispatch(monkeypatch):
    # Total funds cover a six-cent attempt; the protected half leaves only five.
    # Fix the estimator here to isolate admission policy from tokenizer arithmetic.
    monkeypatch.setattr(engine, "estimate_call_micros", lambda *_args: 60_000)
    dispatched = []
    original = provider.fixture

    def observe_dispatch(issue, **kwargs):
        dispatched.append(issue["id"])
        return original(issue, **kwargs)

    monkeypatch.setattr(provider, "fixture", observe_dispatch)
    state = act(engine.new_state("reserve"), "configure_budget", limit_usd=0.10,
                reserve_percent=50, strategy="balanced")
    state = act(state, "qualify", mode="fixture", suite="quick", repetitions=1)

    assert dispatched == []
    assert state["qualification"]["passed"] == 0
    assert state["qualification"]["total"] == 4
    assert state["budget"]["blocked_calls"] == 4
    assert state["budget"]["spent_usd"] == 0
    assert state["budget"]["reserved_usd"] == 0
    assert state["budget"]["protected_usd"] == 0.05
    assert all("reserve" in case["error"] for case in state["qualification"]["cases"])


def test_behavioral_hold_preserves_completed_work_and_blocks_future_actions():
    state = approved_session("drift")
    state = act(state, "execute", issue_id="hold-01", mode="fixture")
    completed_board = deepcopy(state["board"])
    state = act(state, "canary", scenario="injected_drift")

    assert state["drift"]["status"] in {"drift", "warning"}
    assert state["drift"]["mode"] == "controlled_fault_injection"
    assert state["drift"]["recomputed"] is True
    assert state["drift"]["observations"] > 1
    calls_after_probe = state["metrics"]["fixture_calls"]
    state = act(state, "execute", issue_id="hold-02", mode="fixture")

    assert state["board"] == completed_board
    assert not state["governance"]["approval_valid"]
    assert state["metrics"]["fixture_calls"] == calls_after_probe

    # A reassuring synthetic A/A run is not permission to clear the incident hold.
    state = act(state, "canary", scenario="stable")
    state = act(state, "execute", issue_id="hold-02", mode="fixture")
    assert state["board"] == completed_board
    assert state["drift"]["mitigation"] == "hold"
    assert not state["governance"]["approval_valid"]


def test_fallback_restores_configuration_but_requires_new_evidence_and_approval():
    state = approved_session("fallback")
    original_fingerprint = state["candidate"]["fingerprint"]
    state = act(state, "mutate", change="prompt")
    assert state["candidate"]["fingerprint"] != original_fingerprint
    state = act(state, "mitigate", strategy="fallback")
    assert state["candidate"]["fingerprint"] == original_fingerprint
    before = deepcopy(state["board"])
    state = act(state, "promote")
    state = act(state, "execute", issue_id="hold-01", mode="fixture")
    assert state["board"] == before
    assert not state["governance"]["approval_valid"]
    assert state["qualification"]["status"] != "passed"

    state = act(state, "mitigate", strategy="requalify")
    assert not state["governance"]["approval_valid"]  # Explicit approval is still needed.
    state = act(state, "promote")
    state = act(state, "execute", issue_id="hold-01", mode="fixture")
    assert state["governance"]["approval_valid"]
    assert state["board"][0]["status"] == "draft_ready"


def test_changed_server_evidence_cannot_be_bypassed_with_fallback(monkeypatch):
    state = approved_session("changed-corpus")
    original_fingerprint = state["candidate"]["fingerprint"]
    updated_cases = deepcopy(engine.load_issues())
    updated_cases[0]["body"] += " Additional reproduction evidence changes the tested corpus."
    monkeypatch.setattr(engine, "load_issues", lambda: deepcopy(updated_cases))
    before = deepcopy(state["board"])

    state = act(state, "mitigate", strategy="fallback")
    state = act(state, "promote")
    state = act(state, "execute", issue_id="hold-01", mode="fixture")

    assert state["candidate"]["fingerprint"] != original_fingerprint
    assert state["board"] == before
    assert not state["governance"]["approval_valid"]
    assert any(event["title"] == "Fallback evidence became stale" for event in state["events"])


def test_an_economy_output_cap_change_needs_requalification():
    state = approved_session("budget-contract")
    old_fingerprint = state["candidate"]["fingerprint"]
    before = deepcopy(state["board"])
    state = act(state, "configure_budget", limit_usd=0.25, reserve_percent=25, strategy="economy")
    state = act(state, "execute", issue_id="hold-01", mode="fixture")

    assert state["candidate"]["fingerprint"] != old_fingerprint
    assert not state["governance"]["approval_valid"]
    assert state["board"] == before


def test_fixture_approval_does_not_authorize_live_execution():
    state = approved_session("source-boundary")
    before = deepcopy(state["board"])
    state = act(state, "execute", issue_id="hold-01", mode="live")

    assert state["board"] == before
    assert state["metrics"]["live_calls"] == 0
    assert any(event["title"] == "Execution mode mismatch" for event in state["events"])
