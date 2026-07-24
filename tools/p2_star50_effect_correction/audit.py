"""Read-only, independently recomputable P2-2C defect and boundary audits."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from tools.p2_star50_effect_correction.calendar import official_calendar, purged_window_segments
from tools.p2_star50_effect_correction.contract import CorrectionGateFailure


def label_maturity_audit(
    protocol: dict[str, Any], benchmark: pd.DataFrame
) -> dict[str, Any]:
    calendar = official_calendar(benchmark)
    windows: dict[str, Any] = {}
    for window in protocol["evaluation"]["windows"]:
        _, audit = purged_window_segments(
            window,
            calendar,
            protocol["model"]["required_purged_last_signal_dates"][window["name"]],
        )
        windows[window["name"]] = audit
    return {
        "label": protocol["model"]["label"],
        "label_horizon_trade_days": protocol["model"]["label_horizon_trade_days"],
        "required_purged_last_signal_dates": protocol["model"]["required_purged_last_signal_dates"],
        "windows": windows,
        "all_purged_maturities_within_original_segments": all(
            row["train_label_maturity_within_original_segment"]
            and row["valid_label_maturity_within_original_segment"]
            and row["valid_label_maturity_before_test"]
            for row in windows.values()
        ),
        "all_original_unpurged_segments_demonstrably_leak": all(
            row["original_unpurged_train_would_cross_boundary"]
            and row["original_unpurged_valid_would_cross_boundary"]
            for row in windows.values()
        ),
    }


def opening_flag_audit(market: pd.DataFrame, member_days: pd.DataFrame) -> dict[str, Any]:
    required = {
        "trade_date",
        "ts_code",
        "open",
        "pre_close",
        "factor",
        "raw_volume",
        "limit_buy",
        "limit_sell",
    }
    if missing := required - set(market.columns):
        raise CorrectionGateFailure(f"market is missing open audit fields: {sorted(missing)}")
    frame = market.copy()
    frame["trade_date"] = frame["trade_date"].astype(str)
    frame["ts_code"] = frame["ts_code"].astype(str)
    frame = frame.loc[frame["trade_date"].between("20230101", "20260630")].copy()
    raw_open = pd.to_numeric(frame["open"], errors="coerce") * pd.to_numeric(
        frame["factor"], errors="coerce"
    )
    raw_pre_close = pd.to_numeric(frame["pre_close"], errors="coerce") * pd.to_numeric(
        frame["factor"], errors="coerce"
    )
    raw_volume = pd.to_numeric(frame["raw_volume"], errors="coerce")
    valid = (
        np.isfinite(raw_open)
        & np.isfinite(raw_pre_close)
        & np.isfinite(raw_volume)
        & raw_open.gt(0)
        & raw_pre_close.gt(0)
        & raw_volume.gt(0)
    )
    opening_change = raw_open / raw_pre_close - 1.0
    tolerance = 0.01 / raw_pre_close
    frame["open_upper"] = valid & opening_change.ge(0.195 - tolerance)
    frame["open_lower"] = valid & opening_change.le(-0.195 + tolerance)
    all_market = {
        "row_count": int(len(frame)),
        "valid_open_row_count": int(valid.sum()),
        "buy_flag_mismatch_count": int(
            frame["limit_buy"].astype(bool).ne(frame["open_upper"]).sum()
        ),
        "sell_flag_mismatch_count": int(
            frame["limit_sell"].astype(bool).ne(frame["open_lower"]).sum()
        ),
    }
    members = member_days.loc[:, ["trade_date", "ts_code"]].copy()
    members["trade_date"] = members["trade_date"].astype(str)
    members["ts_code"] = members["ts_code"].astype(str)
    joined = frame.merge(members, on=["trade_date", "ts_code"], how="inner", validate="one_to_one")
    official = {
        "row_count": int(len(joined)),
        "buy_flag_mismatch_count": int(
            joined["limit_buy"].astype(bool).ne(joined["open_upper"]).sum()
        ),
        "sell_flag_mismatch_count": int(
            joined["limit_sell"].astype(bool).ne(joined["open_lower"]).sum()
        ),
    }
    return {"period": ["2023-01-01", "2026-06-30"], "all_market": all_market, "official": official}


def original_capacity_audit(
    market: pd.DataFrame,
    benchmark: pd.DataFrame,
    trades_by_window: dict[str, pd.DataFrame],
    windows: list[dict[str, Any]],
) -> dict[str, Any]:
    market_slice = market.loc[:, ["trade_date", "ts_code", "amount"]].copy()
    market_slice["trade_date"] = market_slice["trade_date"].astype(str)
    market_slice["ts_code"] = market_slice["ts_code"].astype(str)
    benchmark_dates = benchmark["trade_date"].astype(str)
    global_calendar = sorted(market_slice["trade_date"].unique())
    amount = {
        (str(row.trade_date), str(row.ts_code)): float(row.amount)
        for row in market_slice.itertuples(index=False)
        if pd.notna(row.amount)
    }
    rows: list[dict[str, Any]] = []
    window_map = {row["name"]: row for row in windows}
    for name, trades in trades_by_window.items():
        test = window_map[name]["test"]
        calendar = sorted(
            benchmark_dates.loc[
                benchmark_dates.between(test[0].replace("-", ""), test[1].replace("-", ""))
            ].unique()
        )
        execution_to_signal = {
            calendar[index + 1]: calendar[index] for index in range(0, len(calendar) - 1, 10)
        }
        for row in trades.itertuples(index=False):
            trade_date = str(row.trade_date)
            if trade_date not in execution_to_signal:
                raise CorrectionGateFailure(f"original trade is off the frozen rebalance schedule: {trade_date}")
            signal_date = execution_to_signal[trade_date]
            position = global_calendar.index(signal_date)
            lookback = global_calendar[max(0, position - 19) : position + 1]
            values = [
                amount[(day, str(row.ts_code))]
                for day in lookback
                if (day, str(row.ts_code)) in amount
                and np.isfinite(amount[(day, str(row.ts_code))])
                and amount[(day, str(row.ts_code))] > 0
            ]
            median = float(np.median(values)) if values else float("nan")
            rows.append(
                {
                    "window": name,
                    "side": str(row.side),
                    "valid_days": len(values),
                    "capacity_ratio": float(row.notional) / median if median > 0 else float("nan"),
                }
            )
    frame = pd.DataFrame(rows)
    sell_violations = frame.loc[frame["side"].eq("SELL") & frame["capacity_ratio"].gt(0.05 + 1e-12)]
    return {
        "original_base_trade_count": int(len(frame)),
        "original_base_buy_count": int(frame["side"].eq("BUY").sum()),
        "original_base_sell_count": int(frame["side"].eq("SELL").sum()),
        "original_buy_capacity_violation_count": int(
            (frame["side"].eq("BUY") & frame["capacity_ratio"].gt(0.05 + 1e-12)).sum()
        ),
        "original_sell_capacity_violation_count": int(len(sell_violations)),
        "original_maximum_buy_capacity_ratio": float(
            frame.loc[frame["side"].eq("BUY"), "capacity_ratio"].max()
        ),
        "original_maximum_sell_capacity_ratio": float(
            frame.loc[frame["side"].eq("SELL"), "capacity_ratio"].max()
        ),
        "original_sell_capacity_violations_by_window": {
            key: int(value) for key, value in sell_violations.groupby("window").size().items()
        },
        "original_sell_minimum_valid_amount_days": int(
            frame.loc[frame["side"].eq("SELL"), "valid_days"].min()
        ),
    }


def member_listing_lead_audit(
    market: pd.DataFrame,
    member_days: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> dict[str, Any]:
    market_slice = market.loc[:, ["trade_date", "ts_code", "raw_volume"]].copy()
    members = member_days.loc[:, ["trade_date", "ts_code"]].copy()
    for frame in (market_slice, members):
        frame["trade_date"] = frame["trade_date"].astype(str)
        frame["ts_code"] = frame["ts_code"].astype(str)
    calendar = official_calendar(benchmark)
    positions = {day: index for index, day in enumerate(calendar)}
    first_member = members.groupby("ts_code")["trade_date"].min()
    first_bar = (
        market_slice.loc[pd.to_numeric(market_slice["raw_volume"], errors="coerce").gt(0)]
        .groupby("ts_code")["trade_date"]
        .min()
    )
    lead = first_member.map(positions) - first_bar.reindex(first_member.index).map(positions)
    return {
        "member_code_count": int(len(lead)),
        "missing_first_valid_bar_count": int(lead.isna().sum()),
        "minimum_first_member_bar_lead_trade_days": int(lead.min()),
        "maximum_first_member_bar_lead_trade_days": int(lead.max()),
        "minimum_lead_codes": sorted(lead.loc[lead.eq(lead.min())].index.tolist()),
        "forbidden_bj_member_day_count": int(members["ts_code"].str.endswith(".BJ").sum()),
    }
