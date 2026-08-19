"""Command-line entrypoints for the TS-C v2 qualification and audit."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from shaiwei.research.trend_swing.ts_c.audit_v2 import audit_v2_once
from shaiwei.research.trend_swing.ts_c.fixture import fixture
from shaiwei.research.trend_swing.ts_c.profile_v2 import run_profile_v2_once


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TS-C v2 trigger qualification (permission-ON years)")
    parser.add_argument("action", choices=("fixture", "profile", "audit"))
    action = parser.parse_args(argv).action
    result = {"fixture": fixture, "profile": run_profile_v2_once, "audit": audit_v2_once}[action]()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
