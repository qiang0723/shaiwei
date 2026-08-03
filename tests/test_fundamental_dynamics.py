from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.fundamental_dynamics_contract import (
    FundamentalDynamicsProtocol,
    verify_predecessor_effect,
)
from shaiwei.research.fundamental_dynamics_features import FEATURE_IDS, calculate_dynamics
from shaiwei.research.fundamental_dynamics_gate import build_dynamics_panel
from shaiwei.research.fundamental_dynamics_pairing import latest_consecutive_pairs
from shaiwei.research.fundamental_pit_contract import FundamentalPitError


PROTOCOL = PROJECT_ROOT / "config/f2_csi800_fundamental_dynamics_v1.yaml"


def _protocol() -> FundamentalDynamicsProtocol:
    return FundamentalDynamicsProtocol.load(PROTOCOL)


def _statement_row(name: str, end_date: str, f_ann_date: str, scale: float) -> dict[str, object]:
    base: dict[str, object] = {
        "ts_code": "688001.SH",
        "f_ann_date": f_ann_date,
        "end_date": end_date,
        "report_type": "1",
        "update_flag": "1",
    }
    values = {
        "income": {
            "n_income_attr_p": 8.0 if scale == 1.0 else 12.0,
            "operate_profit": 10.0 if scale == 1.0 else 15.0,
            "total_revenue": 100.0 if scale == 1.0 else 130.0,
        },
        "balancesheet": {
            "total_assets": 100.0 if scale == 1.0 else 120.0,
            "total_liab": 40.0 if scale == 1.0 else 45.0,
            "money_cap": 20.0 if scale == 1.0 else 30.0,
        },
        "cashflow": {"n_cashflow_act": 7.0 if scale == 1.0 else 11.0},
    }
    return {**base, **values[name]}


def _frames() -> dict[str, pd.DataFrame]:
    calendar = pd.DataFrame(
        {
            "exchange": ["SSE"] * 7,
            "cal_date": [
                "20160429",
                "20160503",
                "20170428",
                "20170502",
                "20180430",
                "20180502",
                "20180531",
            ],
            "is_open": [1] * 7,
        }
    )
    index_weight = pd.DataFrame(
        {
            "index_code": ["000906.SH"],
            "con_code": ["688001.SH"],
            "trade_date": ["20180501"],
            "weight": [100.0],
        }
    )
    frames = {"tushare.trade_cal": calendar, "tushare.index_weight": index_weight}
    for name in ("income", "balancesheet", "cashflow"):
        ordinary = pd.DataFrame(
            [
                _statement_row(name, "20161231", "20170428", 1.0),
                _statement_row(name, "20171231", "20180430", 2.0),
            ]
        )
        frames[f"tushare.{name}"] = ordinary
        frames[f"tushare.{name}_vip"] = ordinary.iloc[:0].copy()
    return frames


def test_protocol_freezes_independent_family_and_cumulative_attempts(tmp_path: Path):
    protocol = _protocol()
    family = protocol.document["family_boundary"]
    assert family["static_level_feature_retries_forbidden"] is True
    assert family["cumulative_attempt_count_if_effects_are_ever_inspected"] == 12
    assert protocol.document["scope"]["factor_results_authorized"] is False
    tampered = deepcopy(protocol.document)
    tampered["gates"]["feature_aggregate_coverage_minimum"] = 0.80
    path = tmp_path / "tampered.yaml"
    path.write_text(yaml.safe_dump(tampered, allow_unicode=True), encoding="utf-8")
    with pytest.raises(FundamentalPitError, match="gates"):
        FundamentalDynamicsProtocol.load(path)


def test_predecessor_effect_reject_identity_is_bound():
    predecessor = verify_predecessor_effect(_protocol())
    assert predecessor["verdict"] == "REJECT"
    assert predecessor["candidate_attempt_count"] == 6
    assert predecessor["formal_library_insertions"] == 0


def test_feature_formulas_use_exact_consecutive_pair_and_average_assets():
    panel, diagnostics = build_dynamics_panel(_protocol(), _frames())
    row = panel.loc[panel["formation_date"].eq("20180531")].iloc[0]
    assert row["current_end_date"] == "20171231"
    assert row["predecessor_end_date"] == "20161231"
    assert row[FEATURE_IDS[0]] == pytest.approx(0.2)
    assert row[FEATURE_IDS[1]] == pytest.approx(0.3)
    assert row[FEATURE_IDS[2]] == pytest.approx(5.0 / 110.0)
    assert row[FEATURE_IDS[3]] == pytest.approx(4.0 / 110.0)
    assert row[FEATURE_IDS[4]] == pytest.approx(4.0 / 110.0)
    assert row[FEATURE_IDS[5]] == pytest.approx(10.0 / 110.0)
    assert diagnostics["nonconsecutive_pair_rows"] == 0
    assert diagnostics["future_availability_rows"] == 0


def test_latest_pair_falls_back_without_bridging_a_missing_year():
    members = pd.DataFrame(
        {"formation_date": ["20190531"], "ts_code": ["688001.SH"], "membership_snapshot_date": ["20190501"]}
    )
    common = pd.DataFrame(
        {
            "formation_date": ["20190531"] * 3,
            "ts_code": ["688001.SH"] * 3,
            "end_date": ["20151231", "20161231", "20181231"],
        }
    )
    for name in ("income", "balancesheet", "cashflow"):
        common[f"{name}_end_date"] = common["end_date"]
        common[f"{name}_available_date"] = "20190502"
        common[f"{name}_f_ann_date"] = "20190430"
    selected, newer_unpaired = latest_consecutive_pairs(members, common)
    assert selected.iloc[0]["current_end_date"] == "20161231"
    assert selected.iloc[0]["predecessor_end_date"] == "20151231"
    assert bool(newer_unpaired.iloc[0]) is True


def test_invalid_denominators_fail_closed_to_null():
    panel = pd.DataFrame(
        {
            "current_balancesheet_total_assets": [100.0],
            "predecessor_balancesheet_total_assets": [0.0],
            "current_income_total_revenue": [100.0],
            "predecessor_income_total_revenue": [0.0],
            "current_income_operate_profit": [10.0],
            "predecessor_income_operate_profit": [9.0],
            "current_income_n_income_attr_p": [8.0],
            "predecessor_income_n_income_attr_p": [7.0],
            "current_cashflow_n_cashflow_act": [7.0],
            "predecessor_cashflow_n_cashflow_act": [6.0],
            "current_balancesheet_money_cap": [20.0],
            "predecessor_balancesheet_money_cap": [18.0],
        }
    )
    result = calculate_dynamics(panel)
    assert result.iloc[0][list(FEATURE_IDS)].isna().all()


def test_compose_and_make_targets_are_offline_release_bound_and_narrow():
    compose = yaml.safe_load((PROJECT_ROOT / "compose.research.yaml").read_text(encoding="utf-8"))
    service = compose["services"]["f2-fundamental-dynamics"]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert "env_file" not in service
    assert service["build"]["args"]["SHAIWEI_RELEASE_GIT_HEAD"] == "${SHAIWEI_F2_RELEASE_GIT_HEAD:-}"
    writes = [volume for volume in service["volumes"] if volume.get("read_only") is False]
    assert [volume["source"] for volume in writes] == [
        "./data/research/f2_csi800_fundamental_dynamics_v1"
    ]
    makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
    assert 'SHAIWEI_F2_RELEASE_GIT_HEAD="$(F2_RELEASE_GIT_HEAD)"' in makefile
