"""Command-line entrypoints for the TS-C qualification and audit."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from shaiwei.research.trend_swing.ts_c.audit import audit_once
from shaiwei.research.trend_swing.ts_c.fixture import fixture
from shaiwei.research.trend_swing.ts_c.profile import run_profile_once


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="TS-C trigger qualification result-blind preflight")
    value.add_argument("action", choices=("fixture", "profile", "audit"))
    return value


def main(argv: Sequence[str] | None = None) -> int:
    action = parser().parse_args(argv).action
    result = {"fixture": fixture, "profile": run_profile_once, "audit": audit_once}[action]()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
