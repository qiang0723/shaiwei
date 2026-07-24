from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shaiwei import ledger
from tools.p2_star50_effect_correction.calendar import official_calendar, purged_window_segments
from tools.p2_star50_effect_correction.contract import (
    ORIGINAL_PROTOCOL_PATH,
    load_protocol,
    verify_frozen_inputs,
)
from tools.p2_star50_effect_correction.executor import execute_period, opening_state
from tools.p2_star50_effect_correction.model import training_time_contract


def _fixture(*, periods: int = 40):
    evaluation_dates = pd.bdate_range("2025-01-02", periods=periods)
    warmup_dates = pd.bdate_range(end=evaluation_dates[0] - pd.Timedelta(days=1), periods=20)
    all_dates = [*warmup_dates, *evaluation_dates]
    codes = [f"688{index:03d}.SH" for index in range(1, 17)]
    market_rows = []
    member_rows = []
    prediction_rows = []
    for day_index, date in enumerate(all_dates):
        day = date.strftime("%Y%m%d")
        is_evaluation = date in evaluation_dates
        for code_index, code in enumerate(codes):
            amount = 1_000_000_000.0 if day_index <= 20 else 1_000_000.0
            market_rows.append(
                {
                    "trade_date": day,
                    "ts_code": code,
                    "open": 10.0,
                    "pre_close": 10.0,
                    "close": 10.0,
                    "factor": 1.0,
                    "raw_volume": 1_000_000.0,
                    "amount": amount,
                    "limit_buy": False,
                    "limit_sell": False,
                }
            )
            if is_evaluation:
                eval_index = evaluation_dates.get_loc(date)
                member_rows.append(
                    {
                        "trade_date": day,
                        "ts_code": code,
                        "has_market_bar": True,
                        "industry": f"I{code_index // 3}",
                        "is_st": bool(eval_index >= 20 and code_index in {8, 9}),
                    }
                )
                prediction_rows.append(
                    (date, f"SH{code[:6]}", float(100 - code_index))
                )
    index = pd.MultiIndex.from_tuples(
        [(day, code) for day, code, _ in prediction_rows],
        names=["datetime", "instrument"],
    )
    predictions = pd.Series([score for _, _, score in prediction_rows], index=index)
    benchmark = pd.DataFrame(
        {
            "trade_date": evaluation_dates.strftime("%Y%m%d"),
            "pct_chg": np.zeros(len(evaluation_dates)),
        }
    )
    protocol = deepcopy(load_protocol())
    protocol["portfolio"]["account_rmb"] = 1_000_000
    return (
        predictions,
        pd.DataFrame(market_rows),
        pd.DataFrame(member_rows),
        benchmark,
        evaluation_dates,
        protocol,
    )


def _execute(fixture, *, end_index: int | None = None):
    predictions, market, members, benchmark, dates, protocol = fixture
    end = dates[-1] if end_index is None else dates[end_index]
    return execute_period(
        predictions=predictions,
        market=market,
        member_days=members,
        benchmark=benchmark,
        start=dates[0].strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        cost_multiplier=1.0,
        extra_slippage_each_side=0.0,
        protocol=protocol,
    )


def test_exact_purged_dates_and_unpurged_boundaries_are_proved_from_official_calendar():
    protocol = load_protocol()
    benchmark = pd.read_parquet(
        "data/research/star50/p2-star50-engineering-v1/dataset/benchmark.parquet"
    )
    calendar = official_calendar(benchmark)
    for window in protocol["evaluation"]["windows"]:
        segments, audit = purged_window_segments(
            window,
            calendar,
            protocol["model"]["required_purged_last_signal_dates"][window["name"]],
        )
        assert segments["test"] == tuple(window["test"])
        assert audit["train_label_maturity_within_original_segment"]
        assert audit["valid_label_maturity_within_original_segment"]
        assert audit["valid_label_maturity_before_test"]
        assert audit["original_unpurged_train_would_cross_boundary"]
        assert audit["original_unpurged_valid_would_cross_boundary"]


def test_handler_fit_end_is_the_purged_train_last_signal_and_test_does_not_move():
    protocol = load_protocol()
    benchmark = pd.read_parquet(
        "data/research/star50/p2-star50-engineering-v1/dataset/benchmark.parquet"
    )
    calendar = official_calendar(benchmark)
    pressure = {
        row["frozen_model_window"]: row for row in protocol["evaluation"]["pressure_periods"]
    }
    for window in protocol["evaluation"]["windows"]:
        clock = training_time_contract(protocol, window, pressure[window["name"]], calendar)
        assert clock["fit_end_time"] == clock["segments"]["train"][1]
        assert clock["segments"]["test"] == tuple(window["test"])
        assert clock["maturity"]["valid"]["purged_label_maturity"] < clock["maturity"][
            "first_test_trade_date"
        ]


def test_correction_protocol_preserves_all_original_noncorrected_sections_and_inputs():
    evidence = verify_frozen_inputs(load_protocol())
    assert evidence["original_p2_2_result_tree"]["file_count"] == 115
    assert evidence["original_p2_2_result_tree"]["canonical_tree_sha256"] == (
        "98637864c9e341f1af413c300e922b9e80a02589c5fc91fec8eadb315bd5f3a6"
    )
    assert evidence["qlib"]["artifact_sha256"] == (
        "b8f736ef9bc9e31cc236a81ca281a23e904789fb5ec87caa9195b572c6b78729"
    )
    assert ORIGINAL_PROTOCOL_PATH.is_file()


def test_open_executability_ignores_close_based_flags_and_uses_raw_tick_boundary():
    protocol = load_protocol()
    close_limit_open_normal = {
        "open": 10.0,
        "pre_close": 10.0,
        "factor": 0.8,
        "raw_volume": 100.0,
        "close": 12.0,
        "pct_chg": 20.0,
        "limit_buy": True,
        "limit_sell": True,
    }
    state = opening_state(close_limit_open_normal, protocol)
    assert state.tradeable and not state.buy_blocked and not state.sell_blocked

    open_limit_close_normal = dict(close_limit_open_normal, open=11.94, close=10.0, limit_buy=False)
    boundary = opening_state(open_limit_close_normal, protocol)
    assert boundary.buy_blocked
    below = opening_state(dict(open_limit_close_normal, open=11.937), protocol)
    assert not below.buy_blocked


def test_same_day_close_and_legacy_flags_cannot_change_that_days_opening_decision_or_nav_open():
    fixture = _fixture(periods=3)
    predictions, market, members, benchmark, dates, protocol = fixture
    baseline = _execute(fixture, end_index=1)
    changed = market.copy()
    execution_day = dates[1].strftime("%Y%m%d")
    changed.loc[changed["trade_date"].eq(execution_day), "close"] = 99.0
    changed.loc[changed["trade_date"].eq(execution_day), ["limit_buy", "limit_sell"]] = True
    corrected = execute_period(
        predictions=predictions,
        market=changed,
        member_days=members,
        benchmark=benchmark,
        start=dates[0].strftime("%Y-%m-%d"),
        end=dates[1].strftime("%Y-%m-%d"),
        cost_multiplier=1.0,
        extra_slippage_each_side=0.0,
        protocol=protocol,
    )
    pd.testing.assert_frame_equal(baseline.trades, corrected.trades)
    assert baseline.daily.iloc[-1]["nav_open"] == corrected.daily.iloc[-1]["nav_open"]


def test_open_limit_and_zero_volume_block_execution_even_when_close_is_not_limited():
    fixture = _fixture(periods=3)
    predictions, market, members, benchmark, dates, protocol = fixture
    execution_day = dates[1].strftime("%Y%m%d")
    open_limit = market.copy()
    open_limit.loc[open_limit["trade_date"].eq(execution_day), "open"] = 11.94
    blocked = execute_period(
        predictions=predictions,
        market=open_limit,
        member_days=members,
        benchmark=benchmark,
        start=dates[0].strftime("%Y-%m-%d"),
        end=dates[1].strftime("%Y-%m-%d"),
        cost_multiplier=1.0,
        extra_slippage_each_side=0.0,
        protocol=protocol,
    )
    assert blocked.trades.empty

    zero_volume = market.copy()
    zero_volume.loc[zero_volume["trade_date"].eq(execution_day), "raw_volume"] = 0.0
    suspended = execute_period(
        predictions=predictions,
        market=zero_volume,
        member_days=members,
        benchmark=benchmark,
        start=dates[0].strftime("%Y-%m-%d"),
        end=dates[1].strftime("%Y-%m-%d"),
        cost_multiplier=1.0,
        extra_slippage_each_side=0.0,
        protocol=protocol,
    )
    assert suspended.trades.empty


def test_sell_capacity_is_partial_and_retried_for_hard_ineligible_holdings():
    result = _execute(_fixture())
    sells = result.trades.loc[
        result.trades["side"].eq("SELL") & result.trades["ts_code"].isin(["688009.SH", "688010.SH"])
    ]
    assert sells["signal_date"].nunique() >= 2
    assert sells.groupby("ts_code")["trade_date"].nunique().min() >= 2
    assert sells["capacity_utilization"].le(1.0 + 1e-12).all()
    assert result.trades.loc[result.trades["side"].eq("BUY"), "capacity_utilization"].le(
        1.0 + 1e-12
    ).all()


def test_correction_ledger_is_idempotent_and_collision_closed(tmp_path: Path):
    path = tmp_path / "correction.csv"
    path.write_text("run_id,protocol_frozen_at,run_finished_at,status,operator\n", encoding="utf-8")
    row = {
        "run_id": "p2-2c-one",
        "protocol_frozen_at": "2026-07-25T01:30:00+08:00",
        "run_finished_at": "2026-07-24T18:00:00+00:00",
        "status": "NO_GO",
        "operator": "test",
    }
    assert ledger.append_p2_star50_effect_correction_run(path=path, **row)
    assert not ledger.append_p2_star50_effect_correction_run(path=path, **row)
    with pytest.raises(ValueError, match="collision"):
        ledger.append_p2_star50_effect_correction_run(path=path, **{**row, "status": "GO"})
