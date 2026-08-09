"""Project only the two frozen R2 recovery categories into exact source keys."""

from __future__ import annotations

import pandas as pd

from shaiwei.research_gates.m7_moneyflow.contract import sha256_json
from shaiwei.research_gates.m7_moneyflow_lineage.compute import (
    _joined,
    _normalize,
    compute_lineage_core,
)
from shaiwei.research_gates.m7_moneyflow_lineage.contract import LineageProtocol
from shaiwei.research_gates.m7_moneyflow_lineage.reader import LineageInputs

from .contract import RecoveryError, RecoveryProtocol, TARGET_COLUMNS


TRACK_A = "PRIMARY_FULL_DAY_SUSPENSION_ONLY_UNRESOLVED"
TRACK_B = "CONFIRMED_MONEYFLOW_GAP_DAILY_PRESENT"
OUTPUT_COLUMNS = ("trade_date", "source_date", "universe_id", "ts_code", "segment")


def _project(missing: pd.DataFrame, category: str) -> pd.DataFrame:
    selected = missing.loc[missing["category"].eq(category)].copy()
    result = selected.loc[:, OUTPUT_COLUMNS].astype("string")
    return result.sort_values(list(OUTPUT_COLUMNS)).reset_index(drop=True)


def recovery_request_targets(projected: pd.DataFrame) -> pd.DataFrame:
    """Derive the provider request view without destroying the feature date."""

    if not set(OUTPUT_COLUMNS) <= set(projected.columns):
        raise RecoveryError("recovery target projection columns differ")
    result = projected.loc[:, ["source_date", "universe_id", "ts_code", "segment"]].copy()
    result = result.rename(columns={"source_date": "trade_date"})
    return result.loc[:, TARGET_COLUMNS].astype("string")


def project_recovery_targets(
    recovery: RecoveryProtocol,
    lineage: LineageProtocol,
    inputs: LineageInputs,
    *,
    expected_lineage_core_sha256: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Reuse the frozen R2 classifier and bind the exact predecessor core."""

    core = compute_lineage_core(lineage, inputs)
    core_sha256 = sha256_json(core)
    if core_sha256 != expected_lineage_core_sha256:
        raise RecoveryError("recovery target projection lineage core differs")
    membership, diagnostics = _normalize(inputs, lineage)
    missing, missing_mapping = _joined(lineage, inputs, membership)
    if missing_mapping or any(diagnostics.values()):
        raise RecoveryError("recovery target projection predecessor validity differs")
    track_a = _project(missing, TRACK_A)
    track_b = _project(missing, TRACK_B)
    if len(track_a) != recovery.expected_track_a_rows or len(track_b) != recovery.expected_track_b_rows:
        raise RecoveryError("recovery target projection category counts differ")
    if track_a.duplicated(["trade_date", "universe_id", "ts_code"]).any() or track_b.duplicated(
        ["trade_date", "universe_id", "ts_code"]
    ).any():
        raise RecoveryError("recovery target projection contains duplicate member rows")
    if track_a["ts_code"].str.endswith(".BJ").any() or track_b["ts_code"].str.endswith(".BJ").any():
        raise RecoveryError("recovery target projection contains BSE securities")
    summary = {
        "schema_version": "m7-moneyflow-recovery-target-summary-v1",
        "lineage_core_sha256": core_sha256,
        "track_a_member_rows": len(track_a),
        "track_a_unique_source_keys": len(track_a.drop_duplicates(["ts_code", "source_date"])),
        "track_b_member_rows": len(track_b),
        "track_b_unique_source_keys": len(track_b.drop_duplicates(["ts_code", "source_date"])),
        "numeric_moneyflow_value_columns_read": 0,
        "security_codes_in_summary": False,
        "production_authorization": "none",
    }
    return track_a, track_b, summary
