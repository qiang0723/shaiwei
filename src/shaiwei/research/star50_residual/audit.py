"""Independent structural audit of persisted M4-0 evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.star50_residual.compute import CANDIDATES
from shaiwei.research.star50_residual.contract import ResidualGateError, ResidualProtocol, sha256_file


def audit_outputs(
    protocol: ResidualProtocol,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    identity = protocol.document["identity"]
    report_path = project_root / identity["quality_report"]
    feature_path = project_root / identity["feature_artifact"]
    if not report_path.is_file() or not feature_path.is_file():
        raise ResidualGateError("M4-0 audit artifacts are missing")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    features = pd.read_parquet(feature_path)
    required = {"trade_date", "ts_code", *CANDIDATES, "window_start", "window_end"}
    if missing := required - set(features.columns):
        raise ResidualGateError(f"M4-0 feature artifact missing columns: {sorted(missing)}")
    numeric = features[list(CANDIDATES)].to_numpy(dtype=float)
    checks = {
        "feature_sha256_match": sha256_file(feature_path) == report["artifact"]["sha256"],
        "feature_row_count_match": len(features) == int(report["artifact"]["row_count"]),
        "duplicate_key_count_zero": not features.duplicated(["trade_date", "ts_code"]).any(),
        "candidate_values_finite": bool(np.isfinite(numeric).all()),
        "bse_row_count_zero": not features["ts_code"].astype(str).str.endswith(".BJ").any(),
        "window_is_not_future": bool(
            (features["window_start"].astype(str) <= features["trade_date"].astype(str)).all()
            and (features["window_end"].astype(str) == features["trade_date"].astype(str)).all()
        ),
        "result_blind_flags": all(
            (
                report.get("factor_effect_or_rank_ic_computed") is False,
                report.get("label_read") is False,
                report.get("sealed_validation_read") is False,
                report.get("provider_calls") == 0,
                report.get("api_key_read") is False,
                report.get("strategy_results_inspected") is False,
                report.get("production_authorization") == "none",
            )
        ),
    }
    if not all(checks.values()):
        raise ResidualGateError(f"M4-0 independent audit failed: {checks}")
    return {
        "status": "PASS",
        "checks": checks,
        "feature_sha256": sha256_file(feature_path),
        "quality_report_sha256": sha256_file(report_path),
        "verdict": report["verdict"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        protocol = ResidualProtocol.load(args.protocol) if args.protocol else ResidualProtocol.load()
        result = audit_outputs(protocol)
    except (OSError, ResidualGateError, TypeError, ValueError) as error:
        print(json.dumps({"status": "FAIL", "error_class": type(error).__name__}, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

