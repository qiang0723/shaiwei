"""R2-1R1 评估器：冻结钉扎、live-dual 判定、缺口与代码快照重置、锁存、计数输出无净值、日历覆盖、信号核验与一次性描述报告（全合成）。"""

import hashlib
import json
import shutil
from datetime import date, timedelta

import pandas as pd
import pytest

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.r2_1r1 import cli
from shaiwei.research.r2_1r1.contract import DOCUMENT_RELATIVE, PROTOCOL_RELATIVE, Contract, R21R1Error
from shaiwei.research.r2_1r1.evidence import daily_gate, load_signals, official_open_days
from shaiwei.research.r2_1r1.report import build_report, write_once
from shaiwei.research.r2_1r1.segment import AccountDay, DayEvidence, Signal, build_segments, classify_day, latched_segment, progress
from shaiwei.shadow.manifest import _canonical_json


@pytest.fixture(scope="module")
def contract() -> Contract:
    return Contract.load()


def _days(count: int, start: str = "20261102") -> list[str]:
    cursor, result = date(int(start[:4]), int(start[4:6]), int(start[6:])), []
    while len(result) < count:
        if cursor.weekday() < 5:
            result.append(cursor.strftime("%Y%m%d"))
        cursor += timedelta(days=1)
    return result


def _row(contract: Contract, role: str, day: str, *, started: str | None = None, **overrides: str) -> dict[str, str]:
    account = contract.control if role == "control" else contract.comparison
    base = {
        "account_id": account.account_id, "started_at": started or f"{day[:4]}-{day[4:6]}-{day[6:]}T17:20:00+08:00",
        "operator": "docker-scheduler", "policy_sha256": account.policy_sha256, "signal_trade_date": "20261101",
        "execution_trade_date": day, "signal_sha256": f"sig-{day}", "reconciliation_sha256": f"rec-{day}",
        "data_snapshot_sha256": "data", "code_snapshot_sha256": "code-a",
    }
    return {**base, **overrides}


def _pair(contract: Contract, day: str, *, control: dict | None = None, comparison: dict | None = None,
          gate: bool = True, mode: str = "FORWARD") -> dict[str, list[AccountDay]]:
    rows = {"control": _row(contract, "control", day, **(control or {})), "comparison": _row(contract, "comparison", day, **(comparison or {}))}
    return {role: [AccountDay(row, mode, (contract.control if role == "control" else contract.comparison).policy_version, gate)]
            for role, row in rows.items()}


def _signals(days: list[str], rebalance: set[str] = frozenset(), late: set[str] = frozenset()) -> dict[str, Signal]:
    return {f"sig-{day}": Signal(day in rebalance, day not in late) for day in days}


def test_frozen_files_are_pinned_and_tampering_fails_closed(tmp_path, contract):
    assert contract.minimum_days == 20 and contract.minimum_rebalances == 2 and contract.history_start == "20260803"
    for relative in (PROTOCOL_RELATIVE, DOCUMENT_RELATIVE):
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT_ROOT / relative, tmp_path / relative)
    Contract.load(tmp_path)
    (tmp_path / PROTOCOL_RELATIVE).write_text((tmp_path / PROTOCOL_RELATIVE).read_text() + "\n", encoding="utf-8")
    with pytest.raises(R21R1Error):
        Contract.load(tmp_path)


def test_every_frozen_predicate_turns_a_day_into_a_gap(contract):
    day = "20261102"
    signals = _signals([day])
    assert classify_day(day, contract, _pair(contract, day), signals).live
    cases = {
        "CONTROLLED_CATCHUP_control": _pair(contract, day, control={"started_at": "2026-11-03T01:00:00+08:00"}),
        "OPERATOR_comparison": _pair(contract, day, comparison={"operator": "manual"}),
        "POLICY_IDENTITY_control": _pair(contract, day, control={"policy_sha256": "0" * 64}),
        "PAIR_IDENTITY_MISMATCH": _pair(contract, day, comparison={"reconciliation_sha256": "other"}),
        "ACCOUNTING_FRESHNESS_OR_BSE_control": _pair(contract, day, gate=False),
        "NOT_FORWARD_comparison": _pair(contract, day, mode="BACKFILL"),
    }
    for reason, account_days in cases.items():
        assert reason in classify_day(day, contract, account_days, signals).reasons
    pair = _pair(contract, day)
    assert classify_day(day, contract, {"control": pair["control"], "comparison": []}, signals).reasons == ("MISSING_comparison",)
    assert classify_day(day, contract, {"control": pair["control"] * 2, "comparison": pair["comparison"]}, signals).reasons == ("DUPLICATE_control",)
    with pytest.raises(R21R1Error, match="started before"):
        classify_day(day, contract, _pair(contract, day, control={"started_at": "2026-11-01T17:00:00+08:00"}), signals)
    with pytest.raises(R21R1Error, match="no verified shadow signal"):
        classify_day(day, contract, _pair(contract, day), {})


def _evidence(days: list[str], *, gaps: set[str] = frozenset(), rebalance: set[str] = frozenset(),
              code: dict[str, str] | None = None, late: set[str] = frozenset()) -> list[DayEvidence]:
    return [DayEvidence(day, ("MISSING_control",)) if day in gaps
            else DayEvidence(day, (), (code or {}).get(day, "code-a"), day in rebalance, day not in late) for day in days]


def test_gaps_and_code_changes_reset_and_the_first_reach_latches(contract):
    days = _days(60)
    # 19 日 + 缺口：不达门；之后 2 日旧代码，再在新代码下累计 20 日、2 次调仓
    gap, change = days[19], days[22]
    code = {day: ("code-b" if day >= change else "code-a") for day in days}
    evidence = _evidence(days, gaps={gap, days[50]}, rebalance={days[5], days[15], days[25], days[35]}, code=code)
    segments = build_segments(evidence, contract)
    assert [len(segment.days) for segment in segments] == [19, 2, 28, 9]
    latched = latched_segment(segments)
    assert latched is segments[2] and latched.first == change and latched.latch_day == days[41]
    report = progress(evidence, contract, as_of=days[-1], next_open=None)
    assert report["terminal_state"] == "CHECKPOINT_OBSERVED" and report["reset_count"] == 2
    assert report["latched_segment"]["latch_day"] == days[41] and report["current_segment"]["first"] == days[51]
    assert "nav" not in json.dumps({key: value for key, value in report.items() if key != "contains_nav_or_return"})


def test_not_due_and_execution_warning_inside_the_latched_window(contract):
    days = _days(25)
    early = _evidence(days[:12], rebalance={days[3]})
    assert progress(early, contract, as_of=days[11], next_open=days[12])["terminal_state"] == "NOT_DUE"
    warned = _evidence(days, rebalance={days[3], days[13]}, late={days[7]})
    assert progress(warned, contract, as_of=days[-1], next_open=None)["terminal_state"] == "OBSERVED_WITH_EXECUTION_WARN"
    after_latch = _evidence(days, rebalance={days[3], days[13]}, late={days[22]})
    assert progress(after_latch, contract, as_of=days[-1], next_open=None)["terminal_state"] == "CHECKPOINT_OBSERVED"
    ends_in_gap = _evidence(days[:5], gaps={days[4]})
    assert progress(ends_in_gap, contract, as_of=days[4], next_open=None)["current_segment"] is None


def test_daily_gate_requires_identity_freshness_and_no_bse():
    nav = {"cash": "100.00", "market_value": "900.00", "net_asset": "1000.00", "freshness_status": "PASS",
           "positions": [{"ts_code": "600000.SH", "market_value": "900.00"}]}
    assert daily_gate({"result": {"nav": nav}})
    assert not daily_gate({"result": {"nav": {**nav, "net_asset": "1000.01"}}})
    assert not daily_gate({"result": {"nav": {**nav, "freshness_status": "STALE"}}})
    assert not daily_gate({"result": {"nav": {**nav, "positions": [{"ts_code": "430001.BJ", "market_value": "900.00"}]}}})


def _calendar_ledger(tmp_path, frames: dict[str, pd.DataFrame]):
    rows = []
    for index, (batch, frame) in enumerate(frames.items()):
        path = tmp_path / f"{batch}.parquet"
        frame.to_parquet(path, index=False)
        rows.append({"batch_id": batch, "ingest_time": f"2026-10-0{index + 1}T00:00:00+00:00", "source_api": "tushare.trade_cal",
                     "params_json": json.dumps({"exchange": "SSE", "start_date": batch}), "row_count": len(frame),
                     "parquet_path": str(path), "content_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    ledger = tmp_path / "ingest.csv"
    pd.DataFrame(rows).to_csv(ledger, index=False)
    return ledger


def test_calendar_must_cover_every_day_and_batches_must_agree(tmp_path):
    days = pd.date_range("2026-11-01", "2026-11-10", freq="D").strftime("%Y%m%d")
    frame = pd.DataFrame({"exchange": "SSE", "cal_date": days, "is_open": [str(int(pd.Timestamp(d).weekday() < 5)) for d in days]})
    ledger = _calendar_ledger(tmp_path, {"a": frame})
    assert official_open_days("20261102", "20261106", ingest_path=ledger) == _days(5)
    with pytest.raises(R21R1Error, match="does not cover"):
        official_open_days("20261102", "20261112", ingest_path=ledger)
    conflict = frame.assign(is_open=frame["is_open"].where(frame["cal_date"] != "20261103", "0"))
    second = tmp_path / "conflict"
    second.mkdir()
    with pytest.raises(R21R1Error, match="conflict"):
        official_open_days("20261102", "20261106", ingest_path=_calendar_ledger(second, {"a": frame, "b": conflict}))


def test_shadow_signals_are_verified_against_their_manifest(tmp_path):
    payload = {"signal_date": "2026-11-02", "rebalance_due": True}
    digest = hashlib.sha256(_canonical_json(payload)).hexdigest()
    manifest = tmp_path / "signal.json"
    manifest.write_text(json.dumps({**payload, "signal_sha256": digest}), encoding="utf-8")
    ledger = tmp_path / "shadow_runs.csv"
    row = {"run_id": "r1", "status": "PASS", "signal_sha256": digest, "signal_manifest_path": str(manifest), "rebalance_due": "true", "on_time": "false"}
    pd.DataFrame([row]).to_csv(ledger, index=False)
    assert load_signals({digest}, path=ledger) == {digest: Signal(True, False)}
    manifest.write_text(json.dumps({**payload, "rebalance_due": False, "signal_sha256": digest}), encoding="utf-8")
    with pytest.raises(R21R1Error):
        load_signals({digest}, path=ledger)


def _document(nav: str, benchmark: str, *, fees: str, orders: list | None = None) -> dict:
    return {"result": {"nav": {"normalized_nav": nav, "benchmark_nav": benchmark, "turnover": "0.1", "cash_ratio": "0.05",
                               "cumulative_fees": fees, "positions": [{}] * 3},
                       "orders": orders or [], "fills": []}}


def test_descriptive_report_uses_frozen_formulae_and_is_written_once(tmp_path, contract):
    days = _days(22, "20261030")
    anchor, window = days[0], days[1:21]
    evidence = _evidence(days[1:], rebalance={window[4], window[14]})
    segment = latched_segment(build_segments(evidence, contract))
    assert segment is not None and segment.latch_day == window[-1]
    account_days = {role: {day: _pair(contract, day)[role] for day in days} for role in ("control", "comparison")}
    orders = [{"status": "FILLED"}, {"status": "REJECTED"}]
    documents = {role: {day: _document("1.0" if day == anchor else ("0.9" if day == window[2] else "1.1"), "1.0",
                                       fees="10" if day == anchor else "15", orders=orders if day in segment.rebalances else None)
                        for day in days} for role in ("control", "comparison")}
    report = build_report(contract, segment, account_days, documents)
    control = report["per_account"]["control"]
    assert control["anchored_portfolio_nav"] == "1.10000000" and control["anchored_net_excess"] == "0.10000000"
    assert control["maximum_drawdown"] == "-0.18181818" and control["checkpoint_fees"] == "5.00000000"
    assert control["cumulative_turnover"] == "2.00000000" and control["anchor_stratum"] == "SAME_DAY"
    assert report["segment"]["live_dual_days"] == 20 and report["rebalance_comparison"][0]["control"] == {
        "orders": 2, "filled": 1, "rejected": 1, "fills": 0}
    write_once(tmp_path / "report.json", report)
    with pytest.raises(R21R1Error, match="exactly once"):
        write_once(tmp_path / "report.json", report)


def test_cli_blocks_on_integrity_errors_and_refuses_reports_without_go_ahead(contract):
    def broken(*args, **kwargs):
        raise R21R1Error("trade calendar does not cover 20261231")

    result = cli.run_progress("20261231", contract=contract, history=broken, next_open=lambda _: None)
    assert result["terminal_state"] == "BLOCKED_EVIDENCE" and result["contains_nav_or_return"] is False
    with pytest.raises(R21R1Error, match="go-ahead"):
        cli.run_report("20261231", user_go_ahead=False)
