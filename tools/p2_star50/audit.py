"""Audit Star50 index history, PIT membership feasibility, and P2-0 gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ingest.catalog import load_latest_api
from tools.p2_star50.contract import (
    INDEX_CODE,
    PROTOCOL_PATH,
    canonical_frame_sha256,
    sha256_file,
    tool_snapshot_sha256,
    write_immutable_json,
)


def _months(start: str, end: str) -> list[str]:
    return [item.strftime("%Y-%m") for item in pd.period_range(start, end, freq="M")]


def _completed_month_end(end_date: str) -> str:
    parsed = pd.to_datetime(end_date, format="%Y%m%d", errors="raise")
    if parsed.is_month_end:
        return parsed.strftime("%Y-%m-%d")
    return (parsed.replace(day=1) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")


def _open_dates(calendar: pd.DataFrame, start: str, end: str) -> list[str]:
    frame = calendar.loc[
        calendar["exchange"].astype(str).eq("SSE")
        & pd.to_numeric(calendar["is_open"], errors="coerce").eq(1)
    ].copy()
    values = frame["cal_date"].astype(str)
    return sorted(set(values.loc[values.between(start, end)]))


def _segment_counts(calendar: pd.DataFrame, protocol: dict) -> dict[str, object]:
    windows = {}
    for window in protocol["evaluation"]["windows"]:
        windows[window["name"]] = {
            segment: len(
                _open_dates(
                    calendar,
                    str(bounds[0]).replace("-", ""),
                    str(bounds[1]).replace("-", ""),
                )
            )
            for segment, bounds in (
                ("train", window["train"]),
                ("valid", window["valid"]),
                ("test", window["test"]),
            )
        }
    pressures = {
        item["name"]: len(
            _open_dates(
                calendar,
                str(item["start"]).replace("-", ""),
                str(item["end"]).replace("-", ""),
            )
        )
        for item in protocol["evaluation"]["pressure_periods"]
    }
    return {"windows": windows, "pressure_periods": pressures}


def _canonical_hash(payload: object) -> str:
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(rendered).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--collection-report", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
    collection_path = (
        args.collection_report
        if args.collection_report.is_absolute()
        else PROJECT_ROOT / args.collection_report
    )
    collection = json.loads(collection_path.read_text(encoding="utf-8"))
    if collection["protocol_sha256"] != sha256_file(PROTOCOL_PATH):
        raise SystemExit("collection report is bound to a different protocol")

    daily = load_latest_api("tushare.index_daily")
    daily = daily.loc[daily["ts_code"].astype(str).eq(INDEX_CODE)].copy()
    weights = load_latest_api("tushare.index_weight")
    weights = weights.loc[weights["index_code"].astype(str).eq(INDEX_CODE)].copy()
    calendar = load_latest_api("tushare.trade_cal")
    stock_basic = load_latest_api("tushare.stock_basic")

    daily["trade_date"] = daily["trade_date"].astype(str)
    weights["trade_date"] = weights["trade_date"].astype(str)
    daily_key_duplicates = int(daily.duplicated(["ts_code", "trade_date"]).sum())
    weight_key_duplicates = int(
        weights.duplicated(["index_code", "con_code", "trade_date"]).sum()
    )
    usable_start = "20200723"
    official_dates = _open_dates(calendar, usable_start, args.end_date)
    observed_dates = set(daily["trade_date"])
    missing_daily = sorted(set(official_dates) - observed_dates)
    extra_daily = sorted(
        observed_dates - set(_open_dates(calendar, "20191231", args.end_date))
    )
    daily_coverage = (
        (len(official_dates) - len(missing_daily)) / len(official_dates)
        if official_dates
        else 0.0
    )
    numeric = {
        column: pd.to_numeric(daily[column], errors="coerce")
        for column in ("open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount")
    }
    daily_invalid_ohlc = int(
        (
            numeric["high"].lt(numeric["low"])
            | numeric["high"].lt(numeric["open"])
            | numeric["high"].lt(numeric["close"])
            | numeric["low"].gt(numeric["open"])
            | numeric["low"].gt(numeric["close"])
            | numeric["vol"].lt(0)
            | numeric["amount"].lt(0)
        ).sum()
    )
    valid_preclose = numeric["pre_close"].gt(0)
    recomputed_pct = (numeric["close"] / numeric["pre_close"] - 1.0) * 100.0
    daily_pct_mismatch = int(
        (
            valid_preclose
            & recomputed_pct.sub(numeric["pct_chg"]).abs().gt(0.02)
        ).sum()
    )

    completed_month_end = _completed_month_end(args.end_date)
    expected_months = _months("2020-07-01", completed_month_end)
    pending_months = sorted(
        set(_months("2020-07-01", args.end_date)) - set(expected_months)
    )
    observed_months = sorted(set(weights["trade_date"].str[:6].str.replace(r"(\d{4})(\d{2})", r"\1-\2", regex=True)))
    missing_months = sorted(set(expected_months) - set(observed_months))
    snapshot = (
        weights.groupby("trade_date", sort=True)
        .agg(
            constituent_count=("con_code", "nunique"),
            row_count=("con_code", "size"),
            weight_sum=("weight", lambda values: float(pd.to_numeric(values, errors="coerce").sum())),
        )
        .reset_index()
    )
    gate = protocol["data_gate"]
    snapshot_count_violations = snapshot.loc[
        ~snapshot["constituent_count"].between(
            gate["index_weight_constituent_count_minimum"],
            gate["index_weight_constituent_count_maximum"],
        )
    ]
    snapshot_weight_violations = snapshot.loc[
        ~snapshot["weight_sum"].between(
            gate["index_weight_sum_minimum"],
            gate["index_weight_sum_maximum"],
        )
    ]
    bse_count = int(weights["con_code"].astype("string").str.endswith(".BJ", na=False).sum())
    known_codes = set(stock_basic["ts_code"].dropna().astype(str))
    unknown_constituents = sorted(set(weights["con_code"].dropna().astype(str)) - known_codes)
    set_by_date = {
        day: sorted(set(group["con_code"].dropna().astype(str)))
        for day, group in weights.groupby("trade_date", sort=True)
    }
    distinct_constituent_sets = len({_canonical_hash(value) for value in set_by_date.values()})

    open_index = {day: index for index, day in enumerate(official_dates)}
    lag_failures = []
    effective_dates = {}
    for snapshot_date in sorted(set(weights["trade_date"])):
        later = [day for day in official_dates if day > snapshot_date]
        if not later:
            continue
        effective_dates[snapshot_date] = later[0]
        if open_index.get(later[0], -1) < 0:
            lag_failures.append(snapshot_date)
    first_effective_date = min(effective_dates.values()) if effective_dates else None
    uncovered_pit_dates = (
        [day for day in official_dates if first_effective_date is None or day < first_effective_date]
    )

    revision_mismatches = int(collection.get("revision_mismatch_count", -1))
    long_term_revision_documented = False
    checks = {
        "permission_index_daily": len(daily) > 0,
        "permission_index_weight": len(weights) > 0,
        "daily_coverage": daily_coverage >= gate["index_daily_official_calendar_coverage_minimum"],
        "daily_duplicate_keys": daily_key_duplicates <= gate["index_daily_duplicate_key_count_maximum"],
        "daily_validity": daily_invalid_ohlc == 0 and daily_pct_mismatch == 0 and not extra_daily,
        "weight_month_coverage": not missing_months,
        "weight_duplicate_keys": weight_key_duplicates <= gate["index_weight_duplicate_key_count_maximum"],
        "weight_snapshot_counts": snapshot_count_violations.empty,
        "weight_sums": snapshot_weight_violations.empty,
        "weight_reference_integrity": not unknown_constituents,
        "bse_exclusion": bse_count <= gate["bse_row_count_maximum"],
        "immediate_revision_stability": (
            revision_mismatches <= gate["immediate_revision_mismatch_count_maximum"]
        ),
        "pit_one_trade_day_lag_constructible": bool(effective_dates) and not lag_failures,
        "pit_coverage_from_frozen_start": not uncovered_pit_dates,
        "long_term_revision_semantics": long_term_revision_documented,
    }
    blocking_checks = [
        name
        for name, passed in checks.items()
        if not passed
    ]
    data_feasible = not [
        name for name in blocking_checks if name != "long_term_revision_semantics"
    ]
    source_collection_checks = (
        "permission_index_daily",
        "permission_index_weight",
        "daily_coverage",
        "daily_duplicate_keys",
        "daily_validity",
        "weight_month_coverage",
        "weight_duplicate_keys",
        "weight_snapshot_counts",
        "weight_sums",
        "weight_reference_integrity",
        "bse_exclusion",
        "immediate_revision_stability",
    )
    source_collection_feasible = all(checks[name] for name in source_collection_checks)
    strategy_history_go = not blocking_checks
    verdict = "GO" if strategy_history_go else "NO_GO"
    payload = {
        "schema_version": "p2-star50-quality-v1",
        "protocol_sha256": sha256_file(PROTOCOL_PATH),
        "tool_snapshot_sha256": tool_snapshot_sha256(),
        "collection_report_sha256": sha256_file(collection_path),
        "collection_ingest_snapshot_sha256": collection["ingest_snapshot_sha256"],
        "index_code": INDEX_CODE,
        "grain": {
            "index_daily": "one row per index and official trade date",
            "index_weight": "one row per index, constituent, and provider snapshot date",
        },
        "source_contract": {
            "index_daily_permission_minimum_points": 2000,
            "index_weight_permission_minimum_points": 2000,
            "index_weight_documented_frequency": "monthly",
            "index_weight_documented_fields_include_publish_time": False,
            "index_weight_documented_fields_include_revision_version": False,
            "bounded_pagination": "calendar-year index_daily; calendar-month index_weight; no offset API",
            "historical_release_after_close": "2020-07-22",
            "first_realtime_publication_date": "2020-07-23",
        },
        "daily": {
            "row_count": len(daily),
            "min_trade_date": min(observed_dates) if observed_dates else None,
            "max_trade_date": max(observed_dates) if observed_dates else None,
            "official_usable_trade_date_count": len(official_dates),
            "coverage_rate": daily_coverage,
            "missing_trade_date_count": len(missing_daily),
            "missing_trade_dates": missing_daily,
            "extra_noncalendar_date_count": len(extra_daily),
            "extra_noncalendar_dates": extra_daily,
            "duplicate_key_count": daily_key_duplicates,
            "invalid_ohlc_or_nonnegative_count": daily_invalid_ohlc,
            "pct_change_mismatch_count": daily_pct_mismatch,
            "canonical_sha256": canonical_frame_sha256("index_daily", daily),
        },
        "weights": {
            "row_count": len(weights),
            "min_trade_date": weights["trade_date"].min() if not weights.empty else None,
            "max_trade_date": weights["trade_date"].max() if not weights.empty else None,
            "expected_month_count": len(expected_months),
            "observed_month_count": len(set(expected_months) & set(observed_months)),
            "missing_month_count": len(missing_months),
            "missing_months": missing_months,
            "pending_not_due_months": pending_months,
            "snapshot_count": len(snapshot),
            "constituent_count_minimum": int(snapshot["constituent_count"].min()) if not snapshot.empty else 0,
            "constituent_count_maximum": int(snapshot["constituent_count"].max()) if not snapshot.empty else 0,
            "weight_sum_minimum": float(snapshot["weight_sum"].min()) if not snapshot.empty else None,
            "weight_sum_maximum": float(snapshot["weight_sum"].max()) if not snapshot.empty else None,
            "snapshot_constituent_count_violation_count": len(snapshot_count_violations),
            "snapshot_weight_sum_violation_count": len(snapshot_weight_violations),
            "duplicate_key_count": weight_key_duplicates,
            "bse_row_count": bse_count,
            "unknown_constituent_count": len(unknown_constituents),
            "unknown_constituents": unknown_constituents,
            "distinct_constituent_set_count": distinct_constituent_sets,
            "first_lagged_effective_date": first_effective_date,
            "uncovered_pit_trade_date_count": len(uncovered_pit_dates),
            "uncovered_pit_trade_dates": uncovered_pit_dates,
            "canonical_sha256": canonical_frame_sha256("index_weight", weights),
        },
        "revision": {
            "immediate_probe_count": len(collection.get("revision_probes", [])),
            "immediate_mismatch_count": revision_mismatches,
            "long_term_version_or_revision_field_available": False,
            "long_term_revision_semantics": "UNPROVEN",
        },
        "sample_feasibility": {
            **_segment_counts(calendar, protocol),
            "csi800_six_annual_windows_reusable": False,
            "reason": "four frozen CSI800 windows begin before Star50 realtime publication; backfill cannot repair PIT availability",
        },
        "checks": checks,
        "blocking_checks": blocking_checks,
        "source_collection_feasible": source_collection_feasible,
        "data_feasible": data_feasible,
        "engineering_complete": False,
        "strategy_effective": False,
        "strategy_results_inspected": False,
        "verdict": verdict,
        "verdict_scope": "authorization_to_begin_strategy_engineering",
        "production_authorization": "none",
    }
    report_path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
    created = write_immutable_json(report_path, payload)
    print(
        json.dumps(
            {
                "verdict": verdict,
                "data_feasible": data_feasible,
                "blocking_checks": blocking_checks,
                "daily_rows": len(daily),
                "weight_rows": len(weights),
                "report": str(report_path.relative_to(PROJECT_ROOT)),
                "report_created": created,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if verdict == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
