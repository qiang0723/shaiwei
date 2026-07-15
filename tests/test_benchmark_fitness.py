import numpy as np
import pandas as pd

from shaiwei.benchmark.fitness import benchmark_decision, forward_open_return, neutralized_rank_ic


def test_forward_open_return_uses_next_open_and_ten_day_holding():
    prices = pd.DataFrame({"A": np.arange(1.0, 15.0)})
    result = forward_open_return(prices, 10)
    assert result.loc[0, "A"] == 12.0 / 2.0 - 1.0


def test_neutralized_rank_ic_removes_industry_and_size_exposure():
    random = np.random.default_rng(42)
    rows = []
    for day in ("2020-01-01", "2020-01-02"):
        signals = random.normal(size=100)
        caps = random.lognormal(size=100)
        for index in range(100):
            industry = "I1" if index < 50 else "I2"
            cap = float(caps[index])
            signal = float(signals[index])
            rows.append(
                {
                    "trade_date": day,
                    "instrument": f"S{index:03d}",
                    "factor": signal + 2.0 * np.log(cap) + (5.0 if industry == "I2" else 0.0),
                    "label": signal,
                    "industry": industry,
                    "market_cap": cap,
                }
            )
    mean_ic, daily = neutralized_rank_ic(pd.DataFrame(rows), min_cross_section=30)
    assert len(daily) == 2
    assert mean_ic > 0.8


def test_benchmark_decision_uses_time_and_rank_ic_threshold():
    assert benchmark_decision(100, 0.04, scale_hours=4, abort_hours=12) == "scale_stage1"
    assert benchmark_decision(13 * 3600, 0.04, scale_hours=4, abort_hours=12) == "fallback_or_reduce"
