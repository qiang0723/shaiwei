"""巡检 harness（ADR 0020）：巡检容器内常驻循环，container 模式巡检 + 去重飞书告警。

只读生产状态；只写 logs/ops-patrol/（latest.json、state.json、events_YYYYMMDD.jsonl），投递记录由
FeishuNotifier 写 logs/notifications/。不重启容器、不写账本、不触发任何生产动作。
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

from shaiwei.config import PROJECT_ROOT
from shaiwei.ops_patrol_config import CONFIG_PATH, PatrolConfig, load_config

PATROL_DIR = PROJECT_ROOT / "logs" / "ops-patrol"
# 签名只取稳定字段：心跳时长、失败次数、磁盘余量每轮都变，不能让它们触发重复告警。
_STABLE_KEYS = ("trade_date", "signal_trade_date", "execution_trade_date", "account_id", "name", "path")
_DELIVERED = {"PASS", "DISABLED"}
Report = dict[str, object]


class Delivery(Protocol):
    status: str


class Sender(Protocol):
    def send(self, event: str, title: str, fields: dict[str, object] | None = None) -> Delivery: ...


@dataclass
class ServiceState:
    last_tick_at: str = ""
    signature: list[str] = field(default_factory=list)
    digest_trade_date: str = ""
    cap_day: str = ""
    sent_today: int = 0
    suppressed: int = 0
    grace_until: str = ""
    gaps: list[dict[str, object]] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "ServiceState":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return cls(**{key: raw[key] for key in cls.__dataclass_fields__ if key in raw})
        except (OSError, TypeError, ValueError):
            return cls()


@dataclass(frozen=True)
class Outgoing:
    event: str
    title: str
    fields: dict[str, object]
    digest: bool


def signature(report: Report) -> list[str]:
    items = {
        "|".join([f["code"], *(f"{key}={f['detail'][key]}" for key in _STABLE_KEYS if key in f["detail"])])
        for f in report["attention"]  # type: ignore[union-attr]
    }
    return sorted(items)


def _heartbeat(report: Report) -> str:
    for finding in report["findings"]:  # type: ignore[union-attr]
        if finding["code"].startswith("HEALTH_"):
            detail = finding["detail"]
            if "age_seconds" not in detail:
                return finding["code"]
            return f"{finding['code']} {detail['status']} {detail['detail']} · {detail['age_seconds']} 秒前".strip()
    return "无"


def _gaps_text(gaps: list[dict[str, object]]) -> str:
    if not gaps:
        return "无"
    listed = "；".join(f"{g['from_local']}→{g['to_local']}（{g['minutes']} 分钟）" for g in gaps[-3:])
    return f"{len(gaps)} 段，最长 {max(int(g['minutes']) for g in gaps)} 分钟：{listed}"


def plan(report: Report, state: ServiceState) -> Outgoing | None:
    """一轮最多一条：未发过的预期交易日先发日结论（并入当前问题），否则只在签名变化时告警或报恢复。"""
    current = signature(report)
    expected = str(report.get("expected_trade_date") or "")
    status = str(report["status"])
    base: dict[str, object] = {"状态": status, "预期交易日": expected or "未知", "心跳": _heartbeat(report)}
    if expected and expected != state.digest_trade_date:
        fields = {**base, "问题": "；".join(current) or "无", "休眠": _gaps_text(state.gaps)}
        if state.suppressed:
            fields["已抑制"] = f"{state.suppressed} 条"
        return Outgoing("ops_patrol_daily", f"巡检日结论 {expected}：{status}", fields, True)
    if current == state.signature:
        return None
    if not current:
        return Outgoing("ops_patrol_recovered", "巡检恢复：全部正常", {**base, "已恢复": "；".join(state.signature)}, False)
    added = sorted(set(current) - set(state.signature))
    resolved = sorted(set(state.signature) - set(current))
    title = f"巡检告警：{status}" if added else f"巡检部分恢复：仍有 {len(current)} 项"
    fields = {**base, "新增": "；".join(added) or "无", "已恢复": "；".join(resolved) or "无", "问题": "；".join(current)}
    return Outgoing("ops_patrol_alert", title, fields, False)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _note_resume(state: ServiceState, now_utc: datetime, config: PatrolConfig) -> dict[str, object] | None:
    service, tz = config.service, ZoneInfo(config.timezone)
    if not state.last_tick_at:
        return None
    last = datetime.fromisoformat(state.last_tick_at)
    gap = now_utc - last
    if gap <= timedelta(minutes=service.interval_minutes * service.resume_gap_intervals):
        return None
    item: dict[str, object] = {
        "from_local": last.astimezone(tz).strftime("%m-%d %H:%M"),
        "to_local": now_utc.astimezone(tz).strftime("%m-%d %H:%M"),
        "minutes": int(gap.total_seconds() // 60),
    }
    state.gaps.append(item)
    state.grace_until = (now_utc + timedelta(minutes=service.resume_grace_minutes)).isoformat()
    return item


def tick(
    *,
    now_utc: datetime,
    config: PatrolConfig,
    state_dir: Path,
    patrol: Callable[[datetime], Report],
    sender: Sender,
    dry_run: bool = False,
) -> dict[str, object]:
    tz = ZoneInfo(config.timezone)
    today = now_utc.astimezone(tz).strftime("%Y%m%d")
    state = ServiceState.load(state_dir / "state.json")
    if state.cap_day != today:
        state.cap_day, state.sent_today = today, 0
    events: list[dict[str, object]] = []
    if resumed := _note_resume(state, now_utc, config):
        events.append({"kind": "HOST_RESUMED", **resumed})  # 主机刚唤醒：心跳可能陈旧最多一个 scheduler 轮询
    state.last_tick_at = now_utc.isoformat()
    report = patrol(now_utc)
    grace = bool(state.grace_until) and now_utc < datetime.fromisoformat(state.grace_until)
    outgoing = None if grace else plan(report, state)
    delivery = ""
    if outgoing and dry_run:
        delivery = "DRY_RUN"
    elif outgoing and state.sent_today >= config.service.daily_message_cap:
        delivery, state.suppressed = "SUPPRESSED", state.suppressed + 1
    elif outgoing:
        delivery = sender.send(outgoing.event, outgoing.title, outgoing.fields).status
        state.sent_today += 1
    if outgoing and delivery != "FAIL":  # 投递失败不更新签名，下一轮重试（仍受每日上限约束）
        state.signature = signature(report)
        if outgoing.digest:
            state.digest_trade_date = str(report["expected_trade_date"])
            if delivery in _DELIVERED:
                state.gaps, state.suppressed = [], 0
    if outgoing:  # 签名只含稳定键；完整明细（HTTP 状态码、耗时等）随事件落盘，供事后定因
        events.append({"kind": "MESSAGE", "event": outgoing.event, "delivery_status": delivery, "signature": signature(report),
                       "attention": report["attention"]})
    service = {
        "grace_active": grace,
        "healthy_until": (now_utc + timedelta(minutes=config.service.latest_stale_minutes)).isoformat(),
        "planned_message": asdict(outgoing) if outgoing else None,
        "delivery_status": delivery,
    }
    if not dry_run:
        _write_json(state_dir / "latest.json", {**report, "service": service})
        _write_json(state_dir / "state.json", asdict(state))
        with (state_dir / f"events_{today}.jsonl").open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps({"at": now_utc.isoformat(), **event}, ensure_ascii=False, sort_keys=True) + "\n")
    return {"status": report["status"], "expected_trade_date": report.get("expected_trade_date"), "events": events, **service}


def serve(
    *,
    interval: timedelta,
    wake_seconds: int,
    stop: threading.Event,
    run_tick: Callable[[datetime], object],
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> None:
    """按墙钟到期才巡检：容器随主机休眠暂停，唤醒后最多 wake_seconds 内补巡。"""
    due: datetime | None = None
    while not stop.is_set():
        now = clock()
        if due is None or now >= due or due - now > interval:  # 末项防墙钟回拨把下一轮推得过远
            try:
                run_tick(now)
            except Exception as error:  # 单轮异常不得退出循环；持续失败表现为 latest.json 陈旧 → unhealthy
                print(json.dumps({"at": now.isoformat(), "tick_error": type(error).__name__}), file=sys.stderr, flush=True)
            due = now + interval
        stop.wait(wake_seconds)


def healthcheck(path: Path, now_utc: datetime) -> bool:
    try:
        return now_utc < datetime.fromisoformat(json.loads(path.read_text(encoding="utf-8"))["service"]["healthy_until"])
    except (OSError, KeyError, TypeError, ValueError):
        return False


def drill(sender: Sender) -> str:
    fields = {"说明": "ADR 0020 部署验收演练，仅此一条；不改巡检状态，不代表任何故障"}
    return sender.send("ops_patrol_drill", "巡检演练（非故障）", fields).status


def _container_patrol(config: PatrolConfig, stale_seconds: int) -> Callable[[datetime], Report]:
    from shaiwei.ingest.catalog import load_latest_api
    from shaiwei.ops_patrol import PatrolPaths, http_status, run_patrol

    paths = PatrolPaths(project_root=PATROL_DIR)  # 磁盘检查须落在绑定挂载上才反映宿主磁盘

    def patrol(now_utc: datetime) -> Report:
        return run_patrol(
            config=config,
            paths=paths,
            now_utc=now_utc,
            docker=None,
            git=None,
            calendar_loader=lambda: load_latest_api("tushare.trade_cal"),
            stale_seconds=stale_seconds,
            web_probe=lambda url: http_status(url, config.web_probe.timeout_seconds),
            mode="container",
        )

    return patrol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--once", action="store_true", help="只巡检一轮（写状态、按规则发送）")
    action.add_argument("--dry-run", action="store_true", help="只巡检一轮并打印计划消息；不发送、不写文件")
    action.add_argument("--drill", action="store_true", help="只发一条演练消息；不巡检、不改状态")
    action.add_argument("--healthcheck", action="store_true", help="latest.json 是否在新鲜期内")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args(argv)
    if args.healthcheck:
        return 0 if healthcheck(PATROL_DIR / "latest.json", datetime.now(timezone.utc)) else 1

    from shaiwei.config import load
    from shaiwei.notify.feishu import FeishuNotifier

    settings = load()
    config = load_config(args.config)
    sender = FeishuNotifier(settings.notifications)
    if args.drill:
        status = drill(sender)
        print(json.dumps({"event": "ops_patrol_drill", "delivery_status": status}))
        return 0 if status == "PASS" else 1
    patrol = _container_patrol(config, settings.daily.health_stale_seconds)

    def run(now_utc: datetime) -> dict[str, object]:
        return tick(now_utc=now_utc, config=config, state_dir=PATROL_DIR, patrol=patrol, sender=sender, dry_run=args.dry_run)

    if args.once or args.dry_run:
        print(json.dumps(run(datetime.now(timezone.utc)), ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda _signum, _frame: stop.set())
    interval = timedelta(minutes=config.service.interval_minutes)
    serve(interval=interval, wake_seconds=config.service.wake_check_seconds, stop=stop, run_tick=run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
