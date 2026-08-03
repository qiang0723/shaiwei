"""Pure formulas for the F2 consecutive-annual fundamental change family."""

from __future__ import annotations

import numpy as np
import pandas as pd


FEATURE_IDS = (
    "fundamental_asset_growth_v1",
    "fundamental_revenue_growth_v1",
    "fundamental_operating_profit_change_v1",
    "fundamental_net_income_change_v1",
    "fundamental_operating_cashflow_change_v1",
    "fundamental_cash_balance_change_v1",
)


def _numeric(panel: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(panel[column], errors="coerce")


def calculate_dynamics(panel: pd.DataFrame) -> pd.DataFrame:
    result = panel.copy()
    assets = _numeric(result, "current_balancesheet_total_assets")
    prior_assets = _numeric(result, "predecessor_balancesheet_total_assets")
    revenue = _numeric(result, "current_income_total_revenue")
    prior_revenue = _numeric(result, "predecessor_income_total_revenue")
    average_assets = (assets + prior_assets) / 2.0
    valid_assets = np.isfinite(assets) & assets.gt(0)
    valid_prior_assets = np.isfinite(prior_assets) & prior_assets.gt(0)
    valid_average = (
        valid_assets & valid_prior_assets & np.isfinite(average_assets) & average_assets.gt(0)
    )
    valid_revenue = np.isfinite(prior_revenue) & prior_revenue.gt(0)
    result[FEATURE_IDS[0]] = (assets / prior_assets - 1.0).where(valid_assets & valid_prior_assets)
    result[FEATURE_IDS[1]] = (revenue / prior_revenue - 1.0).where(valid_revenue)
    changes = (
        ("current_income_operate_profit", "predecessor_income_operate_profit"),
        ("current_income_n_income_attr_p", "predecessor_income_n_income_attr_p"),
        ("current_cashflow_n_cashflow_act", "predecessor_cashflow_n_cashflow_act"),
        ("current_balancesheet_money_cap", "predecessor_balancesheet_money_cap"),
    )
    for feature_id, (current, predecessor) in zip(FEATURE_IDS[2:], changes, strict=True):
        value = (_numeric(result, current) - _numeric(result, predecessor)) / average_assets
        result[feature_id] = value.where(valid_average)
    result[list(FEATURE_IDS)] = result[list(FEATURE_IDS)].replace([np.inf, -np.inf], np.nan)
    return result
