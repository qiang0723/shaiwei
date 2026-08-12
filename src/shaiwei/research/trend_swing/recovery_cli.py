"""CLI for separate TS-1A-R2 network, offline profile, and audit stages."""

from __future__ import annotations

import argparse
import json

from shaiwei.research.trend_swing.recovery_audit import audit_offline_once
from shaiwei.research.trend_swing.recovery_network import execute_network_once
from shaiwei.research.trend_swing.recovery_run import run_offline_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("network", "profile", "audit"))
    args = parser.parse_args(argv)
    result = {
        "network": execute_network_once,
        "profile": run_offline_once,
        "audit": audit_offline_once,
    }[args.stage]()
    summary = {
        "stage": args.stage,
        "verdict": result.get("verdict", "COMPLETED"),
        "strategy_effective": result.get("strategy_effective", "NOT_EVALUATED"),
        "production_authorization": result.get("production_authorization", "none"),
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
