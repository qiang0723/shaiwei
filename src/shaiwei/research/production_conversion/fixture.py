"""Pure synthetic engineering gate for the production Head30 release path."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.model_attribution.effect_contract import write_once_document
from shaiwei.research.production_conversion.audit_statistics import independently_evaluate
from shaiwei.research.production_conversion.metrics import WINDOWS, evaluate
from shaiwei.research.production_conversion.real_contract import ReleaseProtocol


def _daily(window: int) -> list[dict[str, float | str]]:
    return [
        {
            "date": f"2020-{window:02d}-{day:02d}",
            "gross_return": 0.002 + window * 0.0001,
            "benchmark_return": 0.0005,
            "recorded_cost": 0.0001,
            "turnover": 0.08,
        }
        for day in range(1, 6)
    ]


def _case() -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    treatments, controls = {}, {}
    for index, window in enumerate(WINDOWS, start=1):
        treatments[window] = {
            "daily": _daily(index),
            "rebalances": [
                {
                    "trade_date": f"2020-{index:02d}-01", "signal_date": f"2019-{index:02d}-31",
                    "targets": [f"SH{code:06d}" for code in range(1, 31)],
                    "previous_targets": [], "replacement_count": 30,
                    "retained_reweight_notional": 0.0, "account_value": 100_000_000.0,
                }
            ],
            "positions": [
                {"date": f"2020-{index:02d}-{day:02d}", "position_count": 30, "cash_ratio": 0.01}
                for day in range(1, 6)
            ],
        }
        controls[window] = [
            {**row, "gross_return": 0.0005, "recorded_cost": 0.0, "turnover": 0.02}
            for row in _daily(index)
        ]
    return treatments, controls


def build_bundle() -> dict[str, Any]:
    protocol = ReleaseProtocol.load()
    treatments, controls = _case()
    control_active = {
        window: [
            (1 + float(row["gross_return"]) - float(row["recorded_cost"]))
            / (1 + float(row["benchmark_return"]))
            - 1
            for row in controls[window]
        ]
        for window in WINDOWS
    }
    result = evaluate(treatments, controls)
    bundle = {
        "schema_version": "m6-production-head30-pass-bundle-v1",
        "converter_protocol_sha256": protocol.base.sha256,
        "release_engineering_sha256": protocol.sha256,
        "treatments": treatments,
        "control_base_daily_active_return": control_active,
        "result": result,
    }
    rebuilt = independently_evaluate(bundle)
    if canonical_sha256(rebuilt) != canonical_sha256(result):
        raise RuntimeError("production-converter synthetic independent reconstruction differs")
    return bundle


def run(output_root: Path) -> dict[str, Any]:
    first, replay = build_bundle(), build_bundle()
    if first != replay:
        raise RuntimeError("production-converter synthetic replay differs")
    first_sha, _ = write_once_document(output_root / "first_pass.json", first)
    replay_sha, _ = write_once_document(output_root / "replay.json", replay)
    if first_sha != replay_sha:
        raise RuntimeError("production-converter synthetic physical replay differs")
    report = {
        "schema_version": "m6-production-head30-engineering-fixture-v1",
        "first_pass_sha256": first_sha,
        "replay_sha256": replay_sha,
        "independent_reconstruction": "PASS",
        "real_effect_read": False,
        "portfolio_attempts_consumed": 0,
        "production_authorization": "none",
    }
    digest, reused = write_once_document(output_root / "report.json", report)
    return {"report_sha256": digest, "reused": reused, **report}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
