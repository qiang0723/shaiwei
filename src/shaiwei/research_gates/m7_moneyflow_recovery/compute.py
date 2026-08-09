"""Pandas authority for synthetic M7 evidence-recovery quality decisions."""

from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd

from shaiwei.research_gates.m7_moneyflow.contract import sha256_json

from .contract import RecoveryProtocol, TARGET_COLUMNS, UNIVERSE_IDS
from .inputs import RecoveryInputs
from .planning import plan_moneyflow_requests, plan_status_requests


CODE_RE = re.compile(r"^[0-9]{6}\.SH$")
DATE_RE = re.compile(r"^[0-9]{8}$")
SEGMENT_RE = re.compile(r"^[0-9]{4}H[12]$")


def _duplicate_rows(frame: pd.DataFrame, keys: list[str]) -> int:
    return int(frame.duplicated(keys, keep=False).sum())


def _target_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if not set(TARGET_COLUMNS) <= set(frame.columns):
        return pd.DataFrame(columns=TARGET_COLUMNS)
    result = frame.loc[:, TARGET_COLUMNS].copy()
    for column in TARGET_COLUMNS:
        result[column] = result[column].astype("string")
    return result


def _key_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if not {"ts_code", "trade_date"} <= set(frame.columns):
        return pd.DataFrame(columns=["ts_code", "trade_date"])
    result = frame.loc[:, ["ts_code", "trade_date"]].copy()
    result["ts_code"] = result["ts_code"].astype("string")
    result["trade_date"] = result["trade_date"].astype("string")
    return result


def _keys(frame: pd.DataFrame) -> set[tuple[str, str]]:
    return set(_key_frame(frame).itertuples(index=False, name=None))


def _target_invalid_rows(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    invalid = (
        ~frame["ts_code"].fillna("").str.fullmatch(CODE_RE)
        | ~frame["trade_date"].fillna("").str.fullmatch(DATE_RE)
        | ~frame["segment"].fillna("").str.fullmatch(SEGMENT_RE)
        | ~frame["universe_id"].isin(UNIVERSE_IDS)
    )
    return int(invalid.sum())


def _moneyflow_metrics(
    protocol: RecoveryProtocol,
    frame: pd.DataFrame,
    target_keys: set[tuple[str, str]],
) -> tuple[dict[str, int], dict[tuple[str, str], str]]:
    fields = protocol.moneyflow_fields
    schema_errors = int(tuple(frame.columns) != fields)
    metrics = {
        "schema_errors": schema_errors,
        "duplicate_rows": 0,
        "numeric_invalid_cells": 0,
        "missing_keys": len(target_keys),
        "extra_keys": 0,
    }
    if schema_errors:
        return metrics, {}
    normalized = frame.loc[:, fields].copy()
    normalized["ts_code"] = normalized["ts_code"].astype("string")
    normalized["trade_date"] = normalized["trade_date"].astype("string")
    metrics["duplicate_rows"] = _duplicate_rows(normalized, ["ts_code", "trade_date"])
    observed = _keys(normalized)
    metrics["missing_keys"] = len(target_keys - observed)
    metrics["extra_keys"] = len(observed - target_keys)
    numeric_fields = fields[2:]
    values = normalized.loc[:, numeric_fields].apply(pd.to_numeric, errors="coerce")
    invalid = values.isna()
    for column in numeric_fields:
        invalid[column] |= ~values[column].map(math.isfinite)
    metrics["numeric_invalid_cells"] = int(invalid.sum().sum())
    signatures: dict[tuple[str, str], str] = {}
    if not metrics["duplicate_rows"] and not metrics["numeric_invalid_cells"]:
        for index, row in normalized.iterrows():
            key = (str(row["ts_code"]), str(row["trade_date"]))
            signatures[key] = sha256_json(
                [key[0], key[1], *[float(values.at[index, field]) for field in numeric_fields]]
            )
    return metrics, signatures


def _plan_metrics(
    protocol: RecoveryProtocol,
    track_a: pd.DataFrame,
    track_b: pd.DataFrame,
    official_dates: tuple[str, ...],
) -> dict[str, int]:
    try:
        status = plan_status_requests(protocol, track_a, official_dates)
        moneyflow = plan_moneyflow_requests(protocol, track_b)
    except (KeyError, TypeError, ValueError, RuntimeError):
        return {
            "status_request_count": 0,
            "full_market_request_count": 0,
            "targeted_request_count": 0,
            "request_plan_failures": 1,
        }
    return {
        "status_request_count": len(status),
        "full_market_request_count": sum(
            request.shape == "full_market_by_trade_date" for request in moneyflow
        ),
        "targeted_request_count": sum(
            request.shape == "one_security_one_date" for request in moneyflow
        ),
        "request_plan_failures": 0,
    }


def compute_audit_vector(
    protocol: RecoveryProtocol,
    inputs: RecoveryInputs,
) -> dict[str, int]:
    track_a = _target_frame(inputs.track_a_targets)
    track_b = _target_frame(inputs.track_b_targets)
    track_a_keys = _keys(track_a)
    track_b_keys = _keys(track_b)
    daily = _key_frame(inputs.daily_keys)
    daily_keys = _keys(daily)
    status = inputs.independent_status.copy()
    status_schema = int(tuple(status.columns) != ("ts_code", "trade_date", "trade_status"))
    if not status_schema:
        status = status.astype("string")
        status["trade_status"] = status["trade_status"].str.strip()
        status_keys = _keys(status)
        status_invalid = int((~status["trade_status"].isin(["0", "1"])).sum())
        status_duplicates = _duplicate_rows(status, ["ts_code", "trade_date"])
        nontrading = _keys(status.loc[status["trade_status"].eq("0")])
        trading = _keys(status.loc[status["trade_status"].eq("1")])
    else:
        status_keys, nontrading, trading = set(), set(), set()
        status_invalid = status_duplicates = len(status)
    full_metrics, full_signatures = _moneyflow_metrics(
        protocol, inputs.full_market_target_rows, track_b_keys
    )
    targeted_metrics, targeted_signatures = _moneyflow_metrics(
        protocol, inputs.targeted_rows, track_b_keys
    )
    comparable = set(full_signatures) & set(targeted_signatures) & track_b_keys
    vector = {
        "track_a_target_member_rows": len(track_a),
        "track_a_unique_keys": len(track_a_keys),
        "track_b_target_member_rows": len(track_b),
        "track_b_unique_keys": len(track_b_keys),
        "target_membership_duplicate_rows": _duplicate_rows(
            track_a, ["trade_date", "universe_id", "ts_code"]
        )
        + _duplicate_rows(track_b, ["trade_date", "universe_id", "ts_code"]),
        "target_invalid_rows": _target_invalid_rows(track_a) + _target_invalid_rows(track_b),
        "target_bse_rows": int(track_a["ts_code"].str.endswith(".BJ", na=False).sum())
        + int(track_b["ts_code"].str.endswith(".BJ", na=False).sum()),
        "track_overlap_unique_keys": len(track_a_keys & track_b_keys),
        "daily_duplicate_rows": _duplicate_rows(daily, ["ts_code", "trade_date"]),
        "track_a_daily_present_keys": len(track_a_keys & daily_keys),
        "track_b_daily_missing_keys": len(track_b_keys - daily_keys),
        "daily_extra_keys": len(daily_keys - track_a_keys - track_b_keys),
        "status_schema_errors": status_schema,
        "status_duplicate_rows": status_duplicates,
        "status_invalid_rows": status_invalid,
        "status_extra_keys": len(status_keys - track_a_keys),
        "status_missing_keys": len(track_a_keys - status_keys),
        "status_trading_keys": len(track_a_keys & trading),
        "status_nontrading_keys": len(track_a_keys & nontrading),
        "full_schema_errors": full_metrics["schema_errors"],
        "targeted_schema_errors": targeted_metrics["schema_errors"],
        "full_duplicate_rows": full_metrics["duplicate_rows"],
        "targeted_duplicate_rows": targeted_metrics["duplicate_rows"],
        "moneyflow_numeric_invalid_cells": full_metrics["numeric_invalid_cells"]
        + targeted_metrics["numeric_invalid_cells"],
        "full_missing_keys": full_metrics["missing_keys"],
        "targeted_missing_keys": targeted_metrics["missing_keys"],
        "full_extra_keys": full_metrics["extra_keys"],
        "targeted_extra_keys": targeted_metrics["extra_keys"],
        "matching_content_keys": sum(
            full_signatures[key] == targeted_signatures[key] for key in comparable
        ),
        "content_mismatch_keys": sum(
            full_signatures[key] != targeted_signatures[key] for key in comparable
        ),
        "saturated_response_count": sum(
            count >= int(
                protocol.document["track_b_same_semantic_moneyflow"]["maximum_rows_per_response"]
            )
            for count in inputs.full_market_response_row_counts
        ),
        "immutable_batch_integrity_failures": int(not inputs.immutable_batch_integrity),
        **_plan_metrics(protocol, track_a, track_b, inputs.official_dates),
    }
    return vector


def _gate(gate_id: str, passed: bool, observed: Any, threshold: Any) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": "PASS" if passed else "FAIL",
        "observed": observed,
        "threshold": threshold,
    }


def _segments(
    targets: pd.DataFrame,
    closed_keys: set[tuple[str, str]],
    track: str,
) -> list[dict[str, Any]]:
    frame = _target_frame(targets)
    frame["closed"] = [
        (str(row.ts_code), str(row.trade_date)) in closed_keys for row in frame.itertuples(index=False)
    ]
    rows = []
    for universe in UNIVERSE_IDS:
        for segment in sorted(set(frame["segment"].dropna().astype(str))):
            cell = frame.loc[
                frame["universe_id"].eq(universe) & frame["segment"].eq(segment)
            ]
            rows.append(
                {
                    "track": track,
                    "universe_id": universe,
                    "segment": segment,
                    "member_row_count": len(cell),
                    "closed_member_row_count": int(cell["closed"].sum()),
                }
            )
    return rows


def compute_recovery_core(
    protocol: RecoveryProtocol,
    inputs: RecoveryInputs,
) -> dict[str, Any]:
    vector = compute_audit_vector(protocol, inputs)
    duplicate_total = sum(vector[field] for field in (
        "target_membership_duplicate_rows",
        "daily_duplicate_rows",
        "status_duplicate_rows",
        "full_duplicate_rows",
        "targeted_duplicate_rows",
    ))
    invalid_total = sum(vector[field] for field in (
        "target_invalid_rows",
        "target_bse_rows",
        "status_schema_errors",
        "status_invalid_rows",
        "full_schema_errors",
        "targeted_schema_errors",
        "moneyflow_numeric_invalid_cells",
        "saturated_response_count",
    ))
    extra_total = sum(vector[field] for field in (
        "daily_extra_keys", "status_extra_keys", "full_extra_keys", "targeted_extra_keys"
    ))
    partition_failures = (
        abs(vector["track_a_target_member_rows"] - protocol.expected_track_a_rows)
        + abs(vector["track_b_target_member_rows"] - protocol.expected_track_b_rows)
        + vector["track_overlap_unique_keys"]
    )
    track_a_unresolved = vector["status_missing_keys"]
    track_a_conflicts = vector["status_trading_keys"] + vector["track_a_daily_present_keys"]
    track_b_missing = vector["full_missing_keys"] + vector["targeted_missing_keys"]
    gates = [
        _gate("predecessor_identity_pass", True, 0, 0),
        _gate("exact_partition_domain_pass", partition_failures == 0, partition_failures, 0),
        _gate("key_uniqueness_pass", duplicate_total == 0, duplicate_total, 0),
        _gate("key_validity_and_bj_zero_pass", invalid_total == 0, invalid_total, 0),
        _gate(
            "request_plan_complete_and_no_extra_keys_pass",
            vector["request_plan_failures"] + extra_total == 0,
            vector["request_plan_failures"] + extra_total,
            0,
        ),
        _gate(
            "track_a_all_908_terminal_pass",
            vector["status_nontrading_keys"] == vector["track_a_unique_keys"]
            and track_a_unresolved == 0,
            vector["status_nontrading_keys"],
            vector["track_a_unique_keys"],
        ),
        _gate(
            "track_a_conflict_and_unresolved_zero_pass",
            track_a_conflicts + track_a_unresolved == 0,
            track_a_conflicts + track_a_unresolved,
            0,
        ),
        _gate(
            "track_b_all_unique_keys_recovered_pass",
            track_b_missing == 0,
            track_b_missing,
            0,
        ),
        _gate(
            "track_b_request_shape_presence_and_content_agreement_pass",
            track_b_missing + vector["content_mismatch_keys"] == 0,
            track_b_missing + vector["content_mismatch_keys"],
            0,
        ),
        _gate(
            "immutable_batch_integrity_pass",
            vector["immutable_batch_integrity_failures"] == 0,
            vector["immutable_batch_integrity_failures"],
            0,
        ),
    ]
    status_keys = _keys(inputs.independent_status.loc[
        inputs.independent_status.get("trade_status", pd.Series(dtype="string")).astype("string").eq("0")
    ]) if "trade_status" in inputs.independent_status else set()
    full_keys = _keys(inputs.full_market_target_rows)
    targeted_keys = _keys(inputs.targeted_rows)
    decision = protocol.document["decision"]
    verdict = decision["go"] if all(gate["status"] == "PASS" for gate in gates) else decision["no_go"]
    return {
        "dataset_and_grain": {
            "grain": "source_date_x_ts_code_with_member_row_projection",
            "track_a_member_rows": vector["track_a_target_member_rows"],
            "track_b_member_rows": vector["track_b_target_member_rows"],
            "track_a_unique_keys": vector["track_a_unique_keys"],
            "track_b_unique_keys": vector["track_b_unique_keys"],
        },
        "request_plan": {
            "status_request_count": vector["status_request_count"],
            "full_market_request_count": vector["full_market_request_count"],
            "targeted_request_count": vector["targeted_request_count"],
            "external_provider_call_count": 0,
        },
        "track_a": {
            "confirmed_nontrading_unique_keys": vector["status_nontrading_keys"],
            "conflict_unique_keys": track_a_conflicts,
            "unresolved_unique_keys": track_a_unresolved,
        },
        "track_b": {
            "recovered_unique_keys": vector["matching_content_keys"],
            "missing_shape_key_count": track_b_missing,
            "content_mismatch_key_count": vector["content_mismatch_keys"],
        },
        "segments": [
            *_segments(inputs.track_a_targets, status_keys, "A"),
            *_segments(inputs.track_b_targets, full_keys & targeted_keys, "B"),
        ],
        "audit_vector": vector,
        "gates": gates,
        "authority": {
            "adjusted_or_counterfactual_coverage_computed": False,
            "candidate_definition_count": 0,
            "effect_test_count": 0,
            "research_attempt_increment": 0,
            "strategy_effective": "NOT_EVALUATED",
            "production_authorization": "none",
        },
        "verdict": verdict,
    }
