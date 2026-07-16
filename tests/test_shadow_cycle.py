import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from shaiwei.config import load
from shaiwei.pipeline import shadow_cycle


SHADOW_HEADER = [
    "run_id",
    "started_at",
    "finished_at",
    "signal_trade_date",
    "status",
    "daily_run_id",
    "data_snapshot_sha256",
    "code_snapshot_sha256",
    "qlib_artifact_sha256",
    "model_spec_sha256",
    "model_artifact_sha256",
    "sentinel_report_path",
    "signal_manifest_path",
    "signal_sha256",
    "rebalance_due",
    "on_time",
    "error_type",
    "operator",
]


def _header(path: Path, fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=fields).writeheader()


def test_shadow_cycle_generates_once_for_one_daily_pass(monkeypatch, tmp_path: Path):
    daily = tmp_path / "daily.csv"
    shadow = tmp_path / "shadow.csv"
    reconciliation = tmp_path / "reconciliation.csv"
    _header(
        daily,
        [
            "run_id",
            "finished_at",
            "target_trade_date",
            "status",
            "data_snapshot_sha256",
        ],
    )
    with daily.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(
            handle,
            fieldnames=[
                "run_id",
                "finished_at",
                "target_trade_date",
                "status",
                "data_snapshot_sha256",
            ],
        ).writerow(
            {
                "run_id": "daily1",
                "finished_at": "2026-07-16T12:00:00+00:00",
                "target_trade_date": "20260716",
                "status": "PASS",
                "data_snapshot_sha256": "d" * 64,
            }
        )
    _header(shadow, SHADOW_HEADER)
    _header(
        reconciliation,
        [
            "finished_at",
            "signal_trade_date",
            "execution_trade_date",
            "status",
        ],
    )
    monkeypatch.setattr(shadow_cycle, "DAILY_RUNS", daily)
    monkeypatch.setattr(shadow_cycle, "SHADOW_RUNS", shadow)
    monkeypatch.setattr(shadow_cycle, "SHADOW_RECONCILIATIONS", reconciliation)
    monkeypatch.setattr(shadow_cycle, "ingest_snapshot_sha256", lambda: "d" * 64)
    monkeypatch.setattr(shadow_cycle, "code_snapshot_sha256", lambda: "c" * 64)
    monkeypatch.setattr(shadow_cycle, "_reconcile_pending", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(shadow_cycle, "write_forward_report", lambda _settings: tmp_path / "report.json")
    monkeypatch.setattr(
        shadow_cycle,
        "FeishuNotifier",
        lambda _config: SimpleNamespace(send=lambda *_args, **_kwargs: None),
    )
    sentinel = tmp_path / "sentinel.json"
    sentinel.write_text("{}")
    manifest = tmp_path / "signal.json"
    manifest.write_text(json.dumps({"generated_at": "2026-07-16T12:30:00+00:00"}))
    snapshot = SimpleNamespace(
        artifact_sha256="q" * 64,
        sentinel_report_path=sentinel,
    )
    generated = SimpleNamespace(
        manifest_path=manifest,
        model_spec_sha256="s" * 64,
        model_artifact_sha256="m" * 64,
        signal_sha256="h" * 64,
        rebalance_due=True,
    )
    monkeypatch.setattr(
        "shaiwei.transform.qlib_forward.ensure_forward_snapshot",
        lambda _settings: snapshot,
    )
    calls = []
    monkeypatch.setattr(
        "shaiwei.shadow.generation.generate_forward_signal",
        lambda *_args, **_kwargs: calls.append("generated") or generated,
    )

    def append_run(**row):
        row = {
            "run_id": "shadow1",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "operator": "test",
            **row,
        }
        row["on_time"] = str(row["on_time"]).lower()
        with shadow.open("a", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=SHADOW_HEADER).writerow(row)

    monkeypatch.setattr(shadow_cycle, "append_shadow_run", append_run)
    monkeypatch.setattr(
        shadow_cycle,
        "_rebalance_context",
        lambda _settings, _signal_date: (None, True),
    )
    settings = load()
    first = shadow_cycle.run_once(settings)
    second = shadow_cycle.run_once(settings)
    assert first.status == "PASS"
    assert second.status == "NOOP"
    assert calls == ["generated"]


def test_shadow_cycle_cli_reports_lock_contention_as_busy(monkeypatch, capsys):
    def busy():
        raise shadow_cycle.ShadowCycleBusy("already running")

    monkeypatch.setattr(shadow_cycle, "run_once", busy)

    assert shadow_cycle.main([]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "generated_signal": False,
        "reconciled_trade_days": [],
        "report_path": "",
        "signal_trade_date": "",
        "status": "BUSY",
    }


def test_shadow_cycle_run_once_still_exposes_busy_to_python_callers(monkeypatch):
    @shadow_cycle.contextmanager
    def busy_lock():
        raise shadow_cycle.ShadowCycleBusy("already running")
        yield

    monkeypatch.setattr(shadow_cycle, "shadow_lock", busy_lock)
    with pytest.raises(shadow_cycle.ShadowCycleBusy):
        shadow_cycle.run_once(load())


def test_rebalance_context_changes_targets_only_every_ten_open_days(monkeypatch, tmp_path: Path):
    shadow = tmp_path / "shadow.csv"
    _header(shadow, SHADOW_HEADER)
    manifest = tmp_path / "previous.json"
    manifest.write_text(json.dumps({"rebalance_due": True}), encoding="utf-8")
    with shadow.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=SHADOW_HEADER).writerow(
            {
                **{field: "" for field in SHADOW_HEADER},
                "run_id": "one",
                "finished_at": "2026-07-01T12:00:00+00:00",
                "signal_trade_date": "20260701",
                "status": "PASS",
                "signal_manifest_path": str(manifest),
                "rebalance_due": "true",
                "on_time": "true",
            }
        )
    monkeypatch.setattr(shadow_cycle, "SHADOW_RUNS", shadow)
    days = [f"202607{day:02d}" for day in range(1, 16)]
    monkeypatch.setattr(
        shadow_cycle,
        "load_latest_api",
        lambda _api: pd.DataFrame({"cal_date": days, "is_open": [1] * len(days)}),
    )
    settings = load()
    _, before = shadow_cycle._rebalance_context(settings, "20260710")
    _, due = shadow_cycle._rebalance_context(settings, "20260711")
    assert before is False
    assert due is True
