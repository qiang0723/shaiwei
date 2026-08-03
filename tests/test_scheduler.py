import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from shaiwei.config import load
from shaiwei.pipeline.daily import DailyResult
from shaiwei.pipeline.scheduler import (
    healthcheck,
    run_paper_cycle,
    run_scheduler,
    run_shadow_cycle,
    write_health,
)


class RecordingNotifier:
    def __init__(self, _settings, calls):
        self.calls = calls

    def send(self, *args, **kwargs):
        self.calls.append((args, kwargs))


def test_scheduler_health_is_fresh_and_rejects_degraded(tmp_path: Path):
    path = tmp_path / "health.json"
    settings = load()
    write_health("noop", path=path)
    assert healthcheck(settings, path=path)

    payload = json.loads(path.read_text())
    payload["status"] = "degraded"
    path.write_text(json.dumps(payload))
    assert not healthcheck(settings, path=path)


def test_scheduler_health_rejects_stale_file(tmp_path: Path):
    path = tmp_path / "health.json"
    settings = load()
    path.write_text(
        json.dumps(
            {
                "status": "noop",
                "updated_at": (
                    datetime.now(timezone.utc)
                    - timedelta(seconds=settings.daily.health_stale_seconds + 1)
                ).isoformat(),
            }
        )
    )
    assert not healthcheck(settings, path=path)


def test_scheduler_runs_shadow_as_isolated_subprocess(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "shaiwei.pipeline.scheduler.subprocess.run",
        lambda argv, check: calls.append((argv, check)),
    )
    run_shadow_cycle(load())
    assert calls[0][0][-2:] == ["-m", "shaiwei.pipeline.shadow_cycle"]
    assert calls[0][1] is True


def test_scheduler_runs_paper_as_isolated_subprocess(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "shaiwei.pipeline.scheduler.subprocess.run",
        lambda argv, check: calls.append((argv, check)),
    )
    monkeypatch.setattr(
        "shaiwei.pipeline.scheduler.TOP20_RELEASE_PATH",
        Path("config/paper_top20_v1.yaml"),
    )
    monkeypatch.setattr(
        "shaiwei.pipeline.scheduler.load_paper_top20_release",
        lambda _path: type("Release", (), {"account_id": "model_top20"})(),
    )
    monkeypatch.setattr("shaiwei.pipeline.scheduler.paper_replay_ready", lambda account_id: True)
    run_paper_cycle(load())
    assert len(calls) == 6
    for offset, account_id in ((0, "model_baseline"), (3, "model_top20")):
        assert calls[offset][0][-2:] == ["--account-id", account_id]
        assert calls[offset][0][1:3] == ["-m", "shaiwei.pipeline.paper_cycle"]
        assert calls[offset][1] is True
        assert calls[offset + 1][0][-3:] == ["verify", "--account-id", account_id]
        assert calls[offset + 1][1] is True
        assert calls[offset + 2][0][-3:] == ["acceptance", "--account-id", account_id]
        assert calls[offset + 2][1] is True


def test_scheduler_does_not_run_top20_before_distinct_release(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "shaiwei.pipeline.scheduler.subprocess.run",
        lambda argv, check: calls.append((argv, check)),
    )
    monkeypatch.setattr("shaiwei.pipeline.scheduler.paper_replay_ready", lambda account_id: False)
    monkeypatch.setattr(
        "shaiwei.pipeline.scheduler.TOP20_RELEASE_PATH",
        Path("config/paper_top20_release_v1.yaml.missing"),
    )
    run_paper_cycle(load())
    assert len(calls) == 1
    assert calls[0][0][-2:] == ["--account-id", "model_baseline"]


def test_scheduler_waiting_source_skips_downstream_and_notifications(monkeypatch):
    downstream = []
    notifications = []
    health = []
    result = DailyResult("WAITING_SOURCE", "20260731", "20260804", (), 0, 0)
    monkeypatch.setattr("shaiwei.pipeline.scheduler.run_once", lambda **_kwargs: result)
    monkeypatch.setattr(
        "shaiwei.pipeline.scheduler.run_shadow_cycle",
        lambda _settings: downstream.append("shadow"),
    )
    monkeypatch.setattr(
        "shaiwei.pipeline.scheduler.run_paper_cycle",
        lambda _settings: downstream.append("paper"),
    )
    monkeypatch.setattr(
        "shaiwei.pipeline.scheduler.FeishuNotifier",
        lambda settings: RecordingNotifier(settings, notifications),
    )
    monkeypatch.setattr(
        "shaiwei.pipeline.scheduler.write_health",
        lambda status, detail="": health.append((status, detail)),
    )

    assert run_scheduler(once=True, settings=load()) == 0
    assert downstream == []
    assert notifications == []
    assert ("waiting_source", "20260804") in health
    assert not any(status == "degraded" for status, _detail in health)


def test_scheduler_pass_still_runs_all_downstream(monkeypatch):
    downstream = []
    notifications = []
    health = []
    result = DailyResult("PASS", "20260731", "20260804", ("20260804",), 5, 1)
    monkeypatch.setattr("shaiwei.pipeline.scheduler.run_once", lambda **_kwargs: result)
    monkeypatch.setattr(
        "shaiwei.pipeline.scheduler.run_shadow_cycle",
        lambda _settings: downstream.append("shadow"),
    )
    monkeypatch.setattr(
        "shaiwei.pipeline.scheduler.run_paper_cycle",
        lambda _settings: downstream.append("paper"),
    )
    monkeypatch.setattr(
        "shaiwei.pipeline.scheduler.FeishuNotifier",
        lambda settings: RecordingNotifier(settings, notifications),
    )
    monkeypatch.setattr(
        "shaiwei.pipeline.scheduler.write_health",
        lambda status, detail="": health.append((status, detail)),
    )

    assert run_scheduler(once=True, settings=load()) == 0
    assert downstream == ["shadow", "paper"]
    assert notifications == []
    assert ("pass", "20260804") in health
