import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from shaiwei.ops_patrol_config import load_config
from shaiwei.ops_patrol_service import ServiceState, drill, healthcheck, serve, signature, tick

T0 = datetime(2026, 10, 13, 10, 45, tzinfo=timezone.utc)  # 北京时间 18:45
HEALTH_OK = {"code": "HEALTH_OK", "severity": "INFO", "detail": {"status": "noop", "detail": "20261013", "age_seconds": 60}}
ALLOWED_FIELDS = {"状态", "预期交易日", "心跳", "问题", "休眠", "已抑制", "新增", "已恢复", "说明"}


@dataclass(frozen=True)
class Result:
    status: str


class Sender:
    def __init__(self, status="PASS"):
        self.status = status
        self.sent = []

    def send(self, event, title, fields=None):
        self.sent.append((event, title, fields))
        return Result(self.status)


def _finding(code, severity="FAIL", **detail):
    return {"code": code, "severity": severity, "detail": detail}


def _report(*attention, expected="20261013"):
    worst = max((a["severity"] for a in attention), key=["WARN", "FAIL"].index, default="PASS")
    return {
        "status": worst,
        "expected_trade_date": expected,
        "attention": list(attention),
        "findings": [HEALTH_OK, *attention],
    }


def _tick(tmp_path, report, *, at=T0, sender=None, config=None, dry_run=False):
    sender = sender or Sender()
    result = tick(
        now_utc=at,
        config=config or load_config(),
        state_dir=tmp_path,
        patrol=lambda _now: report,
        sender=sender,
        dry_run=dry_run,
    )
    return sender, result


def _events(sender):
    return [event for event, _title, _fields in sender.sent]


def test_first_tick_sends_one_daily_conclusion_and_then_stays_quiet(tmp_path: Path):
    sender, _ = _tick(tmp_path, _report())
    assert _events(sender) == ["ops_patrol_daily"]
    _event, title, fields = sender.sent[0]
    assert title == "巡检日结论 20261013：PASS"
    assert fields["问题"] == "无" and fields["休眠"] == "无"
    assert set(fields) <= ALLOWED_FIELDS
    for minutes in (10, 20, 30):
        sender, _ = _tick(tmp_path, _report(), at=T0 + timedelta(minutes=minutes))
        assert sender.sent == []
    assert (tmp_path / "latest.json").is_file()


def test_new_problem_alerts_once_volatile_detail_is_ignored_and_recovery_is_reported(tmp_path: Path):
    _tick(tmp_path, _report())
    stale = _finding("HEALTH_STALE", status="noop", detail="", age_seconds=4000)
    sender, _ = _tick(tmp_path, _report(stale), at=T0 + timedelta(minutes=10))
    assert _events(sender) == ["ops_patrol_alert"]
    assert sender.sent[0][1] == "巡检告警：FAIL"
    worse = _finding("HEALTH_STALE", status="noop", detail="", age_seconds=4600)
    sender, _ = _tick(tmp_path, _report(worse), at=T0 + timedelta(minutes=20))
    assert sender.sent == []
    sender, _ = _tick(tmp_path, _report(), at=T0 + timedelta(minutes=30))
    assert _events(sender) == ["ops_patrol_recovered"]
    assert sender.sent[0][2]["已恢复"] == "HEALTH_STALE"


def test_repeated_fail_counts_do_not_change_signature():
    first = _report(_finding("SHADOW_SIGNAL_REPEATED_FAIL", signal_trade_date="20261012", fail_count=3))
    later = _report(_finding("SHADOW_SIGNAL_REPEATED_FAIL", signal_trade_date="20261012", fail_count=40))
    assert signature(first) == signature(later) == ["SHADOW_SIGNAL_REPEATED_FAIL|signal_trade_date=20261012"]


def test_daily_conclusion_is_once_per_expected_trade_date_and_absorbs_current_problem(tmp_path: Path):
    _tick(tmp_path, _report(expected="20261012"))
    missing = _finding("DAILY_MISSING", trade_date="20261013")
    sender, _ = _tick(tmp_path, _report(missing), at=T0 + timedelta(minutes=10))
    assert _events(sender) == ["ops_patrol_daily"]
    assert sender.sent[0][2]["问题"] == "DAILY_MISSING|trade_date=20261013"
    sender, _ = _tick(tmp_path, _report(missing), at=T0 + timedelta(minutes=20))
    assert sender.sent == []  # 日结论已带出该问题，不再单发告警
    weekend = T0 + timedelta(days=4)
    sender, _ = _tick(tmp_path, _report(), at=weekend)
    sender, _ = _tick(tmp_path, _report(), at=weekend + timedelta(minutes=10))
    assert sender.sent == []


def test_resume_after_sleep_holds_alerts_during_grace_and_reports_the_gap(tmp_path: Path):
    _tick(tmp_path, _report(expected="20261012"))
    wake = T0 + timedelta(hours=5)
    stale = _finding("HEALTH_STALE", status="noop", detail="", age_seconds=18000)
    sender, result = _tick(tmp_path, _report(stale), at=wake)
    assert sender.sent == [] and result["grace_active"] is True
    assert result["events"][0]["kind"] == "HOST_RESUMED" and result["events"][0]["minutes"] == 300
    sender, _ = _tick(tmp_path, _report(), at=wake + timedelta(minutes=10))
    assert sender.sent == []
    sender, _ = _tick(tmp_path, _report(expected="20261013"), at=wake + timedelta(minutes=21))
    assert _events(sender) == ["ops_patrol_daily"]
    assert sender.sent[0][2]["休眠"].startswith("1 段，最长 300 分钟")
    assert ServiceState.load(tmp_path / "state.json").gaps == []


def test_daily_cap_suppresses_and_reports_the_count_in_next_conclusion(tmp_path: Path):
    config = load_config()
    config = config.model_copy(update={"service": config.service.model_copy(update={"daily_message_cap": 2})})
    codes = ["DAILY_MISSING", "PAPER_MISSING", "WEB_UNHEALTHY"]
    _tick(tmp_path, _report(expected="20261012"), config=config)
    sent = []
    for index, code in enumerate(codes, start=1):
        sender, result = _tick(tmp_path, _report(_finding(code), expected="20261012"), at=T0 + timedelta(minutes=10 * index), config=config)
        sent += _events(sender)
    assert sent == ["ops_patrol_alert"] and result["delivery_status"] == "SUPPRESSED"
    next_day = T0 + timedelta(days=1)
    sender, result = _tick(tmp_path, _report(_finding("WEB_UNHEALTHY")), at=next_day, config=config)
    assert sender.sent == [] and result["grace_active"] is True  # 跨夜间隔本身即被判为主机唤醒
    sender, _ = _tick(tmp_path, _report(_finding("WEB_UNHEALTHY")), at=next_day + timedelta(minutes=21), config=config)
    assert _events(sender) == ["ops_patrol_daily"]
    assert sender.sent[0][2]["已抑制"] == "2 条"
    assert ServiceState.load(tmp_path / "state.json").suppressed == 0


def test_delivery_failure_keeps_signature_so_next_tick_retries(tmp_path: Path):
    _tick(tmp_path, _report())
    problem = _report(_finding("WEB_UNREACHABLE", path="/healthz", error_type="OSError"))
    sender, _ = _tick(tmp_path, problem, at=T0 + timedelta(minutes=10), sender=Sender("FAIL"))
    assert _events(sender) == ["ops_patrol_alert"]
    sender, _ = _tick(tmp_path, problem, at=T0 + timedelta(minutes=20))
    assert _events(sender) == ["ops_patrol_alert"]
    sender, _ = _tick(tmp_path, problem, at=T0 + timedelta(minutes=30))
    assert sender.sent == []


def test_dry_run_neither_sends_nor_writes(tmp_path: Path):
    sender, result = _tick(tmp_path, _report(_finding("DAILY_MISSING")), dry_run=True)
    assert sender.sent == [] and result["delivery_status"] == "DRY_RUN"
    assert result["planned_message"]["event"] == "ops_patrol_daily"
    assert list(tmp_path.iterdir()) == []


def test_events_log_and_healthcheck_follow_latest(tmp_path: Path):
    _tick(tmp_path, _report())
    rows = [json.loads(line) for line in (tmp_path / "events_20261013.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["event"] for row in rows] == ["ops_patrol_daily"]
    assert healthcheck(tmp_path / "latest.json", T0 + timedelta(minutes=29))
    assert not healthcheck(tmp_path / "latest.json", T0 + timedelta(minutes=31))
    assert not healthcheck(tmp_path / "missing.json", T0)


def test_serve_runs_when_due_and_survives_a_failing_tick():
    stop = threading.Event()
    times = iter(T0 + timedelta(minutes=m) for m in (0, 1, 9, 10, 11, 20))
    runs = []

    def clock():
        try:
            return next(times)
        except StopIteration:
            stop.set()
            return T0 + timedelta(minutes=21)

    def run(now):
        runs.append(now)
        if len(runs) == 1:
            raise RuntimeError("boom")

    serve(interval=timedelta(minutes=10), wake_seconds=0, stop=stop, run_tick=run, clock=clock)
    assert runs == [T0, T0 + timedelta(minutes=10), T0 + timedelta(minutes=20)]


def test_drill_sends_exactly_one_marked_message():
    sender = Sender()
    assert drill(sender) == "PASS"
    assert _events(sender) == ["ops_patrol_drill"]
    assert "演练" in sender.sent[0][1]
