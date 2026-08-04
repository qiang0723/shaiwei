from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from shaiwei import daily_early_release_guard as guard
from shaiwei import release
from shaiwei.release_guard import SchedulerIdentity


LEGACY_PROTOCOL = Path(__file__).parents[1] / "config" / "daily_early_readiness_release_guard_v1.yaml"
PROTOCOL = Path(__file__).parents[1] / "config" / "daily_early_readiness_release_guard_v2.yaml"
SHANGHAI = ZoneInfo("Asia/Shanghai")


class FakeEnvironment:
    def __init__(self):
        self.protocol = guard.load_protocol(PROTOCOL)
        self.git = {"status": "", "head": "f" * 40, "origin_main": "f" * 40}
        self.audit_status = "PASS"
        self.old = self.protocol.expected_running_release.model_dump()
        self.candidate = self.protocol.candidate.model_dump()
        self.current = deepcopy(self.old)
        self.previous = {
            "image": "shaiwei:scheduler-" + "e" * 16,
            "image_id": "sha256:" + "e" * 64,
            "code_snapshot_sha256": "e" * 64,
            "git_head": "e" * 40,
        }
        self.running = self._running(self.old, "old-container")
        self.verified = deepcopy(self.candidate)
        self.forwards = {
            item.account_id: item.model_dump() for item in self.protocol.expected_latest_forward
        }
        self.ready = {
            "status": "PASS",
            "mode": "CROSS_SNAPSHOT_WITH_NEW_DATA",
            "available_new_trade_dates": [self.protocol.target_trade_date],
        }
        self.promote_calls = 0
        self.start_calls = 0
        self.rollback_calls = 0
        self.promote_error = False
        self.start_error = False
        self.rollback_error = False

    @staticmethod
    def _running(identity, container_id, health="healthy"):
        return SchedulerIdentity(
            container_id=container_id,
            image_id=identity["image_id"],
            health=health,
            code_snapshot_sha256=identity["code_snapshot_sha256"],
            git_head=identity["git_head"],
        )

    def git_state(self):
        return self.git

    def release_status(self):
        return {
            "status": self.audit_status,
            "state": {"current": self.current, "previous": self.previous},
        }

    def verify_candidate(self, _image):
        return self.verified

    def running_scheduler(self):
        return self.running

    def latest_forward(self, account_id):
        return self.forwards[account_id]

    def readiness(self, _snapshot):
        return self.ready

    def promote_and_start(self, _image):
        self.promote_calls += 1
        if self.promote_error:
            self.running = self._running(self.candidate, "failed-candidate", "unhealthy")
            raise release.ReleaseError("synthetic promotion failure")
        self.previous = deepcopy(self.old)
        self.current = deepcopy(self.candidate)
        self.running = self._running(self.candidate, "candidate-container")
        return {"status": "PROMOTE_PASS"}

    def start_current(self):
        self.start_calls += 1
        if self.start_error:
            raise release.ReleaseError("synthetic start failure")
        identity = self.current
        name = "candidate-container" if identity == self.candidate else "restored-old-container"
        self.running = self._running(identity, name)
        return {"status": "START_PASS"}

    def rollback_and_start(self):
        self.rollback_calls += 1
        if self.rollback_error:
            raise release.ReleaseError("synthetic rollback failure")
        former = deepcopy(self.current)
        self.current = deepcopy(self.old)
        self.previous = former
        self.running = self._running(self.old, "rolled-back-container")
        return {"status": "ROLLBACK_PASS"}


def local(day, hour, minute=0):
    return datetime(2026, 8, day, hour, minute, tzinfo=SHANGHAI)


@pytest.mark.parametrize(
    ("now", "message"),
    [
        (local(4, 17), "target date"),
        (local(5, 16, 4), "not opened"),
        (local(5, 19), "expired"),
        (local(6, 16, 5), "target date"),
    ],
)
def test_time_boundary_blocks_before_any_mutation(now, message):
    env = FakeEnvironment()
    with pytest.raises(guard.GuardError, match=message):
        guard.run_guard(env.protocol, now=now, execute=True, environment=env)
    assert (env.promote_calls, env.start_calls, env.rollback_calls) == (0, 0, 0)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda env: env.git.update(status=" M STATE.md"), "clean worktree"),
        (lambda env: env.git.update(origin_main="a" * 40), "HEAD to equal"),
        (lambda env: setattr(env, "audit_status", "FAIL"), "audit status"),
        (lambda env: env.verified.update(git_head="0" * 40), "runtime identity"),
        (
            lambda env: setattr(env, "running", env._running(env.old, "old", "unhealthy")),
            "not healthy",
        ),
        (
            lambda env: env.forwards["model_baseline"].update(execution_trade_date="20260731"),
            "execution_trade_date",
        ),
        (
            lambda env: env.forwards["model_top20"].update(artifact_sha256="1" * 64),
            "artifact_sha256",
        ),
        (lambda env: env.ready.update(mode="SAME_RELEASE_RESTART"), "readiness mode"),
        (
            lambda env: env.ready.update(available_new_trade_dates=["20260805", "20260806"]),
            "single frozen target",
        ),
    ],
)
def test_preconditions_fail_closed_without_mutation(mutate, message):
    env = FakeEnvironment()
    mutate(env)
    with pytest.raises(guard.GuardError, match=message):
        guard.run_guard(env.protocol, now=local(5, 16, 5), execute=True, environment=env)
    assert (env.promote_calls, env.start_calls, env.rollback_calls) == (0, 0, 0)


def test_unrecognized_release_transition_state_is_blocked():
    env = FakeEnvironment()
    env.current["image_id"] = "sha256:" + "1" * 64
    with pytest.raises(guard.GuardError, match="authorized transition state"):
        guard.run_guard(env.protocol, now=local(5, 16, 5), execute=True, environment=env)
    assert env.promote_calls == 0


def test_dry_run_is_ready_without_mutation():
    env = FakeEnvironment()
    result = guard.run_guard(
        env.protocol,
        now=local(5, 16, 5),
        execute=False,
        environment=env,
    )
    assert result["status"] == "READY"
    assert result["action"] == "PROMOTE_AND_START"
    assert result["mutation_invoked"] is False
    assert (env.promote_calls, env.start_calls, env.rollback_calls) == (0, 0, 0)


def test_fresh_execute_promotes_and_starts_exactly_once():
    env = FakeEnvironment()
    result = guard.run_guard(
        env.protocol,
        now=local(5, 16, 5),
        execute=True,
        environment=env,
    )
    assert result["status"] == "STARTED"
    assert result["mutation_invoked"] is True
    assert (env.promote_calls, env.start_calls, env.rollback_calls) == (1, 0, 0)
    assert env.current == env.candidate
    assert env.running.image_id == env.candidate["image_id"]


def test_exact_candidate_already_active_is_idempotent():
    env = FakeEnvironment()
    env.current = deepcopy(env.candidate)
    env.previous = deepcopy(env.old)
    env.running = env._running(env.candidate, "candidate-container")
    result = guard.run_guard(
        env.protocol,
        now=local(5, 16, 5),
        execute=True,
        environment=env,
    )
    assert result["status"] == "ALREADY_ACTIVE"
    assert result["mutation_invoked"] is False
    assert (env.promote_calls, env.start_calls, env.rollback_calls) == (0, 0, 0)


def test_promoted_but_old_running_resumes_start_once():
    env = FakeEnvironment()
    env.current = deepcopy(env.candidate)
    env.previous = deepcopy(env.old)
    result = guard.run_guard(
        env.protocol,
        now=local(5, 16, 5),
        execute=True,
        environment=env,
    )
    assert result["status"] == "RESUMED_AND_STARTED"
    assert (env.promote_calls, env.start_calls, env.rollback_calls) == (0, 1, 0)
    assert env.running.image_id == env.candidate["image_id"]


def test_failed_fresh_promotion_restarts_restored_old_release():
    env = FakeEnvironment()
    env.promote_error = True
    with pytest.raises(guard.GuardError, match="previous release restored"):
        guard.run_guard(env.protocol, now=local(5, 16, 5), execute=True, environment=env)
    assert (env.promote_calls, env.start_calls, env.rollback_calls) == (1, 1, 0)
    assert env.current == env.old
    assert env.running.image_id == env.old["image_id"]
    assert env.running.health == "healthy"


def test_failed_resumed_start_rolls_back_and_starts_old_release():
    env = FakeEnvironment()
    env.current = deepcopy(env.candidate)
    env.previous = deepcopy(env.old)
    env.start_error = True
    with pytest.raises(guard.GuardError, match="previous release restored"):
        guard.run_guard(env.protocol, now=local(5, 16, 5), execute=True, environment=env)
    assert (env.promote_calls, env.start_calls, env.rollback_calls) == (0, 1, 1)
    assert env.current == env.old
    assert env.running.image_id == env.old["image_id"]


def test_failed_promotion_and_failed_restoration_report_both_failures():
    env = FakeEnvironment()
    env.promote_error = True
    env.start_error = True
    with pytest.raises(guard.GuardError, match="restoration also failed"):
        guard.run_guard(env.protocol, now=local(5, 16, 5), execute=True, environment=env)
    assert (env.promote_calls, env.start_calls, env.rollback_calls) == (1, 1, 0)


def test_protocol_rejects_unknown_fields_and_incomplete_accounts():
    document = guard.load_protocol(PROTOCOL).model_dump(mode="json")
    document["unexpected"] = True
    with pytest.raises(ValueError, match="Extra inputs"):
        guard.GuardProtocol.model_validate(document)

    document = guard.load_protocol(PROTOCOL).model_dump(mode="json")
    document["expected_latest_forward"] = document["expected_latest_forward"][:1]
    with pytest.raises(ValueError, match="exactly the Top30 and Top20"):
        guard.GuardProtocol.model_validate(document)


def test_protocol_is_bound_to_august_5_and_the_built_candidate():
    protocol = guard.load_protocol()
    assert guard.PROTOCOL_PATH == PROTOCOL
    assert protocol.target_trade_date == "20260805"
    assert protocol.window.not_before.isoformat() == "16:05:00"
    assert protocol.window.expires_at.isoformat() == "19:00:00"
    assert protocol.candidate.image == "shaiwei:scheduler-0640574ba7353c3e"
    assert {
        item.account_id: (item.execution_trade_date, item.artifact_sha256)
        for item in protocol.expected_latest_forward
    } == {
        "model_baseline": (
            "20260804",
            "691987e0fdc3cae0fed405d6d6e7eb9c50c1e49d0404a46f31de408be472e89f",
        ),
        "model_top20": (
            "20260804",
            "26de5b7fcaa0682e3e8d47a4c4120f685dbe8766b30189303f37d75a81abafec",
        ),
    }


def test_august_4_protocol_remains_loadable_and_unchanged():
    legacy = guard.load_protocol(LEGACY_PROTOCOL)
    assert legacy.guard_id == "daily-early-readiness-release-guard-20260804"
    assert legacy.target_trade_date == "20260804"
    assert {
        item.account_id: item.artifact_sha256 for item in legacy.expected_latest_forward
    } == {
        "model_baseline": "ff8ddb0beb9e468611bdc527e3c0ee8c4dda08da3bef4ebd043328e91f671235",
        "model_top20": "f0c4eae56bd4f90bd3ea5578c014f8a024d2df9aa796b38e60b56e5de2c326fc",
    }
