"""只读运维巡检：核对守护健康、容器状态、日链完成度、重复失败与账本积压；不写任何文件。"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Callable, Iterable, Literal
from zoneinfo import ZoneInfo

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, Field

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.ingest.catalog import load_latest_api
from shaiwei.ledger import DAILY_RUNS, PAPER_RUNS, SHADOW_RECONCILIATIONS, SHADOW_RUNS
from shaiwei.pipeline.scheduler import HEALTH_PATH

CONFIG_PATH = PROJECT_ROOT / "config" / "ops_patrol_v1.yaml"
Severity = Literal["INFO", "WARN", "FAIL"]
_RANK = {"INFO": 0, "WARN": 1, "FAIL": 2}
_STATUS = {"INFO": "PASS", "WARN": "WARN", "FAIL": "FAIL"}
_CONTAINER_FORMAT = (
    "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}"
    "|{{.RestartCount}}|{{.Image}}"
)
Query = Callable[[list[str]], str]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Containers(FrozenModel):
    scheduler: str
    web: tuple[str, ...]


class PatrolConfig(FrozenModel):
    schema_version: Literal["shaiwei-ops-patrol-v1"]
    patrol_id: Literal["ops-patrol-v1"]
    status: Literal["ACTIVE_READ_ONLY"]
    timezone: Literal["Asia/Shanghai"]
    chain_deadline_local: time
    lookback_open_days: int = Field(ge=1, le=30)
    repeated_shadow_fail_threshold: int = Field(ge=2, le=50)
    ledger_backlog_warn_lines: int = Field(ge=100)
    disk_free_warn_gb: int = Field(ge=1)
    containers: Containers
    scheduler_current_tag: str
    accounts: tuple[str, ...] = Field(min_length=1)


def load_config(path: Path = CONFIG_PATH) -> PatrolConfig:
    return PatrolConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    detail: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class PatrolPaths:
    daily_runs: Path = DAILY_RUNS
    shadow_runs: Path = SHADOW_RUNS
    shadow_reconciliations: Path = SHADOW_RECONCILIATIONS
    paper_runs: Path = PAPER_RUNS
    health: Path = HEALTH_PATH
    project_root: Path = PROJECT_ROOT


@dataclass(frozen=True)
class LedgerRows:
    daily: list[dict[str, str]]
    shadow: list[dict[str, str]]
    reconciliations: list[dict[str, str]]
    paper: list[dict[str, str]]

    @classmethod
    def read(cls, paths: PatrolPaths) -> "LedgerRows":
        return cls(
            _read_csv(paths.daily_runs),
            _read_csv(paths.shadow_runs),
            _read_csv(paths.shadow_reconciliations),
            _read_csv(paths.paper_runs),
        )


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def docker_query(args: list[str]) -> str:
    result = subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()


def git_query(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, timeout=30, cwd=PROJECT_ROOT
    )
    return result.stdout.strip()


def open_days(calendar: pd.DataFrame) -> list[str]:
    mask = calendar["is_open"].astype(str).isin({"1", "1.0"})
    return sorted({str(value)[:8] for value in calendar.loc[mask, "cal_date"]})


def expected_trade_date(now_local: datetime, days: list[str], deadline: time) -> str | None:
    """日链已到期的最近开放日：开放日且已过截止时刻取当日，否则取上一开放日。"""
    today = now_local.strftime("%Y%m%d")
    if today in days and now_local.time().replace(tzinfo=None) >= deadline:
        return today
    past = [day for day in days if day < today]
    return past[-1] if past else None


def check_health(path: Path, now_utc: datetime, stale_seconds: int) -> list[Finding]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        updated = datetime.fromisoformat(str(payload["updated_at"])).astimezone(timezone.utc)
    except (OSError, KeyError, TypeError, ValueError):
        return [Finding("HEALTH_FILE_UNREADABLE", "FAIL", {"path": str(path)})]
    age = int((now_utc - updated).total_seconds())
    status = str(payload.get("status", ""))
    detail = {"status": status, "detail": str(payload.get("detail", "")), "age_seconds": age}
    if age < 0 or age > stale_seconds:
        return [Finding("HEALTH_STALE", "FAIL", detail)]
    if status == "degraded":
        return [Finding("HEALTH_DEGRADED", "FAIL", detail)]
    return [Finding("HEALTH_OK", "INFO", detail)]


def inspect_container(docker: Query, name: str) -> dict[str, str] | None:
    try:
        raw = docker(["inspect", "--format", _CONTAINER_FORMAT, name])
    except (subprocess.SubprocessError, OSError):
        return None
    parts = raw.split("|")
    if len(parts) != 4:
        return None
    return {"status": parts[0], "health": parts[1], "restart_count": parts[2], "image_id": parts[3]}


def check_containers(
    docker: Query, names: Iterable[str]
) -> tuple[list[Finding], dict[str, dict[str, str]]]:
    findings: list[Finding] = []
    seen: dict[str, dict[str, str]] = {}
    for name in names:
        info = inspect_container(docker, name)
        if info is None:
            findings.append(Finding("CONTAINER_MISSING", "FAIL", {"name": name}))
            continue
        seen[name] = info
        detail = {"name": name, **info, "image_id": info["image_id"][:19]}
        if info["status"] != "running" or info["health"] not in {"healthy", "none"}:
            findings.append(Finding("CONTAINER_UNHEALTHY", "FAIL", detail))
        elif info["restart_count"] != "0":
            findings.append(Finding("CONTAINER_RESTARTED", "WARN", detail))
        else:
            findings.append(Finding("CONTAINER_OK", "INFO", detail))
    return findings, seen


def check_tag_drift(docker: Query, tag: str, scheduler: dict[str, str] | None) -> list[Finding]:
    try:
        tag_image = docker(["image", "inspect", "--format", "{{.Id}}", tag])
    except (subprocess.SubprocessError, OSError):
        return [Finding("SCHEDULER_TAG_UNRESOLVED", "WARN", {"tag": tag})]
    running = scheduler["image_id"] if scheduler else ""
    detail = {"tag": tag, "tag_image_id": tag_image[:19], "running_image_id": running[:19]}
    if running and tag_image != running:
        return [Finding("SCHEDULER_TAG_DRIFT", "WARN", detail)]
    return [Finding("SCHEDULER_TAG_ALIGNED", "INFO", detail)]


def _local_day(timestamp: str, tz: ZoneInfo) -> str:
    return datetime.fromisoformat(timestamp).astimezone(tz).strftime("%Y%m%d %H:%M")


def check_chain(
    rows: LedgerRows, expected: str, accounts: Iterable[str], tz: ZoneInfo
) -> list[Finding]:
    """只核对日期/状态/身份字段，不把模拟仓数值带进诊断输出。"""
    findings: list[Finding] = []
    daily = [r for r in rows.daily if r["target_trade_date"] == expected and r["status"] == "PASS"]
    if not daily:
        findings.append(Finding("DAILY_MISSING", "FAIL", {"trade_date": expected}))
    else:
        started = _local_day(daily[-1]["started_at"], tz)
        detail = {"trade_date": expected, "started_local": started}
        late = started[:8] != expected
        findings.append(Finding("DAILY_NEXT_DAY_CATCHUP" if late else "DAILY_OK", "WARN" if late else "INFO", detail))
    shadow = [r for r in rows.shadow if r["signal_trade_date"] == expected and r["status"] == "PASS"]
    if not shadow:
        findings.append(Finding("SHADOW_SIGNAL_MISSING", "FAIL", {"signal_trade_date": expected}))
    else:
        detail = {"signal_trade_date": expected, "rebalance_due": shadow[-1].get("rebalance_due", "")}
        late = shadow[-1].get("on_time", "") == "false"
        findings.append(Finding("SHADOW_SIGNAL_LATE" if late else "SHADOW_SIGNAL_OK", "WARN" if late else "INFO", detail))
    recon = any(
        r["execution_trade_date"] == expected and r["status"] == "PASS" for r in rows.reconciliations
    )
    findings.append(
        Finding("RECONCILIATION_OK" if recon else "RECONCILIATION_MISSING", "INFO" if recon else "WARN", {"execution_trade_date": expected})
    )
    for account in accounts:
        done = any(
            r["account_id"] == account and r["execution_trade_date"] == expected and r["status"] == "PASS"
            for r in rows.paper
        )
        detail = {"account_id": account, "execution_trade_date": expected}
        findings.append(Finding("PAPER_OK" if done else "PAPER_MISSING", "INFO" if done else "WARN", detail))
    return findings


def check_failures(
    rows: LedgerRows, days: list[str], expected: str, threshold: int, lookback: int
) -> list[Finding]:
    window = set([day for day in days if day <= expected][-lookback:])
    findings: list[Finding] = []
    passed = {r["signal_trade_date"] for r in rows.shadow if r["status"] == "PASS"}
    fails = Counter(
        r["signal_trade_date"] for r in rows.shadow if r["status"] != "PASS" and r["signal_trade_date"] in window
    )
    for day, count in sorted(fails.items()):
        if count >= threshold and day not in passed:
            findings.append(Finding("SHADOW_SIGNAL_REPEATED_FAIL", "FAIL", {"signal_trade_date": day, "fail_count": count}))
    daily_fail = sum(1 for r in rows.daily if r["status"] != "PASS" and r["target_trade_date"] in window)
    paper_fail = sum(1 for r in rows.paper if r["status"] != "PASS" and r["execution_trade_date"] in window)
    if daily_fail:
        findings.append(Finding("DAILY_RECENT_FAIL", "WARN", {"fail_rows": daily_fail, "window_open_days": lookback}))
    if paper_fail:
        findings.append(Finding("PAPER_RECENT_FAIL", "WARN", {"fail_rows": paper_fail, "window_open_days": lookback}))
    return findings


def check_ledger_backlog(git: Query, threshold: int) -> list[Finding]:
    try:
        numstat = git(["diff", "--numstat", "--", "ledger"])
    except (subprocess.SubprocessError, OSError):
        return [Finding("GIT_UNAVAILABLE", "WARN", {})]
    added = sum(
        int(line.split("\t")[0]) for line in numstat.splitlines() if line.split("\t")[0].isdigit()
    )
    severity: Severity = "WARN" if added > threshold else "INFO"
    return [Finding("LEDGER_UNCOMMITTED_LINES", severity, {"added_lines": added, "warn_threshold": threshold})]


def check_git_sync(git: Query) -> list[Finding]:
    try:
        behind, ahead = (int(v) for v in git(["rev-list", "--left-right", "--count", "origin/main...HEAD"]).split())
    except (subprocess.SubprocessError, OSError, ValueError):
        return [Finding("GIT_SYNC_UNKNOWN", "WARN", {})]
    severity: Severity = "WARN" if (ahead or behind) else "INFO"
    return [Finding("GIT_SYNC", severity, {"ahead_of_origin": ahead, "behind_origin": behind})]


def check_disk(root: Path, warn_gb: int) -> list[Finding]:
    free_gb = round(shutil.disk_usage(root).free / 1e9, 1)
    severity: Severity = "WARN" if free_gb < warn_gb else "INFO"
    return [Finding("DISK_FREE", severity, {"free_gb": free_gb, "warn_gb": warn_gb})]


def run_patrol(
    *,
    config: PatrolConfig,
    paths: PatrolPaths,
    now_utc: datetime,
    docker: Query,
    git: Query,
    calendar_loader: Callable[[], pd.DataFrame],
    stale_seconds: int,
) -> dict[str, object]:
    tz = ZoneInfo(config.timezone)
    now_local = now_utc.astimezone(tz)
    findings = check_health(paths.health, now_utc, stale_seconds)
    container_findings, seen = check_containers(
        docker, [config.containers.scheduler, *config.containers.web]
    )
    findings += container_findings
    findings += check_tag_drift(docker, config.scheduler_current_tag, seen.get(config.containers.scheduler))
    expected: str | None = None
    try:
        days = open_days(calendar_loader())
    except Exception as error:  # 日历不可读本身就是发现，不能让巡检静默退出
        findings.append(Finding("CALENDAR_UNREADABLE", "FAIL", {"error_type": type(error).__name__}))
        days = []
    if days:
        expected = expected_trade_date(now_local, days, config.chain_deadline_local)
    if expected:
        rows = LedgerRows.read(paths)
        findings += check_chain(rows, expected, config.accounts, tz)
        findings += check_failures(
            rows, days, expected, config.repeated_shadow_fail_threshold, config.lookback_open_days
        )
    findings += check_ledger_backlog(git, config.ledger_backlog_warn_lines)
    findings += check_git_sync(git)
    findings += check_disk(paths.project_root, config.disk_free_warn_gb)
    worst = max((f.severity for f in findings), key=_RANK.__getitem__, default="INFO")
    return {
        "schema_version": config.schema_version,
        "patrol_id": config.patrol_id,
        "generated_at": now_utc.isoformat(),
        "now_local": now_local.isoformat(timespec="minutes"),
        "expected_trade_date": expected,
        "status": _STATUS[worst],
        "exit_code": _RANK[worst],
        "counts": dict(Counter(f.severity for f in findings)),
        "attention": [asdict(f) for f in findings if f.severity != "INFO"],
        "findings": [asdict(f) for f in findings],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args(argv)
    settings = load()
    report = run_patrol(
        config=load_config(args.config),
        paths=PatrolPaths(),
        now_utc=datetime.now(timezone.utc),
        docker=docker_query,
        git=git_query,
        calendar_loader=lambda: load_latest_api("tushare.trade_cal"),
        stale_seconds=settings.daily.health_stale_seconds,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
