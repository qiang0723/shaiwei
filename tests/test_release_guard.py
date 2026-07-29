from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from shaiwei import release_guard


PROTOCOL = Path(__file__).parents[1] / "config" / "paper_top20_release_guard_v1.yaml"
SHANGHAI = ZoneInfo("Asia/Shanghai")


class FakeEnvironment:
    def __init__(self):
        self.protocol = release_guard.load_protocol(PROTOCOL)
        self.start_calls = 0
        self.git = {"status": "", "head": "f" * 40, "origin_main": "f" * 40}
        self.current = self.protocol.candidate.model_dump()
        self.verified = dict(self.current)
        self.previous = {
            "image": "shaiwei:scheduler-old",
            "image_id": self.protocol.expected_running_release.image_id,
            "code_snapshot_sha256": self.protocol.expected_running_release.code_snapshot_sha256,
            "git_head": "e" * 40,
        }
        self.running = release_guard.SchedulerIdentity(
            container_id="old-container",
            image_id=self.protocol.expected_running_release.image_id,
            health="healthy",
            code_snapshot_sha256=self.protocol.expected_running_release.code_snapshot_sha256,
            git_head="e" * 40,
        )
        self.forward = {
            "account_id": "model_baseline",
            "status": "PASS",
            "execution_trade_date": self.protocol.expected_latest_forward.execution_trade_date,
            "code_snapshot_sha256": self.protocol.expected_latest_forward.code_snapshot_sha256,
        }
        self.ready = {
            "status": "PASS",
            "mode": "CROSS_SNAPSHOT_WITH_NEW_DATA",
            "available_new_trade_dates": [self.protocol.target_trade_date],
        }

    def git_state(self):
        return self.git

    def release_status(self):
        return {"status": "PASS", "state": {"current": self.current, "previous": self.previous}}

    def verify_candidate(self, _image):
        return self.verified

    def running_scheduler(self):
        return self.running

    def latest_forward(self, _account_id):
        return self.forward

    def readiness(self, _snapshot):
        return self.ready

    def start_current(self):
        self.start_calls += 1
        return {"container_id": "new-container", "code_snapshot_sha256": self.current["code_snapshot_sha256"]}


def local(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 7, day, hour, minute, tzinfo=SHANGHAI)


@pytest.mark.parametrize(
    ("now", "message"),
    [
        (local(29, 17), "target date"),
        (local(30, 16, 4), "not opened"),
        (local(30, 19), "expired"),
        (local(31, 16, 5), "target date"),
    ],
)
def test_time_boundary_blocks_before_any_start(now, message):
    env = FakeEnvironment()
    with pytest.raises(release_guard.GuardError, match=message):
        release_guard.run_guard(env.protocol, now=now, execute=True, environment=env)
    assert env.start_calls == 0


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda env: env.git.update(status=" M STATE.md"), "clean worktree"),
        (lambda env: env.git.update(origin_main="a" * 40), "HEAD to equal"),
        (
            lambda env: setattr(env, "release_status", lambda: {"status": "FAIL"}),
            "audit status",
        ),
        (lambda env: env.current.update(image_id="sha256:" + "0" * 64), "promoted release"),
        (lambda env: env.verified.update(git_head="0" * 40), "runtime identity"),
        (
            lambda env: setattr(env, "running", replace(env.running, health="unhealthy")),
            "not healthy",
        ),
        (
            lambda env: setattr(
                env,
                "running",
                replace(env.running, image_id="sha256:" + "1" * 64),
            ),
            "image differs",
        ),
        (
            lambda env: setattr(
                env,
                "running",
                replace(env.running, code_snapshot_sha256="3" * 64),
            ),
            "snapshot differs",
        ),
        (
            lambda env: setattr(env, "running", replace(env.running, git_head="4" * 40)),
            "Git identity",
        ),
        (lambda env: env.forward.update(execution_trade_date="20260730"), "execution date"),
        (lambda env: env.forward.update(code_snapshot_sha256="2" * 64), "baseline snapshot"),
        (lambda env: env.ready.update(mode="SAME_RELEASE_RESTART"), "readiness mode"),
        (lambda env: env.ready.update(available_new_trade_dates=["20260730", "20260731"]), "single"),
    ],
)
def test_preconditions_fail_closed_without_start(mutate, message):
    env = FakeEnvironment()
    mutate(env)
    with pytest.raises(release_guard.GuardError, match=message):
        release_guard.run_guard(env.protocol, now=local(30, 16, 5), execute=True, environment=env)
    assert env.start_calls == 0


def test_dry_run_returns_ready_without_start():
    env = FakeEnvironment()
    result = release_guard.run_guard(
        env.protocol,
        now=local(30, 16, 5),
        execute=False,
        environment=env,
    )
    assert result["status"] == "READY"
    assert result["start_invoked"] is False
    assert env.start_calls == 0


def test_execute_invokes_existing_start_exactly_once():
    env = FakeEnvironment()
    result = release_guard.run_guard(
        env.protocol,
        now=local(30, 16, 5),
        execute=True,
        environment=env,
    )
    assert result["status"] == "STARTED"
    assert result["start_invoked"] is True
    assert env.start_calls == 1


def test_exact_candidate_already_active_is_idempotent():
    env = FakeEnvironment()
    candidate = env.protocol.candidate
    env.running = release_guard.SchedulerIdentity(
        container_id="candidate-container",
        image_id=candidate.image_id,
        health="healthy",
        code_snapshot_sha256=candidate.code_snapshot_sha256,
        git_head=candidate.git_head,
    )
    result = release_guard.run_guard(
        env.protocol,
        now=local(30, 16, 5),
        execute=True,
        environment=env,
    )
    assert result["status"] == "ALREADY_ACTIVE"
    assert result["start_invoked"] is False
    assert env.start_calls == 0


def test_targeted_docker_inspect_never_requests_environment(monkeypatch):
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        if argv[:4] == ["docker", "compose", "ps", "-q"]:
            return SimpleNamespace(stdout="scheduler-id\n")
        if argv[:3] == ["docker", "inspect", "--format"]:
            return SimpleNamespace(stdout="sha256:" + "a" * 64 + "|healthy\n")
        return SimpleNamespace(
            stdout='{"code_snapshot_sha256":"' + "b" * 64 + '","git_head":"' + "c" * 40 + '"}\n'
        )

    monkeypatch.setattr(release_guard.subprocess, "run", fake_run)
    result = release_guard.GuardEnvironment().running_scheduler()
    assert result.health == "healthy"
    assert all(".Config.Env" not in " ".join(call) for call in calls)
    assert all("inspect" not in call or "--format" in call for call in calls)
