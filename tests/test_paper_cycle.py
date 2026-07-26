import csv
import json
from contextlib import nullcontext
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from shaiwei import ledger
from shaiwei.config import PROJECT_ROOT, load
from shaiwei.paper import query as paper_query
from shaiwei.paper.query import (
    PaperQueryError,
    paper_nav_series,
    paper_orders_fills,
    paper_portfolio_snapshot,
    verify_paper_replay,
)
from shaiwei.pipeline import paper_cycle
from shaiwei.shadow.manifest import write_signal_manifest


def _header(source: str, target: Path) -> None:
    first = (PROJECT_ROOT / source).read_text(encoding="utf-8").splitlines()[0]
    target.write_text(first + "\n", encoding="utf-8")


def _sentinels():
    return [
        {"sentinel": f"S{number}", "status": "NOT_APPLICABLE" if number == 10 else "PASS"}
        for number in range(1, 11)
    ]


def test_paper_cycle_backfills_once_and_exposes_verified_read_only_queries(monkeypatch, tmp_path: Path):
    accounts = tmp_path / "paper_accounts.csv"
    events = tmp_path / "paper_events.csv"
    runs = tmp_path / "paper_runs.csv"
    shadow_runs = tmp_path / "shadow_runs.csv"
    reconciliations = tmp_path / "shadow_reconciliations.csv"
    for source, target in (
        ("ledger/paper_accounts.csv", accounts),
        ("ledger/paper_events.csv", events),
        ("ledger/paper_runs.csv", runs),
        ("ledger/shadow_runs.csv", shadow_runs),
        ("ledger/shadow_reconciliations.csv", reconciliations),
    ):
        _header(source, target)
    generated = datetime(2026, 7, 16, 12, tzinfo=timezone.utc)
    manifest, signal_hash = write_signal_manifest(
        pd.DataFrame({"instrument": ["SH600001"], "score": [1.0]}),
        signal_date=date(2026, 7, 16),
        topk=1,
        sentinel_results=_sentinels(),
        data_complete_at=generated,
        generated_at=generated,
        data_snapshot_sha256="d" * 64,
        code_commit="abc",
        code_snapshot_sha256="c" * 64,
        output_dir=tmp_path / "signals",
    )
    reconciliation = tmp_path / "reconciliation.json"
    reconciliation.write_text(json.dumps({"signal_sha256": signal_hash}), encoding="utf-8")
    reconciliation_hash = ledger.sha256_file(reconciliation)
    with shadow_runs.open("a", newline="", encoding="utf-8") as handle:
        fields = (PROJECT_ROOT / "ledger/shadow_runs.csv").read_text().splitlines()[0].split(",")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writerow(
            {
                "run_id": "shadow1",
                "started_at": generated.isoformat(),
                "finished_at": generated.isoformat(),
                "signal_trade_date": "20260716",
                "status": "PASS",
                "daily_run_id": "daily1",
                "data_snapshot_sha256": "d" * 64,
                "code_snapshot_sha256": "c" * 64,
                "qlib_artifact_sha256": "q" * 64,
                "model_spec_sha256": "m" * 64,
                "model_artifact_sha256": "a" * 64,
                "sentinel_report_path": "sentinel.json",
                "signal_manifest_path": str(manifest),
                "signal_sha256": signal_hash,
                "rebalance_due": "true",
                "on_time": "true",
                "error_type": "",
                "operator": "test",
            }
        )
    with reconciliations.open("a", newline="", encoding="utf-8") as handle:
        fields = (
            (PROJECT_ROOT / "ledger/shadow_reconciliations.csv")
            .read_text()
            .splitlines()[0]
            .split(",")
        )
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writerow(
            {
                "reconciliation_id": "rec1",
                "started_at": generated.isoformat(),
                "finished_at": generated.isoformat(),
                "signal_trade_date": "20260716",
                "execution_trade_date": "20260717",
                "status": "PASS",
                "signal_sha256": signal_hash,
                "data_snapshot_sha256": "d" * 64,
                "artifact_path": str(reconciliation),
                "artifact_sha256": reconciliation_hash,
                "order_count": 1,
                "trade_count": 1,
                "executable_count": 1,
                "turnover": 1,
                "mean_abs_open_deviation": 0,
                "estimated_cost": 0,
                "error_type": "",
                "operator": "test",
            }
        )
    settings = load().model_copy(deep=True)
    settings.runtime.data_root = tmp_path / "data"
    settings.notifications.feishu_enabled = False
    settings.paper_portfolio.initial_cash = 10_000
    daily = pd.DataFrame(
        [
            {
                "ts_code": "600001.SH",
                "trade_date": "20260717",
                "open": 10.0,
                "pre_close": 10.0,
                "close": 10.2,
                "vol": 1000,
            }
        ]
    )
    signal_daily = daily.assign(trade_date="20260716", close=10.0)
    stock = pd.DataFrame(
        [{"ts_code": "600001.SH", "list_date": "20100101", "delist_date": None}]
    )
    names = pd.DataFrame(
        [
            {
                "ts_code": "600001.SH",
                "name": "普通样本",
                "start_date": "20100101",
                "end_date": None,
            }
        ]
    )
    calendar = pd.DataFrame(
        {
            "cal_date": [
                "20100104",
                "20100105",
                "20100106",
                "20100107",
                "20100108",
                "20260716",
                "20260717",
            ],
            "is_open": [1] * 7,
        }
    )
    empty_suspend = pd.DataFrame(
        columns=["ts_code", "trade_date", "suspend_timing", "suspend_type"]
    )
    index = pd.DataFrame(
        [
            {
                "ts_code": "000906.SH",
                "trade_date": "20260717",
                "open": 100.0,
                "close": 101.0,
            }
        ]
    )

    def fake_api(api: str):
        return {
            "tushare.stock_basic": stock,
            "tushare.namechange": names,
            "tushare.dividend": pd.DataFrame(),
            "tushare.trade_cal": calendar,
        }[api]

    def fake_request(api: str, params: dict[str, object]):
        frame = {
            ("daily", "20260716"): signal_daily,
            ("daily", "20260717"): daily,
            ("suspend_d", "20260717"): empty_suspend,
            ("index_daily", "20260717"): index,
        }[(api, str(params["trade_date"]))]
        return frame, {
            "batch_id": f"{api}-{params['trade_date']}",
            "source_api": f"tushare.{api}",
            "params_json": "{}",
            "row_count": len(frame),
            "content_sha256": api[0] * 64,
            "path": f"raw/{api}",
        }

    monkeypatch.setattr(paper_cycle, "PAPER_ACCOUNTS", accounts)
    monkeypatch.setattr(paper_cycle, "PAPER_RUNS", runs)
    monkeypatch.setattr(paper_cycle, "SHADOW_RUNS", shadow_runs)
    monkeypatch.setattr(paper_cycle, "SHADOW_RECONCILIATIONS", reconciliations)
    monkeypatch.setattr(paper_cycle, "paper_lock", lambda: nullcontext())
    monkeypatch.setattr(paper_cycle, "load_latest_api", fake_api)
    monkeypatch.setattr(paper_cycle, "_request", fake_request)
    monkeypatch.setattr(paper_cycle, "code_snapshot_sha256", lambda: "x" * 64)
    monkeypatch.setattr(paper_cycle, "ingest_snapshot_sha256", lambda: "y" * 64)
    monkeypatch.setattr(
        paper_cycle,
        "append_paper_account",
        lambda **kwargs: ledger.append_paper_account(path=accounts, **kwargs),
    )
    monkeypatch.setattr(
        paper_cycle,
        "append_paper_event",
        lambda **kwargs: ledger.append_paper_event(path=events, **kwargs),
    )
    monkeypatch.setattr(
        paper_cycle,
        "append_paper_run",
        lambda **kwargs: ledger.append_paper_run(path=runs, **kwargs),
    )

    real_journal = paper_cycle._journal
    journal_attempts = 0

    def interrupt_after_first_event(document, artifact, reconciliation_hash, **kwargs):
        nonlocal journal_attempts
        journal_attempts += 1
        if journal_attempts == 1:
            paper_cycle.append_paper_event(**paper_cycle._event_rows(document)[0])
            raise OSError("simulated interruption after first paper event")
        return real_journal(document, artifact, reconciliation_hash, **kwargs)

    monkeypatch.setattr(paper_cycle, "_journal", interrupt_after_first_event)
    with pytest.raises(OSError, match="simulated interruption"):
        paper_cycle.run_once(settings)
    failed_rows = list(csv.DictReader(runs.open(newline="", encoding="utf-8")))
    assert [row["status"] for row in failed_rows] == ["FAIL"]
    assert len(list(csv.DictReader(events.open(newline="", encoding="utf-8")))) == 1
    with pytest.raises(PaperQueryError, match="no completed runs"):
        verify_paper_replay(
            accounts_path=accounts,
            events_path=events,
            runs_path=runs,
        )

    first = paper_cycle.run_once(settings)
    before = (accounts.read_bytes(), events.read_bytes(), runs.read_bytes())
    second = paper_cycle.run_once(settings)
    after = (accounts.read_bytes(), events.read_bytes(), runs.read_bytes())
    assert first.status == "PASS"
    assert first.completed_trade_dates == ("20260717",)
    assert second.status == "NOOP"
    assert before == after
    artifact_document = json.loads(Path(first.latest_artifact_path).read_text(encoding="utf-8"))
    assert artifact_document["execution_policy_version"] == settings.paper_portfolio.execution_policy_version

    snapshot = paper_portfolio_snapshot(runs_path=runs)
    orders = paper_orders_fills(signal_hash, runs_path=runs)
    nav = paper_nav_series(runs_path=runs)
    replay = verify_paper_replay(
        accounts_path=accounts,
        events_path=events,
        runs_path=runs,
    )
    assert snapshot["mode"] == "BACKFILL"
    assert snapshot["net_asset"] == "10174.91"
    assert len(orders["orders"]) == 1
    assert len(orders["fills"]) == 1
    assert nav["forward_status"] == "NOT_READY"
    assert nav["forward_observation_count"] == 0
    assert replay["status"] == "PASS"
    assert replay["run_count"] == 1
    assert replay["event_count"] == 5

    tampered = tmp_path / "tampered_events.csv"
    tampered_rows = list(csv.DictReader(events.open(newline="", encoding="utf-8")))
    tampered_rows[0]["evidence_sha256"] = "0" * 64
    with tampered.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(tampered_rows[0]))
        writer.writeheader()
        writer.writerows(tampered_rows)
    with pytest.raises(PaperQueryError, match="evidence hash mismatch"):
        verify_paper_replay(
            accounts_path=accounts,
            events_path=tampered,
            runs_path=runs,
        )


def test_temporal_contract_rejects_future_and_non_next_session():
    signal = {"signal_date": "2026-07-16"}
    calendar = pd.DataFrame(
        {"cal_date": ["20260716", "20260717", "20260720"], "is_open": [1, 1, 1]}
    )
    paper_cycle._validate_temporal_contract(
        signal=signal,
        signal_date="20260716",
        execution_date="20260717",
        trade_cal=calendar,
        today="20260722",
    )
    with pytest.raises(paper_cycle.PaperCycleError, match="next open"):
        paper_cycle._validate_temporal_contract(
            signal=signal,
            signal_date="20260716",
            execution_date="20260720",
            trade_cal=calendar,
            today="20260722",
        )
    with pytest.raises(paper_cycle.PaperCycleError, match="future"):
        paper_cycle._validate_temporal_contract(
            signal=signal,
            signal_date="20260716",
            execution_date="20260717",
            trade_cal=calendar,
            today="20260716",
        )


def test_forward_acceptance_requires_bound_identity_and_notification(monkeypatch, tmp_path: Path):
    artifact = tmp_path / "forward.json"
    artifact.write_text("{}\n", encoding="utf-8")
    run = {
        "run_id": "forward1",
        "finished_at": "2026-07-23T12:00:00+00:00",
        "account_id": "model_baseline",
        "execution_trade_date": "20260723",
        "operator": "docker-scheduler",
        "freshness_status": "PASS",
        "artifact_sha256": "a" * 64,
    }
    document = {
        "mode": "FORWARD",
        "execution_policy_version": "paper-v1",
        "code_snapshot_sha256": "c" * 64,
        "policy_sha256": "p" * 64,
    }
    monkeypatch.setattr(paper_query, "_passed_runs", lambda account_id, path: [run])
    monkeypatch.setattr(paper_query, "_document", lambda row: (artifact, document))
    monkeypatch.setattr(
        paper_query,
        "verify_paper_replay",
        lambda *args, **kwargs: {
            "status": "PASS",
            "ledger_hashes": {"accounts": "1", "events": "2", "runs": "3"},
        },
    )
    event_rows = [{"account_id": "model_baseline", "ts_code": "600001.SH"}]
    monkeypatch.setattr(paper_query, "_csv_rows", lambda path: event_rows)
    notifications = tmp_path / "notifications"
    notifications.mkdir()
    records = [
        {
            "event": event,
            "status": "PASS",
            "delivered_at": "2026-07-23T12:00:01+00:00",
            "message_id": event,
            "attempt": 1,
            "max_attempts": 3,
            "recovered": False,
        }
        for event in ("paper_cycle_started", "paper_cycle_completed")
    ]
    (notifications / "feishu_20260723.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    result = paper_query.paper_forward_acceptance(
        notifications_dir=notifications,
        expected_code_sha256="c" * 64,
        expected_policy_sha256="p" * 64,
    )
    assert result["status"] == "PASS"
    assert result["forward_observation_count"] == 1
    assert set(result["notification_delivery"]) == {
        "paper_cycle_started",
        "paper_cycle_completed",
    }
    event_rows[0]["ts_code"] = "920001.BJ"
    with pytest.raises(PaperQueryError, match="forbidden BSE"):
        paper_query.paper_forward_acceptance(
            notifications_dir=notifications,
            expected_code_sha256="c" * 64,
            expected_policy_sha256="p" * 64,
        )
def test_paper_event_append_is_idempotent_and_rejects_key_collision(tmp_path: Path):
    path = tmp_path / "events.csv"
    _header("ledger/paper_events.csv", path)
    row = {
        "event_id": "event1",
        "run_id": "run1",
        "recorded_at": "2026-07-22T00:00:00+00:00",
        "account_id": "model_baseline",
        "effective_date": "20260722",
        "sequence": 1,
        "event_type": "CASH",
        "business_key": "20260722",
        "signal_sha256": "s" * 64,
        "ts_code": "",
        "side": "",
        "quantity": "",
        "price": "",
        "amount": "",
        "fee": "",
        "cash_after": "500000.00",
        "position_after": "",
        "payload_json": {"cash": "500000.00"},
        "evidence_sha256": "e" * 64,
        "operator": "test",
    }
    assert ledger.append_paper_event(path=path, **row)
    assert not ledger.append_paper_event(path=path, **row)
    changed = {**row, "cash_after": "1.00"}
    try:
        ledger.append_paper_event(path=path, **changed)
    except ValueError as error:
        assert "key collision" in str(error)
    else:
        raise AssertionError("event key collision must fail closed")
