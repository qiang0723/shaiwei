from datetime import date

import pandas as pd

from shaiwei.transform.universe import active_securities, index_members_on, st_flags_on, st_status_on


def test_active_securities_is_survivorship_free_and_bse_switch_is_suffix_based():
    master = pd.DataFrame(
        [
            {"ts_code": "600001.SH", "list_date": "20100101", "delist_date": "20191231"},
            {"ts_code": "600002.SH", "list_date": "20200101", "delist_date": None},
            {"ts_code": "920001.BJ", "list_date": "20150101", "delist_date": None},
        ]
    )
    old = active_securities(master, date(2018, 1, 1), include_bse=False)
    assert old["ts_code"].tolist() == ["600001.SH"]
    with_bse = active_securities(master, date(2018, 1, 1), include_bse=True)
    assert with_bse["ts_code"].tolist() == ["600001.SH", "920001.BJ"]


def test_index_members_uses_latest_snapshot_known_at_date():
    weights = pd.DataFrame(
        [
            {"index_code": "000906.SH", "con_code": "A", "trade_date": "20200102", "weight": 1.0},
            {"index_code": "000906.SH", "con_code": "B", "trade_date": "20200203", "weight": 2.0},
        ]
    )
    result = index_members_on(weights, date(2020, 1, 31))
    assert result["con_code"].tolist() == ["A"]


def test_st_status_latest_effective_name_does_not_pin_removed_st_forever():
    history = pd.DataFrame(
        [
            {"ts_code": "A", "name": "ST旧名", "start_date": "20180101", "end_date": "20181231"},
            {"ts_code": "A", "name": "新名", "start_date": "20190101", "end_date": None},
        ]
    )
    observations = pd.DataFrame([{"ts_code": "A", "trade_date": "20200102"}])
    result = st_status_on(history, observations)
    assert result.loc[0, "effective_name"] == "新名"
    assert not result.loc[0, "is_st"]


def test_st_status_is_conservative_on_same_day_ties_and_excludes_delisting_name():
    history = pd.DataFrame(
        [
            {"ts_code": "A", "name": "普通名", "start_date": "20200101", "end_date": None},
            {"ts_code": "A", "name": "*ST普通名", "start_date": "20200101", "end_date": None},
            {"ts_code": "B", "name": "ST公司退", "start_date": "20200101", "end_date": None},
        ]
    )
    observations = pd.DataFrame(
        [
            {"ts_code": "A", "trade_date": "20200102"},
            {"ts_code": "B", "trade_date": "20200102"},
        ]
    )
    result = st_status_on(history, observations)
    assert result.set_index("ts_code")["is_st"].to_dict() == {"A": True, "B": False}
    assert st_flags_on(history, observations).tolist() == [True, False]
