import pandas as pd

from shaiwei.research.trend_swing.r3g2.effect_fixture import _partition
from shaiwei.research.trend_swing.r3g2.effect_models import scenario
from shaiwei.research.trend_swing.v6_3.metrics import pre_fee_expectancy
from shaiwei.research.trend_swing.v6_4.cli import main
from shaiwei.research.trend_swing.v6_4.contract import V64Scope
from shaiwei.research.trend_swing.v6_4.execution import simulate_no_takeprofit
from shaiwei.research.trend_swing.v6_4.fixture import fixture


def test_removed_take_profit_never_fires_and_structural_exits_survive() -> None:
    scope = V64Scope.load()
    prepared = _partition(scope, "discovery")
    point = scope.selected_point_hashes[0]
    events = prepared.events.loc[prepared.events["point_hash"].eq(point)].copy()
    result = simulate_no_takeprofit(
        events=events,
        bars=prepared.bars,
        benchmark=prepared.benchmark,
        calendar=prepared.calendar,
        current=scenario("base_1x"),
    )
    trades = pd.DataFrame(list(result.trade_rows))
    reasons = set(trades["reason"].astype(str))
    assert "TAKE_PROFIT" not in reasons
    assert "TIME_EXIT" in reasons
    assert trades["closed_trade"].astype(bool).any()
    assert pre_fee_expectancy(trades) is not None


def test_fixture_and_cli_are_stable(capsys) -> None:
    assert fixture()["fixture_pass"] is True
    assert main(["fixture"]) == 0
    assert '"fixture_pass": true' in capsys.readouterr().out
