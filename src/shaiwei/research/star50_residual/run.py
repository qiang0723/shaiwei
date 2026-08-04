"""One-off result-blind M4-0 STAR50 residual feature data gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research.star50_residual.compute import compute_feature_frame, load_inputs
from shaiwei.research.star50_residual.contract import (
    ResidualExecutionRelease,
    ResidualGateError,
    ResidualProtocol,
)
from shaiwei.research.star50_residual.evidence import build_quality_report, code_bundle_sha256


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--execution-release", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = ResidualProtocol.load(args.protocol)
        release = ResidualExecutionRelease.load(
            args.execution_release,
            protocol,
            code_bundle_sha256=code_bundle_sha256(),
        )
        inputs = load_inputs(protocol)
        features, denominator = compute_feature_frame(inputs, protocol)
        report, _ = build_quality_report(protocol, release, inputs, features, denominator)
    except (OSError, ResidualGateError, TypeError, ValueError) as error:
        print(json.dumps({"status": "FAIL", "error_class": type(error).__name__}, sort_keys=True))
        return 2
    print(
        json.dumps(
            {
                "status": "PASS",
                "verdict": report["verdict"],
                "feature_row_count": report["artifact"]["row_count"],
                "candidate_coverage": report["feature_gate"]["candidate_coverage"],
                "minimum_daily_finite_count": report["feature_gate"]["minimum_daily_finite_count"],
                "feature_sha256": report["artifact"]["sha256"],
                "quality_report_sha256": report["quality_report_sha256"],
                "artifact_reused": report["artifact_reused"],
                "quality_report_reused": report["quality_report_reused"],
                "label_read": False,
                "sealed_validation_read": False,
                "provider_calls": 0,
                "api_key_read": False,
                "strategy_effective": "NOT_EVALUATED",
                "production_authorization": "none",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
