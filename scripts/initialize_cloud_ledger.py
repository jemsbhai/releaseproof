"""One-time operator step. Credentials are read from secrets/ADC and never printed."""
from __future__ import annotations

import argparse
import json

from releaseproof.cloud_ledger import FirestoreLedger


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the separate durable $25 spending ledger without overwriting any existing counters.")
    parser.add_argument("--adc", action="store_true", help="Use operator Application Default Credentials instead of service-account JSON secret")
    parser.add_argument("--limit-micros", type=int, default=25_000_000)
    parser.add_argument("--opening-committed-micros", type=int, default=0, help="Carry forward prior local spend/reservations when migrating the authority")
    args = parser.parse_args()
    ledger = FirestoreLedger.from_environment(args.limit_micros, use_adc=args.adc)
    print(json.dumps(ledger.initialize(opening_committed_micros=args.opening_committed_micros), indent=2))


if __name__ == "__main__":
    main()
