"""PIT CSI800 member-day open/prev-close field profile (counts and classes only)."""

from __future__ import annotations

from typing import Any, Mapping

import duckdb

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.trend_swing.r4_contract import load_r3_manifest
from shaiwei.research.trend_swing.recovery_store import configure_store, prepare_core_tables
from shaiwei.research.rf_0b.contract import RFBError, RFBScope


PERIOD = ("20190102", "20251231")

CLASSES = (
    "NO_BAR_SUSPENDED",
    "NO_BAR_UNEXPLAINED",
    "DUPLICATE_BAR_RECORD",
    "VALUE_VARIANT_CONFLICT",
    "OPEN_MISSING_OR_NONPOSITIVE",
    "PRE_CLOSE_MISSING_OR_NONPOSITIVE",
    "FIRST_LISTING_DAY",
    "CORPORATE_ACTION_DAY",
    "ONE_WORD_LIMIT_OPEN_PROXY",
    "BSE_ROW",
)


def classify_member_day(row: Mapping[str, Any]) -> tuple[str, ...]:
    """Classify one member day into zero or more failure/anomaly classes."""
    classes: list[str] = []
    if str(row["ts_code"]).endswith(".BJ"):
        classes.append("BSE_ROW")
    has_bar = bool(row["bar_record_count"])
    if not has_bar:
        classes.append(
            "NO_BAR_SUSPENDED" if row["primary_suspended"] else "NO_BAR_UNEXPLAINED"
        )
        return tuple(classes)
    if int(row["bar_record_count"]) != 1:
        classes.append("DUPLICATE_BAR_RECORD")
    if int(row["bar_variant_count"]) != 1:
        classes.append("VALUE_VARIANT_CONFLICT")
    open_ = row["open"]
    if open_ is None or not float(open_) > 0:
        classes.append("OPEN_MISSING_OR_NONPOSITIVE")
    pre_close = row["pre_close"]
    has_prior_bar = bool(row["prior_bar_close"] and float(row["prior_bar_close"]) > 0)
    if (pre_close is None or not float(pre_close) > 0) and not has_prior_bar:
        classes.append("PRE_CLOSE_MISSING_OR_NONPOSITIVE")
    if str(row["trade_date"]) == str(row["list_date"]):
        classes.append("FIRST_LISTING_DAY")
    if row["adj_factor"] is not None and row["prior_adj_factor"] is not None and float(
        row["adj_factor"]
    ) != float(row["prior_adj_factor"]):
        classes.append("CORPORATE_ACTION_DAY")
    if (
        open_ is not None
        and float(open_) > 0
        and pre_close is not None
        and float(pre_close) > 0
        and row["high"] is not None
        and row["low"] is not None
        and row["close"] is not None
        and float(row["open"]) == float(row["high"]) == float(row["low"]) == float(row["close"])
        and float(open_) > float(pre_close) * 1.045
    ):
        classes.append("ONE_WORD_LIMIT_OPEN_PROXY")
    return tuple(classes)


def _prepare_panel(connection: duckdb.DuckDBPyConnection, manifest: Mapping[str, Any]) -> None:
    configure_store(connection, None)
    prepare_core_tables(connection, manifest, start_date=PERIOD[0], end_date=PERIOD[1])
    connection.execute(
        """
        CREATE TEMP TABLE rf_daily AS
        SELECT CAST(d.ts_code AS VARCHAR) AS ts_code,
               CAST(d.trade_date AS VARCHAR) AS trade_date,
               count(*) AS bar_record_count,
               count(DISTINCT hash(d.open,d.high,d.low,d.close,d.pre_close,d.vol,d.amount))
                 AS bar_variant_count,
               max(try_cast(d.open AS DOUBLE)) AS open,
               max(try_cast(d.high AS DOUBLE)) AS high,
               max(try_cast(d.low AS DOUBLE)) AS low,
               max(try_cast(d.close AS DOUBLE)) AS close,
               max(try_cast(d.pre_close AS DOUBLE)) AS pre_close
        FROM daily d JOIN expected e
          ON CAST(d.ts_code AS VARCHAR)=e.ts_code
         AND CAST(d.trade_date AS VARCHAR)=e.trade_date
        GROUP BY 1,2
        """
    )
    connection.execute(
        """
        CREATE TEMP TABLE rf_panel AS
        SELECT e.ts_code, e.trade_date, e.list_date,
               coalesce(r.bar_record_count, 0) AS bar_record_count,
               coalesce(r.bar_variant_count, 0) AS bar_variant_count,
               r.open, r.high, r.low, r.close, r.pre_close,
               a.adj_factor,
               lag(a.adj_factor) OVER(
                 PARTITION BY e.ts_code ORDER BY e.trade_date
               ) AS prior_adj_factor,
               lag(r.close) OVER(
                 PARTITION BY e.ts_code ORDER BY e.trade_date
               ) AS prior_bar_close,
               coalesce(p.ts_code IS NOT NULL, false) AS primary_suspended
        FROM expected e
        LEFT JOIN rf_daily r USING(ts_code, trade_date)
        LEFT JOIN adj_keys a USING(ts_code, trade_date)
        LEFT JOIN primary_suspension p USING(ts_code, trade_date)
        """
    )


def field_profile(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    rows = connection.execute(
        "SELECT * FROM rf_panel ORDER BY ts_code, trade_date"
    ).fetchdf().to_dict("records")
    if not rows:
        raise RFBError("RF-0B member-day panel is empty")
    counts = {name: 0 for name in CLASSES}
    open_ok = prev_close_ok = unclassified_missing = 0
    for row in rows:
        classes = classify_member_day(row)
        for name in classes:
            counts[name] += 1
        no_bar = "NO_BAR_SUSPENDED" in classes or "NO_BAR_UNEXPLAINED" in classes
        open_ok += int(
            not no_bar and "OPEN_MISSING_OR_NONPOSITIVE" not in classes
        )
        prev_close_ok += int(
            not no_bar and "PRE_CLOSE_MISSING_OR_NONPOSITIVE" not in classes
        )
        if (
            ("OPEN_MISSING_OR_NONPOSITIVE" in classes)
            and len(classes) == 1
        ):
            unclassified_missing += 1
    total = len(rows)
    return {
        "period": {"start": PERIOD[0], "end": PERIOD[1]},
        "member_day_count": total,
        "open_coverage": open_ok / total,
        "prev_close_coverage": prev_close_ok / total,
        "class_counts": counts,
        "unclassified_missing_open_rows": unclassified_missing,
    }


def evaluate_field_gate(profile: Mapping[str, Any], gate: Mapping[str, Any]) -> dict[str, Any]:
    checks = {
        "open_coverage": profile["open_coverage"]
        >= float(gate["open_coverage_minimum_of_member_days"]),
        "prev_close_coverage": profile["prev_close_coverage"]
        >= float(gate["prev_close_join_minimum_of_member_days"]),
        "bse_rows": profile["class_counts"]["BSE_ROW"]
        <= int(gate["bse_row_maximum"]),
        "unclassified_missing": profile["class_counts"]["NO_BAR_UNEXPLAINED"]
        <= int(gate["unclassified_missing_field_rows_maximum"]),
    }
    return {"checks": checks, "pass": all(checks.values())}


def real_field_profile(scope: RFBScope, temporary_root: Any = None) -> dict[str, Any]:
    manifest_path = PROJECT_ROOT / scope.document["frozen_inputs"]["raw_market_store"][
        "r3_frozen_input_manifest"
    ]["path"]
    manifest = load_r3_manifest(manifest_path)
    connection = duckdb.connect(":memory:")
    try:
        _prepare_panel(connection, manifest)
        return field_profile(connection)
    finally:
        connection.close()
