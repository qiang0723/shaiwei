"""CLI for the one-shot TS-1A-R4 result-blind profile and audit."""

from __future__ import annotations

import argparse
import json

from shaiwei.research.trend_swing.r4_audit import audit_once
from shaiwei.research.trend_swing.r4_profile import run_profile_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("profile", "audit"))
    args = parser.parse_args(argv)
    result = {"profile": run_profile_once, "audit": audit_once}[args.stage]()
    print(
        json.dumps(
            {
                "stage": args.stage,
                "verdict": result.get("verdict", "PASS"),
                "strategy_effective": result.get("strategy_effective", "NOT_EVALUATED"),
                "production_authorization": result.get("production_authorization", "none"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
