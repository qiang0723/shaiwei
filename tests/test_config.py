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
    assert settings.alphagen_benchmark.min_daily_ic_observations == 252
    assert len(settings.evaluation.g0_windows) == 6
    assert settings.evaluation.g0_windows[0].test_start == date(2019, 1, 1)
    assert settings.evaluation.g0_windows[-1].test_end == date(2024, 12, 31)
    assert settings.evaluation.forward_oos_start == date(2026, 7, 9)
    assert settings.notifications.timeout_seconds == 10
    assert settings.notifications.heartbeat_seconds == 1800
    assert settings.daily.poll_seconds == 900
    assert settings.daily.ready_hour == 19
    assert settings.daily.ready_minute == 30
    assert settings.daily.max_catchup_trade_days == 20
    assert settings.daily.min_market_rows == 3000
    assert settings.shadow_pipeline.enabled
    assert settings.shadow_pipeline.qlib_versions_to_keep == 2
    assert settings.shadow_pipeline.trial_trade_days == 3
    assert settings.g1_admission.spec_version == "g1-v1"
    assert settings.g1_admission.dsr_probability_threshold == 0.95
    assert settings.g1_admission.hac_t_threshold == 3.0
    assert settings.g1_admission.hac_lags == 10
    assert settings.g1_admission.min_observations == 252
    assert settings.g1_admission.discovery_end == date(2018, 12, 31)
    assert settings.g1_admission.factor_blend_weight == 0.1
    assert settings.g1_admission.slippage_stress_extra_each_side == 0.001
    assert settings.g1_admission.promoted_candidates == 2
