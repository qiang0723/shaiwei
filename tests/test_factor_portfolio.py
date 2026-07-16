import pandas as pd
import pytest

from shaiwei.research.factor_portfolio import augment_signal, daily_rank_ic, icir, summarize_report


def _series(values):
    index = pd.MultiIndex.from_product(
        [pd.to_datetime(["2020-01-02", "2020-01-03"]), ["A", "B", "C"]],
        names=["datetime", "instrument"],
    )
    return pd.Series(values, index=index, dtype=float)


def test_augmented_signal_uses_cross_sectional_ranks_and_fixed_weight():
    baseline = _series([1, 2, 3, 3, 2, 1])
    factor = _series([3, 2, 1, 1, 2, 3])
    result = augment_signal(baseline, factor, factor_weight=0.1)
    assert len(result) == 6
    assert result.loc[(pd.Timestamp("2020-01-02"), "C")] == pytest.approx(
        0.9 * 1.0 + 0.1 / 3.0
    )


def test_daily_rank_ic_and_icir_are_computed_from_aligned_panels():
    dates = pd.date_range("2020-01-01", periods=3)
    instruments = [f"S{index:02d}" for index in range(30)]
    index = pd.MultiIndex.from_product([dates, instruments], names=["datetime", "instrument"])
    signal = pd.Series(list(range(30)) * 3, index=index, dtype=float)
    labels = signal + pd.Series([0.01 * (index % 3) for index in range(len(signal))], index=index)
    daily = daily_rank_ic(signal, labels)
    assert len(daily) == 3
    assert daily.min() > 0.99
    assert icir(daily) > 100


def test_report_summary_uses_relative_daily_excess_and_turnover():
    report = pd.DataFrame(
        {
            "return": [0.02, -0.01],
            "bench": [0.01, -0.02],
            "cost": [0.001, 0.001],
            "turnover": [0.2, 0.1],
        },
        index=pd.to_datetime(["2020-01-02", "2020-01-03"]),
    )
    result = summarize_report(report)
    expected = ((1 + 0.019) / 1.01) * ((1 - 0.011) / (1 - 0.02)) - 1
    assert result.cumulative_excess == pytest.approx(expected)
    assert result.turnover == pytest.approx(0.3)
