"""Atomic REST protocol tests with a thread-safe Firestore commit/precondition fake."""
from __future__ import annotations

import copy
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from releaseproof.cloud_ledger import API, FirestoreLedger, LedgerUnavailable, _decode


class Response:
    def __init__(self, status, value):
        self.status_code, self.value = status, value

    def json(self):
        return copy.deepcopy(self.value)


class AtomicFirestore:
    def __init__(self):
        self.documents, self.lock = {}, threading.Lock()
        self.clock, self.lose_next_commit, self.deny_reads, self.deny_writes = 0, False, False, False

    def request(self, method, url, *, json, **kwargs):
        with self.lock:
            if method == "GET":
                if self.deny_reads:
                    return Response(403, {"error": {"message": "secret diagnostic"}})
                document = self.documents.get(url.removeprefix(API))
                return Response(200 if document else 404, document or {})
            assert method == "POST" and url.endswith("documents:commit")
            if self.deny_writes:
                return Response(403, {"error": {"message": "secret diagnostic"}})
            for write in json["writes"]:
                name = write["update"]["name"]
                existing, condition = self.documents.get(name), write["currentDocument"]
                if (condition.get("exists") is False and existing is not None) or ("updateTime" in condition and (not existing or existing["updateTime"] != condition["updateTime"])):
                    return Response(409, {"error": {"status": "FAILED_PRECONDITION"}})
            # Check all preconditions first, then apply every document atomically.
            self.clock += 1
            timestamp = f"2026-10-30T00:00:00.{self.clock:06d}Z"
            for write in json["writes"]:
                self.documents[write["update"]["name"]] = {**copy.deepcopy(write["update"]), "updateTime": timestamp}
            if self.lose_next_commit:
                self.lose_next_commit = False
                raise TimeoutError("Response lost after successful commit")
            return Response(200, {"writeResults": [{"updateTime": timestamp} for _ in json["writes"]], "commitTime": timestamp})


def ledger(limit=1000, transport=None):
    transport = transport or AtomicFirestore()
    result = FirestoreLedger("releaseproof-test", transport, limit, max_attempts=20)
    result._pause = lambda attempt: None
    return result


def test_missing_authority_fails_closed_and_constructor_never_initializes():
    book = ledger()
    with pytest.raises(LedgerUnavailable, match="missing"):
        book.reserve(100)
    assert not book.session.documents


def test_initialize_is_explicit_and_never_resets_spending():
    book = ledger()
    book.initialize(opening_committed_micros=100)
    identity = book.reserve(300)
    book.settle(identity, 200)
    assert book.initialize()["committed_usd"] == 0.0003
    assert book.totals()["held_usd"] == 0


def test_concurrent_instances_cannot_oversubscribe_budget():
    transport = AtomicFirestore()
    ledger(transport=transport).initialize()
    def attempt(_):
        try:
            return ledger(transport=transport).reserve(100)
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=16) as pool:
        identities = list(pool.map(attempt, range(40)))
    assert len([value for value in identities if value]) == 10
    totals = ledger(transport=transport).totals()
    assert totals["committed_usd"] == totals["held_usd"] == 0.001
    assert totals["remaining_usd"] == 0


def test_lost_reserve_ack_recovers_one_identity_without_double_charge():
    book = ledger()
    book.initialize()
    book.session.lose_next_commit = True
    identity = book.reserve(100)
    assert len(identity) == 32
    assert book.totals()["reservations"] == 1
    assert book.totals()["committed_usd"] == 0.0001


def test_lost_settlement_ack_and_duplicate_settlement_are_idempotent():
    book = ledger()
    book.initialize()
    identity = book.reserve(100)
    book.session.lose_next_commit = True
    book.settle(identity, 60)
    book.settle(identity, 60)
    assert book.totals()["committed_usd"] == 0.00006
    assert book.totals()["held_usd"] == 0
    with pytest.raises(ValueError, match="Conflicting"):
        book.settle(identity, 0)
    assert book.totals()["committed_usd"] == 0.00006


def test_restart_keeps_unsettled_reservations_pessimistically():
    book = ledger()
    book.initialize()
    identity = book.reserve(900)
    replacement = ledger(transport=book.session)
    assert replacement.totals()["held_usd"] == 0.0009
    with pytest.raises(ValueError, match="allowance"):
        replacement.reserve(101)
    replacement.settle(identity, 400)
    assert replacement.totals()["committed_usd"] == 0.0004


def test_larger_runtime_setting_cannot_enlarge_durable_budget():
    first = ledger(limit=100)
    first.initialize()
    second = ledger(limit=1000, transport=first.session)
    assert second.totals()["limit_usd"] == 0.0001
    with pytest.raises(ValueError, match="allowance"):
        second.reserve(101)


def test_actual_overrun_is_charged_and_blocks_later_work():
    book = ledger(limit=100)
    book.initialize()
    identity = book.reserve(80)
    book.settle(identity, 120)
    assert book.totals()["committed_usd"] == 0.00012
    assert book.totals()["remaining_usd"] == 0
    with pytest.raises(ValueError, match="allowance"):
        book.reserve(1)


def test_failed_settlement_keeps_prior_reservation():
    book = ledger()
    book.initialize()
    identity = book.reserve(500)
    book.session.deny_writes = True
    with pytest.raises(LedgerUnavailable):
        book.settle(identity, 100)
    book.session.deny_writes = False
    assert book.totals()["held_usd"] == 0.0005


def test_permission_errors_are_sanitized_and_do_not_authorize_dispatch():
    book = ledger()
    book.session.deny_reads = True
    with pytest.raises(LedgerUnavailable) as caught:
        book.reserve(100)
    assert "secret diagnostic" not in str(caught.value)


def test_counter_corruption_fails_closed():
    book = ledger()
    book.initialize()
    book.session.documents[book.document]["fields"]["held_micros"] = {"integerValue": "99"}
    with pytest.raises(LedgerUnavailable, match="invalid"):
        book.reserve(100)


@pytest.mark.parametrize("limit", [-1, 25_000_001, True])
def test_absolute_authorization_limit_is_enforced(limit):
    with pytest.raises(ValueError):
        ledger(limit)
