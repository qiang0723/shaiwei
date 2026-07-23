import numpy as np
import pandas as pd
import pytest

from tools.p1_moneyflow.contract import MONEYFLOW_FIELDS
from tools.p1_moneyflow.features import (
    FORMAL_CANDIDATES,
    MoneyflowFeatureError,
    audit_feature_lineage,
    build_moneyflow_features,
    residualize_moneyflow_candidates,
)


def _calendar(periods: int = 25) -> list[str]:
    return pd.bdate_range("2026-01-05", periods=periods).strftime("%Y%m%d").tolist()


def _frames(
    *,
    codes: tuple[str, ...] = ("000001.SZ", "600001.SH", "688001.SH"),
    periods: int = 25,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    calendar = _calendar(periods)
    moneyflow_rows = []
    daily_rows = []
    for code_index, code in enumerate(codes, start=1):
        for day_index, trade_date in enumerate(calendar, start=1):
            row = {column: 0.0 for column in MONEYFLOW_FIELDS["moneyflow"]}
            row.update(
                ts_code=code,
                trade_date=trade_date,
                buy_lg_amount=15.0 + code_index,
                sell_lg_amount=5.0,
                buy_elg_amount=10.0,
                sell_elg_amount=0.0,
                net_mf_amount=float(day_index * code_index),
            )
            moneyflow_rows.append(row)
            daily_rows.append(
                {
                    "ts_code": code,
                    "trade_date": trade_date,
                    "amount": 1000.0,
                }
            )
    return (
        pd.DataFrame(moneyflow_rows, columns=MONEYFLOW_FIELDS["moneyflow"]),
        pd.DataFrame(daily_rows),
        calendar,
    )


def test_features_use_previous_official_trade_day_and_frozen_units():
    moneyflow, daily, calendar = _frames()
    panel = build_moneyflow_features(moneyflow, daily, calendar, min_cross_section=2)
    first = panel.loc[
        panel["ts_code"].eq("000001.SZ") & panel["source_trade_date"].eq(calendar[0])
    ].iloc[0]
    assert first["trade_date"] == calendar[1]
    # The smallest of three cross-sectional values is clipped to the 1% quantile.
    assert first["mf_net_intensity_1d"] == pytest.approx(0.0102)
    assert first["mf_large_intensity_1d"] == pytest.approx(0.2102)
    assert pd.isna(first["mf_net_intensity_5d"])
    assert audit_feature_lineage(panel, calendar)["status"] == "PASS"


def test_rolling_windows_refuse_to_bridge_missing_official_day():
    moneyflow, daily, calendar = _frames()
    missing_date = calendar[4]
    moneyflow = moneyflow.loc[
        ~(moneyflow["ts_code"].eq("000001.SZ") & moneyflow["trade_date"].eq(missing_date))
    ].copy()
    panel = build_moneyflow_features(moneyflow, daily, calendar, min_cross_section=2)
    broken = panel.loc[
        panel["ts_code"].eq("000001.SZ") & panel["source_trade_date"].eq(calendar[7])
    ].iloc[0]
    recovered = panel.loc[
        panel["ts_code"].eq("000001.SZ") & panel["source_trade_date"].eq(calendar[9])
    ].iloc[0]
    assert pd.isna(broken["mf_net_intensity_5d"])
    assert recovered["mf_net_intensity_5d"] == pytest.approx(0.0816)


def test_future_source_perturbation_cannot_change_earlier_features():
    moneyflow, daily, calendar = _frames()
    original = build_moneyflow_features(moneyflow, daily, calendar, min_cross_section=2)
    cutoff = calendar[11]
    changed = moneyflow.copy()
    changed.loc[changed["trade_date"].gt(cutoff), "net_mf_amount"] *= -1000
    perturbed = build_moneyflow_features(changed, daily, calendar, min_cross_section=2)
    columns = ["ts_code", "trade_date", "source_trade_date", *FORMAL_CANDIDATES]
    pd.testing.assert_frame_equal(
        original.loc[original["source_trade_date"].le(cutoff), columns].reset_index(drop=True),
        perturbed.loc[perturbed["source_trade_date"].le(cutoff), columns].reset_index(drop=True),
    )


@pytest.mark.parametrize("failure", ["duplicate", "bse"])
def test_features_fail_closed_on_invalid_scope(failure: str):
    moneyflow, daily, calendar = _frames()
    if failure == "duplicate":
        moneyflow = pd.concat([moneyflow, moneyflow.iloc[[0]]], ignore_index=True)
        match = "duplicate keys"
    else:
        moneyflow.loc[0, "ts_code"] = "920001.BJ"
        match = "\\.BJ"
    with pytest.raises(MoneyflowFeatureError, match=match):
        build_moneyflow_features(moneyflow, daily, calendar, min_cross_section=2)


def test_residualization_requires_complete_exposure_and_is_deterministic():
    codes = tuple(f"{index:06d}.SZ" for index in range(1, 41))
    moneyflow, daily, calendar = _frames(codes=codes)
    features = build_moneyflow_features(moneyflow, daily, calendar, min_cross_section=30)
    exposures = []
    for trade_date in calendar[1:]:
        for index, code in enumerate(codes, start=1):
            exposures.append(
                {
                    "ts_code": code,
                    "trade_date": trade_date,
                    "industry": f"I{index % 4}",
                    "market_cap": 1000.0 + index * 10,
                    "amount": 100.0 + index,
                    "turnover_rate": 0.5 + index / 100,
                    "baseline_score": np.sin(index),
                }
            )
    exposure_frame = pd.DataFrame(exposures)
    first = residualize_moneyflow_candidates(features, exposure_frame, min_cross_section=30)
    second = residualize_moneyflow_candidates(features, exposure_frame, min_cross_section=30)
    pd.testing.assert_frame_equal(first, second)
    assert first.duplicated(["ts_code", "trade_date"]).sum() == 0
    assert set(FORMAL_CANDIDATES) <= set(first.columns)
    assert first["mf_net_intensity_20d"].notna().any()

    core_exposures = exposure_frame.drop(columns="baseline_score")
    core = residualize_moneyflow_candidates(
        features,
        core_exposures,
        min_cross_section=30,
        include_baseline_score=False,
    )
    assert core["mf_net_intensity_20d"].notna().any()


def test_lineage_audit_rejects_same_day_use():
    moneyflow, daily, calendar = _frames()
    panel = build_moneyflow_features(moneyflow, daily, calendar, min_cross_section=2)
    panel.loc[panel.index[0], "source_trade_date"] = panel.loc[panel.index[0], "trade_date"]
    with pytest.raises(MoneyflowFeatureError, match="T\\+1"):
        audit_feature_lineage(panel, calendar)
