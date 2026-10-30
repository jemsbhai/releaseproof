"""Single-host durable state and pessimistic, cumulative inference accounting."""
from __future__ import annotations

import json
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable


MAX_SESSIONS = 250
MAX_SESSION_ACTIONS = 100
MAX_SESSION_BYTES = 2 * 1024 * 1024
MAX_DATABASE_BYTES = 512 * 1024 * 1024
DATABASE_HEADROOM_BYTES = 16 * 1024 * 1024


class StorageLimitError(ValueError):
    """An operation was refused before dispatch to retain existing evidence."""


def _encoded_state(state: dict) -> str:
    # Quota diagnostics are derived from SQLite, not part of the engine evidence.
    return json.dumps({key: value for key, value in state.items() if key != "storage"},
                      ensure_ascii=False, allow_nan=False)


def _hold(state: dict, message: str) -> None:
    state.update(_approval=None, active=None, status="held", busy=False, last_error=message)
    state.setdefault("governance", {}).update(status="held", approval_valid=False, reasons=[message])
    if state.get("qualification"):
        state["qualification"]["status"] = "stale"
    state.setdefault("drift", {})["mitigation"] = "hold"


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
              id TEXT PRIMARY KEY, state TEXT NOT NULL, updated REAL NOT NULL,
              busy INTEGER NOT NULL DEFAULT 0, error TEXT,
              action_count INTEGER NOT NULL DEFAULT 0,
              storage_reserved INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS reservations (
              id TEXT PRIMARY KEY, reserved INTEGER NOT NULL CHECK(reserved >= 0),
              charged INTEGER CHECK(charged >= 0), created REAL NOT NULL
            );
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(sessions)")}
            for column in ("action_count", "storage_reserved"):
                if column not in columns:
                    db.execute(f"ALTER TABLE sessions ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(str(self.path), timeout=20)
        db.row_factory = sqlite3.Row
        try:
            page_size = db.execute("PRAGMA page_size").fetchone()[0]
            db.execute(f"PRAGMA max_page_count={max(1, MAX_DATABASE_BYTES // page_size)}")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def recover_interrupted(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            message = "The last operation was interrupted. Pending provider reservations remain held; run qualification again before activation."
            for row in db.execute("SELECT id,state FROM sessions WHERE busy=1").fetchall():
                state = json.loads(row["state"])
                _hold(state, message)
                db.execute("UPDATE sessions SET state=?,busy=0,error=?,storage_reserved=0 WHERE id=?",
                           (_encoded_state(state), message, row["id"]))

    def _check_database_budget(self, db, additional_bytes: int) -> None:
        pages = db.execute("PRAGMA page_count").fetchone()[0]
        page_size = db.execute("PRAGMA page_size").fetchone()[0]
        reserved = db.execute("SELECT COALESCE(SUM(storage_reserved),0) FROM sessions").fetchone()[0]
        if pages * page_size + reserved + additional_bytes + DATABASE_HEADROOM_BYTES > MAX_DATABASE_BYTES:
            raise StorageLimitError("The demonstration storage allowance is full. Existing evidence is retained and can be exported; no new work was dispatched.")

    def storage_totals(self) -> dict:
        with self.connect() as db:
            count, reserved = db.execute("SELECT COUNT(*),COALESCE(SUM(storage_reserved),0) FROM sessions").fetchone()
        return {"database_bytes": self.path.stat().st_size, "reserved_growth_bytes": reserved,
                "database_limit_bytes": MAX_DATABASE_BYTES, "session_count": count,
                "session_limit": MAX_SESSIONS, "session_snapshot_limit_bytes": MAX_SESSION_BYTES,
                "session_action_limit": MAX_SESSION_ACTIONS}

    def create(self, state: dict):
        encoded = _encoded_state(state)
        size = len(encoded.encode("utf-8"))
        if size > MAX_SESSION_BYTES:
            raise StorageLimitError("The initial session exceeds its evidence storage allowance.")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            if count >= MAX_SESSIONS:
                raise ValueError("The demonstration workspace is at capacity. Please use an existing browser session.")
            self._check_database_budget(db, size)
            db.execute("INSERT INTO sessions(id,state,updated) VALUES(?,?,?)", (
                state["session_id"], encoded, time.time()))

    def get(self, session_id: str) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT state,busy,error,action_count,storage_reserved FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            return None
        result = json.loads(row["state"])
        result["busy"] = bool(row["busy"])
        result["last_error"] = row["error"]
        result["storage"] = {"snapshot_bytes": len(row["state"].encode("utf-8")),
                             "snapshot_limit_bytes": MAX_SESSION_BYTES, "actions_used": row["action_count"],
                             "action_limit": MAX_SESSION_ACTIONS, "reserved_growth_bytes": row["storage_reserved"]}
        return result

    def claim(self, session_id: str) -> bool:
        with self.connect() as db:
            return db.execute("UPDATE sessions SET busy=1,error=NULL WHERE id=? AND busy=0", (session_id,)).rowcount == 1

    def claim_and_get(self, session_id: str, *, action: str | None = None,
                      storage_estimator: Callable[[dict], int] | None = None) -> dict | None:
        """Serialize ownership and snapshot so an old read cannot overwrite new state."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,busy,action_count FROM sessions WHERE id=?", (session_id,)).fetchone()
            if row is None or row["busy"]:
                return None
            state = json.loads(row["state"])
            growth = 0
            if action is not None:
                if row["action_count"] >= MAX_SESSION_ACTIONS:
                    raise StorageLimitError("This workspace reached its 100-action lifetime limit. Evidence is retained; export it and start a new workspace. Reset does not renew this limit.")
                growth = storage_estimator(state) if storage_estimator else 64 * 1024
                if isinstance(growth, bool) or not isinstance(growth, int) or growth < 0:
                    raise ValueError("Invalid server storage reservation.")
                # Reset is an explicit user-requested replacement, not silent pruning.
                if action != "reset" and len(row["state"].encode("utf-8")) + growth > MAX_SESSION_BYTES:
                    raise StorageLimitError("This action could exceed the 2 MiB session evidence limit. Reduce the suite/repetitions, or export evidence and start a new workspace. Existing evidence is retained; nothing was dispatched.")
                self._check_database_budget(db, growth)
            db.execute("UPDATE sessions SET busy=1,error=NULL,action_count=action_count+?,storage_reserved=? WHERE id=?",
                       (int(action is not None), growth, session_id))
            state["busy"] = True
            state["last_error"] = None
            return state

    def save(self, state: dict, error: str | None = None) -> bool:
        state["busy"] = False
        state["last_error"] = error
        encoded = _encoded_state(state)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,storage_reserved FROM sessions WHERE id=?", (state["session_id"],)).fetchone()
            if row is None:
                return False
            prior_size, size = len(row["state"].encode("utf-8")), len(encoded.encode("utf-8"))
            if size > MAX_SESSION_BYTES or (row["storage_reserved"] and size - prior_size > row["storage_reserved"]):
                message = ("The action exceeded its reserved evidence storage and was not committed. Prior board state and evidence were retained; approval is held. Any provider spend remains recorded. Export the retained evidence before starting a new workspace.")
                retained = json.loads(row["state"])
                _hold(retained, message)
                db.execute("UPDATE sessions SET state=?,updated=?,busy=0,error=?,storage_reserved=0 WHERE id=?",
                           (_encoded_state(retained), time.time(), message, state["session_id"]))
                return False
            db.execute("UPDATE sessions SET state=?,updated=?,busy=0,error=?,storage_reserved=0 WHERE id=?", (
                encoded, time.time(), error, state["session_id"]))
            return True


class LiveLedger:
    """Reservations survive worker restarts and are never reset by a demo reset.

    Ambiguous provider outcomes retain the entire reservation. Amounts are integer
    microdollars based on configured token prices, not reconciled provider bills.
    The deployment must supply persistent storage; an ephemeral deployment must
    disable live operation until a durable ledger is configured.
    """

    def __init__(self, store: Store, limit_micros: int):
        if not 0 <= limit_micros <= 25_000_000:
            raise ValueError("Live limit must stay inside the project's $25 authorization.")
        self.store = store
        self.limit_micros = limit_micros

    def totals(self):
        with self.store.connect() as db:
            row = db.execute("SELECT COALESCE(SUM(COALESCE(charged,reserved)),0) AS committed, COALESCE(SUM(CASE WHEN charged IS NULL THEN reserved ELSE 0 END),0) AS held FROM reservations").fetchone()
        return {"limit_usd": self.limit_micros / 1_000_000,
                "committed_usd": row["committed"] / 1_000_000,
                "held_usd": row["held"] / 1_000_000,
                "remaining_usd": max(0, self.limit_micros - row["committed"]) / 1_000_000,
                "basis": "Conservative reservations and observed-token estimates; not an invoice."}

    def reserve(self, microdollars: int) -> str:
        if isinstance(microdollars, bool) or not isinstance(microdollars, int) or microdollars <= 0:
            raise ValueError("A positive integer provider reservation is required.")
        reservation_id = secrets.token_hex(16)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            committed = db.execute("SELECT COALESCE(SUM(COALESCE(charged,reserved)),0) FROM reservations").fetchone()[0]
            if committed + microdollars > self.limit_micros:
                raise ValueError("The shared live-inference allowance cannot cover this call. No provider request was sent.")
            db.execute("INSERT INTO reservations(id,reserved,created) VALUES(?,?,?)", (reservation_id, microdollars, time.time()))
        return reservation_id

    def settle(self, reservation_id: str, microdollars: int):
        if isinstance(microdollars, bool) or not isinstance(microdollars, int) or microdollars < 0:
            raise ValueError("Invalid provider settlement amount.")
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT reserved,charged FROM reservations WHERE id=?", (reservation_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown provider reservation.")
            if row["charged"] is not None:
                if row["charged"] != microdollars:
                    raise ValueError("Conflicting provider settlement.")
                return
            db.execute("UPDATE reservations SET charged=? WHERE id=?", (microdollars, reservation_id))


def public_state(value):
    if isinstance(value, dict):
        return {k: public_state(v) for k, v in value.items() if not k.startswith("_")}
    if isinstance(value, list):
        return [public_state(v) for v in value]
    return value
