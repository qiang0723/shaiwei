from datetime import date

from shaiwei.config import load


def test_frozen_config_loads():
    settings = load()
    assert settings.universe.index_code == "000906.SH"
    assert settings.backtest.rebalance_days == 10
    assert settings.backtest.topk == 30
    assert settings.ingest.source_row_limit == 6000
    assert settings.ingest.max_concurrent_requests == 8
    assert settings.crosscheck.symbols == ["000001.SZ", "600519.SH", "300750.SZ", "688981.SH"]
    assert settings.alphagen_benchmark.index_code == "000300.SH"
    assert settings.sentinels.reverse_adjustment_samples.delisted == "600401.SH"
    assert settings.ingest.history_window_years == 10
    assert settings.baseline.validation_months == 6
    assert settings.baseline.seed == 42
    assert settings.alphagen_benchmark.generations == 1
    assert settings.alphagen_benchmark.population_size == 100
    assert len(settings.evaluation.g0_windows) == 6
    assert settings.evaluation.g0_windows[0].test_start == date(2019, 1, 1)
    assert settings.evaluation.g0_windows[-1].test_end == date(2024, 12, 31)
    assert settings.evaluation.forward_oos_start == date(2026, 7, 9)
