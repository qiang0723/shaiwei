"""Independent M5 PIT/formula recomputation; intentionally imports no runner or compute modules."""

from __future__ import annotations

import bisect
import math
from collections import defaultdict
from datetime import datetime
from typing import Any

import pandas as pd

from .contract import IDENTITY_FIELDS, STATEMENT_FIELDS, M5DataProtocol, M5GateError


OUTPUT_COLUMNS = (
    "formation_date",
    "effective_date",
    "universe_id",
    "candidate_id",
    "ts_code",
    "current_end_date",
    "predecessor_end_date",
    "candidate_available_date",
    "staleness_days",
    "value",
    "invalid_reason",
)


def _calendar(frame: pd.DataFrame) -> list[str]:
    required = {"exchange", "cal_date", "is_open"}
    if missing := required - set(frame):
        raise M5GateError(f"auditor calendar missing columns: {sorted(missing)}")
    selected = frame.loc[frame["exchange"].astype(str).eq("SSE")].copy()
    selected["cal_date"] = selected["cal_date"].astype(str).str.replace("-", "", regex=False)
    if selected["cal_date"].duplicated().any():
        raise M5GateError("auditor found duplicate SSE calendar date")
    return sorted(
        selected.loc[selected["is_open"].astype(str).eq("1"), "cal_date"].unique()
    )


def _schedule(protocol: M5DataProtocol, open_days: list[str]) -> list[tuple[str, str]]:
    gate = protocol.document["data_gate"]
    months = pd.period_range(gate["quality_start_month"], gate["quality_end_month"], freq="M")
    result = []
    for month in months.astype(str):
        prefix = month.replace("-", "")
        formations = [day for day in open_days if day.startswith(prefix)]
        if not formations:
            raise M5GateError("auditor found a missing formation month")
        formation = formations[-1]
        index = bisect.bisect_right(open_days, formation)
        if index >= len(open_days):
            raise M5GateError("auditor found formation without next open")
        result.append((formation, open_days[index]))
    if len(result) != 60:
        raise M5GateError("auditor formation schedule is not 60 months")
    return result


def _members(
    protocol: M5DataProtocol,
    schedule: list[tuple[str, str]],
    frames: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows = []
    for universe in protocol.universes:
        source = frames[universe.universe_id].copy()
        source["trade_date"] = source["trade_date"].astype(str).str.replace("-", "", regex=False)
        source["ts_code"] = source["ts_code"].astype(str).str.upper()
        if universe.filter_column:
            source = source.loc[
                source[universe.filter_column].astype(str).eq(str(universe.filter_value))
            ].copy()
            source["formation_date"] = (
                source["formation_date"].astype(str).str.replace("-", "", regex=False)
            )
        for formation, effective in schedule:
            day = source.loc[source["trade_date"].eq(effective)]
            if day.empty:
                raise M5GateError("auditor found missing exact effective membership")
            if universe.filter_column and not day["formation_date"].eq(formation).all():
                raise M5GateError("auditor found custom membership formation mismatch")
            rows.extend(
                {
                    "formation_date": formation,
                    "effective_date": effective,
                    "universe_id": universe.universe_id,
                    "ts_code": str(code),
                }
                for code in day["ts_code"]
            )
    result = pd.DataFrame(rows)
    keys = ["formation_date", "effective_date", "universe_id", "ts_code"]
    if result.duplicated(keys).any() or result["ts_code"].str.endswith(".BJ").any():
        raise M5GateError("auditor membership key or .BJ gate failed")
    return result.sort_values(keys, kind="stable").reset_index(drop=True)


def _tables(
    frames: dict[str, pd.DataFrame], open_days: list[str]
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    result = {}
    for table, fields in STATEMENT_FIELDS.items():
        required = set(IDENTITY_FIELDS) | set(fields)
        pieces = []
        for api in (f"tushare.{table}", f"tushare.{table}_vip"):
            frame = frames[api]
            if missing := required - set(frame):
                raise M5GateError(f"auditor {api} missing columns: {sorted(missing)}")
            pieces.append(frame.loc[:, sorted(required)])
        combined = pd.concat(pieces, ignore_index=True)
        for column in IDENTITY_FIELDS:
            combined[column] = combined[column].astype("string")
        combined["end_date"] = combined["end_date"].str.replace("-", "", regex=False)
        combined["f_ann_date"] = combined["f_ann_date"].str.replace("-", "", regex=False)
        combined = combined.loc[
            combined["end_date"].str.endswith("1231", na=False)
            & combined["report_type"].isin(["1", "5"])
        ].copy()
        for _, group in combined.groupby(list(IDENTITY_FIELDS), dropna=False, sort=False):
            if group.loc[:, fields].nunique(dropna=False).gt(1).any():
                raise M5GateError("auditor found conflicting statement source identity")
        combined = combined.drop_duplicates(list(IDENTITY_FIELDS), keep="last").copy()
        for field in fields:
            combined[field] = pd.to_numeric(combined[field], errors="coerce")
        available = []
        for announcement in combined["f_ann_date"]:
            index = bisect.bisect_right(open_days, str(announcement))
            available.append(open_days[index] if index < len(open_days) else None)
        combined["available_date"] = available
        combined = combined.loc[combined["available_date"].notna()].copy()
        combined["report_priority"] = combined["report_type"].map({"1": 2, "5": 1})
        combined["update_priority"] = pd.to_numeric(
            combined["update_flag"], errors="coerce"
        ).fillna(-1)
        by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in combined.to_dict("records"):
            by_code[str(row["ts_code"])].append(row)
        result[table] = dict(by_code)
    return result


def _versions(
    rows: list[dict[str, Any]], formation: str
) -> dict[str, dict[str, Any]]:
    eligible = [row for row in rows if str(row["available_date"]) <= formation]
    selected: dict[str, dict[str, Any]] = {}
    for row in eligible:
        end_date = str(row["end_date"])
        priority = (
            str(row["available_date"]),
            str(row["f_ann_date"]),
            int(row["report_priority"]),
            float(row["update_priority"]),
        )
        old = selected.get(end_date)
        if old is None or priority > old["_audit_priority"]:
            selected[end_date] = {**row, "_audit_priority": priority}
    return selected


def _previous(end_date: str) -> str:
    parsed = datetime.strptime(end_date, "%Y%m%d")
    return f"{parsed.year - 1:04d}{parsed.month:02d}{parsed.day:02d}"


def _pair(
    candidate: Any,
    versions: dict[str, dict[str, dict[str, Any]]],
) -> tuple[str | None, str | None, dict[str, float], str | None]:
    current_tables = {
        item.split(".", 1)[0] for item in candidate.inputs if item.endswith("_t")
    }
    predecessor_tables = {
        item.split(".", 1)[0] for item in candidate.inputs if item.endswith("_p")
    }
    possible = set.intersection(
        *(set(versions[table]) for table in sorted(current_tables))
    )
    for current in sorted(possible, reverse=True):
        predecessor = _previous(current)
        if not all(predecessor in versions[table] for table in predecessor_tables):
            continue
        values = {}
        availability = []
        for component in candidate.inputs:
            table, field_period = component.split(".", 1)
            field, period = field_period.rsplit("_", 1)
            row = versions[table][current if period == "t" else predecessor]
            values[component] = row[field]
            availability.append(str(row["available_date"]))
        return current, predecessor, values, max(availability)
    return None, None, {}, None


def _invalid_reason(
    protocol: M5DataProtocol,
    candidate: Any,
    values: dict[str, Any],
    current: str | None,
    predecessor: str | None,
    formation: str,
    available: str | None,
) -> tuple[str | None, int | None]:
    if current is None or predecessor is None:
        return "NO_CONSECUTIVE_PAIR", None
    staleness = (datetime.strptime(formation, "%Y%m%d") - datetime.strptime(current, "%Y%m%d")).days
    if available is None:
        return "MISSING_AVAILABILITY", staleness
    if available > formation:
        return "FUTURE_AVAILABILITY", staleness
    if staleness > 548:
        return "STALE_ANNUAL_PAIR", staleness
    nonnegative = set(protocol.document["denominator_and_missing_policy"]["nonnegative_required_fields"])
    for component, raw in values.items():
        if raw is None or pd.isna(raw):
            return "MISSING_COMPONENT", staleness
        value = float(raw)
        if not math.isfinite(value):
            return "NONFINITE_COMPONENT", staleness
        base = component.rsplit("_", 1)[0]
        if base in nonnegative and value < 0:
            return "NEGATIVE_DISALLOWED_COMPONENT", staleness
        if base in {
            "income.total_revenue",
            "balancesheet.total_assets",
            "balancesheet.total_cur_liab",
        } and value <= 0:
            return "INVALID_DENOMINATOR", staleness
    return None, staleness


def _formula(candidate_id: str, value: dict[str, float]) -> float:
    get = value.__getitem__
    if candidate_id == "m5_gross_margin_improvement_v1":
        revenue_t, revenue_p = get("income.total_revenue_t"), get("income.total_revenue_p")
        return (revenue_t - get("income.total_cogs_t")) / revenue_t - (
            revenue_p - get("income.total_cogs_p")
        ) / revenue_p
    if candidate_id == "m5_rd_intensity_improvement_v1":
        revenue_t, revenue_p = get("income.total_revenue_t"), get("income.total_revenue_p")
        return get("income.rd_exp_t") / revenue_t - get("income.rd_exp_p") / revenue_p
    if candidate_id == "m5_receivables_to_revenue_deterioration_v1":
        revenue_t, revenue_p = get("income.total_revenue_t"), get("income.total_revenue_p")
        return get("balancesheet.accounts_receiv_t") / revenue_t - get(
            "balancesheet.accounts_receiv_p"
        ) / revenue_p
    if candidate_id == "m5_current_ratio_improvement_v1":
        return get("balancesheet.total_cur_assets_t") / get(
            "balancesheet.total_cur_liab_t"
        ) - get("balancesheet.total_cur_assets_p") / get("balancesheet.total_cur_liab_p")
    if candidate_id == "m5_free_cashflow_margin_improvement_v1":
        revenue_t, revenue_p = get("income.total_revenue_t"), get("income.total_revenue_p")
        return get("cashflow.free_cashflow_t") / revenue_t - get(
            "cashflow.free_cashflow_p"
        ) / revenue_p
    assets_t = get("balancesheet.total_assets_t")
    assets_p = get("balancesheet.total_assets_p")
    average_assets = (assets_t + assets_p) / 2.0
    if candidate_id == "m5_inventory_accumulation_v1":
        return (get("balancesheet.inventories_t") - get("balancesheet.inventories_p")) / average_assets
    if candidate_id == "m5_leverage_change_v1":
        return get("balancesheet.total_liab_t") / assets_t - get("balancesheet.total_liab_p") / assets_p
    if candidate_id == "m5_external_financing_dependence_v1":
        return get("cashflow.n_cash_flows_fnc_act_t") / average_assets
    raise M5GateError("auditor found unknown candidate formula")


def recompute_panel(
    protocol: M5DataProtocol,
    frames: dict[str, pd.DataFrame],
    membership_frames: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    open_days = _calendar(frames["tushare.trade_cal"])
    members = _members(protocol, _schedule(protocol, open_days), membership_frames)
    tables = _tables(frames, open_days)
    cache = {}
    rows = []
    for member in members.itertuples(index=False):
        key = (member.formation_date, member.ts_code)
        if key not in cache:
            cache[key] = {
                table: _versions(by_code.get(member.ts_code, []), member.formation_date)
                for table, by_code in tables.items()
            }
        versions = cache[key]
        for candidate in protocol.candidates:
            current, predecessor, values, available = _pair(candidate, versions)
            reason, staleness = _invalid_reason(
                protocol,
                candidate,
                values,
                current,
                predecessor,
                member.formation_date,
                available,
            )
            computed = None
            if reason is None:
                computed = _formula(candidate.candidate_id, values)
                if not math.isfinite(computed):
                    computed, reason = None, "NONFINITE_OUTPUT"
            rows.append(
                {
                    "formation_date": member.formation_date,
                    "effective_date": member.effective_date,
                    "universe_id": member.universe_id,
                    "candidate_id": candidate.candidate_id,
                    "ts_code": member.ts_code,
                    "current_end_date": current,
                    "predecessor_end_date": predecessor,
                    "candidate_available_date": available,
                    "staleness_days": staleness,
                    "value": computed,
                    "invalid_reason": reason,
                }
            )
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS).sort_values(
        ["formation_date", "effective_date", "universe_id", "candidate_id", "ts_code"],
        kind="stable",
    ).reset_index(drop=True)
