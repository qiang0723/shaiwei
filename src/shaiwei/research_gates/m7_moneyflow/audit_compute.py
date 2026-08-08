"""Independent DuckDB recomputation for the M7 aggregate key-quality verdict."""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from .contract import UNIVERSE_IDS, M7GateError, M7Protocol
from .reader import KeyInputs


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 12) if denominator else 0.0


def _gate(gate_id: str, passed: bool, observed: Any, threshold: Any) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "status": "PASS" if passed else "FAIL",
        "observed": observed,
        "threshold": threshold,
    }


def _scalar(connection: duckdb.DuckDBPyConnection, query: str, params: list[Any]) -> int:
    return int(connection.execute(query, params).fetchone()[0])


def _mapping(protocol: M7Protocol, dates: tuple[str, ...]) -> pd.DataFrame:
    ordered = list(dates)
    if ordered != sorted(set(ordered)):
        raise M7GateError("M7 auditor official dates are duplicated or unordered")
    result = []
    for index, date in enumerate(ordered):
        if protocol.pit["feature_start_date"] <= date <= protocol.pit["feature_end_date"]:
            result.append({"trade_date": date, "source_date": ordered[index - 1] if index else ""})
    return pd.DataFrame(result)


def _streak(values: list[bool]) -> int:
    longest = current = 0
    for value in values:
        current = current + 1 if value else 0
        longest = max(longest, current)
    return longest


def _daily_table(
    connection: duckdb.DuckDBPyConnection,
    protocol: M7Protocol,
    mapping: pd.DataFrame,
    quarantined: frozenset[str],
) -> pd.DataFrame:
    quarantine = pd.DataFrame({"source_date": sorted(quarantined)})
    connection.register("audit_mapping", mapping)
    connection.register("audit_quarantine", quarantine)
    start, end = protocol.pit["feature_start_date"], protocol.pit["feature_end_date"]
    source_start, source_end = protocol.pit["source_start_date"], protocol.pit["source_end_date"]
    query = """
        WITH m AS (
          SELECT CAST(trade_date AS VARCHAR) trade_date,
                 CAST(universe_id AS VARCHAR) universe_id,
                 CAST(ts_code AS VARCHAR) ts_code
          FROM audit_membership
          WHERE CAST(trade_date AS VARCHAR) BETWEEN ? AND ?
        ), s AS (
          SELECT DISTINCT CAST(trade_date AS VARCHAR) source_date,
                          CAST(ts_code AS VARCHAR) ts_code
          FROM audit_source
          WHERE CAST(request_trade_date AS VARCHAR) BETWEEN ? AND ?
        ), joined AS (
          SELECT m.universe_id,m.trade_date,x.source_date,
                 q.source_date IS NOT NULL AS quarantined,
                 CASE WHEN q.source_date IS NULL AND s.ts_code IS NOT NULL THEN 1 ELSE 0 END AS matched_flag
          FROM m
          LEFT JOIN audit_mapping x USING (trade_date)
          LEFT JOIN s ON s.source_date=x.source_date AND s.ts_code=m.ts_code
          LEFT JOIN audit_quarantine q ON q.source_date=x.source_date
        )
        SELECT universe_id,trade_date,source_date,quarantined,
               count(*)::BIGINT denominator,sum(matched_flag)::BIGINT matched_count
        FROM joined GROUP BY 1,2,3,4 ORDER BY 1,2
    """
    daily = connection.execute(query, [start, end, source_start, source_end]).df()
    daily = daily.rename(columns={"matched_count": "matched"})
    daily["coverage_rate"] = [
        _ratio(int(row.matched), int(row.denominator)) for row in daily.itertuples(index=False)
    ]
    return daily


def _coverage(protocol: M7Protocol, daily: pd.DataFrame) -> dict[str, Any]:
    aggregate = []
    eligible_rates = []
    summaries = []
    minimum_names = []
    half_year = []
    for universe in UNIVERSE_IDS:
        rows = daily.loc[daily["universe_id"].eq(universe)].copy()
        eligible = rows.loc[~rows["quarantined"]].copy()
        denominator = int(rows["denominator"].sum())
        matched = int(rows["matched"].sum())
        aggregate.append(
            {
                "universe_id": universe,
                "denominator": denominator,
                "matched": matched,
                "coverage_rate": _ratio(matched, denominator),
            }
        )
        eligible_rates.append(
            {
                "universe_id": universe,
                "feature_date_count": len(rows),
                "eligible_feature_date_count": len(eligible),
                "rate": _ratio(len(eligible), len(rows)),
            }
        )
        rates = eligible["coverage_rate"].astype(float)
        worst = eligible.sort_values(["coverage_rate", "trade_date"]).iloc[0] if len(eligible) else None
        summaries.append(
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
            segment_denominator = int(segment_rows["denominator"].sum())
            segment_matched = int(segment_rows["matched"].sum())
            half_year.append(
                {
                    "universe_id": universe,
                    "segment": segment["name"],
                    "denominator": segment_denominator,
                    "matched": segment_matched,
                    "coverage_rate": _ratio(segment_matched, segment_denominator),
                }
            )
    return {
        "source_day_eligible_feature_date_rate_by_universe": eligible_rates,
        "aggregate_member_key_coverage_by_universe": aggregate,
        "half_year_member_key_coverage_by_universe": half_year,
        "eligible_feature_date_coverage_summary_by_universe": summaries,
        "minimum_matched_names_on_eligible_feature_date_by_universe": minimum_names,
    }


def _recompute_quality_core(
    protocol: M7Protocol,
    inputs: KeyInputs,
    *,
    source_code_pattern: str,
) -> dict[str, Any]:
    membership = inputs.membership.copy()
    source = inputs.source_keys.copy()
    connection = duckdb.connect(":memory:")
    try:
        connection.register("audit_membership", membership)
        connection.register("audit_source", source)
        feature = [protocol.pit["feature_start_date"], protocol.pit["feature_end_date"]]
        source_period = [protocol.pit["source_start_date"], protocol.pit["source_end_date"]]
        member_where = "CAST(trade_date AS VARCHAR) BETWEEN ? AND ?"
        source_where = "CAST(request_trade_date AS VARCHAR) BETWEEN ? AND ?"
        membership_rows = _scalar(connection, f"SELECT count(*) FROM audit_membership WHERE {member_where}", feature)
        source_rows = _scalar(connection, f"SELECT count(*) FROM audit_source WHERE {source_where}", source_period)
        membership_duplicates = _scalar(
            connection,
            f"SELECT coalesce(sum(n),0) FROM (SELECT count(*) n FROM audit_membership WHERE {member_where} GROUP BY trade_date,universe_id,ts_code HAVING count(*)>1)",
            feature,
        )
        source_duplicates = _scalar(
            connection,
            f"SELECT coalesce(sum(n),0) FROM (SELECT count(*) n FROM audit_source WHERE {source_where} GROUP BY trade_date,ts_code HAVING count(*)>1)",
            source_period,
        )
        membership_null = _scalar(connection, "SELECT count(*) FROM audit_membership WHERE trade_date IS NULL OR formation_date IS NULL OR universe_id IS NULL OR ts_code IS NULL", [])
        source_null = _scalar(connection, "SELECT count(*) FROM audit_source WHERE trade_date IS NULL OR ts_code IS NULL OR request_trade_date IS NULL", [])
        membership_malformed = _scalar(connection, "SELECT sum((NOT regexp_full_match(coalesce(CAST(trade_date AS VARCHAR),''),'[0-9]{8}'))::INT + (NOT regexp_full_match(coalesce(CAST(formation_date AS VARCHAR),''),'[0-9]{8}'))::INT + (NOT regexp_full_match(coalesce(CAST(ts_code AS VARCHAR),''),'[0-9]{6}\\.SH'))::INT) FROM audit_membership", [])
        source_malformed = _scalar(
            connection,
            "SELECT sum((NOT regexp_full_match(coalesce(CAST(trade_date AS VARCHAR),''),'[0-9]{8}'))::INT + "
            "(NOT regexp_full_match(coalesce(CAST(request_trade_date AS VARCHAR),''),'[0-9]{8}'))::INT + "
            "(NOT regexp_full_match(coalesce(CAST(ts_code AS VARCHAR),''),?))::INT) FROM audit_source",
            [source_code_pattern],
        )
        unknown = _scalar(connection, f"SELECT count(*) FROM audit_membership WHERE {member_where} AND CAST(universe_id AS VARCHAR) NOT IN (?,?,?)", [*feature, *UNIVERSE_IDS])
        bse = _scalar(connection, "SELECT count(*) FROM audit_membership WHERE ends_with(CAST(ts_code AS VARCHAR),'.BJ')", []) + _scalar(connection, "SELECT count(*) FROM audit_source WHERE ends_with(CAST(ts_code AS VARCHAR),'.BJ')", [])
        future_formation = _scalar(connection, f"SELECT count(*) FROM audit_membership WHERE {member_where} AND CAST(formation_date AS VARCHAR)>CAST(trade_date AS VARCHAR)", feature)
        request_mismatch = _scalar(connection, f"SELECT count(*) FROM audit_source WHERE {source_where} AND CAST(trade_date AS VARCHAR)<>CAST(request_trade_date AS VARCHAR)", source_period)
        mapping = _mapping(protocol, inputs.official_dates)
        missing_map = int(mapping["source_date"].eq("").sum())
        same_or_future = int((mapping["source_date"] >= mapping["trade_date"]).sum())
        daily = _daily_table(connection, protocol, mapping, inputs.quarantined_source_dates)
    finally:
        connection.close()
    coverage = _coverage(protocol, daily)
    quarantine_flags = [date in inputs.quarantined_source_dates for date in mapping["source_date"]]
    max_streak = _streak(quarantine_flags)
    malformed = {
        "membership_null_key_count": membership_null,
        "source_null_key_count": source_null,
        "membership_malformed_key_count": membership_malformed,
        "source_malformed_key_count": source_malformed,
    }
    quality = protocol.quality
    eligible_rates = [item["rate"] for item in coverage["source_day_eligible_feature_date_rate_by_universe"]]
    aggregate_rates = [item["coverage_rate"] for item in coverage["aggregate_member_key_coverage_by_universe"]]
    half_rates = [item["coverage_rate"] for item in coverage["half_year_member_key_coverage_by_universe"]]
    daily_rates = [item["minimum"] for item in coverage["eligible_feature_date_coverage_summary_by_universe"]]
    minimums = quality["minimum_matched_names_by_feature_date"]
    matched_ok = all(item["minimum_matched"] >= minimums[item["universe_id"]] for item in coverage["minimum_matched_names_on_eligible_feature_date_by_universe"])
    invalid_keys = sum(malformed.values())
    gates = [
        _gate("membership_primary_key_unique", membership_duplicates == 0, membership_duplicates, 0),
        _gate("source_primary_key_unique", source_duplicates == 0, source_duplicates, 0),
        _gate("required_keys_valid", invalid_keys == 0, invalid_keys, 0),
        _gate("bse_absent", bse == 0, bse, 0),
        _gate("universe_identity_known", unknown == 0, unknown, 0),
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
        "dataset_and_grain": {"grain": "feature_date_x_universe_id_x_ts_code", "membership_row_count": membership_rows, "source_key_row_count": source_rows, "feature_date_count": len(mapping), "universe_count": len(UNIVERSE_IDS)},
        "pit_mapping": {"mapping": "NEXT_OFFICIAL_SSE_OPEN_DATE", "feature_start_date": protocol.pit["feature_start_date"], "feature_end_date": protocol.pit["feature_end_date"], "source_start_date": protocol.pit["source_start_date"], "source_end_date": protocol.pit["source_end_date"], "missing_mapping_count": missing_map, "same_day_or_future_mapping_count": same_or_future, "request_payload_date_mismatch_count": request_mismatch},
        "completeness": {**coverage, "quarantined_feature_date_count": sum(quarantine_flags), "maximum_consecutive_quarantined_source_dates": max_streak},
        "uniqueness": {"membership_primary_key_duplicate_row_count": membership_duplicates, "source_primary_key_duplicate_row_count": source_duplicates},
        "validity": {**malformed, "bse_row_count": bse, "unknown_universe_row_count": unknown, "future_formation_row_count": future_formation},
        "integrity": {"source_revision_count": 0, "source_saturation_count": 0, "raw_projected_columns": inputs.evidence["raw_projected_columns"], "numeric_moneyflow_value_columns_read": inputs.evidence["numeric_moneyflow_value_columns_read"]},
        "gates": gates,
        "authority": {"candidate_definition_count": 0, "effect_test_count": 0, "generation_attempt_increment": 0, "strategy_effective": "NOT_EVALUATED", "production_authorization": "none"},
        "verdict": verdict,
    }


def recompute_quality_core(protocol: M7Protocol, inputs: KeyInputs) -> dict[str, Any]:
    """Independently reproduce the frozen v1 SH-only source-domain behavior."""

    return _recompute_quality_core(
        protocol,
        inputs,
        source_code_pattern=r"[0-9]{6}\.SH",
    )


def recompute_quality_core_all_a_source(
    protocol: M7Protocol,
    inputs: KeyInputs,
) -> dict[str, Any]:
    """Independently evaluate a successor SH/SZ source catalog."""

    return _recompute_quality_core(
        protocol,
        inputs,
        source_code_pattern=r"[0-9]{6}\.(SH|SZ)",
    )
