import subprocess

import pandas as pd

from shaiwei.sentinel.checks import (
    s1_completeness,
    s2_dual_calculation,
    s3_reverse_adjustment,
    s4_units,
    s5_financial_pit,
    s6_suspensions,
    s7_price_volume_logic,
    s8_cross_source,
    s9_st_status,
    s10_git_consistency,
)
from shaiwei.transform.market import sanitize_adj_factors, transform_market_data


def _market_inputs():
    daily = pd.DataFrame(
        [
            {"ts_code": "A", "trade_date": "20200102", "open": 9, "high": 11, "low": 8,
             "close": 10, "pre_close": 9, "change": 1, "pct_chg": 11.111111, "vol": 2, "amount": 2},
            {"ts_code": "A", "trade_date": "20200103", "open": 10, "high": 12, "low": 10,
             "close": 11, "pre_close": 10, "change": 1, "pct_chg": 10, "vol": 2, "amount": 2.2},
        ]
    )
    factors = pd.DataFrame(
        [
            {"ts_code": "A", "trade_date": "20200102", "adj_factor": 1.0},
            {"ts_code": "A", "trade_date": "20200103", "adj_factor": 1.0},
        ]
    )
    return daily, factors


def test_s1_accepts_only_calendar_minus_suspensions():
    cal = pd.DataFrame({"cal_date": ["20200102", "20200103"], "is_open": [1, 1]})
    stocks = pd.DataFrame([{"ts_code": "A", "list_date": "20200101", "delist_date": None}])
    daily, _ = _market_inputs()
    suspensions = pd.DataFrame(columns=["ts_code", "trade_date", "suspend_type"])
    assert s1_completeness(cal, stocks, daily, suspensions, start="20200101", end="20200103").status == "PASS"
    assert s1_completeness(cal, stocks, daily.iloc[:1], suspensions, start="20200101", end="20200103").status == "FAIL"


def test_s2_s3_s4_and_s7_pass_consistent_market_data():
    daily, factors = _market_inputs()
    transformed = transform_market_data(daily, factors)
    assert s2_dual_calculation(daily, factors).status == "PASS"
    assert s3_reverse_adjustment(transformed, daily).status == "PASS"
    assert s4_units(transformed).status == "PASS"
    assert s7_price_volume_logic(transformed).status == "PASS"


def test_s4_rejects_self_consistent_vwap_with_wrong_absolute_units():
    daily, factors = _market_inputs()
    transformed = transform_market_data(daily, factors)
    transformed["amount"] *= 1000
    transformed["vwap"] *= 1000
    assert s4_units(transformed).status == "FAIL"


def test_s3_corporate_action_keeps_adjusted_close_return_continuous():
    daily, factors = _market_inputs()
    daily = daily.astype(
        {field: "float64" for field in ("open", "high", "low", "close", "pre_close", "change", "amount")}
    )
    daily.loc[1, ["open", "high", "low", "close", "pre_close", "change", "amount"]] = [
        5.0, 6.0, 5.0, 5.5, 5.0, 0.5, 1.1,
    ]
    factors.loc[1, "adj_factor"] = 2.0
    transformed = transform_market_data(daily, factors)
    assert s3_reverse_adjustment(transformed, daily).status == "PASS"

    broken = transformed.copy()
    broken.loc[1, "close"] = daily.loc[1, "close"]
    assert s3_reverse_adjustment(broken, daily).status == "FAIL"


def test_s6_detects_non_nan_suspended_bar():
    suspended = pd.DataFrame([{"ts_code": "A", "trade_date": "20200102", "suspend_type": "S"}])
    aligned = pd.DataFrame([{"ts_code": "A", "trade_date": "20200102", "open": 1.0}])
    assert s6_suspensions(aligned, suspended).status == "FAIL"
    aligned["open"] = float("nan")
    assert s6_suspensions(aligned, suspended).status == "PASS"


def test_s5_requires_three_structural_tables_and_preserves_restated_pit():
    calendar = pd.DataFrame(
        {
            "cal_date": ["20230428", "20230504", "20230510", "20230511"],
            "is_open": [1, 1, 1, 1],
        }
    )
    income = pd.DataFrame(
        [
            {
                "ts_code": "000725.SZ",
                "f_ann_date": "20230428",
                "end_date": "20221231",
                "report_type": "5",
                "update_flag": "0",
            },
            {
                "ts_code": "000725.SZ",
                "f_ann_date": "20230510",
                "end_date": "20221231",
                "report_type": "1",
                "update_flag": "1",
            },
        ]
    )
    result = s5_financial_pit(
        income,
        calendar,
        statement_tables={"balancesheet": income.copy(), "cashflow": income.copy()},
    )
    assert result.status == "PASS"
    assert set(result.metrics["tables"]) == {"income", "balancesheet", "cashflow"}

    missing_cashflow = s5_financial_pit(
        income,
        calendar,
        statement_tables={"balancesheet": income.copy(), "cashflow": income.iloc[:0]},
    )
    assert missing_cashflow.status == "FAIL"


def test_s7_requires_factor_jumps_to_match_implemented_corporate_actions():
    daily, factors = _market_inputs()
    factors.loc[1, "adj_factor"] = 2.0
    market = transform_market_data(daily, factors)
    actions = pd.DataFrame(
        [{"ts_code": "A", "ex_date": "20200103", "div_proc": "实施"}]
    )
    assert s7_price_volume_logic(market, actions).status == "PASS"
    actions.loc[0, "ex_date"] = "20200104"
    assert s7_price_volume_logic(market, actions).status == "FAIL"


def test_s7_accepts_preclose_evidence_and_counts_corrected_source_patch():
    daily, factors = _market_inputs()
    daily = daily.astype({field: "float64" for field in ("close", "pre_close")})
    daily.loc[1, "pre_close"] = 5.0
    factors.loc[1, "adj_factor"] = 2.0
    actions = pd.DataFrame(columns=["ts_code", "ex_date", "div_proc"])
    supported = transform_market_data(daily, sanitize_adj_factors(daily, factors, actions))
    supported_result = s7_price_volume_logic(supported, actions)
    assert supported_result.status == "PASS"
    assert supported_result.metrics["factor_jump_rows"] == 1
    assert supported_result.metrics["corrected_factor_rows"] == 0

    daily.loc[1, "pre_close"] = daily.loc[0, "close"]
    corrected = transform_market_data(daily, sanitize_adj_factors(daily, factors, actions))
    corrected_result = s7_price_volume_logic(corrected, actions)
    assert corrected_result.status == "PASS"
    assert corrected_result.metrics["factor_jump_rows"] == 0
    assert corrected_result.metrics["corrected_factor_rows"] == 1


def test_s8_checks_close_and_volume_with_same_raw_units():
    daily, _ = _market_inputs()
    ak = daily.loc[:, ["ts_code", "trade_date", "close", "vol", "amount"]].copy()
    ak["amount"] *= 1000
    ak["close"] = ak["close"].astype(float)
    assert s8_cross_source(daily, ak).status == "PASS"
    ak.loc[0, "close"] *= 1.02
    assert s8_cross_source(daily, ak).status == "FAIL"


def test_s9_requires_a_removed_st_sample_and_handles_delisting_name():
    names = pd.DataFrame(
        [
            {"ts_code": "A", "name": "ST旧名", "start_date": "20180101", "end_date": "20181231"},
            {"ts_code": "A", "name": "新名", "start_date": "20190101", "end_date": None},
            {"ts_code": "B", "name": "ST公司退", "start_date": "20190101", "end_date": None},
        ]
    )
    observations = pd.DataFrame(
        [{"ts_code": "A", "trade_date": "20200102"}, {"ts_code": "B", "trade_date": "20200102"}]
    )
    assert s9_st_status(names, observations).status == "PASS"


def test_s10_is_na_in_dev_without_expected_and_passes_exact_head():
    assert s10_git_consistency(environment="dev").status == "NOT_APPLICABLE"
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    assert s10_git_consistency(environment="prod", expected_commit=head).status == "PASS"
