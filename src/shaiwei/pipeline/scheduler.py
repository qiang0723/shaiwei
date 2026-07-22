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

from shaiwei.config import PROJECT_ROOT, Settings, load
from shaiwei.ledger import PAPER_RUNS
from shaiwei.notify.feishu import FeishuNotifier
from shaiwei.pipeline.daily import AlreadyRunning, run_once

HEALTH_PATH = PROJECT_ROOT / "logs" / "scheduler" / "health.json"


def run_shadow_cycle(settings: Settings) -> None:
    if not settings.shadow_pipeline.enabled:
        return
    subprocess.run(
        [sys.executable, "-m", "shaiwei.pipeline.shadow_cycle"],
        check=True,
    )


def run_paper_cycle(settings: Settings) -> None:
    if not settings.paper_portfolio.enabled:
        return
    subprocess.run(
        [sys.executable, "-m", "shaiwei.pipeline.paper_cycle"],
        check=True,
    )
    if paper_replay_ready():
        subprocess.run(
            [sys.executable, "-m", "shaiwei.paper.query", "verify"],
            check=True,
        )


def paper_replay_ready(path: Path = PAPER_RUNS) -> bool:
    if not path.is_file():
        return False
    with path.open(newline="", encoding="utf-8") as handle:
        return any(row["status"] == "PASS" for row in csv.DictReader(handle))


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


def run_scheduler(*, once: bool = False, settings: Settings | None = None) -> int:
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
        try:
            result = run_once(settings=settings)
            write_health("shadow", detail=result.eligible_target)
            run_shadow_cycle(settings)
            write_health("paper", detail=result.eligible_target)
            run_paper_cycle(settings)
            write_health(result.status.lower(), detail=result.eligible_target)
        except AlreadyRunning:
            write_health("waiting", detail="daily lock is held")
        except Exception as error:
            exit_code = 1
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
    return run_scheduler(once=args.once, settings=settings)


if __name__ == "__main__":
    raise SystemExit(main())
