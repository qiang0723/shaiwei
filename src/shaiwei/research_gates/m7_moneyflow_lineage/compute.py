"""Pandas main computation for aggregate-only M7 missing-key lineage."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .contract import CATEGORIES, UNIVERSE_IDS, LineageError, LineageProtocol
from .reader import LineageInputs


DATE_RE = re.compile(r"^[0-9]{8}$")
MEMBER_RE = re.compile(r"^[0-9]{6}\.SH$")
SOURCE_RE = re.compile(r"^[0-9]{6}\.(?:SH|SZ)$")
CONFLICTS = frozenset(
    {
        "CONFLICTING_INDEPENDENT_TRADE_STATUS",
        "CONFLICT_DAILY_PRESENT_INDEPENDENT_NONTRADING",
        "CONFLICT_DAILY_ABSENT_INDEPENDENT_TRADING",
        "CONFLICTING_PRIMARY_SUSPENSION_ROWS",
    }
)
UNRESOLVED = frozenset(
    {
        "PRIMARY_FULL_DAY_SUSPENSION_ONLY_UNRESOLVED",
        "INTRADAY_SUSPENSION_NOT_EXPLANATION",
        "UNRESOLVED_NO_TRADE_EVIDENCE",
    }
)


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 12) if denominator else 0.0


def _gate(gate_id: str, passed: bool, observed: Any, threshold: Any) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": "PASS" if passed else "FAIL",
        "observed": observed,
        "threshold": threshold,
    }


def _mapping(protocol: LineageProtocol, dates: tuple[str, ...]) -> pd.DataFrame:
    ordered = list(dates)
    if ordered != sorted(set(ordered)):
        raise LineageError("lineage official dates are duplicated or unordered")
    positions = {date: index for index, date in enumerate(ordered)}
    scope = protocol.document["scope"]
    features = [date for date in ordered if scope["feature_date_start"] <= date <= scope["feature_date_end"]]
    return pd.DataFrame(
        [
            {
                "trade_date": feature,
                "source_date": ordered[positions[feature] - 1] if positions[feature] else "",
            }
            for feature in features
        ]
    )


def _normalize(inputs: LineageInputs, protocol: LineageProtocol) -> tuple[pd.DataFrame, dict[str, int]]:
    membership = inputs.membership.copy()
    moneyflow = inputs.moneyflow_keys.copy()
    scope = protocol.document["scope"]
    for frame, columns in (
        (membership, ("trade_date", "formation_date", "universe_id", "ts_code")),
        (moneyflow, ("trade_date", "ts_code", "request_trade_date")),
    ):
        for column in columns:
            frame[column] = frame[column].astype("string")
    membership = membership.loc[
        membership["trade_date"].between(scope["feature_date_start"], scope["feature_date_end"])
    ].copy()
    moneyflow = moneyflow.loc[
        moneyflow["trade_date"].between(scope["source_date_start"], scope["source_date_end"])
    ].copy()
    source_frames = [
        moneyflow[["ts_code", "trade_date"]],
        inputs.daily_keys,
        inputs.suspension,
        inputs.independent_status,
    ]
    diagnostics = {
        "membership_duplicate_rows": int(
            membership.duplicated(["trade_date", "universe_id", "ts_code"], keep=False).sum()
        ),
        "moneyflow_duplicate_rows": int(moneyflow.duplicated(["trade_date", "ts_code"], keep=False).sum()),
        "membership_invalid_rows": int((~membership["ts_code"].fillna("").str.fullmatch(MEMBER_RE)).sum()),
        "source_invalid_rows": sum(
            int((~frame["ts_code"].astype("string").fillna("").str.fullmatch(SOURCE_RE)).sum())
            for frame in source_frames
        ),
        "bse_rows": sum(
            int(frame["ts_code"].astype("string").fillna("").str.endswith(".BJ").sum())
            for frame in [membership, *source_frames]
        ),
        "invalid_independent_status_rows": int(
            inputs.independent_status.get("invalid_status_rows", pd.Series(dtype=int)).sum()
        ),
    }
    return membership, diagnostics


def _classify(joined: pd.DataFrame) -> pd.Series:
    status_conflict = joined["independent_nontrading"].eq(1) & joined["independent_trading"].eq(1)
    choices = [
        joined["quarantined"],
        status_conflict,
        joined["daily_present"] & joined["independent_nontrading"].eq(1),
        joined["daily_present"],
        ~joined["daily_present"] & joined["independent_trading"].eq(1),
        joined["independent_nontrading"].eq(1),
        joined["primary_full_day"].eq(1) & joined["primary_intraday"].eq(1),
        joined["primary_full_day"].eq(1),
        joined["primary_intraday"].eq(1),
    ]
    result = pd.Series("UNRESOLVED_NO_TRADE_EVIDENCE", index=joined.index, dtype="string")
    for condition, category in reversed(list(zip(choices, CATEGORIES[:-1]))):
        result.loc[condition.fillna(False)] = category
    return result


def _joined(
    protocol: LineageProtocol, inputs: LineageInputs, membership: pd.DataFrame
) -> tuple[pd.DataFrame, int]:
    mapping = _mapping(protocol, inputs.official_dates)
    joined = membership.merge(mapping, on="trade_date", how="left", validate="many_to_one")
    moneyflow = (
        inputs.moneyflow_keys[["ts_code", "trade_date"]]
        .drop_duplicates()
        .rename(columns={"trade_date": "source_date"})
    )
    moneyflow["moneyflow_present"] = True
    daily = (
        inputs.daily_keys[["ts_code", "trade_date"]]
        .drop_duplicates()
        .rename(columns={"trade_date": "source_date"})
    )
    daily["daily_present"] = True
    suspension = inputs.suspension.rename(columns={"trade_date": "source_date"})
    independent = inputs.independent_status.rename(columns={"trade_date": "source_date"})
    for evidence in (moneyflow, daily, suspension, independent):
        joined = joined.merge(evidence, on=["ts_code", "source_date"], how="left", validate="many_to_one")
    joined["quarantined"] = joined["source_date"].isin(inputs.quarantined_source_dates)
    joined["moneyflow_present"] = joined["moneyflow_present"].eq(True)
    joined["daily_present"] = joined["daily_present"].eq(True)
    for column in ("primary_full_day", "primary_intraday", "independent_nontrading", "independent_trading"):
        joined[column] = joined[column].fillna(0).astype(int)
    joined["matched"] = joined["moneyflow_present"] & ~joined["quarantined"]
    missing = joined.loc[~joined["matched"]].copy()
    missing["category"] = _classify(missing)
    missing_mapping = int(joined["source_date"].isna().sum() + joined["source_date"].eq("").sum())
    return missing, missing_mapping


def _segments(protocol: LineageProtocol, missing: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    segments = protocol.document["scope"]["complete_half_year_segments"]
    for universe in UNIVERSE_IDS:
        universe_rows = missing.loc[missing["universe_id"].eq(universe)]
        for segment in segments:
            cell = universe_rows.loc[universe_rows["trade_date"].between(segment["start"], segment["end"])]
            counts = cell["category"].value_counts().to_dict()
            total = len(cell)
            rows.append(
                {
                    "universe_id": universe,
                    "segment": segment["name"],
                    "missing_row_count": total,
                    "category_counts": {category: int(counts.get(category, 0)) for category in CATEGORIES},
                    "category_rates": {
                        category: _ratio(int(counts.get(category, 0)), total) for category in CATEGORIES
                    },
                }
            )
    return rows


def compute_lineage_core(protocol: LineageProtocol, inputs: LineageInputs) -> dict[str, Any]:
    membership, diagnostics = _normalize(inputs, protocol)
    missing, missing_mapping = _joined(protocol, inputs, membership)
    counts = missing["category"].value_counts().to_dict()
    category_counts = {category: int(counts.get(category, 0)) for category in CATEGORIES}
    conflict_count = sum(category_counts[item] for item in CONFLICTS)
    unresolved_count = sum(category_counts[item] for item in UNRESOLVED)
    partition_delta = len(missing) - sum(category_counts.values())
    invalid_keys = (
        diagnostics["membership_invalid_rows"]
        + diagnostics["source_invalid_rows"]
        + diagnostics["bse_rows"]
        + diagnostics["invalid_independent_status_rows"]
    )
    gates = [
        _gate(
            "input_key_rows_unique",
            diagnostics["membership_duplicate_rows"] + diagnostics["moneyflow_duplicate_rows"] == 0,
            diagnostics["membership_duplicate_rows"] + diagnostics["moneyflow_duplicate_rows"],
            0,
        ),
        _gate("key_domain_pass", invalid_keys == 0, invalid_keys, 0),
        _gate("pit_mapping_pass", missing_mapping == 0, missing_mapping, 0),
        _gate("missing_row_partition_pass", partition_delta == 0, partition_delta, 0),
        _gate("conflict_row_count_zero", conflict_count == 0, conflict_count, 0),
        _gate("unresolved_row_count_zero", unresolved_count == 0, unresolved_count, 0),
    ]
    decision = protocol.document["decision"]
    verdict = decision["go"] if all(item["status"] == "PASS" for item in gates) else decision["no_go"]
    return {
        "dataset_and_grain": {
            "grain": "feature_date_x_universe_id_x_ts_code",
            "membership_row_count": len(membership),
            "missing_row_count": len(missing),
            "universe_count": len(UNIVERSE_IDS),
            "half_year_segment_count": len(protocol.document["scope"]["complete_half_year_segments"]),
        },
        "lineage_partition": {
            "category_counts": category_counts,
            "category_rates_within_missing": {
                category: _ratio(count, len(missing)) for category, count in category_counts.items()
            },
            "conflict_row_count": conflict_count,
            "unresolved_row_count": unresolved_count,
            "partition_delta": partition_delta,
            "cells": _segments(protocol, missing),
        },
        "validity": diagnostics,
        "gates": gates,
        "authority": {
            "adjusted_or_counterfactual_coverage_computed": False,
            "candidate_definition_count": 0,
            "effect_test_count": 0,
            "generation_attempt_increment": 0,
            "strategy_effective": "NOT_EVALUATED",
            "production_authorization": "none",
        },
        "verdict": verdict,
    }
