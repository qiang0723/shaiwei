"""TP-F-0B member-day classes, the counts-only field profile and the frozen gates (protocol §4, addendum A1)."""

from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np
import pandas as pd

from shaiwei.research.rf_0c.fields import CLASSES as RF_0C_CLASSES, classify_member_day
from shaiwei.research.tp_f_0b.panel import PanelParams


RF_0C_COLUMNS = (
    "ts_code", "trade_date", "list_date", "bar_record_count", "bar_variant_count", "open", "high", "low", "close",
    "pre_close", "adj_factor", "prior_adj_factor", "prior_bar_close", "primary_suspended", "independent_status",
)
PRICE_FEATURES = ("open", "close", "high", "low", "vwap")
TP_CLASSES = (
    "ZERO_VOLUME_DAY",
    "QLIB_OPEN_MISSING", "QLIB_CLOSE_MISSING", "QLIB_HIGH_MISSING", "QLIB_LOW_MISSING", "QLIB_VOLUME_MISSING",
    "QLIB_VWAP_MISSING",
    "QLIB_VALUE_ON_NO_BAR_DAY",
    "QLIB_NONPOSITIVE_PRICE",
    "QLIB_ADJUSTMENT_INCONSISTENT",
    "NEXT_DAY_OPEN_MISSING",
    "NEXT_DAY_LIMIT_UP_AT_OPEN",
    "NEXT_DAY_LIMIT_DOWN_AT_OPEN",
    "EXIT_DAY_OPEN_MISSING",
    "SW_L1_NONE",
    "SW_L1_MULTIPLE",
    "SW_L1_CHANGE_DAY",
    "SW_L1_RAW_MULTIPLE_HIT",
    "WARMUP_BEFORE_QLIB_CALENDAR_START",
    "LISTING_SHORTER_THAN_WARMUP",
    "INDEX_ENTRY_DAY",
    "INDEX_EXIT_DAY",
)
CLASSES = (*RF_0C_CLASSES, *TP_CLASSES)


def _none(value: Any) -> Any:
    """The inherited RF-0C classifier tests `is None`; SQL NULLs arrive from pandas as NaN."""
    return None if isinstance(value, float) and math.isnan(value) else value


def classify_panel(panel: pd.DataFrame, params: PanelParams) -> pd.DataFrame:
    """One boolean column per class; RF-0C raw classes come from its own classifier, row by row and unchanged."""
    inherited = [
        set(classify_member_day({key: _none(value) for key, value in zip(RF_0C_COLUMNS, values, strict=True)}))
        for values in panel.loc[:, list(RF_0C_COLUMNS)].itertuples(index=False, name=None)
    ]
    flags = {name: np.fromiter((name in row for row in inherited), dtype=bool, count=len(inherited)) for name in RF_0C_CLASSES}

    def number(column: str) -> np.ndarray:  # DuckDB 的可空整数/浮点统一成 float，NULL→NaN，比较恒为 False
        return panel[column].astype("Float64").to_numpy(dtype=float, na_value=np.nan)

    def mask(column: str) -> np.ndarray:
        return panel[column].astype("boolean").fillna(False).to_numpy(dtype=bool)

    has_bar = number("bar_record_count") > 0
    qlib = {name: number(f"qlib_{name}") for name in params.qlib_features}
    present = {name: np.isfinite(values) for name, values in qlib.items()}
    flags["ZERO_VOLUME_DAY"] = has_bar & ~(number("vol") > 0)
    for name in params.qlib_features:
        flags[f"QLIB_{name.upper()}_MISSING"] = has_bar & ~present[name]
    flags["QLIB_VALUE_ON_NO_BAR_DAY"] = ~has_bar & np.logical_or.reduce(list(present.values()))
    nonpositive = [present[name] & (qlib[name] <= 0) for name in PRICE_FEATURES if name in qlib]
    flags["QLIB_NONPOSITIVE_PRICE"] = has_bar & np.logical_or.reduce(nonpositive)
    flags["QLIB_ADJUSTMENT_INCONSISTENT"] = mask("adjustment_inconsistent")
    entry_ok = number("entry_open") > 0
    flags["NEXT_DAY_OPEN_MISSING"] = has_bar & ~entry_ok
    flags["NEXT_DAY_LIMIT_UP_AT_OPEN"] = has_bar & entry_ok & mask("entry_limit_up")
    flags["NEXT_DAY_LIMIT_DOWN_AT_OPEN"] = has_bar & entry_ok & mask("entry_limit_down")
    flags["EXIT_DAY_OPEN_MISSING"] = has_bar & ~(number("exit_open") > 0)
    industries = number("industry_count")
    flags["SW_L1_NONE"] = industries == 0
    flags["SW_L1_MULTIPLE"] = industries > 1
    changed = panel["prior_industry"].notna() & panel["industry"].ne(panel["prior_industry"])
    flags["SW_L1_CHANGE_DAY"] = (industries == 1) & changed.astype("boolean").fillna(False).to_numpy(dtype=bool)
    flags["SW_L1_RAW_MULTIPLE_HIT"] = number("raw_l1_count") > 1
    flags["WARMUP_BEFORE_QLIB_CALENDAR_START"] = number("qlib_calendar_index") + 1 < params.warmup
    flags["LISTING_SHORTER_THAN_WARMUP"] = number("calendar_rank") - number("listing_rank") + 1 < params.warmup
    rank = number("market_rank")
    flags["INDEX_ENTRY_DAY"] = (rank > 1) & (number("prior_member_rank") != rank - 1)
    flags["INDEX_EXIT_DAY"] = (rank < number("period_last_rank")) & (number("next_member_rank") != rank + 1)
    return pd.DataFrame(flags, index=panel.index).loc[:, list(CLASSES)]


def field_profile(panel: pd.DataFrame, flags: pd.DataFrame, params: PanelParams) -> dict[str, Any]:
    """Counts and ratios only: no candidate value, feature distribution, return or label."""
    total = len(panel)
    has_bar = panel["bar_record_count"] > 0
    bars = int(has_bar.sum())
    suspended = int(flags["NO_BAR_SUSPENDED"].sum())
    basis = total - suspended  # 补遗 A1：分母剔除两层规则确认停牌日；未解释无 bar 日留在分母
    open_ok = int((has_bar & ~flags["OPEN_MISSING_OR_NONPOSITIVE"]).sum())
    prev_ok = int((has_bar & ~flags["PRE_CLOSE_MISSING_OR_NONPOSITIVE"]).sum())
    qlib_missing = flags.loc[:, [f"QLIB_{name.upper()}_MISSING" for name in params.qlib_features]].any(axis=1)
    qlib_ok = int((has_bar & ~qlib_missing).sum())
    entry_ok = int((has_bar & ~flags["NEXT_DAY_OPEN_MISSING"]).sum())
    unique_industry = int((panel["industry_count"] == 1).sum())
    primary = int((flags["NO_BAR_SUSPENDED"] & panel["primary_suspended"].astype(bool)).sum())
    if min(total, bars, basis) <= 0:
        raise ValueError("TP-F-0B profile has an empty denominator")
    return {
        "period": {"start": params.period[0], "end": params.period[1]},
        "warmup_trading_days": params.warmup,
        "label_clock": {"entry_offset": params.entry_offset, "exit_offset": params.exit_offset},
        "member_day_count": total,
        "bar_member_day_count": bars,
        "confirmed_suspended_member_days": suspended,
        "raw_coverage_basis": "addendum_a1_member_days_not_confirmed_suspended",
        "raw_coverage_basis_member_days": basis,
        "raw_open_coverage": open_ok / basis,
        "raw_prev_close_coverage": prev_ok / basis,
        "report_only_all_member_day_open_coverage": open_ok / total,
        "report_only_all_member_day_prev_close_coverage": prev_ok / total,
        "qlib_feature_non_missing_on_traded_member_days": qlib_ok / bars,
        "sw_l1_unique_industry_coverage": unique_industry / total,
        "next_day_open_exists_on_traded_member_days": entry_ok / bars,
        "class_counts": {name: int(flags[name].sum()) for name in CLASSES},
        "suspension_evidence_layers": {"suspend_d_primary": primary, "independent_baostock_only": suspended - primary},
        "unclassified_missing_field_rows": int(flags["NO_BAR_UNEXPLAINED"].sum()),
    }


def evaluate_gates(profile: Mapping[str, Any], gates: Mapping[str, Any]) -> dict[str, Any]:
    counts = profile["class_counts"]
    checks = {
        "raw_open_coverage": profile["raw_open_coverage"] >= float(gates["raw_open_coverage_minimum"]),
        "raw_prev_close_join": profile["raw_prev_close_coverage"] >= float(gates["raw_prev_close_join_minimum"]),
        "unclassified_missing": profile["unclassified_missing_field_rows"] <= int(gates["unclassified_missing_field_rows_maximum"]),
        "bse_rows": counts["BSE_ROW"] <= int(gates["bse_row_maximum"]),
        "qlib_features": profile["qlib_feature_non_missing_on_traded_member_days"]
        >= float(gates["qlib_feature_non_missing_on_traded_member_days_minimum"]),
        "sw_l1_unique": profile["sw_l1_unique_industry_coverage"] >= float(gates["sw_l1_unique_industry_minimum"]),
        "next_day_open": profile["next_day_open_exists_on_traded_member_days"]
        >= float(gates["next_day_open_exists_on_traded_member_days_minimum"]),
    }
    return {"checks": checks, "pass": all(checks.values())}


def final_verdict(gate: Mapping[str, Any], identity: str) -> str:
    """Identity occupation is terminal for the mechanism and outranks a recoverable data block."""
    if identity == "REJECT_DUPLICATE":
        return "REJECT_DUPLICATE"
    return "GO_FORMAL_PROTOCOL" if gate["pass"] else "BLOCKED_DATA"
