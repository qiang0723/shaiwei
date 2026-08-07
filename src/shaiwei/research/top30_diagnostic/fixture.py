"""Synthetic, no-data fixture for the M6 Top30 diagnostic classifier."""

from __future__ import annotations

import json
from typing import Any

from shaiwei.research.top30_diagnostic.audit import classify_exact


def _rows(offset: float = 0.0) -> list[dict[str, str]]:
    return [
        {
            "date": f"2020-01-{day:02d}",
            "gross_return": (0.001 * day + offset).hex(),
            "benchmark_return": (0.0002 * day).hex(),
            "recorded_cost": (0.00003 * day).hex(),
            "turnover": (0.01 * day).hex(),
        }
        for day in range(1, 6)
    ]


def _adapter(first: list[dict[str, str]], second: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "replay_1": {"rows": first},
        "replay_2": {"rows": first if second is None else second},
    }


def _bundle(original: list[dict[str, str]], new: list[dict[str, str]] | None = None) -> dict[str, Any]:
    adapters = {"original_execution": _adapter(original)}
    if new is not None:
        adapters["new_execution"] = _adapter(new)
    return {"adapters": adapters}


def run_fixture() -> dict[str, Any]:
    canonical, changed, another = _rows(), _rows(1e-6), _rows(2e-6)
    cases = {
        "NO_CURRENT_MISMATCH_REPRODUCED": (
            _bundle(canonical), _bundle(canonical, canonical)
        ),
        "NEW_ADAPTER_DIVERGENCE": (
            _bundle(canonical), _bundle(canonical, changed)
        ),
        "FAILED_IMAGE_ENVIRONMENT_DIVERGENCE": (
            _bundle(canonical), _bundle(changed, changed)
        ),
        "HISTORICAL_REPRODUCIBILITY_GAP": (
            _bundle(changed), _bundle(changed, changed)
        ),
        "MIXED_UNRESOLVED": (
            _bundle(changed), _bundle(another, changed)
        ),
    }
    observed = {
        expected: classify_exact(canonical, original, current)[0]
        for expected, (original, current) in cases.items()
    }
    nondeterministic_original = _bundle(canonical)
    nondeterministic_original["adapters"]["original_execution"]["replay_2"]["rows"] = changed
    observed["RUNTIME_NONDETERMINISM"] = classify_exact(
        canonical, nondeterministic_original, _bundle(canonical, canonical)
    )[0]
    if any(expected != actual for expected, actual in observed.items()):
        raise RuntimeError(f"Top30 synthetic classifier differs: {observed}")
    return {
        "fixture": "PASS",
        "classification_case_count": len(observed),
        "classifications": observed,
        "real_qlib_read": False,
        "sealed_report_read": False,
        "real_top30_backtest_count": 0,
        "top20_backtest_count": 0,
        "external_call_count": 0,
        "production_authorization": "none",
    }


def main() -> int:
    print(json.dumps(run_fixture(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
