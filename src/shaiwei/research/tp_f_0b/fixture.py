"""Eighteen adversarial synthetic fixtures run through the real TP-F-0B store, panel and classifier path."""

from __future__ import annotations

import dataclasses
from pathlib import Path
import tempfile
from typing import Any, Callable

import duckdb
import numpy as np
import pandas as pd

from shaiwei.config import load
from shaiwei.research.rf_0c.fixture import fixture as rf_0c_fixture
from shaiwei.research.tp_f_0b.contract import TPFError, TPFScope, validate_raw_artifacts
from shaiwei.research.tp_f_0b.fields import classify_panel, field_profile
from shaiwei.research.tp_f_0b.panel import PanelParams, build_panel
from shaiwei.research.tp_f_0b.registry import semantic_layer
from shaiwei.research.tp_f_0b.signature import SignatureRule, signature
from shaiwei.research.trend_swing.contract import sha256_file
from shaiwei.research.trend_swing.recovery_store import CORE_SOURCES, configure_store
from shaiwei.transform.qlib_bin import qlib_code


DAYS, PERIOD_END, EX_DAY = 130, 115, 105
CAL = [day.strftime("%Y%m%d") for day in pd.bdate_range("2016-01-04", periods=DAYS)]
LONG_AGO = "20000101"
# 代码 → (上市日序号或 None=很早, 有 bar 的日序号)
STOCKS: dict[str, tuple[int | None, set[int]]] = {
    "600001.SH": (None, set(range(DAYS))),
    "600002.SH": (None, set(range(DAYS))),
    "600003.SH": (None, set(range(DAYS)) - {100, 101, 102}),
    "600004.SH": (None, set(range(DAYS)) - {100, 101, 102}),
    "600005.SH": (None, set(range(DAYS)) - {104}),
    "600006.SH": (0, set(range(DAYS))),
    "600007.SH": (30, set(range(30, DAYS))),
    "600008.SH": (None, set(range(DAYS))),
    "600009.SH": (None, set(range(DAYS))),
    "600010.SH": (None, set(range(DAYS))),
    "600011.SH": (None, set(range(116))),
    "600013.SH": (60, set(range(60, DAYS))),
    "430001.BJ": (None, set(range(DAYS))),
}
SNAPSHOTS = {
    0: sorted(set(STOCKS) - {"600006.SH", "600007.SH", "600013.SH"}),
    60: sorted(STOCKS),
    112: sorted(set(STOCKS) - {"600007.SH"}),
}


def _adj(code: str, day: int) -> float:
    return 1.2 if code in {"600001.SH", "600002.SH"} and day >= EX_DAY else 1.0


def _daily_rows() -> list[dict[str, Any]]:
    rows = []
    for code, (_, bars) in STOCKS.items():
        for day in sorted(bars):
            adjusted = 10 + 0.01 * day
            close = adjusted / _adj(code, day)
            pre_close = (10 + 0.01 * (day - 1)) / _adj(code, day)
            open_ = close - 0.05
            if code == "600010.SH" and day in {109, 111}:
                open_ = round(pre_close * (1.10 if day == 109 else 0.90), 2)
            vol = 0.0 if (code, day) == ("600005.SH", 106) else 1e5
            row = {"ts_code": code, "trade_date": CAL[day], "open": open_, "high": max(open_, close) + 0.1,
                   "low": min(open_, close) - 0.1, "close": close, "pre_close": pre_close, "change": 0.0,
                   "pct_chg": 0.0, "vol": vol, "amount": close * vol / 10}
            if (code, day) in {("600001.SH", 50), ("600013.SH", 60)}:
                row["pre_close"] = None
            if (code, day) == ("600013.SH", 70):
                row["open"] = None
            rows.append(row)
    return rows


def _tables(daily: list[dict[str, Any]]) -> dict[str, pd.DataFrame]:
    calendar = pd.date_range(CAL[0], CAL[-1], freq="D").strftime("%Y%m%d")
    industry = [{"l1_code": "801010", "ts_code": code, "in_date": LONG_AGO, "out_date": None}
                for code in STOCKS if code not in {"600008.SH", "600009.SH"}]
    industry += [
        {"l1_code": "801010", "ts_code": "600008.SH", "in_date": LONG_AGO, "out_date": CAL[103]},
        {"l1_code": "801020", "ts_code": "600008.SH", "in_date": CAL[104], "out_date": None},
        {"l1_code": "801030", "ts_code": "600008.SH", "in_date": CAL[107], "out_date": None},
        {"l1_code": "801040", "ts_code": "600008.SH", "in_date": CAL[107], "out_date": None},
    ]
    return {
        "tushare.trade_cal": pd.DataFrame({"exchange": "SSE", "cal_date": calendar,
                                           "is_open": ["1" if day in set(CAL) else "0" for day in calendar]}),
        "tushare.stock_basic": pd.DataFrame([{"ts_code": code, "list_date": LONG_AGO if listed is None else CAL[listed],
                                              "delist_date": ""} for code, (listed, _) in STOCKS.items()]),
        "tushare.daily": pd.DataFrame(daily),
        "tushare.adj_factor": pd.DataFrame([{"ts_code": r["ts_code"], "trade_date": r["trade_date"],
                                             "adj_factor": _adj(r["ts_code"], CAL.index(r["trade_date"]))} for r in daily]),
        "tushare.daily_basic": pd.DataFrame([{"ts_code": r["ts_code"], "trade_date": r["trade_date"], "total_mv": 1e6,
                                              "close": r["close"]} for r in daily]),
        "tushare.index_weight": pd.DataFrame([{"index_code": "000906.SH", "con_code": code, "trade_date": CAL[day],
                                               "weight": 0.1} for day, codes in SNAPSHOTS.items() for code in codes]),
        "tushare.index_daily": pd.DataFrame([{"ts_code": "000906.SH", "trade_date": CAL[0], "close": 1000.0}]),
        "tushare.index_member_all": pd.DataFrame(industry),
        "tushare.namechange": pd.DataFrame([{"ts_code": code, "name": f"Name{code[:6]}", "start_date": LONG_AGO,
                                             "end_date": None} for code in STOCKS]),
        "tushare.suspend_d": pd.DataFrame([{"ts_code": "600003.SH", "trade_date": CAL[day], "suspend_timing": None,
                                            "suspend_type": "S"} for day in (100, 101, 102)]),
        "baostock.history_k_data_plus": pd.DataFrame(
            [{"ts_code": "600004.SH", "trade_date": f"{CAL[d][:4]}-{CAL[d][4:6]}-{CAL[d][6:]}", "trade_status": "0"}
             for d in (100, 101, 102)] + [{"ts_code": "600001.SH", "trade_date": "2016-01-04", "trade_status": "1"}]),
    }


def _write_qlib(root: Path, daily: list[dict[str, Any]]) -> None:
    (root / "calendars").mkdir(parents=True)
    (root / "calendars/day.txt").write_text("\n".join(CAL) + "\n", encoding="utf-8")
    frame = pd.DataFrame(daily).set_index(["ts_code", "trade_date"])
    for code, (_, bars) in STOCKS.items():
        start = min(bars)
        series: dict[str, np.ndarray] = {name: np.full(DAYS - start, np.nan) for name in
                                         ("open", "close", "high", "low", "volume", "vwap", "factor")}
        for day in range(start, DAYS):
            if day not in bars:
                if code == "600004.SH":  # 反例：停牌日被前值填充
                    for values in series.values():
                        values[day - start] = values[day - start - 1]
                continue
            row = frame.loc[(code, CAL[day])]
            multiplier = 1.0 if code == "600002.SH" else _adj(code, day)  # 600002 反例：未复权
            for name in ("open", "close", "high", "low"):
                series[name][day - start] = np.nan if pd.isna(row[name]) else row[name] * multiplier
            series["volume"][day - start] = row["vol"] * 100 / multiplier
            series["vwap"][day - start] = row["amount"] * 1000 / series["volume"][day - start] if row["vol"] > 0 else np.nan
            series["factor"][day - start] = 1 / multiplier
        directory = root / "features" / qlib_code(code).lower()
        directory.mkdir(parents=True)
        for name, values in series.items():
            np.concatenate([[float(start)], values]).astype("<f4").tofile(directory / f"{name}.day.bin")


def build_store(root: Path) -> dict[str, Any]:
    daily = _daily_rows()
    sources = {}
    for source, table in _tables(daily).items():
        relative = f"data/raw/{source}.parquet"
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        table.to_parquet(root / relative, index=False)
        sources[source] = {"artifacts": [{"path": relative, "content_sha256": sha256_file(root / relative)}]}
    _write_qlib(root / "data/qlib_bin", daily)
    return {"sources": sources}


def run_store(root: Path, params: PanelParams) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    manifest = build_store(root)
    validate_raw_artifacts(manifest, list(CORE_SOURCES), root)
    connection = duckdb.connect(":memory:")
    try:
        configure_store(connection, root / "duckdb-tmp")
        panel = build_panel(connection, manifest, params, root=root, qlib_root=root / "data/qlib_bin",
                            limits=load().limit_rules.model_dump())
    finally:
        connection.close()
    flags = classify_panel(panel, params)
    return panel, flags, field_profile(panel, flags, params)


def _signature_cases(rule: SignatureRule) -> dict[str, Callable[[], bool]]:
    def joint(text: str) -> bool:
        return signature(text, rule).joint_state

    def same(left: str, right: str) -> bool:
        return signature(left, rule).canonical == signature(right, rule).canonical

    return {
        "synonymous_canonical_ast_dedup": lambda: same("Add($close,$open)", "$open + $close")
        and same("Div($close,Mean($close,20d))", "$close/Mean($close, 20)") and same("Div(open_,Constant(2.0))", "$open/2")
        and not same("Div($close,$open)", "Div($open,$close)"),
        "joint_state_signature_positive_and_negative_cases": lambda: all((
            joint("Sub(Div($close,Mean($close,30d)),Div($close,Mean($close,5d)))"),
            joint("($close/Mean($close, 60)) * (($close-$low)/($high-$low+1e-12))"),
            joint("Mul(Div($close,Ref($close,20d)),Div(Mean($volume,5d),Mean($volume,20d)))"),
            not joint("Div($close,Mean($close,20d))"),
            not joint("Sub(EMA($close,10d),EMA($close,50d))"),
            not joint("Mul(Div($close,Mean($close,30d)),Div($close,Ref($close,5d)))"),
            not joint("Mul(Div($close,Mean($close,15d)),Div($close,Mean($close,12d)))"),
            not joint("($close-Min($low, 25))/(Max($high, 25)-Min($low, 25)+1e-12)"),
        )),
        "ts_semantic_signature_collision": lambda: semantic_layer([
            {"semantic_signature": "s1", "candidate_fingerprint": "f1"},
            {"semantic_signature": "s1", "candidate_fingerprint": "f2"},
            {"semantic_signature": "", "candidate_fingerprint": ""},
            {"semantic_signature": "s2", "candidate_fingerprint": "f3"},
        ])["semantic_signature_collisions"] == 1,
    }


def fixture() -> dict[str, Any]:
    scope = TPFScope.load()
    params = dataclasses.replace(PanelParams.from_protocol(scope.document), period=(CAL[0], CAL[PERIOD_END]))
    rule = SignatureRule.from_protocol(scope.document["identity_registry"]["joint_state_signature"])
    with tempfile.TemporaryDirectory(prefix="tp-f-0b-fixture-") as directory:
        panel, flags, profile = run_store(Path(directory), params)
    keys = {(code, day): index for index, (code, day) in enumerate(zip(panel["ts_code"], panel["trade_date"], strict=True))}

    def has(code: str, day: int, *names: str) -> bool:
        index = keys.get((code, CAL[day]))
        return index is not None and all(bool(flags[name].iat[index]) for name in names)

    def lacks(code: str, day: int, *names: str) -> bool:
        index = keys.get((code, CAL[day]))
        return index is not None and not any(bool(flags[name].iat[index]) for name in names)

    def rows(code: str, name: str) -> int:
        return int(flags.loc[panel["ts_code"].eq(code), name].sum())

    cases: dict[str, Callable[[], bool]] = {
        "suspension_missing_bar": lambda: has("600003.SH", 100, "NO_BAR_SUSPENDED") and has("600005.SH", 104, "NO_BAR_UNEXPLAINED"),
        "suspension_confirmed_only_by_independent_baostock_status": lambda: has("600004.SH", 101, "NO_BAR_SUSPENDED")
        and profile["suspension_evidence_layers"] == {"suspend_d_primary": 3, "independent_baostock_only": 3},
        "corporate_action_factor_change_between_signal_and_entry": lambda: has("600001.SH", EX_DAY, "CORPORATE_ACTION_DAY")
        and lacks("600001.SH", EX_DAY - 1, "CORPORATE_ACTION_DAY", "NEXT_DAY_OPEN_MISSING"),
        "first_listing_day_without_prior_close": lambda: has("600013.SH", 60, "FIRST_LISTING_DAY", "PRE_CLOSE_MISSING_OR_NONPOSITIVE"),
        "missing_open_with_present_close": lambda: has("600013.SH", 70, "OPEN_MISSING_OR_NONPOSITIVE"),
        "cross_non_trading_day_prev_close_reference": lambda: lacks("600001.SH", 50, "PRE_CLOSE_MISSING_OR_NONPOSITIVE"),
        "bse_row_rejection": lambda: rows("430001.BJ", "BSE_ROW") == PERIOD_END + 1 and profile["class_counts"]["BSE_ROW"] == PERIOD_END + 1,
        "lookback_window_spanning_suspension_no_forward_or_zero_fill": lambda: rows("600003.SH", "QLIB_VALUE_ON_NO_BAR_DAY") == 0
        and rows("600004.SH", "QLIB_VALUE_ON_NO_BAR_DAY") == 3,
        "adj_factor_change_inside_lookback_window": lambda: rows("600001.SH", "QLIB_ADJUSTMENT_INCONSISTENT") == 0
        and has("600002.SH", EX_DAY, "QLIB_ADJUSTMENT_INCONSISTENT") and rows("600002.SH", "QLIB_ADJUSTMENT_INCONSISTENT") == 1,
        "listing_shorter_than_warmup_window": lambda: has("600007.SH", 110, "LISTING_SHORTER_THAN_WARMUP")
        and lacks("600001.SH", 110, "LISTING_SHORTER_THAN_WARMUP", "WARMUP_BEFORE_QLIB_CALENDAR_START")
        and has("600001.SH", 98, "WARMUP_BEFORE_QLIB_CALENDAR_START"),
        "zero_volume_day_vwap_undefined_classified": lambda: has("600005.SH", 106, "ZERO_VOLUME_DAY", "QLIB_VWAP_MISSING")
        and lacks("600005.SH", 106, "QLIB_CLOSE_MISSING", "QLIB_VOLUME_MISSING"),
        "sw_l1_change_inside_window_and_none_or_multiple_industry": lambda: has("600008.SH", 104, "SW_L1_CHANGE_DAY")
        and has("600008.SH", 108, "SW_L1_MULTIPLE", "SW_L1_RAW_MULTIPLE_HIT") and rows("600009.SH", "SW_L1_NONE") == PERIOD_END + 1
        and rows("600001.SH", "SW_L1_CHANGE_DAY") == 0,
        "pre_membership_history_usable_membership_pit_at_signal_date": lambda: ("600006.SH", CAL[59]) not in keys
        and has("600006.SH", 60, "INDEX_ENTRY_DAY") and has("600007.SH", 111, "INDEX_EXIT_DAY")
        and lacks("600006.SH", 100, "LISTING_SHORTER_THAN_WARMUP", "QLIB_CLOSE_MISSING"),
        "next_day_limit_up_at_open_counted": lambda: has("600010.SH", 108, "NEXT_DAY_LIMIT_UP_AT_OPEN")
        and lacks("600010.SH", 108, "NEXT_DAY_OPEN_MISSING") and has("600010.SH", 110, "NEXT_DAY_LIMIT_DOWN_AT_OPEN"),
        "exit_day_missing_open_counted": lambda: has("600011.SH", 105, "EXIT_DAY_OPEN_MISSING")
        and lacks("600011.SH", 105, "NEXT_DAY_OPEN_MISSING") and has("600003.SH", 99, "NEXT_DAY_OPEN_MISSING"),
        **_signature_cases(rule),
    }
    expected = [*scope.document["adversarial_fixtures"]["inherited_from_rf_0c"], *scope.document["adversarial_fixtures"]["tp_f_specific"]]
    if sorted(cases) != sorted(expected):
        raise TPFError("TP-F-0B fixture set differs from the frozen fixture list")
    failed = sorted(name for name, check in cases.items() if not check())
    basis = profile["member_day_count"] - profile["confirmed_suspended_member_days"]
    if profile["raw_coverage_basis_member_days"] != basis or profile["unclassified_missing_field_rows"] != 1:
        failed.append("addendum_a1_basis")
    if failed:
        raise TPFError(f"TP-F-0B fixture cases failed: {failed}")
    return {"fixture_pass": True, "adversarial_cases": len(cases), "inherited_rf_0c_classifier": rf_0c_fixture(),
            "member_days": profile["member_day_count"], "synthetic_only": True}
