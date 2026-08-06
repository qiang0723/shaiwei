"""Independent M6 synthetic evidence auditor; deliberately avoids inference imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import (
    AttributionError,
    ProtocolBundle,
    canonical_json,
    sha256_file,
    write_once_json,
)


DEFAULT_REPORT = PROJECT_ROOT / "data/research/m6_csi800_model_attribution_v1/engineering/report.json"
DEFAULT_AUDIT = PROJECT_ROOT / "data/research/m6_csi800_model_attribution_v1/engineering/audit.json"


def _decision(inputs: dict[str, dict[str, bool]], blocked: bool) -> str:
    if blocked:
        return "BLOCKED"
    if any(value["score_pass"] and value["portfolio_pass"] for value in inputs.values()):
        return "MODEL_STRUCTURE_SUPPORTED"
    if any(value["score_pass"] for value in inputs.values()) and not any(
        value["portfolio_pass"] for value in inputs.values()
    ):
        return "PORTFOLIO_CONVERSION_BOTTLENECK_INDICATED"
    if not any(value["score_pass"] or value["portfolio_pass"] for value in inputs.values()):
        return "FEATURE_INFORMATION_BOTTLENECK_INDICATED"
    return "MIXED_NOT_CONCLUSIVE"


def _holm(raw: dict[str, float]) -> dict[str, float]:
    if len(raw) != 2:
        raise AttributionError("M6 audit expected two p-values")
    ordered = sorted(raw.items(), key=lambda item: (item[1], item[0]))
    result: dict[str, float] = {}
    running = 0.0
    for index, (name, value) in enumerate(ordered):
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise AttributionError("M6 audit found invalid p-value")
        running = max(running, min(1.0, (2 - index) * value))
        result[name] = running
    return result


def _calendar_boundaries(calendar_path: Path, windows: list[dict[str, Any]]) -> list[dict[str, str]]:
    dates = [line.strip() for line in calendar_path.read_text().splitlines() if line.strip()]
    if dates != sorted(set(dates)):
        raise AttributionError("M6 audit calendar differs")
    output: list[dict[str, str]] = []
    for window in windows:
        row = {"window": str(window["name"])}
        for segment, key in (
            ("train", "purged_train_last_signal"),
            ("valid", "purged_valid_last_signal"),
            ("test", "score_last_signal"),
        ):
            end = str(window[segment][1]).replace("-", "")
            available = [value for value in dates if value <= end]
            value = available[-12]
            row[key] = f"{value[:4]}-{value[4:6]}-{value[6:]}"
        output.append(row)
    return output


def audit(report_path: Path, calendar_path: Path, output: Path) -> dict[str, Any]:
    bundle = ProtocolBundle.load()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report_sha = sha256_file(report_path)
    checks: dict[str, bool] = {
        "protocol_identity": report.get("protocol_sha256") == bundle.result_sha256,
        "engineering_identity": report.get("engineering_protocol_sha256")
        == bundle.engineering_sha256,
        "result_blind": report.get("real_model_fit_count") == 0
        and report.get("real_prediction_count") == 0
        and report.get("real_label_or_effect_read") is False
        and report.get("real_backtest_count") == 0,
        "no_external_calls": report.get("external_call_count") == 0,
        "non_production": report.get("strategy_effective") == "NOT_EVALUATED"
        and report.get("production_authorization") == "none",
        "clock_reconstruction": report.get("window_clock")
        == _calendar_boundaries(calendar_path, bundle.result["windows"]),
        "failure_matrix": len(report.get("failure_closed_checks", {})) == 12
        and all(report.get("failure_closed_checks", {}).values()),
    }
    case_checks: dict[str, bool] = {}
    for row in report.get("decision_cases", []):
        expected_holm = _holm({key: float(value) for key, value in row["raw_p"].items()})
        saved_holm = {key: float(value) for key, value in row["holm_adjusted_p"].items()}
        holm_equal = all(
            math.isclose(expected_holm[key], saved_holm[key], rel_tol=0.0, abs_tol=1e-15)
            for key in expected_holm
        )
        actual = _decision(row["decision_inputs"], bool(row["blocked"]))
        case_checks[str(row["case"])] = bool(
            holm_equal and actual == row["actual"] == row["expected"]
        )
    checks["five_decision_cases"] = len(case_checks) == 5 and all(case_checks.values())
    code_bundle = report.get("code_bundle", {})
    checks["code_bundle"] = bool(code_bundle) and all(
        sha256_file(PROJECT_ROOT / relative) == digest for relative, digest in code_bundle.items()
    )
    code_payload = canonical_json(code_bundle)
    checks["code_bundle_identity"] = (
        hashlib.sha256(code_payload).hexdigest() == report.get("code_bundle_sha256")
    )
    if not all(checks.values()):
        raise AttributionError(f"M6 independent audit failed: {[key for key, value in checks.items() if not value]}")
    audit_document = {
        "schema_version": "m6-model-attribution-engineering-audit-v1",
        "report_sha256": report_sha,
        "checks": checks,
        "decision_case_checks": case_checks,
        "independent_audit": "PASS",
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }
    audit_sha, reused = write_once_json(output, audit_document)
    return {
        "audit_path": str(output),
        "audit_sha256": audit_sha,
        "report_sha256": report_sha,
        "reused": reused,
        "independent_audit": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--calendar-path",
        type=Path,
        default=PROJECT_ROOT / "data/qlib_bin/calendars/day.txt",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()
    print(json.dumps(audit(args.report, args.calendar_path, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
