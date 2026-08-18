"""Command-line entrypoints for the TS-v6-1 ranking preflight and audit."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from shaiwei.research.trend_swing.v6_1.audit import audit_once
from shaiwei.research.trend_swing.v6_1.profile import fixture, run_profile_once


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="TS-v6-1 entry-quality ranking result-blind preflight")
    value.add_argument("action", choices=("fixture", "profile", "audit"))
    return value


def main(argv: Sequence[str] | None = None) -> int:
    action = parser().parse_args(argv).action
    result = {"fixture": fixture, "profile": run_profile_once, "audit": audit_once}[action]()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
