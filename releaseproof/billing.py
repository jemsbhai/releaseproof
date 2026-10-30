"""Small, integer-microdollar reservation ledger; provider bills remain authoritative."""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_CEILING


def micros(value: float | str) -> int:
    return int((Decimal(str(value)) * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


def cost_micros(input_tokens: int, output_tokens: int, model: dict) -> int:
    cost = (Decimal(input_tokens) * Decimal(str(model["input_per_million"]))
            + Decimal(output_tokens) * Decimal(str(model["output_per_million"])))
    return int(cost.to_integral_value(rounding=ROUND_CEILING))


def ledger(state: dict, mode: str) -> dict:
    return state["_budgets"].setdefault(mode, {"spent": 0, "reserved": 0})


def available(state: dict, mode: str, recovery: bool = False) -> int:
    book = ledger(state, mode)
    limit = micros(state["budget"]["limit_usd"])
    protected = 0 if recovery else math.ceil(limit * state["budget"]["reserve_percent"] / 100)
    return max(0, limit - book["spent"] - book["reserved"] - protected)


def reserve(state: dict, mode: str, amount: int, *, recovery: bool = False) -> bool:
    if amount > available(state, mode, recovery):
        return False
    ledger(state, mode)["reserved"] += amount
    return True


def settle(state: dict, mode: str, reserved: int, observed: int) -> None:
    book = ledger(state, mode)
    book["reserved"] = max(0, book["reserved"] - reserved)
    book["spent"] += max(0, observed)


def refresh(state: dict) -> None:
    budget = state["budget"]
    book = ledger(state, state["mode"])
    budget.update(spent_usd=book["spent"] / 1_000_000,
                  reserved_usd=book["reserved"] / 1_000_000,
                  remaining_usd=max(0, micros(budget["limit_usd"]) - book["spent"] - book["reserved"]) / 1_000_000,
                  live_spent_usd=ledger(state, "live")["spent"] / 1_000_000,
                  simulated_spent_usd=ledger(state, "fixture")["spent"] / 1_000_000,
                  accounting_mode=state["mode"],
                  cost_basis="simulated token cost" if state["mode"] == "fixture" else "estimated from provider usage; not an authoritative bill",
                  protected_usd=micros(budget["limit_usd"]) * budget["reserve_percent"] / 100 / 1_000_000)
