"""CLI for the one-shot TS-v4B density profile and independent audit."""

from __future__ import annotations

import argparse
import json

from shaiwei.research.trend_swing.v4_density_audit import audit_once
from shaiwei.research.trend_swing.v4_density_profile import run_profile_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("profile", "audit"))
    args = parser.parse_args(argv)
    result = {"profile": run_profile_once, "audit": audit_once}[args.stage]()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
