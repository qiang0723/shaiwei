"""Independent statement versioning and candidate-specific consecutive annual pairing."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

import duckdb
import pandas as pd

from .contract import STATEMENT_FIELDS, Candidate, M5DataProtocol, M5GateError
from .source_conflicts import assess_statement_sources


COMPONENT_PREFIX = "component__"


def canonical_statement(
    name: str,
    ordinary: pd.DataFrame,
    vip: pd.DataFrame,
    open_days: list[str],
) -> tuple[pd.DataFrame, dict[str, int]]:
    assessment = assess_statement_sources(name, ordinary, vip)
    conflict_count = assessment.conflict_count
    if conflict_count:
        raise M5GateError(f"{name} contains conflicting duplicate source identities")
    combined = assessment.canonical_frame.copy()
    for field in STATEMENT_FIELDS[name]:
        combined[field] = pd.to_numeric(combined[field], errors="coerce")
    announcements = pd.to_datetime(combined["f_ann_date"], format="%Y%m%d", errors="coerce")
    calendar = pd.to_datetime(pd.Series(sorted(set(open_days))), format="%Y%m%d")
    positions = calendar.searchsorted(announcements, side="right")
    available = pd.Series(pd.NA, index=combined.index, dtype="string")
    valid = announcements.notna() & (positions < len(calendar))
    available.loc[valid] = calendar.iloc[positions[valid]].dt.strftime("%Y%m%d").to_numpy()
    combined["available_date"] = available
    invalid_announcement_rows = int(combined["available_date"].isna().sum())
    combined = combined.loc[combined["available_date"].notna()].copy()
    combined["_report_priority"] = combined["report_type"].map({"1": 2, "5": 1}).fillna(0)
    combined["_update_priority"] = pd.to_numeric(
        combined["update_flag"], errors="coerce"
    ).fillna(-1)
    return combined.reset_index(drop=True), {
        "canonical_rows": len(combined),
        "source_identity_conflicts": conflict_count,
        "source_duplicate_rows_collapsed": int(
            assessment.report["exact_duplicate_extra_row_count"]
        ),
        "invalid_announcement_rows": invalid_announcement_rows,
    }


def statement_periods(
    members: pd.DataFrame,
    statement: pd.DataFrame,
    name: str,
) -> pd.DataFrame:
    keys = members[["formation_date", "ts_code"]].drop_duplicates()
    connection = duckdb.connect(":memory:")
    try:
        connection.register("members", keys)
        connection.register("statement", statement)
        fields = ",".join(f's."{field}"' for field in STATEMENT_FIELDS[name])
        selected = connection.execute(
            f"""
            SELECT m.formation_date,m.ts_code,s.end_date,s.available_date,s.f_ann_date,
                   s._report_priority,s._update_priority,{fields}
            FROM members m
            JOIN statement s
              ON m.ts_code=s.ts_code AND s.available_date<=m.formation_date
            QUALIFY row_number() OVER (
              PARTITION BY m.formation_date,m.ts_code,s.end_date
              ORDER BY s.available_date DESC,s.f_ann_date DESC,
                       s._report_priority DESC,s._update_priority DESC
            )=1
            ORDER BY m.formation_date,m.ts_code,s.end_date
            """
        ).df()
    finally:
        connection.close()
    return selected


def _predecessor(end_date: str) -> str:
    parsed = datetime.strptime(end_date, "%Y%m%d")
    return f"{parsed.year - 1:04d}{parsed.month:02d}{parsed.day:02d}"


def _component_column(component: str) -> str:
    return COMPONENT_PREFIX + component.replace(".", "__")


def _period_maps(
    periods: dict[str, pd.DataFrame],
) -> dict[str, dict[tuple[str, str], dict[str, dict[str, Any]]]]:
    result: dict[str, dict[tuple[str, str], dict[str, dict[str, Any]]]] = {}
    for table, frame in periods.items():
        table_result: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in frame.to_dict("records"):
            key = (str(row["formation_date"]), str(row["ts_code"]))
            table_result[key][str(row["end_date"])] = row
        result[table] = dict(table_result)
    return result


def _candidate_components(
    candidate: Candidate,
    key: tuple[str, str],
    maps: dict[str, dict[tuple[str, str], dict[str, dict[str, Any]]]],
) -> dict[str, Any]:
    current_tables = {
        component.split(".", 1)[0]
        for component in candidate.inputs
        if component.rsplit("_", 1)[1] == "t"
    }
    predecessor_tables = {
        component.split(".", 1)[0]
        for component in candidate.inputs
        if component.rsplit("_", 1)[1] == "p"
    }
    current_sets = [set(maps[table].get(key, {})) for table in sorted(current_tables)]
    possible_current = sorted(set.intersection(*current_sets) if current_sets else set(), reverse=True)
    selected_current = None
    selected_predecessor = None
    for current in possible_current:
        predecessor = _predecessor(current)
        if all(predecessor in maps[table].get(key, {}) for table in predecessor_tables):
            selected_current = current
            selected_predecessor = predecessor
            break
    result: dict[str, Any] = {
        "current_end_date": selected_current,
        "predecessor_end_date": selected_predecessor,
        "candidate_available_date": None,
    }
    if selected_current is None or selected_predecessor is None:
        return result
    availability: list[str] = []
    for component in candidate.inputs:
        table, field_period = component.split(".", 1)
        field, period = field_period.rsplit("_", 1)
        end_date = selected_current if period == "t" else selected_predecessor
        row = maps[table][key][end_date]
        result[_component_column(component)] = row[field]
        availability.append(str(row["available_date"]))
    result["candidate_available_date"] = max(availability)
    return result


def build_candidate_components(
    protocol: M5DataProtocol,
    members: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    calendar = frames.get("tushare.trade_cal")
    if calendar is None:
        raise M5GateError("M5 statements require the exact trade calendar frame")
    open_days = sorted(
        calendar.loc[
            calendar["exchange"].astype(str).eq("SSE")
            & calendar["is_open"].astype(str).eq("1"),
            "cal_date",
        ]
        .astype(str)
        .str.replace("-", "", regex=False)
        .unique()
    )
    if not open_days:
        raise M5GateError("M5 statements have no SSE availability calendar")
    periods: dict[str, pd.DataFrame] = {}
    source_diagnostics: dict[str, Any] = {}
    for table in STATEMENT_FIELDS:
        ordinary = frames.get(f"tushare.{table}")
        vip = frames.get(f"tushare.{table}_vip")
        if ordinary is None or vip is None:
            raise M5GateError(f"M5 statements lack exact {table} ordinary/VIP frames")
        canonical, diagnostics = canonical_statement(table, ordinary, vip, open_days)
        periods[table] = statement_periods(members, canonical, table)
        source_diagnostics[table] = diagnostics
    maps = _period_maps(periods)
    keys = sorted(
        {
            (str(row.formation_date), str(row.ts_code))
            for row in members[["formation_date", "ts_code"]].itertuples(index=False)
        }
    )
    rows: list[dict[str, Any]] = []
    no_pair_counts = {candidate.candidate_id: 0 for candidate in protocol.candidates}
    for formation_date, ts_code in keys:
        for candidate in protocol.candidates:
            components = _candidate_components(candidate, (formation_date, ts_code), maps)
            if components["current_end_date"] is None:
                no_pair_counts[candidate.candidate_id] += 1
            rows.append(
                {
                    "formation_date": formation_date,
                    "ts_code": ts_code,
                    "candidate_id": candidate.candidate_id,
                    **components,
                }
            )
    component_frame = pd.DataFrame(rows)
    merged = members.merge(
        component_frame,
        on=["formation_date", "ts_code"],
        how="left",
        validate="many_to_many",
    )
    if len(merged) != len(members) * len(protocol.candidates):
        raise M5GateError("candidate component expansion is not exactly members x eight")
    current = pd.to_datetime(merged["current_end_date"], format="%Y%m%d", errors="coerce")
    formation = pd.to_datetime(merged["formation_date"], format="%Y%m%d", errors="coerce")
    merged["staleness_days"] = (formation - current).dt.days.astype("Int64")
    future = merged["candidate_available_date"].astype("string").fillna("").gt(
        merged["formation_date"].astype("string")
    )
    if future.any():
        raise M5GateError("candidate components include future availability")
    diagnostics = {
        "source": source_diagnostics,
        "candidate_no_pair_rows_before_pool_expansion": no_pair_counts,
        "future_availability_rows": int(future.sum()),
        "expanded_rows": len(merged),
    }
    return merged.sort_values(
        ["formation_date", "universe_id", "candidate_id", "ts_code"], kind="stable"
    ).reset_index(drop=True), diagnostics
