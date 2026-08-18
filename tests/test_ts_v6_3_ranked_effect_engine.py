import pandas as pd
import pytest

from shaiwei.research.trend_swing.v6_3.cli import main
from shaiwei.research.trend_swing.v6_3.contract import V63Error, V63Scope
from shaiwei.research.trend_swing.v6_3.fixture import fixture
from shaiwei.research.trend_swing.v6_3.inputs import _apply_candidate_filter
from shaiwei.research.trend_swing.v6_3.metrics import (
    evaluate_candidate,
    exit_reason_groups,
    exposure_matched_benchmark,
    pre_fee_expectancy,
    sector_context,
)


def _trades() -> pd.DataFrame:
    return pd.DataFrame([
        {"trade_date": "20210105", "episode_id": "p:600000.SH:20210104", "ts_code": "600000.SH",
         "industry": "银行", "side": "BUY", "batch": 1, "reason": "ENTRY", "gross_notional": 10000.0,
         "fees": 5.0, "closed_trade": False, "closed_trade_pnl": 0.0},
        {"trade_date": "20210110", "episode_id": "p:600000.SH:20210104", "ts_code": "600000.SH",
         "industry": "银行", "side": "SELL", "batch": 1, "reason": "TAKE_PROFIT",
         "gross_notional": 11500.0, "fees": 5.0, "closed_trade": True, "closed_trade_pnl": 1490.0},
        {"trade_date": "20210205", "episode_id": "p:600001.SH:20210204", "ts_code": "600001.SH",
         "industry": "医药", "side": "BUY", "batch": 1, "reason": "ENTRY", "gross_notional": 10000.0,
         "fees": 5.0, "closed_trade": False, "closed_trade_pnl": 0.0},
        {"trade_date": "20210210", "episode_id": "p:600001.SH:20210204", "ts_code": "600001.SH",
         "industry": "医药", "side": "SELL", "batch": 1, "reason": "STOP_EXIT",
         "gross_notional": 9000.0, "fees": 5.0, "closed_trade": True, "closed_trade_pnl": -1010.0},
    ])


def test_pre_fee_expectancy_is_exact_from_frames() -> None:
    trades = _trades()
    after = (1490.0 - 1010.0) / 2
    expected = after + 20.0 / 2
    assert pre_fee_expectancy(trades) == pytest.approx(expected)
    with pytest.raises(V63Error, match="empty"):
        pre_fee_expectancy(trades.iloc[0:0])


def test_exit_groups_exposure_match_and_sector_context() -> None:
    groups = exit_reason_groups(_trades())
    assert groups["TAKE_PROFIT"]["pnl_rmb"] == pytest.approx(1490.0)
    assert groups["STOP_EXIT"]["count"] == 1
    nav = pd.DataFrame({
        "trade_date": ["20210104", "20210105"],
        "gross_weight": [0.5, 0.5],
        "benchmark_return": [0.01, 0.01],
    })
    matched = exposure_matched_benchmark(nav)
    assert matched["mean_gross_weight"] == pytest.approx(0.5)
    assert matched["exposure_matched_h00906_plus_cash_return"] == pytest.approx(
        0.5 * (1.01 * 1.01 - 1.0)
    )
    sectors = sector_context(_trades())
    assert {row["industry"] for row in sectors} == {"银行", "医药"}
    assert sum(row["absolute_pnl_share"] for row in sectors) == pytest.approx(1.0)


def test_candidate_filter_requires_exact_94_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    scope = V63Scope.load()
    keys = {
        (f"6000{index:02d}.SH", "20210104", "20210105") for index in range(94)
    }
    monkeypatch.setattr(
        "shaiwei.research.trend_swing.v6_3.inputs.frozen_candidate_keys", lambda scope: keys
    )
    frame = pd.DataFrame([
        {"point_hash": "p", "ts_code": code, "signal_date": signal, "execution_date": execution}
        for code, signal, execution in sorted(keys)
    ] + [
        {"point_hash": "p", "ts_code": "999999.SH", "signal_date": "20210104",
         "execution_date": "20210105"}
    ])
    filtered = _apply_candidate_filter(frame, scope)
    assert len(filtered) == 94
    with pytest.raises(V63Error, match="BLOCKED_PRE_EFFECT"):
        _apply_candidate_filter(frame.iloc[:-2], scope)


def test_synthetic_fixture_and_cli_are_stable(capsys) -> None:
    assert fixture()["fixture_pass"] is True
    assert main(["fixture"]) == 0
    assert '"fixture_pass": true' in capsys.readouterr().out


def test_gate_fires_when_pre_fee_expectancy_not_positive() -> None:
    nav = pd.DataFrame({
        "trade_date": [f"2021{day:04d}" for day in range(100, 360)],
        "active_return": [0.001] * 260,
    })
    trades = _trades()
    trades.loc[trades["closed_trade"].astype(bool), "closed_trade_pnl"] = [-100.0, -120.0]
    summaries = {
        "base_1x": {
            "closed_trade_count": 40,
            "closed_trade_count_by_year": {"2021": 14, "2022": 13, "2023": 13},
            "pooled_net_return": 0.05,
            "pooled_h00906_net_excess": 0.04,
            "annual": {
                "2021": {"net_return": 0.02, "benchmark_return": 0.0, "net_excess": 0.02},
                "2022": {"net_return": 0.02, "benchmark_return": 0.0, "net_excess": 0.02},
                "2023": {"net_return": 0.01, "benchmark_return": 0.0, "net_excess": 0.01},
            },
            "maximum_drawdown": 0.05,
            "blocked_reason": "",
            "expectancy_rmb": -110.0,
        },
        "all_costs_2x": {"pooled_net_return": 0.01},
        "base_plus_10bp_slippage_each_side": {"pooled_net_return": 0.01},
    }
    gate = {
        "minimum_closed_trades": 30,
        "minimum_closed_trades_each_calendar_year": 5,
        "minimum_positive_h00906_net_excess_calendar_years": 2,
        "maximum_drawdown": 0.20,
        "all_costs_2x_pooled_net_return_minimum": 0.0,
        "extra_10bp_each_side_pooled_net_return_minimum": 0.0,
        "minimum_deflated_sharpe_probability": 0.0,
        "trial_count": 4,
    }
    result = evaluate_candidate(summaries, nav, trades, gate, (0.0, 0.0, 0.0))
    assert result["checks"]["pre_fee_expectancy_positive"] is False
    assert result["passed"] is False
