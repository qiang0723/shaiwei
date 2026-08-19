"""Gap-key extraction and per-key lineage explanation from bound evidence layers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import duckdb

from shaiwei.research.rf_0b.fields import _prepare_panel, classify_member_day
from shaiwei.research.rf_diag.contract import (
    EXPECTED_UNEXPLAINED_KEY_COUNT,
    RFDError,
    RFDScope,
)


EXPLANATION_CLASSES = (
    "SUSPENDED_BY_INDEPENDENT_BAOSTOCK_STATUS",
    "SUSPENDED_BY_SUSPEND_D_WITH_TIMING_ANNOTATION",
    "LIFECYCLE_LIST_OR_DELIST_EDGE",
    "MEMBERSHIP_FORMATION_EDGE",
    "UNEXPLAINED_REMAINS",
)


def assign_explanations(evidence: Mapping[str, Any]) -> tuple[str, ...]:
    """Map one key's bound evidence layers to explanation classes (multi allowed)."""
    classes: list[str] = []
    if evidence.get("baostock_status") == "0":
        classes.append("SUSPENDED_BY_INDEPENDENT_BAOSTOCK_STATUS")
    if evidence.get("suspend_d_record_count", 0) > 0:
        classes.append("SUSPENDED_BY_SUSPEND_D_WITH_TIMING_ANNOTATION")
    if evidence.get("lifecycle_edge"):
        classes.append("LIFECYCLE_LIST_OR_DELIST_EDGE")
    if evidence.get("formation_edge"):
        classes.append("MEMBERSHIP_FORMATION_EDGE")
    if not classes:
        classes.append("UNEXPLAINED_REMAINS")
    return tuple(classes)


def _derive_keys(connection: duckdb.DuckDBPyConnection, manifest: Mapping[str, Any], temporary: Path) -> list[tuple[str, str]]:
    _prepare_panel(connection, manifest, temporary)
    rows = connection.execute(
        "SELECT * FROM rf_panel ORDER BY ts_code, trade_date"
    ).fetchdf().to_dict("records")
    keys = sorted(
        (str(row["ts_code"]), str(row["trade_date"]))
        for row in rows
        if classify_member_day(row) == ("NO_BAR_UNEXPLAINED",)
    )
    if len(keys) != EXPECTED_UNEXPLAINED_KEY_COUNT:
        raise RFDError("RF diagnostic unexplained key count differs from the sealed profile")
    return keys


def _gather_evidence(
    connection: duckdb.DuckDBPyConnection, keys: list[tuple[str, str]]
) -> list[dict[str, Any]]:
    import pandas as pd

    connection.register("gap_keys", pd.DataFrame(keys, columns=["ts_code", "trade_date"]))
    try:
        rows = connection.execute(
            """
            SELECT k.ts_code, k.trade_date,
                   (SELECT count(*) FROM suspend_d s
                     WHERE CAST(s.ts_code AS VARCHAR)=k.ts_code
                       AND CAST(s.trade_date AS VARCHAR)=k.trade_date) AS suspend_d_record_count,
                   (SELECT max(trim(CAST(b.trade_status AS VARCHAR))) FROM baostock_status b
                     WHERE CAST(b.ts_code AS VARCHAR)=k.ts_code
                       AND replace(CAST(b.trade_date AS VARCHAR),'-','')=k.trade_date) AS baostock_status,
                   l.list_date, l.delist_date,
                   e.snapshot_date,
                   (SELECT count(*) FROM open_days d
                     WHERE d.trade_date>=l.list_date AND d.trade_date<=k.trade_date)
                     AS open_days_since_list,
                   (SELECT count(*) FROM open_days d
                     WHERE d.trade_date>=e.snapshot_date AND d.trade_date<=k.trade_date)
                     AS open_days_since_formation
            FROM gap_keys k
            LEFT JOIN lifecycle l USING(ts_code)
            LEFT JOIN expected e ON e.ts_code=k.ts_code AND e.trade_date=k.trade_date
            ORDER BY k.ts_code, k.trade_date
            """
        ).fetchdf().to_dict("records")
    finally:
        connection.unregister("gap_keys")
    evidence = []
    for row in rows:
        trade_date = str(row["trade_date"])
        list_date = str(row["list_date"]) if row["list_date"] else ""
        delist_date = str(row["delist_date"]) if row["delist_date"] else ""
        lifecycle_edge = bool(
            (list_date and int(row["open_days_since_list"]) <= 5)
            or (delist_date and trade_date >= _shift(delist_date, -14))
        )
        formation_edge = bool(
            row["snapshot_date"] is not None and int(row["open_days_since_formation"]) <= 3
        )
        evidence.append({
            "ts_code": str(row["ts_code"]),
            "trade_date": trade_date,
            "suspend_d_record_count": int(row["suspend_d_record_count"]),
            "baostock_status": row["baostock_status"],
            "list_date": list_date,
            "delist_date": delist_date,
            "lifecycle_edge": lifecycle_edge,
            "formation_edge": formation_edge,
        })
    return evidence


def _shift(day: str, calendar_days: int) -> str:
    import pandas as pd

    return (pd.Timestamp(day) + pd.Timedelta(days=calendar_days)).strftime("%Y%m%d")


def run_diagnostic(
    scope: RFDScope, temporary: Path, manifest: Mapping[str, Any]
) -> dict[str, Any]:
    connection = duckdb.connect(":memory:")
    try:
        keys = _derive_keys(connection, manifest, temporary)
        evidence = _gather_evidence(connection, keys)
    finally:
        connection.close()
    report_keys = []
    for row in evidence:
        classes = assign_explanations(row)
        report_keys.append({**row, "explanation_classes": list(classes)})
    all_explained = all(
        "UNEXPLAINED_REMAINS" not in row["explanation_classes"] for row in report_keys
    )
    verdict = (
        "DIAGNOSIS_COMPLETE_ALL_EXPLAINED"
        if all_explained
        else "DIAGNOSIS_COMPLETE_UNEXPLAINED_REMAINS"
    )
    return {
        "schema_version": "rf-0b-gap-lineage-diagnostic-report-v1",
        "protocol_sha256": scope.sha256,
        "unexplained_key_count": len(report_keys),
        "keys": report_keys,
        "authority": {
            "candidate_value_or_score_computed": False,
            "outcome_or_return_read": False,
            "external_api_calls": 0,
            "secret_read": False,
        },
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": verdict,
    }
