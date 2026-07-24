"""Frozen P2-1 contract checks that must run before any engineering work."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = PROJECT_ROOT / "config/p2_star50_engineering_v1.yaml"
V2_PATHS = {
    "v2_manifest_sha256": PROJECT_ROOT / "config/p2_star50_official_sources_v2.json",
    "v2_quality_report_sha256": PROJECT_ROOT / "data/research/star50/p2-star50-v2/quality_report.json",
    "v2_initial_set_sha256": PROJECT_ROOT / "data/research/star50/p2-star50-v2/initial_set.parquet",
    "v2_membership_events_sha256": PROJECT_ROOT
    / "data/research/star50/p2-star50-v2/membership_events.parquet",
    "v2_daily_membership_sha256": PROJECT_ROOT / "data/research/star50/p2-star50-v2/daily_membership.parquet",
}


class GateFailure(ValueError):
    """Fail-closed P2-1 input or engineering contract violation."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_protocol() -> dict[str, Any]:
    protocol = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if protocol.get("scope") != "engineering_only_no_real_strategy_results":
        raise GateFailure("P2-1 protocol scope is not engineering-only")
    if protocol.get("production_authorization") != "none":
        raise GateFailure("P2-1 protocol must not authorize production")
    return protocol


def verify_upstream_evidence(protocol: dict[str, Any]) -> dict[str, Any]:
    """Verify frozen v2 artifacts without recalculating or changing the v2 report."""
    expected = protocol["upstream_evidence"]
    actual: dict[str, str] = {}
    for field, path in V2_PATHS.items():
        if not path.is_file():
            raise GateFailure(f"missing frozen v2 artifact: {path.relative_to(PROJECT_ROOT)}")
        actual[field] = sha256_file(path)
        if actual[field] != expected[field]:
            raise GateFailure(f"frozen v2 artifact hash mismatch: {field}")

    quality = json.loads(V2_PATHS["v2_quality_report_sha256"].read_text(encoding="utf-8"))
    required_v2 = {
        "official_lineage_complete": True,
        "tushare_crosscheck_pass": True,
        "pit_constructible": True,
        "strategy_results_inspected": False,
        "production_authorization": "none",
        "verdict": "GO",
    }
    mismatches = {
        field: {"expected": value, "actual": quality.get(field)}
        for field, value in required_v2.items()
        if quality.get(field) != value
    }
    if mismatches:
        raise GateFailure(f"frozen v2 quality status mismatch: {sorted(mismatches)}")
    return {
        "artifact_hashes": actual,
        "required_status": required_v2,
        "v2_report_recalculated": False,
    }


def normalize_daily_membership(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"trade_date", "code"}
    if missing := required - set(frame.columns):
        raise GateFailure(f"official daily membership missing fields: {sorted(missing)}")
    result = frame.loc[:, ["trade_date", "code"]].copy()
    result["trade_date"] = pd.to_datetime(result["trade_date"], errors="coerce").dt.strftime("%Y%m%d")
    result["code"] = result["code"].astype("string")
    if result.isna().any().any():
        raise GateFailure("official daily membership contains null keys")
    return result.sort_values(["trade_date", "code"]).reset_index(drop=True)


def verify_official_daily_membership(
    frame: pd.DataFrame,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    contract = protocol["dataset_contract"]
    daily = normalize_daily_membership(frame)
    duplicate_keys = int(daily.duplicated(["trade_date", "code"], keep=False).sum())
    counts = daily.groupby("trade_date")["code"].nunique()
    bad_counts = counts.loc[counts.ne(int(contract["official_member_count_per_trade_date"]))]
    bse_rows = int(daily["code"].str.endswith(".BJ", na=False).sum())
    if duplicate_keys > int(contract["official_membership_duplicate_key_count_maximum"]):
        raise GateFailure("official daily membership has duplicate keys")
    if not bad_counts.empty:
        raise GateFailure("official daily membership does not contain exactly 50 members per day")
    if bse_rows:
        raise GateFailure("official daily membership contains forbidden .BJ securities")
    if daily["trade_date"].min() != str(contract["strategy_usable_start"]).replace("-", ""):
        raise GateFailure("official daily membership starts on an unexpected date")
    return {
        "row_count": int(len(daily)),
        "trade_date_count": int(daily["trade_date"].nunique()),
        "unique_member_count": int(daily["code"].nunique()),
        "minimum_trade_date": str(daily["trade_date"].min()),
        "maximum_trade_date": str(daily["trade_date"].max()),
        "member_count_minimum": int(counts.min()),
        "member_count_maximum": int(counts.max()),
        "duplicate_key_count": duplicate_keys,
        "bse_row_count": bse_rows,
    }


def verify_monthly_crosscheck(
    index_weight: pd.DataFrame,
    official_daily: pd.DataFrame,
    protocol: dict[str, Any],
) -> dict[str, Any]:
    """Require the exact month domain and exactly one snapshot in every month.

    This intentionally does not use the old ``snapshot count == 72`` shortcut:
    a missing month and a second snapshot in another month must fail even when
    the total number of snapshot dates remains 72.
    """
    required = {"index_code", "con_code", "trade_date"}
    if missing := required - set(index_weight.columns):
        raise GateFailure(f"index_weight missing fields: {sorted(missing)}")
    gate = protocol["input_gate"]
    expected_months = [str(value) for value in gate["expected_months"]]
    if len(expected_months) != int(gate["expected_month_count"]) or len(set(expected_months)) != len(
        expected_months
    ):
        raise GateFailure("frozen expected month domain is inconsistent")

    weights = index_weight.loc[
        index_weight["index_code"].astype("string").eq(protocol["identity"]["benchmark_source_code"]),
        ["index_code", "con_code", "trade_date"],
    ].copy()
    weights["trade_date"] = pd.to_datetime(
        weights["trade_date"].astype("string"), format="%Y%m%d", errors="coerce"
    )
    weights["con_code"] = weights["con_code"].astype("string")
    if weights.isna().any().any():
        raise GateFailure("index_weight contains null crosscheck keys")
    weights["month"] = weights["trade_date"].dt.strftime("%Y-%m")
    weights["trade_date_key"] = weights["trade_date"].dt.strftime("%Y%m%d")

    duplicate_keys = int(weights.duplicated(["index_code", "con_code", "trade_date_key"], keep=False).sum())
    snapshot_dates_by_month = weights.groupby("month")["trade_date_key"].nunique().to_dict()
    actual_months = set(snapshot_dates_by_month)
    expected_set = set(expected_months)
    missing_months = sorted(expected_set - actual_months)
    unexpected_months = sorted(actual_months - expected_set)
    wrong_snapshot_count_months = sorted(
        month
        for month in expected_set & actual_months
        if int(snapshot_dates_by_month[month]) != int(gate["snapshot_trade_dates_per_month_exact"])
    )
    if (
        missing_months
        or unexpected_months
        or wrong_snapshot_count_months
        or duplicate_keys > int(gate["duplicate_snapshot_key_count_maximum"])
    ):
        raise GateFailure(
            "monthly snapshot domain failed: "
            f"missing={missing_months}, unexpected={unexpected_months}, "
            f"wrong_snapshot_count={wrong_snapshot_count_months}, duplicate_keys={duplicate_keys}"
        )

    official = normalize_daily_membership(official_daily)
    official_sets = official.groupby("trade_date")["code"].agg(lambda values: frozenset(values))
    set_differences: list[dict[str, Any]] = []
    row_count_failures: list[str] = []
    for month in expected_months:
        snapshot = weights.loc[weights["month"].eq(month)]
        trade_date = str(snapshot["trade_date_key"].iloc[0])
        members = frozenset(snapshot["con_code"])
        if len(snapshot) != int(gate["snapshot_rows_per_month_exact"]) or len(members) != int(
            gate["snapshot_unique_constituents_per_month_exact"]
        ):
            row_count_failures.append(month)
            continue
        if trade_date not in official_sets.index:
            raise GateFailure(f"snapshot date is absent from official daily membership: {trade_date}")
        official_members = official_sets.loc[trade_date]
        if members != official_members:
            set_differences.append(
                {
                    "month": month,
                    "trade_date": trade_date,
                    "missing_count": len(official_members - members),
                    "extra_count": len(members - official_members),
                }
            )
    if row_count_failures or set_differences:
        raise GateFailure(
            f"monthly constituent set failed: row_count={row_count_failures}, "
            f"set_difference_months={[row['month'] for row in set_differences]}"
        )
    bse_rows = int(weights["con_code"].str.endswith(".BJ", na=False).sum())
    if bse_rows > int(gate["bse_row_count_maximum"]):
        raise GateFailure("index_weight crosscheck contains forbidden .BJ securities")
    return {
        "expected_month_count": len(expected_months),
        "actual_month_count": len(actual_months),
        "snapshot_trade_date_count": int(weights["trade_date_key"].nunique()),
        "months_with_exactly_one_snapshot": len(expected_months),
        "months_with_exactly_50_rows": len(expected_months),
        "months_with_exactly_50_unique_constituents": len(expected_months),
        "exact_set_match_month_count": len(expected_months),
        "missing_months": [],
        "unexpected_months": [],
        "wrong_snapshot_count_months": [],
        "duplicate_snapshot_key_count": duplicate_keys,
        "set_difference_month_count": 0,
        "bse_row_count": bse_rows,
    }
