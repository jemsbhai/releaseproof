import concurrent.futures

import pytest

from releaseproof.persistence import LiveLedger, Store, public_state


def test_reservations_survive_restart_and_reset_independent(tmp_path):
    path = tmp_path / "state.sqlite3"
    ledger = LiveLedger(Store(path), 100)
    reservation = ledger.reserve(80)
    restarted = LiveLedger(Store(path), 100)
    with pytest.raises(ValueError, match="allowance"):
        restarted.reserve(30)
    restarted.settle(reservation, 50)
    assert restarted.reserve(50)
    with pytest.raises(ValueError):
        restarted.reserve(1)


def test_concurrent_reservations_cannot_overspend(tmp_path):
    ledger = LiveLedger(Store(tmp_path / "state.sqlite3"), 100)
    def reserve():
        try:
            return bool(ledger.reserve(30))
        except ValueError:
            return False
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: reserve(), range(8)))
    assert sum(results) == 3


def test_settlement_is_idempotent_and_overrun_stops_future_calls(tmp_path):
    ledger = LiveLedger(Store(tmp_path / "state.sqlite3"), 100)
    rid = ledger.reserve(50)
    ledger.settle(rid, 110)
    ledger.settle(rid, 110)
    with pytest.raises(ValueError, match="Conflicting"):
        ledger.settle(rid, 0)
    with pytest.raises(ValueError, match="allowance"):
        ledger.reserve(1)


def test_internal_keys_never_reach_browser():
    assert public_state({"a": [{"x": 1, "_token": "secret"}], "_state": "private"}) == {"a": [{"x": 1}]}
