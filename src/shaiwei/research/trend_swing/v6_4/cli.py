"""Command-line entrypoints for the TS-v6-4 no-take-profit effect."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from shaiwei.research.trend_swing.v6_4.audit import audit_once
from shaiwei.research.trend_swing.v6_4.fixture import fixture
from shaiwei.research.trend_swing.v6_4.run import preflight_once, run_once


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="TS-v6-4 no-take-profit discovery effect")
    value.add_argument("action", choices=("fixture", "preflight", "run", "audit"))
    return value


def main(argv: Sequence[str] | None = None) -> int:
    action = parser().parse_args(argv).action
    result = {
        "fixture": fixture,
        "preflight": preflight_once,
        "run": run_once,
        "audit": audit_once,
    }[action]()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
