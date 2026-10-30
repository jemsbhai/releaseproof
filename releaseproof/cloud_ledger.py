"""Durable Firestore spending authority using atomic REST compare-and-swap commits.

Only ledger metadata leaves the app: integer cost counters, opaque reservation IDs,
and timestamps. Issue contents, model outputs, and provider keys are never stored here.
The runtime never recreates a missing budget document. Bootstrap is an explicit
operator step. Lost commit acknowledgements are recovered by the same reservation
identity, and unsettled calls retain their full reservation across host restarts.

Protocol: https://firebase.google.com/docs/firestore/reference/rest/v1/projects.databases.documents/commit
Preconditions: https://firebase.google.com/docs/firestore/reference/rest/v1/Precondition
"""
from __future__ import annotations

import json
import os
import random
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from typing import Any

SCOPE = "https://www.googleapis.com/auth/datastore"
MAX_LIMIT_MICROS = 25_000_000
API = "https://firestore.googleapis.com/v1/"
DOCUMENT = "releaseproof_budgets/global"


class LedgerUnavailable(ValueError):
    """A sanitized fail-closed failure; the caller must not dispatch a provider request."""


class _Conflict(Exception):
    pass


class _UncertainCommit(Exception):
    pass


def _integer(value: Any, name: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or (maximum is not None and value > maximum):
        raise ValueError(f"Invalid {name}.")
    return value


def _encode(fields: dict) -> dict:
    result = {}
    for name, value in fields.items():
        if value is None:
            result[name] = {"nullValue": None}
        elif isinstance(value, int) and not isinstance(value, bool):
            result[name] = {"integerValue": str(value)}
        elif isinstance(value, str):
            result[name] = {"stringValue": value}
        else:
            raise ValueError("Unsupported ledger field type.")
    return result


def _decode(document: dict) -> dict:
    try:
        fields = document["fields"]
        decoded = {}
        for key, value in fields.items():
            if "integerValue" in value:
                decoded[key] = int(value["integerValue"])
            elif "nullValue" in value:
                decoded[key] = None
            elif "stringValue" in value:
                decoded[key] = value["stringValue"]
            else:
                raise ValueError
        return decoded
    except (ValueError, TypeError, KeyError, AttributeError):
        raise LedgerUnavailable("Remote ledger contains invalid data; live dispatch is disabled.") from None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class FirestoreLedger:
    """Drop-in reserve/settle/totals interface for the server's LIVE_BILLING hook."""

    def __init__(self, project: str, session: Any, limit_micros: int = MAX_LIMIT_MICROS, *, max_attempts: int = 8):
        if not isinstance(project, str) or not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project):
            raise ValueError("Invalid Firestore project ID.")
        _integer(limit_micros, "live allowance", MAX_LIMIT_MICROS)
        if not 1 <= max_attempts <= 20:
            raise ValueError("Invalid transaction retry limit.")
        self.project, self.session, self.limit_micros = project, session, limit_micros
        self.database = f"projects/{project}/databases/(default)"
        self.document = self.database + "/documents/" + DOCUMENT
        self.commit_url = API + self.database + "/documents:commit"
        self.max_attempts = max_attempts
        self._request_lock = threading.RLock()

    @classmethod
    def from_environment(cls, limit_micros: int = MAX_LIMIT_MICROS, *, use_adc: bool = False):
        """Load credentials without printing or persisting them; runtime defaults to HF secret JSON."""
        project = os.environ.get("RELEASEPROOF_FIRESTORE_PROJECT", "")
        try:
            from google.auth.transport.requests import AuthorizedSession
            if use_adc:
                import google.auth
                credentials, inferred_project = google.auth.default(scopes=[SCOPE])
                project = project or inferred_project
            else:
                from google.oauth2 import service_account
                info = json.loads(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", ""))
                if not isinstance(info, dict) or info.get("type") != "service_account" or info.get("token_uri") != "https://oauth2.googleapis.com/token":
                    raise ValueError
                if info.get("project_id") != project:
                    raise ValueError
                credentials = service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
            session = AuthorizedSession(credentials)
            return cls(project, session, limit_micros)
        except Exception:
            raise LedgerUnavailable("Firestore ledger credentials or project configuration are unavailable; live dispatch is disabled.") from None

    def _request(self, method: str, url: str, body: dict | None = None) -> dict | None:
        try:
            with self._request_lock:
                response = self.session.request(method, url, json=body, timeout=(5, 15), allow_redirects=False)
            if response.status_code == 404 and method == "GET":
                return None
            if response.status_code in (200, 201):
                result = response.json()
                if not isinstance(result, dict):
                    raise ValueError
                return result
            status = ""
            try:
                status = response.json().get("error", {}).get("status", "")
            except Exception:
                pass
            if response.status_code in (409, 412) or status in {"ABORTED", "FAILED_PRECONDITION", "ALREADY_EXISTS"}:
                raise _Conflict
            if method == "POST" and response.status_code in (408, 429, 500, 502, 503, 504):
                raise _UncertainCommit
            raise LedgerUnavailable("The remote spending ledger rejected the request; no new live inference is authorized.")
        except (_Conflict, _UncertainCommit, LedgerUnavailable):
            raise
        except Exception:
            if method == "POST":
                raise _UncertainCommit from None
            raise LedgerUnavailable("The remote spending ledger is unreachable; live inference remains disabled.") from None

    def _get(self, name: str) -> dict | None:
        return self._request("GET", API + name)

    def _read_budget(self) -> tuple[dict, dict]:
        document = self._get(self.document)
        if document is None:
            raise LedgerUnavailable("Remote budget document is missing. Operator initialization is required; the runtime will not reset spending.")
        data = _decode(document)
        try:
            if data.get("schema") != 1 or not isinstance(document.get("updateTime"), str):
                raise ValueError
            _integer(data["limit_micros"], "stored allowance", MAX_LIMIT_MICROS)
            _integer(data["committed_micros"], "committed spend")
            _integer(data["held_micros"], "held spend")
            _integer(data["reservation_count"], "reservation count")
            if data["held_micros"] > data["committed_micros"]:
                raise ValueError
            # A lower local limit may restrict use; it can never enlarge the durable limit.
        except (ValueError, KeyError, TypeError):
            raise LedgerUnavailable("Remote budget counters are invalid; live dispatch is disabled.") from None
        return document, data

    def _write(self, name: str, data: dict, *, before: dict | None = None) -> dict:
        return {"update": {"name": name, "fields": _encode(data)},
                "currentDocument": {"updateTime": before["updateTime"]} if before else {"exists": False}}

    def _commit(self, writes: list[dict]) -> None:
        result = self._request("POST", self.commit_url, {"writes": writes})
        if not result or not isinstance(result.get("writeResults"), list) or len(result["writeResults"]) != len(writes):
            raise _UncertainCommit

    def _pause(self, attempt: int) -> None:
        time.sleep(min(0.5, 0.01 * (2 ** attempt)) * (0.5 + random.random()))

    def initialize(self, *, opening_committed_micros: int = 0) -> dict:
        """Explicit operator bootstrap. Never overwrites an existing ledger, even after retries.

        opening_committed_micros carries prior local spending conservatively when moving
        the app to a remote authority. Runtime startup must call totals(), not initialize().
        """
        _integer(opening_committed_micros, "opening committed amount", self.limit_micros)
        initial = {"schema": 1, "limit_micros": self.limit_micros, "committed_micros": opening_committed_micros,
                   "held_micros": 0, "reservation_count": 0, "created_at": _now(), "updated_at": _now()}
        for attempt in range(self.max_attempts):
            existing = self._get(self.document)
            if existing is not None:
                return self.totals()
            try:
                self._commit([self._write(self.document, initial)])
                return self.totals()
            except (_Conflict, _UncertainCommit):
                self._pause(attempt)
        raise LedgerUnavailable("Initialization could not be confirmed. Check the remote ledger before retrying; no provider dispatch is authorized.")

    def totals(self) -> dict:
        _, data = self._read_budget()
        limit = min(self.limit_micros, data["limit_micros"])
        return {"limit_usd": limit / 1_000_000, "committed_usd": data["committed_micros"] / 1_000_000,
                "held_usd": data["held_micros"] / 1_000_000,
                "remaining_usd": max(0, limit - data["committed_micros"]) / 1_000_000,
                "reservations": data["reservation_count"], "backend": "firestore",
                "basis": "Durable conservative reservations and observed-token estimates; not an invoice."}

    def reserve(self, microdollars: int) -> str:
        _integer(microdollars, "provider reservation", MAX_LIMIT_MICROS)
        if microdollars == 0:
            raise ValueError("A positive integer provider reservation is required.")
        identity = secrets.token_hex(16)
        name = self.document + "/reservations/" + identity
        for attempt in range(self.max_attempts):
            # Same identity across commit retries recovers a lost successful response.
            existing = self._get(name)
            if existing is not None:
                recorded = _decode(existing)
                if recorded.get("reserved_micros") != microdollars or recorded.get("charged_micros") is not None:
                    raise LedgerUnavailable("Reservation identity conflict; live dispatch is disabled.")
                self._read_budget()  # Fail closed if the authority was removed/corrupted.
                return identity
            document, data = self._read_budget()
            if data["committed_micros"] + microdollars > min(data["limit_micros"], self.limit_micros):
                raise ValueError("The shared live-inference allowance cannot cover this call. No provider request was sent.")
            updated = {**data, "committed_micros": data["committed_micros"] + microdollars,
                       "held_micros": data["held_micros"] + microdollars,
                       "reservation_count": data["reservation_count"] + 1, "updated_at": _now()}
            reservation = {"schema": 1, "reserved_micros": microdollars, "charged_micros": None, "created_at": _now()}
            try:
                self._commit([self._write(self.document, updated, before=document), self._write(name, reservation)])
                return identity
            except (_Conflict, _UncertainCommit):
                self._pause(attempt)
        raise LedgerUnavailable("Reservation could not be confirmed; any possibly committed funds remain held. No provider request is authorized.")

    def settle(self, reservation_id: str, microdollars: int) -> None:
        _integer(microdollars, "provider settlement")
        if not isinstance(reservation_id, str) or not re.fullmatch(r"[0-9a-f]{32}", reservation_id):
            raise ValueError("Invalid reservation identity.")
        name = self.document + "/reservations/" + reservation_id
        for attempt in range(self.max_attempts):
            reservation = self._get(name)
            if reservation is None:
                raise LedgerUnavailable("Unknown provider reservation; no funds were released.")
            item = _decode(reservation)
            charged = item.get("charged_micros")
            if charged is not None:
                if charged != microdollars:
                    raise ValueError("Conflicting provider settlement; existing accounting is unchanged.")
                self._read_budget()
                return
            document, data = self._read_budget()
            try:
                reserved = _integer(item["reserved_micros"], "stored reservation", MAX_LIMIT_MICROS)
                if data["held_micros"] < reserved or data["committed_micros"] < reserved:
                    raise ValueError
            except (ValueError, KeyError):
                raise LedgerUnavailable("Reservation accounting is inconsistent; no funds were released.") from None
            # Debit observed cost even if it exceeded the estimate. Subsequent reserves fail.
            updated = {**data, "committed_micros": data["committed_micros"] - reserved + microdollars,
                       "held_micros": data["held_micros"] - reserved, "updated_at": _now()}
            settled = {**item, "charged_micros": microdollars, "settled_at": _now()}
            try:
                self._commit([self._write(self.document, updated, before=document), self._write(name, settled, before=reservation)])
                return
            except (_Conflict, _UncertainCommit):
                self._pause(attempt)
        raise LedgerUnavailable("Settlement could not be confirmed. The durable reservation remains conservative; retry the same settlement identity.")
