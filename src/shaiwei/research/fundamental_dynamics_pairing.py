"""Strict PIT construction of consecutive common annual statement pairs."""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

from shaiwei.research.fundamental_pit_contract import FundamentalPitError
from shaiwei.research.fundamental_pit_gate import STATEMENT_FIELDS


KEYS = ["formation_date", "ts_code"]


def statement_periods(members: pd.DataFrame, statement: pd.DataFrame, name: str) -> pd.DataFrame:
    """Select the latest version known at formation for every annual end date."""
    connection = duckdb.connect(":memory:")
    try:
        connection.register("members", members[[*KEYS]])
        connection.register("statement", statement)
        fields = ", ".join(f's."{field}"' for field in STATEMENT_FIELDS[name])
        selected = connection.execute(
            f"""
            SELECT m.formation_date, m.ts_code, s.end_date,
                   s.available_date, s.f_ann_date, {fields}
            FROM members m
            JOIN statement s
              ON m.ts_code = s.ts_code AND s.available_date <= m.formation_date
            QUALIFY row_number() OVER (
              PARTITION BY m.formation_date, m.ts_code, s.end_date
              ORDER BY s.f_ann_date DESC,
                       s._report_priority DESC,
                       s._update_priority DESC
            ) = 1
            ORDER BY m.formation_date, m.ts_code, s.end_date
            """
        ).df()
    finally:
        connection.close()
    return selected.rename(
        columns={
            "end_date": f"{name}_end_date",
            "available_date": f"{name}_available_date",
            "f_ann_date": f"{name}_f_ann_date",
            **{field: f"{name}_{field}" for field in STATEMENT_FIELDS[name]},
        }
    )


def common_periods(periods: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Inner-join the three statements on an exact common end date."""
    common = periods["income"].rename(columns={"income_end_date": "end_date"})
    for name in ("balancesheet", "cashflow"):
        candidate = periods[name].rename(columns={f"{name}_end_date": "end_date"})
        common = common.merge(candidate, on=[*KEYS, "end_date"], how="inner", validate="one_to_one")
    for name in STATEMENT_FIELDS:
        common[f"{name}_end_date"] = common["end_date"]
    return common.sort_values([*KEYS, "end_date"]).reset_index(drop=True)


def _previous_annual_end(end_dates: pd.Series) -> pd.Series:
    years = pd.to_numeric(end_dates.astype("string").str[:4], errors="coerce") - 1
    valid = years.notna() & end_dates.astype("string").str.match(r"^\d{8}$", na=False)
    result = pd.Series(pd.NA, index=end_dates.index, dtype="string")
    result.loc[valid] = years.loc[valid].astype(int).astype(str) + end_dates.loc[valid].astype(str).str[4:]
    return result


def latest_consecutive_pairs(
    members: pd.DataFrame,
    common: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """Return one latest PIT-legal current/predecessor annual pair per member formation."""
    current = common.copy()
    current["predecessor_end_date"] = _previous_annual_end(current["end_date"])
    predecessor = common.add_prefix("predecessor_").rename(
        columns={
            "predecessor_formation_date": "formation_date",
            "predecessor_ts_code": "ts_code",
            "predecessor_end_date": "matched_predecessor_end_date",
        }
    )
    pairs = current.merge(
        predecessor,
        left_on=[*KEYS, "predecessor_end_date"],
        right_on=[*KEYS, "matched_predecessor_end_date"],
        how="inner",
        validate="many_to_one",
    )
    pairs = pairs.sort_values([*KEYS, "end_date"]).drop_duplicates(KEYS, keep="last")
    current_rename = {
        column: f"current_{column}"
        for column in common.columns
        if column not in KEYS
    }
    pairs = pairs.rename(columns=current_rename)
    selected = members.merge(pairs, on=KEYS, how="left", validate="one_to_one")
    latest_common = common.groupby(KEYS, as_index=False)["end_date"].max().rename(
        columns={"end_date": "latest_common_end_date"}
    )
    selected = selected.merge(latest_common, on=KEYS, how="left", validate="one_to_one")
    newer_unpaired = selected["latest_common_end_date"].astype("string").fillna("").gt(
        selected["current_end_date"].astype("string").fillna("")
    )
    return selected, newer_unpaired


def pair_diagnostics(panel: pd.DataFrame) -> dict[str, Any]:
    current_periods = panel[[f"current_{name}_end_date" for name in STATEMENT_FIELDS]]
    predecessor_periods = panel[[f"predecessor_{name}_end_date" for name in STATEMENT_FIELDS]]
    current_complete = current_periods.notna().all(axis=1)
    predecessor_complete = predecessor_periods.notna().all(axis=1)
    current_mixed = current_complete & current_periods.nunique(axis=1).gt(1)
    predecessor_mixed = predecessor_complete & predecessor_periods.nunique(axis=1).gt(1)
    expected = _previous_annual_end(panel["current_end_date"])
    paired = panel["current_end_date"].notna() & panel["predecessor_end_date"].notna()
    nonconsecutive = paired & ~panel["predecessor_end_date"].astype("string").eq(expected)
    available_columns = [
        *[f"current_{name}_available_date" for name in STATEMENT_FIELDS],
        *[f"predecessor_{name}_available_date" for name in STATEMENT_FIELDS],
    ]
    future = pd.Series(False, index=panel.index)
    for column in available_columns:
        future |= panel[column].astype("string").fillna("").gt(panel["formation_date"].astype("string"))
    if panel.duplicated(KEYS).any():
        raise FundamentalPitError("F2-0 feature keys are not unique")
    return {
        "duplicate_feature_keys": int(panel.duplicated(KEYS).sum()),
        "current_mixed_component_period_rows": int(current_mixed.sum()),
        "predecessor_mixed_component_period_rows": int(predecessor_mixed.sum()),
        "nonconsecutive_pair_rows": int(nonconsecutive.sum()),
        "future_availability_rows": int(future.sum()),
    }
