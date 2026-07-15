import pandas as pd

from shaiwei.transform.pit import financial_pit_snapshot


def test_boe_2023_restatement_uses_old_report_before_correction_and_new_after():
    statements = pd.DataFrame(
        [
            {
                "ts_code": "000725.SZ", "f_ann_date": "20230428", "end_date": "20221231",
                "report_type": "5", "update_flag": "0", "n_income": 10.0,
            },
            {
                "ts_code": "000725.SZ", "f_ann_date": "20230510", "end_date": "20221231",
                "report_type": "1", "update_flag": "1", "n_income": 8.0,
            },
        ]
    )
    calendar = pd.DataFrame(
        {
            "cal_date": ["20230428", "20230504", "20230510", "20230511"],
            "is_open": [1, 1, 1, 1],
        }
    )
    before = financial_pit_snapshot(statements, calendar, "2023-05-04")
    assert before.loc[0, ["report_type", "update_flag", "n_income"]].tolist() == ["5", "0", 10.0]
    after = financial_pit_snapshot(statements, calendar, "2023-05-11")
    assert after.loc[0, ["report_type", "update_flag", "n_income"]].tolist() == ["1", "1", 8.0]


def test_financial_announcement_is_not_available_same_trading_day():
    statements = pd.DataFrame(
        [{
            "ts_code": "A", "f_ann_date": "20230428", "end_date": "20221231",
            "report_type": "1", "update_flag": "1",
        }]
    )
    calendar = pd.DataFrame({"cal_date": ["20230428", "20230504"], "is_open": [1, 1]})
    assert financial_pit_snapshot(statements, calendar, "2023-04-28").empty
    assert len(financial_pit_snapshot(statements, calendar, "2023-05-04")) == 1
