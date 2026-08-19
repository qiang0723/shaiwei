"""Command-line entrypoints for the RF-1 formal batch lane."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from shaiwei.research.rf_1.contract import RF1Scope, validate_bound_inputs
from shaiwei.research.rf_1.fixture import fixture
from shaiwei.research.rf_1.release import load_execution_release


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RF-1 formal single-mechanism lane")
    parser.add_argument("action", choices=("fixture", "release-check"))
    action = parser.parse_args(argv).action
    if action == "fixture":
        result = fixture()
    else:
        scope = RF1Scope.load()
        validate_bound_inputs(scope)
        result = load_execution_release(scope)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
