import pandas as pd

from shaiwei.transform.availability import build_status_crosscheck_plan, full_day_suspension_keys


def test_status_plan_contains_only_unexplained_gaps_and_source_bar_conflicts():
    calendar = pd.DataFrame({
        "cal_date": ["20200102", "20200103", "20200106", "20200107"],
        "is_open": [1, 1, 1, 1],
    })
    stocks = pd.DataFrame([
        {"ts_code": "000001.SZ", "list_date": "20200101", "delist_date": None},
        {"ts_code": "920001.BJ", "list_date": "20200101", "delist_date": None},
    ])
    daily = pd.DataFrame({
        "ts_code": ["000001.SZ", "000001.SZ"],
        "trade_date": ["20200102", "20200103"],
    })
    suspensions = pd.DataFrame([
        {
            "ts_code": "000001.SZ", "trade_date": "20200103", "suspend_type": "S",
            "suspend_timing": None,
        },
        {
            "ts_code": "000001.SZ", "trade_date": "20200107", "suspend_type": "S",
            "suspend_timing": None,
        },
    ])

    plan = build_status_crosscheck_plan(
        calendar, stocks, daily, suspensions,
        start="20200101", end="20200107", include_bse=False,
    )

    assert [(item.start_date, item.end_date, item.required_dates) for item in plan] == [
        ("20200103", "20200106", ("20200103", "20200106")),
    ]


def test_full_day_suspensions_exclude_timed_intraday_events():
    source = pd.DataFrame([
        {"ts_code": "A", "trade_date": "1", "suspend_type": "S", "suspend_timing": None},
        {"ts_code": "A", "trade_date": "2", "suspend_type": "S", "suspend_timing": "09:30-10:00"},
    ])
    assert full_day_suspension_keys(source) == {("A", "1")}


def test_status_plan_treats_delist_date_as_exclusive():
    calendar = pd.DataFrame({"cal_date": ["20200102", "20200103"], "is_open": [1, 1]})
    stocks = pd.DataFrame([
        {"ts_code": "000001.SZ", "list_date": "20200101", "delist_date": "20200103"}
    ])
    daily = pd.DataFrame({"ts_code": ["000001.SZ"], "trade_date": ["20200102"]})
    assert build_status_crosscheck_plan(
        calendar,
        stocks,
        daily,
        pd.DataFrame(columns=["ts_code", "trade_date", "suspend_type"]),
        start="20200101",
        end="20200103",
        include_bse=False,
    ) == []
