"""Idempotent close-to-next-open forward-shadow cycle."""

from __future__ import annotations

import argparse
import csv
import fcntl
import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

from shaiwei.config import PROJECT_ROOT, Settings, load
from shaiwei.ingest.catalog import load_latest_api, load_latest_request
from shaiwei.ingest.tushare import Request, public_request_params
from shaiwei.ledger import (
    DAILY_RUNS,
    SHADOW_RECONCILIATIONS,
    SHADOW_RUNS,
    append_shadow_reconciliation,
    append_shadow_run,
    ingest_snapshot_sha256,
    portable_artifact_path,
)
from shaiwei.notify.feishu import FeishuNotifier
from shaiwei.provenance import code_snapshot_sha256
from shaiwei.shadow.reconciliation import next_open_date, reconcile_forward_signal
from shaiwei.shadow.report import write_forward_report

SHANGHAI = ZoneInfo("Asia/Shanghai")


class ShadowCycleError(RuntimeError):
    pass


@dataclass(frozen=True)
class ShadowCycleResult:
    status: str
    signal_trade_date: str
    generated_signal: bool
    reconciled_trade_days: tuple[str, ...]
    report_path: str


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _latest_terminal(
    rows: list[dict[str, str]],
    fields: tuple[str, ...],
) -> dict[tuple[str, ...], dict[str, str]]:
    latest: dict[tuple[str, ...], dict[str, str]] = {}
    for row in sorted(rows, key=lambda value: value["finished_at"]):
        latest[tuple(row[field] for field in fields)] = row
    return latest


def latest_daily_pass(path: Path | None = None) -> dict[str, str] | None:
    path = path or DAILY_RUNS
    passed = [row for row in _read(path) if row["status"] == "PASS"]
    return max(passed, key=lambda row: row["target_trade_date"], default=None)


def _exact_daily(trade_date: str):
    request = Request("daily", {"trade_date": trade_date}, {"trade_date": trade_date})
    return load_latest_request("tushare.daily", public_request_params(request))


@contextmanager
def shadow_lock(path: Path | None = None) -> Iterator[None]:
    lock_path = path or PROJECT_ROOT / "logs" / "shadow" / "cycle.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ShadowCycleError("another shadow cycle is already running") from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _manifest_path(row: dict[str, str]) -> Path:
    path = Path(row["signal_manifest_path"])
    return path if path.is_absolute() else PROJECT_ROOT / path


def _rebalance_context(
    settings: Settings,
    signal_date: str,
) -> tuple[Path | None, bool]:
    passed = sorted(
        (
            row
            for row in _read(SHADOW_RUNS)
            if row["status"] == "PASS" and row["signal_trade_date"] < signal_date
        ),
        key=lambda row: row["signal_trade_date"],
    )
    if not passed:
        return None, True
    previous_path = _manifest_path(passed[-1])
    last_rebalance_date = ""
    for row in reversed(passed):
        document = json.loads(_manifest_path(row).read_text(encoding="utf-8"))
        if bool(document.get("rebalance_due", True)):
            last_rebalance_date = row["signal_trade_date"]
            break
    if not last_rebalance_date:
        raise ShadowCycleError("no rebalance anchor exists in prior shadow signals")
    trade_cal = load_latest_api("tushare.trade_cal")
    elapsed = sum(
        last_rebalance_date < day <= signal_date
        for day in trade_cal.loc[
            trade_cal["is_open"].astype(str).eq("1"), "cal_date"
        ].astype(str).unique()
    )
    return previous_path, elapsed >= settings.backtest.rebalance_days


def _is_on_time(settings: Settings, signal_date: str, generated_at: datetime) -> bool:
    local_date = datetime.strptime(signal_date, "%Y%m%d").date()
    deadline = datetime.combine(
        local_date,
        time(
            settings.shadow_pipeline.signal_deadline_hour,
            settings.shadow_pipeline.signal_deadline_minute,
        ),
        tzinfo=SHANGHAI,
    )
    return generated_at.astimezone(SHANGHAI) <= deadline


def _reconcile_pending(
    settings: Settings,
    *,
    latest_data_date: str,
    notifier: FeishuNotifier,
) -> list[str]:
    passed_by_date: dict[str, dict[str, str]] = {}
    for row in sorted(_read(SHADOW_RUNS), key=lambda value: value["finished_at"]):
        if row["status"] == "PASS":
            passed_by_date[row["signal_trade_date"]] = row
    passed_signals = sorted(passed_by_date.values(), key=lambda row: row["signal_trade_date"])
    reconciliation_latest = _latest_terminal(
        _read(SHADOW_RECONCILIATIONS),
        ("signal_trade_date", "execution_trade_date"),
    )
    trade_cal = load_latest_api("tushare.trade_cal")
    stock_basic = load_latest_api("tushare.stock_basic")
    namechange = load_latest_api("tushare.namechange")
    completed: list[str] = []
    for index, signal in enumerate(passed_signals):
        signal_date = signal["signal_trade_date"]
        execution_date = next_open_date(trade_cal, signal_date.replace("-", ""))
        if execution_date is None or execution_date > latest_data_date:
            continue
        key = (signal_date, execution_date)
        if reconciliation_latest.get(key, {}).get("status") == "PASS":
            continue
        started_at = datetime.now(timezone.utc).isoformat()
        try:
            result = reconcile_forward_signal(
                settings,
                manifest_path=_manifest_path(signal),
                previous_manifest_path=(
                    _manifest_path(passed_signals[index - 1]) if index > 0 else None
                ),
                execution_trade_date=execution_date,
                signal_daily=_exact_daily(signal_date.replace("-", "")),
                execution_daily=_exact_daily(execution_date),
                stock_basic=stock_basic,
                namechange=namechange,
            )
            append_shadow_reconciliation(
                started_at=started_at,
                signal_trade_date=signal_date,
                execution_trade_date=execution_date,
                status="PASS",
                signal_sha256=result.signal_sha256,
                data_snapshot_sha256=ingest_snapshot_sha256(),
                artifact_path=portable_artifact_path(result.artifact_path),
                artifact_sha256=result.artifact_sha256,
                order_count=result.order_count,
                trade_count=result.trade_count,
                executable_count=result.executable_count,
                turnover=result.turnover,
                mean_abs_open_deviation=result.mean_abs_open_deviation,
                estimated_cost=result.estimated_cost,
                error_type="",
            )
            notifier.send(
                "shadow_next_open_reconciled",
                "影子次日开盘对账完成",
                {
                    "signal_date": signal_date,
                    "execution_date": execution_date,
                    "executable": f"{result.executable_count}/{result.trade_count}",
                    "turnover": f"{result.turnover:.6f}",
                },
            )
            completed.append(execution_date)
        except Exception as error:
            append_shadow_reconciliation(
                started_at=started_at,
                signal_trade_date=signal_date,
                execution_trade_date=execution_date,
                status="FAIL",
                signal_sha256=signal["signal_sha256"],
                data_snapshot_sha256=ingest_snapshot_sha256(),
                artifact_path="",
                artifact_sha256="",
                order_count=0,
                trade_count=0,
                executable_count=0,
                turnover=0,
                mean_abs_open_deviation=0,
                estimated_cost=0,
                error_type=type(error).__name__,
            )
            notifier.send(
                "shadow_next_open_failed",
                "影子次日开盘对账失败",
                {
                    "signal_date": signal_date,
                    "execution_date": execution_date,
                    "error_type": type(error).__name__,
                },
            )
            raise
    return completed


def run_once(settings: Settings | None = None) -> ShadowCycleResult:
    settings = settings or load()
    if not settings.shadow_pipeline.enabled:
        return ShadowCycleResult("DISABLED", "", False, (), "")
    notifier = FeishuNotifier(settings.notifications)
    with shadow_lock():
        daily = latest_daily_pass()
        if daily is None:
            report = write_forward_report(settings)
            return ShadowCycleResult("NOOP", "", False, (), str(report))
        signal_date = daily["target_trade_date"]
        reconciled = _reconcile_pending(
            settings,
            latest_data_date=signal_date,
            notifier=notifier,
        )
        any_pass = any(
            row["signal_trade_date"] == signal_date and row["status"] == "PASS"
            for row in _read(SHADOW_RUNS)
        )
        if any_pass:
            report = write_forward_report(settings)
            return ShadowCycleResult(
                "NOOP",
                signal_date,
                False,
                tuple(reconciled),
                str(report),
            )
        current_data_hash = ingest_snapshot_sha256()
        if daily["data_snapshot_sha256"] != current_data_hash:
            raise ShadowCycleError(
                "latest daily PASS is not bound to the current ingest snapshot"
            )
        code_hash = code_snapshot_sha256()
        started_at = datetime.now(timezone.utc).isoformat()
        rebalance_due = False
        notifier.send(
            "shadow_signal_started",
            "前瞻影子信号开始",
            {"signal_date": signal_date},
        )
        try:
            # Keep the 15-minute NOOP path light; qlib/LightGBM are imported
            # only when a new PASS date actually needs a signal.
            from shaiwei.shadow.generation import generate_forward_signal
            from shaiwei.transform.qlib_forward import ensure_forward_snapshot

            previous_manifest, rebalance_due = _rebalance_context(settings, signal_date)
            snapshot = ensure_forward_snapshot(settings)
            generated = generate_forward_signal(
                settings,
                signal_date=datetime.strptime(signal_date, "%Y%m%d").date(),
                snapshot=snapshot,
                data_complete_at=datetime.fromisoformat(daily["finished_at"]),
                previous_manifest_path=previous_manifest,
                rebalance_due=rebalance_due,
            )
            manifest = json.loads(generated.manifest_path.read_text(encoding="utf-8"))
            generated_at = datetime.fromisoformat(str(manifest["generated_at"]))
            on_time = _is_on_time(settings, signal_date, generated_at)
            append_shadow_run(
                started_at=started_at,
                signal_trade_date=signal_date,
                status="PASS",
                daily_run_id=daily["run_id"],
                data_snapshot_sha256=current_data_hash,
                code_snapshot_sha256=code_hash,
                qlib_artifact_sha256=snapshot.artifact_sha256,
                model_spec_sha256=generated.model_spec_sha256,
                model_artifact_sha256=generated.model_artifact_sha256,
                sentinel_report_path=portable_artifact_path(snapshot.sentinel_report_path),
                signal_manifest_path=portable_artifact_path(generated.manifest_path),
                signal_sha256=generated.signal_sha256,
                rebalance_due=generated.rebalance_due,
                on_time=on_time,
                error_type="",
            )
            notifier.send(
                "shadow_signal_completed",
                "前瞻影子信号完成",
                {
                    "signal_date": signal_date,
                    "orders": settings.backtest.topk,
                    "rebalance_due": generated.rebalance_due,
                    "on_time": on_time,
                },
            )
        except Exception as error:
            append_shadow_run(
                started_at=started_at,
                signal_trade_date=signal_date,
                status="FAIL",
                daily_run_id=daily["run_id"],
                data_snapshot_sha256=current_data_hash,
                code_snapshot_sha256=code_hash,
                qlib_artifact_sha256="",
                model_spec_sha256="",
                model_artifact_sha256="",
                sentinel_report_path="",
                signal_manifest_path="",
                signal_sha256="",
                rebalance_due=rebalance_due,
                on_time=False,
                error_type=type(error).__name__,
            )
            notifier.send(
                "shadow_signal_failed",
                "前瞻影子信号失败",
                {"signal_date": signal_date, "error_type": type(error).__name__},
            )
            raise
        report = write_forward_report(settings)
        return ShadowCycleResult(
            "PASS",
            signal_date,
            True,
            tuple(reconciled),
            str(report),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(asdict(run_once()), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
