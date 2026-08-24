"""Long-running Docker supervisor for ledger-driven daily reconciliation."""

from __future__ import annotations

import argparse
import csv
import json
import os
import signal
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from shaiwei.config import (
    PROJECT_ROOT,
    Settings,
    load,
    load_paper_top20_protocol,
    load_paper_top20_release,
)
from shaiwei.ledger import PAPER_RUNS
from shaiwei.notify.feishu import FeishuNotifier
from shaiwei.pipeline.daily import AlreadyRunning, run_once
from shaiwei.pipeline.scheduler_timeline import (
    CycleTimeline,
    SchedulerTimeline,
    load_timeline_contract,
    observe_phase,
)

HEALTH_PATH = PROJECT_ROOT / "logs" / "scheduler" / "health.json"
TOP20_RELEASE_PATH = PROJECT_ROOT / "config" / "paper_top20_release_v1.yaml"


def run_shadow_cycle(settings: Settings) -> None:
    if not settings.shadow_pipeline.enabled:
        return
    subprocess.run(
        [sys.executable, "-m", "shaiwei.pipeline.shadow_cycle"],
        check=True,
    )


def run_paper_cycle(settings: Settings, *, observer: CycleTimeline | None = None) -> None:
    if not settings.paper_portfolio.enabled:
        return
    accounts = [settings.paper_portfolio.account_id]
    top20 = load_paper_top20_protocol().paper_portfolio
    if top20.enabled and TOP20_RELEASE_PATH.is_file():
        release = load_paper_top20_release(TOP20_RELEASE_PATH)
        if release.account_id != top20.account_id:
            raise RuntimeError("Top20 scheduler release account differs from protocol")
        accounts.append(top20.account_id)
    for account_id in accounts:
        with observe_phase(observer, "PAPER_EXECUTE", account_id=account_id) as execution:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "shaiwei.pipeline.paper_cycle",
                    "--account-id",
                    account_id,
                ],
                check=True,
            )
            execution.outcome = "PASS"
        if paper_replay_ready(account_id):
            with observe_phase(observer, "PAPER_VERIFY", account_id=account_id) as verify:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "shaiwei.paper.query",
                        "verify",
                        "--account-id",
                        account_id,
                    ],
                    check=True,
                )
                verify.outcome = "PASS"
            with observe_phase(
                observer, "PAPER_ACCEPTANCE", account_id=account_id
            ) as acceptance:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "shaiwei.paper.query",
                        "acceptance",
                        "--account-id",
                        account_id,
                    ],
                    check=True,
                )
                acceptance.outcome = "PASS"


def paper_replay_ready(account_id: str = "model_baseline", path: Path = PAPER_RUNS) -> bool:
    if not path.is_file():
        return False
    with path.open(newline="", encoding="utf-8") as handle:
        return any(
            row["status"] == "PASS" and row["account_id"] == account_id
            for row in csv.DictReader(handle)
        )


def write_health(status: str, *, detail: str = "", path: Path = HEALTH_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "detail": detail,
        "pid": os.getpid(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def healthcheck(settings: Settings, *, path: Path = HEALTH_PATH) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        updated = datetime.fromisoformat(payload["updated_at"])
        age = (datetime.now(timezone.utc) - updated.astimezone(timezone.utc)).total_seconds()
        return age <= settings.daily.health_stale_seconds and payload.get("status") != "degraded"
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def run_scheduler(
    *,
    once: bool = False,
    settings: Settings | None = None,
    timeline: SchedulerTimeline | None = None,
) -> int:
    settings = settings or load()
    notifier = FeishuNotifier(settings.notifications)
    stopped = threading.Event()

    def stop(_signum: int, _frame: object) -> None:
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    write_health("starting")
    exit_code = 0
    while not stopped.is_set():
        write_health("running")
        cycle = None
        target_trade_date = ""

        def warn(phase: str, account_id: str, elapsed: float, budget: float):
            return notifier.send(
                "scheduler_phase_duration_warning",
                "调度阶段耗时超过诊断预算",
                {
                    "phase": phase,
                    "account_id": account_id,
                    "elapsed_seconds": round(elapsed, 3),
                    "budget_seconds": budget,
                },
            )

        try:
            cycle = timeline.start_cycle(warning_sink=warn) if timeline else None
            with observe_phase(cycle, "DAILY") as daily:
                result = run_once(settings=settings, phase_observer=cycle)
                target_trade_date = result.eligible_target
                daily.target_trade_date = target_trade_date
                daily.outcome = result.status
            if result.status == "WAITING_SOURCE":
                write_health("waiting_source", detail=result.eligible_target)
            else:
                write_health("shadow", detail=result.eligible_target)
                with observe_phase(
                    cycle, "SHADOW", target_trade_date=target_trade_date
                ) as shadow:
                    run_shadow_cycle(settings)
                    shadow.outcome = "PASS" if settings.shadow_pipeline.enabled else "NOOP"
                write_health("paper", detail=result.eligible_target)
                with observe_phase(
                    cycle, "PAPER", target_trade_date=target_trade_date
                ) as paper:
                    run_paper_cycle(settings, observer=cycle)
                    paper.outcome = "PASS" if settings.paper_portfolio.enabled else "NOOP"
                write_health(result.status.lower(), detail=result.eligible_target)
            if cycle is not None:
                cycle.finish(result.status, target_trade_date=target_trade_date)
        except AlreadyRunning as error:
            if cycle is not None and not cycle.closed:
                cycle.finish("WAITING_LOCK", error_type=error)
            write_health("waiting", detail="daily lock is held")
        except Exception as error:
            exit_code = 1
            if cycle is not None and not cycle.closed:
                try:
                    cycle.finish(
                        "FAILED",
                        target_trade_date=target_trade_date,
                        error_type=error,
                    )
                except Exception as timeline_error:
                    error = timeline_error
            write_health("degraded", detail=type(error).__name__)
            notifier.send(
                "daily_scheduler_cycle_failed",
                "日增量与影子守护周期失败",
                {"error_type": type(error).__name__},
            )
        if once:
            break
        stopped.wait(settings.daily.poll_seconds)
    write_health("stopped" if stopped.is_set() else "degraded" if exit_code else "idle")
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="run one scheduler cycle")
    parser.add_argument("--healthcheck", action="store_true", help="check scheduler heartbeat freshness")
    args = parser.parse_args(argv)
    settings = load()
    if args.healthcheck:
        return 0 if healthcheck(settings) else 1
    timeline = SchedulerTimeline(load_timeline_contract())
    return run_scheduler(once=args.once, settings=settings, timeline=timeline)


if __name__ == "__main__":
    raise SystemExit(main())
