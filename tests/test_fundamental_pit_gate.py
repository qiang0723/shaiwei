from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.fundamental_pit_contract import FundamentalPitError, FundamentalPitProtocol
from shaiwei.research.fundamental_pit_gate import (
    _canonical_statement,
    _with_availability,
    build_feature_panel,
)


PROTOCOL = PROJECT_ROOT / "config/f1_csi800_fundamental_pit_v1.yaml"


def _protocol() -> FundamentalPitProtocol:
    return FundamentalPitProtocol.load(PROTOCOL)


def _statement(name: str, *, end_date: str = "20171231") -> pd.DataFrame:
    base = {
        "ts_code": ["000001.SZ", "600001.SH"],
        "f_ann_date": ["20180430", "20180430"],
        "end_date": [end_date, end_date],
        "report_type": ["1", "1"],
        "update_flag": ["1", "1"],
    }
    values = {
        "income": {
            "n_income_attr_p": [10.0, 20.0],
            "operate_profit": [12.0, 18.0],
            "total_revenue": [100.0, 200.0],
        },
        "balancesheet": {
            "total_assets": [100.0, 200.0],
            "total_liab": [40.0, 100.0],
            "money_cap": [20.0, 30.0],
        },
        "cashflow": {"n_cashflow_act": [8.0, 25.0]},
    }
    return pd.DataFrame({**base, **values[name]})


def _frames(*, cashflow_end: str = "20171231") -> dict[str, pd.DataFrame]:
    calendar = pd.DataFrame(
        {
            "exchange": ["SSE"] * 5,
            "cal_date": ["20180430", "20180502", "20180531", "20180601", "20180629"],
            "is_open": [1, 1, 1, 1, 1],
        }
    )
    index_weight = pd.DataFrame(
        {
            "index_code": ["000906.SH", "000906.SH"],
            "con_code": ["000001.SZ", "600001.SH"],
            "trade_date": ["20180501", "20180501"],
            "weight": [50.0, 50.0],
        }
    )
    frames = {
        "tushare.trade_cal": calendar,
        "tushare.index_weight": index_weight,
    }
    for name in ("income", "balancesheet", "cashflow"):
        ordinary = _statement(name, end_date=cashflow_end if name == "cashflow" else "20171231")
        frames[f"tushare.{name}"] = ordinary
        frames[f"tushare.{name}_vip"] = ordinary.iloc[:0].copy()
    return frames


def test_protocol_freezes_offline_data_only_authority(tmp_path: Path):
    protocol = _protocol()
    assert len(protocol.features) == 6
    assert protocol.document["scope"]["factor_results_authorized"] is False
    assert protocol.document["sources"]["network_requests_authorized"] is False

    tampered = deepcopy(protocol.document)
    tampered["scope"]["backtest_authorized"] = True
    path = tmp_path / "tampered.yaml"
    path.write_text(yaml.safe_dump(tampered), encoding="utf-8")
    with pytest.raises(FundamentalPitError, match="authority"):
        FundamentalPitProtocol.load(path)


def test_next_open_day_is_strictly_after_announcement():
    frame = _statement("income").iloc[[0]].copy()
    result = _with_availability(frame, ["20180430", "20180502"])
    assert result.loc[result.index[0], "available_date"] == "20180502"


def test_identical_cross_endpoint_rows_deduplicate_but_conflicts_fail():
    ordinary = _statement("income")
    result, conflicts = _canonical_statement("income", [ordinary, ordinary.copy()])
    assert len(result) == len(ordinary)
    assert conflicts == 0

    changed = ordinary.copy()
    changed.loc[0, "n_income_attr_p"] = 999.0
    with pytest.raises(FundamentalPitError, match="conflicting duplicate"):
        _canonical_statement("income", [ordinary, changed])


def test_feature_panel_uses_matching_annual_periods_and_expected_formulas():
    panel, diagnostics = build_feature_panel(_protocol(), _frames())
    row = panel.loc[(panel["formation_date"] == "20180531") & (panel["ts_code"] == "000001.SZ")].iloc[0]
    assert row["end_date"] == "20171231"
    assert row["available_date"] == "20180502"
    assert row["fundamental_net_income_to_assets_v1"] == pytest.approx(0.1)
    assert row["fundamental_operating_margin_v1"] == pytest.approx(0.12)
    assert row["fundamental_cash_return_on_assets_v1"] == pytest.approx(0.08)
    assert row["fundamental_leverage_v1"] == pytest.approx(0.4)
    assert row["fundamental_cash_to_assets_v1"] == pytest.approx(0.2)
    assert row["fundamental_accruals_to_assets_v1"] == pytest.approx(0.02)
    assert diagnostics["future_availability_rows"] == 0
    assert diagnostics["mixed_component_period_rows"] == 0


def test_cross_statement_period_mixing_is_never_constructed():
    panel, diagnostics = build_feature_panel(_protocol(), _frames(cashflow_end="20161231"))
    assert diagnostics["mixed_component_period_rows"] > 0
    assert panel["fundamental_cash_return_on_assets_v1"].isna().all()
    assert panel["fundamental_accruals_to_assets_v1"].isna().all()


def test_missing_statement_component_remains_null_without_mixed_type_comparison():
    frames = _frames()
    frames["tushare.cashflow"] = frames["tushare.cashflow"].iloc[[0]].copy()
    panel, diagnostics = build_feature_panel(_protocol(), frames)
    missing = panel.loc[panel["ts_code"].eq("600001.SH")]
    assert missing["available_date"].isna().all()
    assert missing["fundamental_net_income_to_assets_v1"].isna().all()
    assert diagnostics["future_availability_rows"] == 0


def test_make_target_maps_public_release_identity_into_compose():
    makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
    assert 'SHAIWEI_F1_RELEASE_GIT_HEAD="$(F1_RELEASE_GIT_HEAD)" docker compose' in makefile
