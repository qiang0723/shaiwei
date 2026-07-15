import pandas as pd

from shaiwei.transform.pit import financial_pit_snapshot


def test_real_688502_restatement_uses_old_report_before_correction_and_new_after():
    statements = pd.DataFrame(
        [
            {
                "ts_code": "688502.SH", "f_ann_date": "20230216", "end_date": "20221231",
                "report_type": "5", "update_flag": "0", "n_income": 10.0,
            },
            {
                "ts_code": "688502.SH", "f_ann_date": "20230308", "end_date": "20221231",
                "report_type": "1", "update_flag": "1", "n_income": 8.0,
            },
        ]
    )
    calendar = pd.DataFrame(
        {
            "cal_date": ["20230216", "20230217", "20230308", "20230309"],
            "is_open": [1, 1, 1, 1],
        }
    )
    before = financial_pit_snapshot(statements, calendar, "2023-02-17")
    assert before.loc[0, ["report_type", "update_flag", "n_income"]].tolist() == ["5", "0", 10.0]
    after = financial_pit_snapshot(statements, calendar, "2023-03-09")
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
