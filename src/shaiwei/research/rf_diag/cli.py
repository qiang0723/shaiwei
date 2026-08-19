"""Command-line entrypoints for the RF gap-lineage diagnostic and audit."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from shaiwei.research.rf_diag.audit import audit_once
from shaiwei.research.rf_diag.fixture import fixture
from shaiwei.research.rf_diag.run import run_once


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="RF-0B gap-lineage diagnostic")
    value.add_argument("action", choices=("fixture", "diagnose", "audit"))
    return value


def main(argv: Sequence[str] | None = None) -> int:
    action = parser().parse_args(argv).action
    result = {"fixture": fixture, "diagnose": run_once, "audit": audit_once}[action]()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
