"""CLI for the one-shot TS-v5-R3G-1 profile and audit."""

from __future__ import annotations

import argparse
import json

from shaiwei.research.trend_swing.v5_r3g1_audit import audit_once
from shaiwei.research.trend_swing.v5_r3g1_profile import run_profile_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("profile", "audit"))
    args = parser.parse_args(argv)
    result = {"profile": run_profile_once, "audit": audit_once}[args.stage]()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
