"""Independent DuckDB recomputation of the M7 recovery audit vector."""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from .contract import RecoveryProtocol, TARGET_COLUMNS, UNIVERSE_IDS
from .inputs import RecoveryInputs


def _target(frame: pd.DataFrame) -> pd.DataFrame:
    if not set(TARGET_COLUMNS) <= set(frame.columns):
        return pd.DataFrame(columns=TARGET_COLUMNS)
    result = frame.loc[:, TARGET_COLUMNS].copy()
    for column in TARGET_COLUMNS:
        result[column] = result[column].astype("string")
    return result


def _keys(frame: pd.DataFrame) -> pd.DataFrame:
    if not {"ts_code", "trade_date"} <= set(frame.columns):
        return pd.DataFrame(columns=["ts_code", "trade_date"])
    result = frame.loc[:, ["ts_code", "trade_date"]].copy()
    return result.astype("string")


def _scalar(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    params: list[Any] | None = None,
) -> int:
    value = connection.execute(query, params or []).fetchone()[0]
    return int(value or 0)


def _duplicate_rows(connection: duckdb.DuckDBPyConnection, table: str, keys: str) -> int:
    return _scalar(
        connection,
        f"SELECT coalesce(sum(n),0) FROM (SELECT count(*) n FROM {table} "
        f"GROUP BY {keys} HAVING count(*)>1)",
    )


def _moneyflow_metrics(
    connection: duckdb.DuckDBPyConnection,
    protocol: RecoveryProtocol,
    *,
    table: str,
    frame: pd.DataFrame,
) -> dict[str, int]:
    fields = protocol.moneyflow_fields
    schema_errors = int(tuple(frame.columns) != fields)
    target_count = _scalar(connection, "SELECT count(*) FROM b_keys")
    metrics = {
        "schema_errors": schema_errors,
        "duplicate_rows": 0,
        "numeric_invalid_cells": 0,
        "missing_keys": target_count,
        "extra_keys": 0,
    }
    if schema_errors:
        return metrics
    connection.register(f"raw_{table}", frame)
    connection.execute(
        f"CREATE TEMP TABLE {table} AS SELECT * FROM raw_{table}"
    )
    metrics["duplicate_rows"] = _duplicate_rows(connection, table, "ts_code,trade_date")
    metrics["missing_keys"] = _scalar(
        connection,
        f"SELECT count(*) FROM b_keys b ANTI JOIN "
        f"(SELECT DISTINCT CAST(ts_code AS VARCHAR) ts_code, CAST(trade_date AS VARCHAR) trade_date FROM {table}) x "
        "USING (ts_code,trade_date)",
    )
    metrics["extra_keys"] = _scalar(
        connection,
        f"SELECT count(*) FROM (SELECT DISTINCT CAST(ts_code AS VARCHAR) ts_code, "
        f"CAST(trade_date AS VARCHAR) trade_date FROM {table}) x ANTI JOIN b_keys b "
        "USING (ts_code,trade_date)",
    )
    expressions = [
        f"CASE WHEN try_cast({field} AS DOUBLE) IS NULL "
        f"OR NOT isfinite(try_cast({field} AS DOUBLE)) THEN 1 ELSE 0 END"
        for field in fields[2:]
    ]
    metrics["numeric_invalid_cells"] = _scalar(
        connection, f"SELECT coalesce(sum({' + '.join(expressions)}),0) FROM {table}"
    )
    return metrics


def _plan_metrics(
    connection: duckdb.DuckDBPyConnection,
    protocol: RecoveryProtocol,
    official_dates: tuple[str, ...],
) -> dict[str, int]:
    ordered = list(official_dates)
    if ordered != sorted(set(ordered)):
        return {
            "status_request_count": 0,
            "full_market_request_count": 0,
            "targeted_request_count": 0,
            "request_plan_failures": 1,
        }
    invalid_keys = sum(
        _scalar(
            connection,
            f"SELECT count(*) FROM {table} WHERE "
            "NOT regexp_full_match(coalesce(CAST(ts_code AS VARCHAR),''),'[0-9]{6}\\.SH') OR "
            "NOT regexp_full_match(coalesce(CAST(trade_date AS VARCHAR),''),'[0-9]{8}')",
        )
        for table in ("a_keys", "b_keys")
    )
    if invalid_keys:
        return {
            "status_request_count": 0,
            "full_market_request_count": 0,
            "targeted_request_count": 0,
            "request_plan_failures": 1,
        }
    date_positions = pd.DataFrame(
        {"trade_date": ordered, "position": list(range(len(ordered)))}
    )
    connection.register("date_positions", date_positions)
    missing_dates = _scalar(
        connection,
        "SELECT count(*) FROM a_keys a ANTI JOIN date_positions d USING (trade_date)",
    )
    status_requests = _scalar(
        connection,
        """
        WITH positioned AS (
          SELECT a.ts_code,a.trade_date,d.position,
                 lag(d.position) OVER (PARTITION BY a.ts_code ORDER BY d.position) previous_position
          FROM a_keys a JOIN date_positions d USING (trade_date)
        )
        SELECT count(*) FROM positioned
        WHERE previous_position IS NULL OR position<>previous_position+1
        """,
    )
    full_requests = _scalar(connection, "SELECT count(DISTINCT trade_date) FROM b_keys")
    targeted_requests = _scalar(connection, "SELECT count(*) FROM b_keys")
    track_a = protocol.document["track_a_independent_trade_status"]
    track_b = protocol.document["track_b_same_semantic_moneyflow"]
    budget_failure = int(
        status_requests > int(track_a["maximum_provider_requests"])
        or full_requests > int(track_b["maximum_full_market_requests"])
        or targeted_requests > int(track_b["maximum_targeted_requests"])
        or full_requests + targeted_requests > int(track_b["maximum_provider_requests"])
    )
    return {
        "status_request_count": status_requests,
        "full_market_request_count": full_requests,
        "targeted_request_count": targeted_requests,
        "request_plan_failures": int(bool(missing_dates)) + budget_failure,
    }


def recompute_audit_vector(
    protocol: RecoveryProtocol,
    inputs: RecoveryInputs,
) -> dict[str, int]:
    track_a = _target(inputs.track_a_targets)
    track_b = _target(inputs.track_b_targets)
    daily = _keys(inputs.daily_keys)
    status = inputs.independent_status.copy()
    connection = duckdb.connect(":memory:")
    try:
        for name, frame in (("track_a", track_a), ("track_b", track_b), ("daily", daily)):
            connection.register(f"raw_{name}", frame)
            connection.execute(f"CREATE TEMP TABLE {name} AS SELECT * FROM raw_{name}")
        connection.execute(
            "CREATE TEMP TABLE a_keys AS SELECT DISTINCT CAST(ts_code AS VARCHAR) ts_code, "
            "CAST(trade_date AS VARCHAR) trade_date FROM track_a"
        )
        connection.execute(
            "CREATE TEMP TABLE b_keys AS SELECT DISTINCT CAST(ts_code AS VARCHAR) ts_code, "
            "CAST(trade_date AS VARCHAR) trade_date FROM track_b"
        )
        connection.execute(
            "CREATE TEMP TABLE daily_keys AS SELECT DISTINCT CAST(ts_code AS VARCHAR) ts_code, "
            "CAST(trade_date AS VARCHAR) trade_date FROM daily"
        )
        status_schema = int(tuple(status.columns) != ("ts_code", "trade_date", "trade_status"))
        if status_schema:
            status_duplicates = status_invalid = len(status)
            status_extra = status_missing = _scalar(connection, "SELECT count(*) FROM a_keys")
            status_trading = status_nontrading = 0
        else:
            connection.register("raw_status", status)
            connection.execute("CREATE TEMP TABLE status AS SELECT * FROM raw_status")
            status_duplicates = _duplicate_rows(connection, "status", "ts_code,trade_date")
            status_invalid = _scalar(
                connection,
                "SELECT count(*) FROM status WHERE trim(CAST(trade_status AS VARCHAR)) NOT IN ('0','1') "
                "OR trade_status IS NULL",
            )
            status_extra = _scalar(
                connection,
                "SELECT count(*) FROM (SELECT DISTINCT CAST(ts_code AS VARCHAR) ts_code, "
                "CAST(trade_date AS VARCHAR) trade_date FROM status) s ANTI JOIN a_keys a "
                "USING (ts_code,trade_date)",
            )
            status_missing = _scalar(
                connection,
                "SELECT count(*) FROM a_keys a ANTI JOIN (SELECT DISTINCT CAST(ts_code AS VARCHAR) "
                "ts_code, CAST(trade_date AS VARCHAR) trade_date FROM status) s USING (ts_code,trade_date)",
            )
            status_trading = _scalar(
                connection,
                "SELECT count(*) FROM (SELECT DISTINCT a.ts_code,a.trade_date FROM a_keys a "
                "JOIN status s USING (ts_code,trade_date) "
                "WHERE trim(CAST(s.trade_status AS VARCHAR))='1')",
            )
            status_nontrading = _scalar(
                connection,
                "SELECT count(*) FROM (SELECT DISTINCT a.ts_code,a.trade_date FROM a_keys a "
                "JOIN status s USING (ts_code,trade_date) "
                "WHERE trim(CAST(s.trade_status AS VARCHAR))='0')",
            )
        full = _moneyflow_metrics(
            connection, protocol, table="full_rows", frame=inputs.full_market_target_rows
        )
        targeted = _moneyflow_metrics(
            connection, protocol, table="targeted_rows", frame=inputs.targeted_rows
        )
        matching = mismatch = 0
        if (
            not full["schema_errors"]
            and not targeted["schema_errors"]
            and not full["duplicate_rows"]
            and not targeted["duplicate_rows"]
            and not full["numeric_invalid_cells"]
            and not targeted["numeric_invalid_cells"]
        ):
            comparisons = " OR ".join(
                f"try_cast(f.{field} AS DOUBLE) IS DISTINCT FROM try_cast(t.{field} AS DOUBLE)"
                for field in protocol.moneyflow_fields[2:]
            )
            mismatch = _scalar(
                connection,
                "SELECT count(*) FROM full_rows f JOIN targeted_rows t USING (ts_code,trade_date) "
                f"JOIN b_keys b USING (ts_code,trade_date) WHERE {comparisons}",
            )
            matching = _scalar(
                connection,
                "SELECT count(*) FROM full_rows f JOIN targeted_rows t USING (ts_code,trade_date) "
                f"JOIN b_keys b USING (ts_code,trade_date) WHERE NOT ({comparisons})",
            )
        universe_placeholders = ",".join("?" for _ in UNIVERSE_IDS)
        target_invalid = sum(
            _scalar(
                connection,
                f"SELECT count(*) FROM {table} WHERE "
                "NOT regexp_full_match(coalesce(CAST(ts_code AS VARCHAR),''),'[0-9]{6}\\.SH') OR "
                "NOT regexp_full_match(coalesce(CAST(trade_date AS VARCHAR),''),'[0-9]{8}') OR "
                "NOT regexp_full_match(coalesce(CAST(segment AS VARCHAR),''),'[0-9]{4}H[12]') OR "
                f"CAST(universe_id AS VARCHAR) NOT IN ({universe_placeholders})",
                list(UNIVERSE_IDS),
            )
            for table in ("track_a", "track_b")
        )
        vector = {
            "track_a_target_member_rows": _scalar(connection, "SELECT count(*) FROM track_a"),
            "track_a_unique_keys": _scalar(connection, "SELECT count(*) FROM a_keys"),
            "track_b_target_member_rows": _scalar(connection, "SELECT count(*) FROM track_b"),
            "track_b_unique_keys": _scalar(connection, "SELECT count(*) FROM b_keys"),
            "target_membership_duplicate_rows": _duplicate_rows(
                connection, "track_a", "trade_date,universe_id,ts_code"
            )
            + _duplicate_rows(connection, "track_b", "trade_date,universe_id,ts_code"),
            "target_invalid_rows": target_invalid,
            "target_bse_rows": _scalar(
                connection, "SELECT count(*) FROM track_a WHERE ends_with(CAST(ts_code AS VARCHAR),'.BJ')"
            )
            + _scalar(
                connection, "SELECT count(*) FROM track_b WHERE ends_with(CAST(ts_code AS VARCHAR),'.BJ')"
            ),
            "track_overlap_unique_keys": _scalar(
                connection, "SELECT count(*) FROM a_keys JOIN b_keys USING (ts_code,trade_date)"
            ),
            "daily_duplicate_rows": _duplicate_rows(connection, "daily", "ts_code,trade_date"),
            "track_a_daily_present_keys": _scalar(
                connection, "SELECT count(*) FROM a_keys JOIN daily_keys USING (ts_code,trade_date)"
            ),
            "track_b_daily_missing_keys": _scalar(
                connection, "SELECT count(*) FROM b_keys ANTI JOIN daily_keys USING (ts_code,trade_date)"
            ),
            "daily_extra_keys": _scalar(
                connection,
                "SELECT count(*) FROM daily_keys d ANTI JOIN "
                "(SELECT * FROM a_keys UNION SELECT * FROM b_keys) x USING (ts_code,trade_date)",
            ),
            "status_schema_errors": status_schema,
            "status_duplicate_rows": status_duplicates,
            "status_invalid_rows": status_invalid,
            "status_extra_keys": status_extra,
            "status_missing_keys": status_missing,
            "status_trading_keys": status_trading,
            "status_nontrading_keys": status_nontrading,
            "full_schema_errors": full["schema_errors"],
            "targeted_schema_errors": targeted["schema_errors"],
            "full_duplicate_rows": full["duplicate_rows"],
            "targeted_duplicate_rows": targeted["duplicate_rows"],
            "moneyflow_numeric_invalid_cells": full["numeric_invalid_cells"]
            + targeted["numeric_invalid_cells"],
            "full_missing_keys": full["missing_keys"],
            "targeted_missing_keys": targeted["missing_keys"],
            "full_extra_keys": full["extra_keys"],
            "targeted_extra_keys": targeted["extra_keys"],
            "matching_content_keys": matching,
            "content_mismatch_keys": mismatch,
            "saturated_response_count": sum(
                count
                >= int(
                    protocol.document["track_b_same_semantic_moneyflow"][
                        "maximum_rows_per_response"
                    ]
                )
                for count in inputs.full_market_response_row_counts
            ),
            "immutable_batch_integrity_failures": int(not inputs.immutable_batch_integrity),
            **_plan_metrics(connection, protocol, inputs.official_dates),
        }
        return vector
    finally:
        connection.close()
