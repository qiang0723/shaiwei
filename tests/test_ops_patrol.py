import csv
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from shaiwei import ops_patrol
from shaiwei.ops_patrol import PatrolPaths, load_config, run_patrol

OPEN_DAYS = ["20261008", "20261009", "20261012", "20261013", "20261014", "20261015"]
SCHEDULER_IMAGE = "sha256:" + "7" * 64
CANDIDATE_IMAGE = "sha256:" + "b" * 64


def _calendar() -> pd.DataFrame:
    days = OPEN_DAYS + ["20261010", "20261011"]
    return pd.DataFrame({"cal_date": days, "is_open": ["1"] * len(OPEN_DAYS) + ["0", "0"]})


def _write(path: Path, header: list[str], rows: list[dict[str, str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _ledgers(tmp_path: Path, *, trade_dates=("20261012", "20261013"), shadow_extra=()) -> PatrolPaths:
    daily = [
        {"target_trade_date": d, "status": "PASS", "started_at": f"2026-{d[4:6]}-{d[6:]}T11:40:00+00:00"}
        for d in trade_dates
    ]
    shadow = [
        {"signal_trade_date": d, "status": "PASS", "on_time": "true", "rebalance_due": "false"}
        for d in trade_dates
    ] + list(shadow_extra)
    recon = [{"execution_trade_date": d, "status": "PASS"} for d in trade_dates]
    paper = [
        {"account_id": a, "execution_trade_date": d, "status": "PASS"}
        for d in trade_dates
        for a in ("model_baseline", "model_top20")
    ]
    health = tmp_path / "health.json"
    return PatrolPaths(
        daily_runs=_write(tmp_path / "daily.csv", list(daily[0]), daily),
        shadow_runs=_write(tmp_path / "shadow.csv", list(shadow[0]), shadow),
        shadow_reconciliations=_write(tmp_path / "recon.csv", list(recon[0]), recon),
        paper_runs=_write(tmp_path / "paper.csv", list(paper[0]), paper),
        health=health,
        project_root=tmp_path,
    )


def _docker(*, tag_image=SCHEDULER_IMAGE, restart="0", missing=()):
    def query(args):
        if args[:2] == ["image", "inspect"]:
            return tag_image
        name = args[-1]
        if name in missing:
            raise subprocess.CalledProcessError(1, args)
        return f"running|healthy|{restart}|{SCHEDULER_IMAGE}"

    return query


def _git(args):
    if args[0] == "diff":
        return "40\t0\tledger/daily_runs.csv\n12\t0\tledger/shadow_runs.csv"
    return "0 0"


def _run(paths, *, now_local="2026-10-13T23:45", docker=None, calendar=_calendar, config=None, health_age=60):
    now_utc = datetime.fromisoformat(now_local + ":00+08:00").astimezone(timezone.utc)
    # 心跳时间跟随测试时钟；巡检会把“来自未来”的心跳判为 STALE，所以不能用真实 now 写夹具。
    paths.health.write_text(
        json.dumps({"status": "noop", "updated_at": (now_utc - timedelta(seconds=health_age)).isoformat()})
    )
    return run_patrol(
        config=config or load_config(),
        paths=paths,
        now_utc=now_utc,
        docker=docker or _docker(),
        git=_git,
        calendar_loader=calendar,
        stale_seconds=3600,
    )


def test_real_config_loads_and_rejects_unknown_fields(tmp_path: Path):
    config = load_config()
    assert config.status == "ACTIVE_READ_ONLY"
    assert config.chain_deadline_local.hour == 23
    bad = tmp_path / "bad.yaml"
    bad.write_text(Path(ops_patrol.CONFIG_PATH).read_text(encoding="utf-8") + "\nextra_field: 1\n")
    with pytest.raises(Exception):
        load_config(bad)


def test_all_green_after_deadline_targets_today(tmp_path: Path):
    report = _run(_ledgers(tmp_path))
    assert report["expected_trade_date"] == "20261013"
    assert report["status"] == "PASS"
    assert report["exit_code"] == 0
    assert report["attention"] == []
    codes = {f["code"] for f in report["findings"]}
    assert {"HEALTH_OK", "CONTAINER_OK", "SCHEDULER_TAG_ALIGNED", "DAILY_OK", "SHADOW_SIGNAL_OK", "PAPER_OK"} <= codes
    assert "net_asset" not in json.dumps(report)


def test_before_deadline_checks_previous_open_day(tmp_path: Path):
    report = _run(_ledgers(tmp_path), now_local="2026-10-13T22:00")
    assert report["expected_trade_date"] == "20261012"
    assert report["status"] == "PASS"


def test_missing_shadow_signal_is_fail(tmp_path: Path):
    paths = _ledgers(tmp_path)
    shadow = [r for r in csv.DictReader(paths.shadow_runs.open(encoding="utf-8")) if r["signal_trade_date"] != "20261013"]
    _write(paths.shadow_runs, list(shadow[0]), shadow)
    report = _run(paths)
    assert report["status"] == "FAIL"
    assert report["exit_code"] == 2
    assert "SHADOW_SIGNAL_MISSING" in {f["code"] for f in report["attention"]}


def test_repeated_shadow_failures_in_window_are_fail_but_old_ones_are_not(tmp_path: Path):
    fails = [{"signal_trade_date": "20261012", "status": "FAIL", "on_time": "false", "rebalance_due": "false"}] * 3
    paths = _ledgers(tmp_path, trade_dates=("20261013",), shadow_extra=fails)
    report = _run(paths)
    hit = [f for f in report["attention"] if f["code"] == "SHADOW_SIGNAL_REPEATED_FAIL"]
    assert hit and hit[0]["detail"] == {"signal_trade_date": "20261012", "fail_count": 3}
    old = [{"signal_trade_date": "20260929", "status": "FAIL", "on_time": "false", "rebalance_due": "false"}] * 89
    paths = _ledgers(tmp_path, shadow_extra=old)
    report = _run(paths)
    assert "SHADOW_SIGNAL_REPEATED_FAIL" not in {f["code"] for f in report["findings"]}


def test_tag_drift_and_restart_are_warn(tmp_path: Path):
    report = _run(_ledgers(tmp_path), docker=_docker(tag_image=CANDIDATE_IMAGE, restart="2"))
    codes = {f["code"] for f in report["attention"]}
    assert {"SCHEDULER_TAG_DRIFT", "CONTAINER_RESTARTED"} <= codes
    assert report["status"] == "WARN"
    assert report["exit_code"] == 1


def test_stale_health_and_missing_container_are_fail(tmp_path: Path):
    paths = _ledgers(tmp_path)
    report = _run(paths, docker=_docker(missing=("shaiwei-web-web-ui-1",)), health_age=7200)
    codes = {f["code"] for f in report["attention"]}
    assert {"HEALTH_STALE", "CONTAINER_MISSING"} <= codes
    assert report["status"] == "FAIL"


def test_next_day_catchup_is_warn(tmp_path: Path):
    paths = _ledgers(tmp_path)
    rows = list(csv.DictReader(paths.daily_runs.open(encoding="utf-8")))
    rows[-1]["started_at"] = "2026-10-13T17:42:00+00:00"  # 10-14 01:42 北京时间
    _write(paths.daily_runs, list(rows[0]), rows)
    report = _run(paths)
    assert "DAILY_NEXT_DAY_CATCHUP" in {f["code"] for f in report["attention"]}
    assert report["status"] == "WARN"


def test_unreadable_calendar_is_fail_without_crash(tmp_path: Path):
    def broken():
        raise RuntimeError("hash mismatch")

    report = _run(_ledgers(tmp_path), calendar=broken)
    assert "CALENDAR_UNREADABLE" in {f["code"] for f in report["attention"]}
    assert report["expected_trade_date"] is None
    assert report["status"] == "FAIL"
