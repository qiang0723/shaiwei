"""Deterministic fabricated inputs for M5 construction tests; no real securities or financial rows."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .contract import M5DataProtocol
from .features import calculate_features
from .membership import build_membership_panel, formation_schedule
from .statements import build_candidate_components


def _calendar() -> pd.DataFrame:
    days = pd.date_range("2018-01-01", "2026-01-31", freq="B")
    return pd.DataFrame(
        {
            "exchange": "SSE",
            "cal_date": days.strftime("%Y%m%d"),
            "is_open": "1",
        }
    )


def _codes(count: int) -> list[str]:
    return [f"{990000 + index:06d}.SH" for index in range(count)]


def _memberships(
    protocol: M5DataProtocol,
    calendar: pd.DataFrame,
    pool_sizes: tuple[int, int, int],
) -> dict[str, pd.DataFrame]:
    gate = protocol.document["data_gate"]
    schedule = formation_schedule(
        calendar,
        start_month=gate["quality_start_month"],
        end_month=gate["quality_end_month"],
    )
    all_codes = _codes(sum(pool_sizes))
    offsets = (0, pool_sizes[0], pool_sizes[0] + pool_sizes[1])
    result: dict[str, pd.DataFrame] = {}
    for universe_id, size, offset in zip(
        protocol.universe_ids, pool_sizes, offsets, strict=True
    ):
        codes = all_codes[offset : offset + size]
        rows = [
            {
                "trade_date": row.effective_date,
                "formation_date": row.formation_date,
                "universe_id": universe_id,
                "ts_code": code,
            }
            for row in schedule.itertuples(index=False)
            for code in codes
        ]
        frame = pd.DataFrame(rows)
        if universe_id == "star50-official-pit-v2":
            frame = frame[["trade_date", "ts_code"]]
        result[universe_id] = frame
    return result


def _statement_rows(codes: list[str]) -> dict[str, pd.DataFrame]:
    rows: dict[str, list[dict[str, Any]]] = {
        "income": [],
        "balancesheet": [],
        "cashflow": [],
    }
    for security_index, code in enumerate(codes):
        for year in range(2018, 2025):
            elapsed = year - 2018
            identity = {
                "ts_code": code,
                "f_ann_date": f"{year + 1}0315",
                "end_date": f"{year}1231",
                "report_type": "1",
                "update_flag": "1",
            }
            revenue = 1_000.0 + security_index * 7.0 + elapsed * 100.0
            assets = 2_000.0 + security_index * 9.0 + elapsed * 120.0
            rows["income"].append(
                {
                    **identity,
                    "total_revenue": revenue,
                    "total_cogs": revenue * (0.66 - elapsed * 0.005),
                    "rd_exp": revenue * (0.08 + elapsed * 0.002),
                }
            )
            rows["balancesheet"].append(
                {
                    **identity,
                    "accounts_receiv": revenue * (0.16 - elapsed * 0.002),
                    "inventories": assets * (0.12 + elapsed * 0.001),
                    "total_assets": assets,
                    "total_liab": assets * (0.42 - elapsed * 0.003),
                    "total_cur_assets": assets * (0.35 + elapsed * 0.002),
                    "total_cur_liab": assets * (0.2 - elapsed * 0.001),
                }
            )
            rows["cashflow"].append(
                {
                    **identity,
                    "n_cash_flows_fnc_act": (-1.0 if security_index % 2 else 1.0)
                    * assets
                    * (0.02 + elapsed * 0.001),
                    "free_cashflow": revenue * (-0.03 + elapsed * 0.012),
                }
            )
    return {name: pd.DataFrame(values) for name, values in rows.items()}


def synthetic_inputs(
    protocol: M5DataProtocol,
    *,
    pool_sizes: tuple[int, int, int] = (30, 20, 20),
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    calendar = _calendar()
    memberships = _memberships(protocol, calendar, pool_sizes)
    codes = sorted(
        {
            str(code)
            for frame in memberships.values()
            for code in frame["ts_code"].astype(str).unique()
        }
    )
    statements = _statement_rows(codes)
    frames = {"tushare.trade_cal": calendar}
    for name, frame in statements.items():
        frames[f"tushare.{name}"] = frame.copy()
        frames[f"tushare.{name}_vip"] = frame.copy()
    return frames, memberships


def synthetic_feature_panel(
    protocol: M5DataProtocol,
    *,
    pool_sizes: tuple[int, int, int] = (30, 20, 20),
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frames, membership_frames = synthetic_inputs(protocol, pool_sizes=pool_sizes)
    members, membership_diagnostics = build_membership_panel(
        protocol, frames["tushare.trade_cal"], membership_frames
    )
    components, statement_diagnostics = build_candidate_components(protocol, members, frames)
    panel, feature_diagnostics = calculate_features(protocol, components)
    return panel, {
        "membership": membership_diagnostics,
        "statements": statement_diagnostics,
        "features": feature_diagnostics,
    }
