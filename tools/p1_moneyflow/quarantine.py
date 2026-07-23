"""Freeze a whole-day quarantine mask for stable source gaps before factor results."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ledger import ingest_snapshot_sha256, sha256_file
from shaiwei.provenance import code_snapshot_sha256, git_head
from tools.p1_moneyflow.contract import tool_snapshot_sha256, write_project_json
from tools.p1_moneyflow.features import feature_policy_sha256


QUARANTINE_POLICY: dict[str, object] = {
    "version": "moneyflow-quality-v2",
    "daily_quality_gates_changed": False,
    "failed_source_day_treatment": "quarantine_entire_day_no_fill",
    "minimum_overall_valid_source_date_rate": 0.95,
    "minimum_discovery_valid_source_date_rate": 0.95,
    "minimum_oos_window_valid_source_date_rate": 0.95,
    "minimum_stress_period_valid_source_date_rate": 0.90,
    "maximum_consecutive_quarantined_trade_dates": 10,
}


class QuarantineError(RuntimeError):
    pass


def quarantine_policy_sha256() -> str:
    payload = json.dumps(QUARANTINE_POLICY, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise QuarantineError(f"JSON document must be an object: {path}")
    return document


def maximum_consecutive_failures(rows: pd.DataFrame) -> int:
    ordered = rows.sort_values("trade_date")
    longest = 0
    current = 0
    for failed in ordered["gate_status"].eq("FAIL"):
        current = current + 1 if bool(failed) else 0
        longest = max(longest, current)
    return longest


def _period_coverage(rows: pd.DataFrame, *, name: str, start: str, end: str) -> dict[str, object]:
    period = rows.loc[rows["trade_date"].between(start, end)].copy()
    if period.empty:
        raise QuarantineError(f"period has no official trade dates: {name}")
    valid_count = int(period["gate_status"].eq("PASS").sum())
    return {
        "name": name,
        "start": start,
        "end": end,
        "official_trade_date_count": int(len(period)),
        "valid_source_date_count": valid_count,
        "quarantined_source_date_count": int(len(period) - valid_count),
        "valid_source_date_rate": valid_count / len(period),
    }


def evaluate_quarantine(
    quality: dict[str, object],
    refresh: dict[str, object],
) -> dict[str, object]:
    if quality.get("schema_version") != "p1-moneyflow-full-quality-v1":
        raise QuarantineError("quality input is not p1-moneyflow-full-quality-v1")
    if refresh.get("schema_version") != "p1-moneyflow-failed-date-refresh-v1":
        raise QuarantineError("refresh input is not p1-moneyflow-failed-date-refresh-v1")
    if refresh.get("status") != "STABLE_REFRESH" or refresh.get("revision_trade_dates"):
        raise QuarantineError("failed source dates were not stable under explicit refresh")
    raw_rows = quality.get("per_trade_date")
    if not isinstance(raw_rows, list):
        raise QuarantineError("quality report lacks per_trade_date rows")
    rows = pd.DataFrame(raw_rows)
    required = {"trade_date", "gate_status", "issues"}
    if missing := required - set(rows.columns):
        raise QuarantineError(f"quality rows missing fields: {sorted(missing)}")
    rows["trade_date"] = rows["trade_date"].astype(str)
    if rows["trade_date"].duplicated().any():
        raise QuarantineError("quality report contains duplicate trade dates")
    invalid_status = set(rows["gate_status"]) - {"PASS", "FAIL"}
    if invalid_status:
        raise QuarantineError(f"unknown daily gate statuses: {sorted(invalid_status)}")
    source = quality.get("source")
    if not isinstance(source, dict):
        raise QuarantineError("quality report lacks source summary")
    if int(source.get("revision_observed_count", -1)) != 0:
        raise QuarantineError("quality report contains source revisions")
    if int(source.get("saturated_response_count", -1)) != 0:
        raise QuarantineError("quality report contains saturated source responses")
    allowed_quarantine_issues = {
        "PRIMARY_AMOUNT_SCALE_MISMATCH",
        "PRIMARY_VOLUME_SCALE_MISMATCH",
        "PRIMARY_COVERAGE_BELOW_GATE",
        "PRIMARY_SOURCE_ONLY_ABOVE_GATE",
    }
    failed_rows = rows.loc[rows["gate_status"].eq("FAIL")]
    observed_issues = {
        str(issue)
        for row_issues in failed_rows["issues"]
        for issue in row_issues
    }
    if unexpected := observed_issues - allowed_quarantine_issues:
        raise QuarantineError(f"non-quarantinable quality failures: {sorted(unexpected)}")
    refreshed_dates = {
        str(row["trade_date"])
        for row in refresh.get("observations", [])
        if isinstance(row, dict) and "trade_date" in row
    }
    failed_dates = set(failed_rows["trade_date"])
    if refreshed_dates != failed_dates:
        raise QuarantineError("explicit refresh dates do not match current quality failures")
    settings = load()
    discovery = _period_coverage(
        rows,
        name="discovery",
        start=settings.g1_admission.discovery_start.strftime("%Y%m%d"),
        end=settings.g1_admission.discovery_end.strftime("%Y%m%d"),
    )
    windows = [
        _period_coverage(
            rows,
            name=window.name,
            start=window.test_start.strftime("%Y%m%d"),
            end=window.test_end.strftime("%Y%m%d"),
        )
        for window in settings.evaluation.g0_windows
    ]
    stress = [
        _period_coverage(
            rows,
            name=period.name,
            start=period.start.strftime("%Y%m%d"),
            end=period.end.strftime("%Y%m%d"),
        )
        for period in settings.evaluation.stress_periods
    ]
    valid_count = int(rows["gate_status"].eq("PASS").sum())
    overall_rate = valid_count / len(rows)
    longest = maximum_consecutive_failures(rows)
    gates = {
        "refresh_stable": True,
        "overall_coverage": overall_rate
        >= float(QUARANTINE_POLICY["minimum_overall_valid_source_date_rate"]),
        "discovery_coverage": float(discovery["valid_source_date_rate"])
        >= float(QUARANTINE_POLICY["minimum_discovery_valid_source_date_rate"]),
        "oos_window_coverage": all(
            float(period["valid_source_date_rate"])
            >= float(QUARANTINE_POLICY["minimum_oos_window_valid_source_date_rate"])
            for period in windows
        ),
        "stress_period_coverage": all(
            float(period["valid_source_date_rate"])
            >= float(QUARANTINE_POLICY["minimum_stress_period_valid_source_date_rate"])
            for period in stress
        ),
        "maximum_consecutive_gap": longest
        <= int(QUARANTINE_POLICY["maximum_consecutive_quarantined_trade_dates"]),
    }
    quarantined = rows.loc[rows["gate_status"].eq("FAIL"), ["trade_date", "issues"]]
    return {
        "status": "PASS" if all(gates.values()) else "FAIL",
        "gates": gates,
        "overall": {
            "official_trade_date_count": int(len(rows)),
            "valid_source_date_count": valid_count,
            "quarantined_source_date_count": int(len(rows) - valid_count),
            "valid_source_date_rate": overall_rate,
            "maximum_consecutive_quarantined_trade_dates": longest,
        },
        "discovery": discovery,
        "oos_windows": windows,
        "stress_periods": stress,
        "quarantined_source_dates": quarantined.to_dict("records"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quality-report", type=Path, required=True)
    parser.add_argument("--refresh-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    quality_path = args.quality_report if args.quality_report.is_absolute() else PROJECT_ROOT / args.quality_report
    refresh_path = args.refresh_report if args.refresh_report.is_absolute() else PROJECT_ROOT / args.refresh_report
    quality = _read_json(quality_path)
    refresh = _read_json(refresh_path)
    evaluation = evaluate_quarantine(quality, refresh)
    report = {
        "schema_version": "p1-moneyflow-quarantine-v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": git_head(),
        "production_code_snapshot_sha256": code_snapshot_sha256(),
        "p1_tool_snapshot_sha256": tool_snapshot_sha256(),
        "feature_policy_sha256": feature_policy_sha256(),
        "quarantine_policy": QUARANTINE_POLICY,
        "quarantine_policy_sha256": quarantine_policy_sha256(),
        "ingest_snapshot_sha256": ingest_snapshot_sha256(),
        "quality_report_path": str(quality_path.relative_to(PROJECT_ROOT)),
        "quality_report_sha256": sha256_file(quality_path),
        "refresh_report_path": str(refresh_path.relative_to(PROJECT_ROOT)),
        "refresh_report_sha256": sha256_file(refresh_path),
        "source": quality.get("source"),
        "daily_reference": quality.get("daily_reference"),
        "scope": quality.get("scope"),
        "evaluation": evaluation,
        "summary": {
            "status": evaluation["status"],
            "authorization": (
                "build_isolated_feature_panel" if evaluation["status"] == "PASS" else "none"
            ),
            "production_authorization": "none",
        },
    }
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    write_project_json(report_path, report)
    print(
        json.dumps(
            {
                "status": evaluation["status"],
                "quarantined_source_date_count": evaluation["overall"][
                    "quarantined_source_date_count"
                ],
                "valid_source_date_rate": evaluation["overall"]["valid_source_date_rate"],
                "report": str(report_path.relative_to(PROJECT_ROOT)),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if evaluation["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
