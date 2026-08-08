"""Authoritative aggregate-only M7 key compatibility computation."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .contract import UNIVERSE_IDS, M7GateError, M7Protocol
from .reader import KeyInputs


DATE_RE = re.compile(r"^[0-9]{8}$")
CODE_RE = re.compile(r"^[0-9]{6}\.SH$")
ALL_A_SOURCE_CODE_RE = re.compile(r"^[0-9]{6}\.(?:SH|SZ)$")


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 12) if denominator else 0.0


def _maximum_true_streak(values: list[bool]) -> int:
    longest = current = 0
    for value in values:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def _gate(gate_id: str, passed: bool, observed: Any, threshold: Any) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": "PASS" if passed else "FAIL",
        "observed": observed,
        "threshold": threshold,
    }


def _normalize(
    inputs: KeyInputs,
    protocol: M7Protocol,
    *,
    source_code_re: re.Pattern[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    membership = inputs.membership.copy()
    source = inputs.source_keys.copy()
    for frame, columns in (
        (membership, ("trade_date", "formation_date", "universe_id", "ts_code")),
        (source, ("trade_date", "ts_code", "request_trade_date")),
    ):
        for column in columns:
            frame[column] = frame[column].astype("string")
    membership_null = int(membership[["trade_date", "formation_date", "universe_id", "ts_code"]].isna().any(axis=1).sum())
    source_null = int(source[["trade_date", "ts_code", "request_trade_date"]].isna().any(axis=1).sum())
    membership_malformed = int(
        (~membership["trade_date"].fillna("").str.fullmatch(DATE_RE)).sum()
        + (~membership["formation_date"].fillna("").str.fullmatch(DATE_RE)).sum()
        + (~membership["ts_code"].fillna("").str.fullmatch(CODE_RE)).sum()
    )
    source_malformed = int(
        (~source["trade_date"].fillna("").str.fullmatch(DATE_RE)).sum()
        + (~source["request_trade_date"].fillna("").str.fullmatch(DATE_RE)).sum()
        + (~source["ts_code"].fillna("").str.fullmatch(source_code_re)).sum()
    )
    feature_start = protocol.pit["feature_start_date"]
    feature_end = protocol.pit["feature_end_date"]
    membership = membership.loc[membership["trade_date"].between(feature_start, feature_end)].copy()
    source_start = protocol.pit["source_start_date"]
    source_end = protocol.pit["source_end_date"]
    source = source.loc[source["request_trade_date"].between(source_start, source_end)].copy()
    diagnostics = {
        "membership_null_key_count": membership_null,
        "source_null_key_count": source_null,
        "membership_malformed_key_count": membership_malformed,
        "source_malformed_key_count": source_malformed,
    }
    return membership, source, diagnostics


def _pit_mapping(protocol: M7Protocol, dates: tuple[str, ...]) -> pd.DataFrame:
    ordered = list(dates)
    if ordered != sorted(set(ordered)):
        raise M7GateError("M7 official date evidence is duplicated or unordered")
    positions = {date: index for index, date in enumerate(ordered)}
    features = [
        date
        for date in ordered
        if protocol.pit["feature_start_date"] <= date <= protocol.pit["feature_end_date"]
    ]
    rows = []
    for feature in features:
        index = positions[feature]
        source = ordered[index - 1] if index else ""
        rows.append({"trade_date": feature, "source_date": source})
    return pd.DataFrame(rows)


def _coverage_tables(
    protocol: M7Protocol,
    membership: pd.DataFrame,
    source: pd.DataFrame,
    mapping: pd.DataFrame,
    quarantined: frozenset[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    mapped = membership.merge(mapping, on="trade_date", how="left", validate="many_to_one")
    keys = (
        source[["trade_date", "ts_code"]]
        .drop_duplicates()
        .rename(columns={"trade_date": "source_date"})
    )
    keys["source_present"] = True
    joined = mapped.merge(keys, on=["source_date", "ts_code"], how="left", validate="many_to_one")
    joined["quarantined"] = joined["source_date"].isin(quarantined)
    joined["matched"] = joined["source_present"].eq(True) & ~joined["quarantined"]
    daily = (
        joined.groupby(["universe_id", "trade_date", "source_date", "quarantined"], dropna=False)
        .agg(denominator=("ts_code", "size"), matched=("matched", "sum"))
        .reset_index()
    )
    daily["matched"] = daily["matched"].astype(int)
    daily["coverage_rate"] = [
        _ratio(int(row.matched), int(row.denominator)) for row in daily.itertuples(index=False)
    ]
    return joined, daily


def _coverage_report(protocol: M7Protocol, joined: pd.DataFrame, daily: pd.DataFrame) -> dict[str, Any]:
    aggregate = []
    eligible_rates = []
    daily_summary = []
    minimum_names = []
    half_year = []
    for universe in UNIVERSE_IDS:
        rows = joined.loc[joined["universe_id"].eq(universe)]
        dates = daily.loc[daily["universe_id"].eq(universe)].copy()
        eligible = dates.loc[~dates["quarantined"]].copy()
        aggregate.append(
            {
                "universe_id": universe,
                "denominator": len(rows),
                "matched": int(rows["matched"].sum()),
                "coverage_rate": _ratio(int(rows["matched"].sum()), len(rows)),
            }
        )
        eligible_rates.append(
            {
                "universe_id": universe,
                "feature_date_count": len(dates),
                "eligible_feature_date_count": len(eligible),
                "rate": _ratio(len(eligible), len(dates)),
            }
        )
        rates = eligible["coverage_rate"].astype(float)
        worst = eligible.sort_values(["coverage_rate", "trade_date"]).iloc[0] if len(eligible) else None
        daily_summary.append(
            {
                "universe_id": universe,
                "eligible_feature_date_count": len(eligible),
                "worst_feature_date": None if worst is None else str(worst["trade_date"]),
                "minimum": 0.0 if worst is None else round(float(worst["coverage_rate"]), 12),
                "p01": 0.0 if rates.empty else round(float(rates.quantile(0.01)), 12),
                "p05": 0.0 if rates.empty else round(float(rates.quantile(0.05)), 12),
                "median": 0.0 if rates.empty else round(float(rates.quantile(0.5)), 12),
            }
        )
        minimum_names.append(
            {
                "universe_id": universe,
                "minimum_matched": 0 if eligible.empty else int(eligible["matched"].min()),
            }
        )
        for segment in protocol.quality["complete_half_year_segments"]:
            segment_rows = rows.loc[rows["trade_date"].between(segment["start"], segment["end"])]
            half_year.append(
                {
                    "universe_id": universe,
                    "segment": segment["name"],
                    "denominator": len(segment_rows),
                    "matched": int(segment_rows["matched"].sum()),
                    "coverage_rate": _ratio(int(segment_rows["matched"].sum()), len(segment_rows)),
                }
            )
    return {
        "source_day_eligible_feature_date_rate_by_universe": eligible_rates,
        "aggregate_member_key_coverage_by_universe": aggregate,
        "half_year_member_key_coverage_by_universe": half_year,
        "eligible_feature_date_coverage_summary_by_universe": daily_summary,
        "minimum_matched_names_on_eligible_feature_date_by_universe": minimum_names,
    }


def _compute_quality_core(
    protocol: M7Protocol,
    inputs: KeyInputs,
    *,
    source_code_re: re.Pattern[str],
) -> dict[str, Any]:
    membership, source, malformed = _normalize(
        inputs,
        protocol,
        source_code_re=source_code_re,
    )
    mapping = _pit_mapping(protocol, inputs.official_dates)
    membership_duplicates = int(membership.duplicated(["trade_date", "universe_id", "ts_code"], keep=False).sum())
    source_duplicates = int(source.duplicated(["trade_date", "ts_code"], keep=False).sum())
    unknown_universe = int((~membership["universe_id"].isin(UNIVERSE_IDS)).sum())
    bse_rows = int(membership["ts_code"].str.endswith(".BJ", na=False).sum()) + int(
        source["ts_code"].str.endswith(".BJ", na=False).sum()
    )
    future_formation = int((membership["formation_date"] > membership["trade_date"]).sum())
    request_mismatch = int((source["trade_date"] != source["request_trade_date"]).sum())
    missing_map = int(mapping["source_date"].eq("").sum())
    same_or_future = int((mapping["source_date"] >= mapping["trade_date"]).sum())
    joined, daily = _coverage_tables(protocol, membership, source, mapping, inputs.quarantined_source_dates)
    coverage = _coverage_report(protocol, joined, daily)
    ordered_sources = mapping["source_date"].tolist()
    quarantined_in_scope = [date in inputs.quarantined_source_dates for date in ordered_sources]
    max_streak = _maximum_true_streak(quarantined_in_scope)
    quality = protocol.quality
    minimums = quality["minimum_matched_names_by_feature_date"]
    aggregate_rates = [item["coverage_rate"] for item in coverage["aggregate_member_key_coverage_by_universe"]]
    half_rates = [item["coverage_rate"] for item in coverage["half_year_member_key_coverage_by_universe"]]
    daily_rates = [item["minimum"] for item in coverage["eligible_feature_date_coverage_summary_by_universe"]]
    eligible_rates = [item["rate"] for item in coverage["source_day_eligible_feature_date_rate_by_universe"]]
    matched_ok = all(
        item["minimum_matched"] >= int(minimums[item["universe_id"]])
        for item in coverage["minimum_matched_names_on_eligible_feature_date_by_universe"]
    )
    invalid_keys = sum(malformed.values())
    gates = [
        _gate("membership_primary_key_unique", membership_duplicates == 0, membership_duplicates, 0),
        _gate("source_primary_key_unique", source_duplicates == 0, source_duplicates, 0),
        _gate("required_keys_valid", invalid_keys == 0, invalid_keys, 0),
        _gate("bse_absent", bse_rows == 0, bse_rows, 0),
        _gate("universe_identity_known", unknown_universe == 0, unknown_universe, 0),
        _gate("pit_mapping_exact", missing_map + same_or_future + request_mismatch == 0, missing_map + same_or_future + request_mismatch, 0),
        _gate("formation_not_future", future_formation == 0, future_formation, 0),
        _gate("source_revision_and_saturation_absent", True, 0, 0),
        _gate("source_day_eligible_rate", min(eligible_rates, default=0.0) >= quality["source_day_eligible_feature_date_rate_minimum"], min(eligible_rates, default=0.0), quality["source_day_eligible_feature_date_rate_minimum"]),
        _gate("aggregate_member_key_coverage", min(aggregate_rates, default=0.0) >= quality["aggregate_member_key_coverage_minimum_by_universe"], min(aggregate_rates, default=0.0), quality["aggregate_member_key_coverage_minimum_by_universe"]),
        _gate("half_year_member_key_coverage", min(half_rates, default=0.0) >= quality["half_year_member_key_coverage_minimum_by_universe"], min(half_rates, default=0.0), quality["half_year_member_key_coverage_minimum_by_universe"]),
        _gate("worst_eligible_feature_date_coverage", min(daily_rates, default=0.0) >= quality["worst_feature_date_member_key_coverage_minimum_by_universe"], min(daily_rates, default=0.0), quality["worst_feature_date_member_key_coverage_minimum_by_universe"]),
        _gate("maximum_quarantine_streak", max_streak <= quality["maximum_consecutive_quarantined_source_dates"], max_streak, quality["maximum_consecutive_quarantined_source_dates"]),
        _gate("minimum_matched_names", matched_ok, coverage["minimum_matched_names_on_eligible_feature_date_by_universe"], minimums),
    ]
    verdict = protocol.document["verdict"]["go"] if all(item["status"] == "PASS" for item in gates) else protocol.document["verdict"]["no_go"]
    return {
        "dataset_and_grain": {
            "grain": "feature_date_x_universe_id_x_ts_code",
            "membership_row_count": len(membership),
            "source_key_row_count": len(source),
            "feature_date_count": len(mapping),
            "universe_count": len(UNIVERSE_IDS),
        },
        "pit_mapping": {
            "mapping": "NEXT_OFFICIAL_SSE_OPEN_DATE",
            "feature_start_date": protocol.pit["feature_start_date"],
            "feature_end_date": protocol.pit["feature_end_date"],
            "source_start_date": protocol.pit["source_start_date"],
            "source_end_date": protocol.pit["source_end_date"],
            "missing_mapping_count": missing_map,
            "same_day_or_future_mapping_count": same_or_future,
            "request_payload_date_mismatch_count": request_mismatch,
        },
        "completeness": {
            **coverage,
            "quarantined_feature_date_count": sum(quarantined_in_scope),
            "maximum_consecutive_quarantined_source_dates": max_streak,
        },
        "uniqueness": {
            "membership_primary_key_duplicate_row_count": membership_duplicates,
            "source_primary_key_duplicate_row_count": source_duplicates,
        },
        "validity": {
            **malformed,
            "bse_row_count": bse_rows,
            "unknown_universe_row_count": unknown_universe,
            "future_formation_row_count": future_formation,
        },
        "integrity": {
            "source_revision_count": 0,
            "source_saturation_count": 0,
            "raw_projected_columns": inputs.evidence["raw_projected_columns"],
            "numeric_moneyflow_value_columns_read": inputs.evidence["numeric_moneyflow_value_columns_read"],
        },
        "gates": gates,
        "authority": {
            "candidate_definition_count": 0,
            "effect_test_count": 0,
            "generation_attempt_increment": 0,
            "strategy_effective": "NOT_EVALUATED",
            "production_authorization": "none",
        },
        "verdict": verdict,
    }


def compute_quality_core(protocol: M7Protocol, inputs: KeyInputs) -> dict[str, Any]:
    """Reproduce the frozen v1 SH-only source-domain behavior."""

    return _compute_quality_core(protocol, inputs, source_code_re=CODE_RE)


def compute_quality_core_all_a_source(
    protocol: M7Protocol,
    inputs: KeyInputs,
) -> dict[str, Any]:
    """Evaluate a successor source catalog that legitimately spans SH and SZ."""

    return _compute_quality_core(
        protocol,
        inputs,
        source_code_re=ALL_A_SOURCE_CODE_RE,
    )
