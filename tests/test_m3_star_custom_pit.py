from copy import deepcopy

import pandas as pd
import pytest

from tools.m3_star_custom_pit.builder import _partition_sizes, _usable_start, build_membership, risk_flags_on
from tools.m3_star_custom_pit.contract import GateFailure, load_protocol
from tools.m3_star_custom_pit.inputs import InputBundle


def _protocol() -> dict:
    protocol = deepcopy(load_protocol())
    protocol["identity"]["board_launch_date"] = "2020-01-02"
    protocol["identity"]["source_cutoff_date"] = "2020-06-30"
    protocol["liquidity"]["lookback_open_trade_days"] = 3
    protocol["liquidity"]["minimum_valid_days"] = 2
    protocol["size"]["lookback_open_trade_days"] = 3
    protocol["size"]["minimum_valid_days"] = 2
    protocol["readiness"]["all_minimum_names"] = 6
    protocol["readiness"]["midcap_minimum_names"] = 2
    protocol["readiness"]["smallcap_minimum_names"] = 2
    protocol["readiness"]["minimum_consecutive_ready_formations"] = 4
    return protocol


def _bundle() -> InputBundle:
    dates = pd.bdate_range("2020-01-02", "2020-06-30")
    date_keys = dates.strftime("%Y%m%d").tolist()
    codes = tuple(f"688{index:03d}.SH" for index in range(9))
    stock = pd.DataFrame(
        [
            {
                "ts_code": code,
                "list_date": "20180101",
                "delist_date": "20200415" if code == "688008.SH" else "",
            }
            for code in codes
        ]
    )
    trade_cal = pd.DataFrame(
        {"exchange": "SSE", "cal_date": date_keys, "is_open": 1, "pretrade_date": ""}
    )
    daily_rows = [
        {"ts_code": code, "trade_date": day, "amount": 30000.0}
        for day in date_keys
        for code in codes
        if not (code == "688008.SH" and day >= "20200415")
    ]
    basic_rows = [
        {
            "ts_code": row["ts_code"],
            "trade_date": row["trade_date"],
            "total_mv": float(900 - codes.index(row["ts_code"]) * 50),
        }
        for row in daily_rows
    ]
    history = pd.DataFrame(
        [
            {
                "ts_code": "688007.SH",
                "name": "*ST测试",
                "start_date": "20200410",
                "end_date": "20200420",
                "ann_date": "20200410",
            }
        ]
    )
    return InputBundle(
        stock_basic=stock,
        namechange=history,
        trade_cal=trade_cal,
        daily=pd.DataFrame(daily_rows),
        daily_basic=pd.DataFrame(basic_rows),
        star_codes=codes,
        evidence={"selected_input_sha256": "a" * 64},
    )


def test_frozen_protocol_is_data_only_and_custom():
    protocol = load_protocol()
    assert protocol["scope"] == "data_and_rule_feasibility_only"
    assert protocol["identity"]["identity_kind"] == "CUSTOM_RULE_BASED"
    assert protocol["production_authorization"] == "none"


@pytest.mark.parametrize(
    ("count", "expected"),
    [(6, (2, 2, 2)), (7, (3, 2, 2)), (8, (3, 3, 2)), (9, (3, 3, 3))],
)
def test_partition_sizes_are_deterministic_and_assign_remainder_early(count, expected):
    assert _partition_sizes(count) == expected


def test_risk_flag_waits_for_later_announcement_and_is_conservative_on_ties():
    history = pd.DataFrame(
        [
            {
                "ts_code": "688001.SH",
                "name": "普通名称",
                "start_date": "20200101",
                "end_date": "",
                "ann_date": "20200101",
            },
            {
                "ts_code": "688001.SH",
                "name": "*ST名称",
                "start_date": "20200101",
                "end_date": "",
                "ann_date": "20200103",
            },
        ]
    )
    points = pd.DataFrame(
        [
            {"ts_code": "688001.SH", "trade_date": "20200102"},
            {"ts_code": "688001.SH", "trade_date": "20200103"},
        ]
    )
    assert risk_flags_on(history, points).tolist() == [False, True]


def test_build_uses_month_end_next_day_and_applies_daily_st_and_delist_hard_exits():
    protocol = _protocol()
    result = build_membership(_bundle(), protocol)
    ids = protocol["identity"]["universe_ids"]
    first = result.formation_members.loc[
        (result.formation_members["formation_date"] == "20200131")
        & (result.formation_members["universe_id"] == ids["all"])
    ]
    assert first["effective_date"].unique().tolist() == ["20200203"]
    assert len(first) == 9

    daily_all = result.daily_members.loc[result.daily_members["universe_id"].eq(ids["all"])]
    st_code = daily_all.loc[daily_all["ts_code"].eq("688007.SH"), "trade_date"]
    assert "20200409" in set(st_code)
    assert "20200410" not in set(st_code)
    assert "20200420" not in set(st_code)
    assert "20200421" in set(st_code)
    delisted = daily_all.loc[daily_all["ts_code"].eq("688008.SH"), "trade_date"]
    assert "20200414" in set(delisted)
    assert "20200415" not in set(delisted)
    assert result.metrics["readiness_gate_pass"] is True


def test_positive_daily_bar_without_size_fails_closed():
    protocol = _protocol()
    bundle = _bundle()
    broken = InputBundle(
        stock_basic=bundle.stock_basic,
        namechange=bundle.namechange,
        trade_cal=bundle.trade_cal,
        daily=bundle.daily,
        daily_basic=bundle.daily_basic.iloc[1:].reset_index(drop=True),
        star_codes=bundle.star_codes,
        evidence=bundle.evidence,
    )
    with pytest.raises(GateFailure, match="daily_basic coverage failed"):
        build_membership(broken, protocol)


def test_readiness_cannot_recover_after_first_ready_formation():
    protocol = _protocol()
    summary = pd.DataFrame(
        [
            {"formation_date": "20200131", "effective_date": "20200203", "all_count": 5, "midcap_count": 2, "smallcap_count": 1},
            {"formation_date": "20200228", "effective_date": "20200302", "all_count": 6, "midcap_count": 2, "smallcap_count": 2},
            {"formation_date": "20200331", "effective_date": "20200401", "all_count": 5, "midcap_count": 2, "smallcap_count": 1},
            {"formation_date": "20200430", "effective_date": "20200506", "all_count": 6, "midcap_count": 2, "smallcap_count": 2},
        ]
    )
    protocol["readiness"]["minimum_consecutive_ready_formations"] = 1
    with pytest.raises(GateFailure, match="failed after usable start"):
        _usable_start(summary, protocol)
