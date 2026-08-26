from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from shaiwei import daily_early_release_guard as base
from shaiwei import r2d_release_guard as guard
from shaiwei.release_guard import SchedulerIdentity


SHANGHAI = ZoneInfo("Asia/Shanghai")


def protocol_document(**updates):
    document = {
        "schema_version": "r2d-scheduler-release-guard-v1",
        "guard_id": "r2d-scheduler-release-guard-20260826",
        "timezone": "Asia/Shanghai",
        "prepare_date": "20260825",
        "prepare_window": {"not_before": "19:45:00", "expires_at": "23:00:00"},
        "target_trade_date": "20260826",
        "start_window": {"not_before": "16:05:00", "expires_at": "19:00:00"},
        "candidate": {
            "image": "shaiwei:scheduler-" + "1" * 16,
            "image_id": "sha256:" + "1" * 64,
            "code_snapshot_sha256": "1" * 64,
            "git_head": "1" * 40,
            "lock_authority": "docker-named-volume-v1",
        },
        "expected_running_release": {
            "image": "shaiwei:scheduler-" + "2" * 16,
            "image_id": "sha256:" + "2" * 64,
            "code_snapshot_sha256": "2" * 64,
            "git_head": "2" * 40,
            "lock_authority": "legacy-bind-flock-v0",
        },
        "expected_latest_forward": [
            {
                "account_id": account,
                "execution_trade_date": "20260825",
                "code_snapshot_sha256": "2" * 64,
                "artifact_sha256": artifact * 64,
            }
            for account, artifact in (("model_baseline", "3"), ("model_top20", "4"))
        ],
        "expected_legacy_mounts_before_prepare": [
            "/workspace/data",
            "/workspace/ledger",
            "/workspace/logs",
        ],
        "predecessor_fixture": {
            "release_scope_sha256": "5" * 64,
            "report_path": ".release/r2d/report.json",
            "report_sha256": "6" * 64,
            "tree_path": ".release/r2d/tree.json",
            "tree_file_sha256": "7" * 64,
            "tree_content_sha256": "8" * 64,
            "receipt_path": ".release/r2d/receipt.json",
            "receipt_sha256": "9" * 64,
        },
        "controller_identity": {
            "candidate_base_head": "1" * 40,
            "controller_source_head": "f" * 40,
            "component_paths": [
                "src/shaiwei/release_build_context.py",
                "src/shaiwei/release_guard.py",
                "src/shaiwei/daily_early_release_guard.py",
                "src/shaiwei/r2d_release_guard.py",
            ],
            "component_sha256": "a" * 64,
        },
    }
    document.update(updates)
    return document


def protocol(**updates):
    return guard.GuardProtocol.model_validate(protocol_document(**updates))


def recovery_protocol_document(**updates):
    document = protocol_document(
        schema_version="r2d-scheduler-release-guard-r1-v1",
        guard_id="r2d-scheduler-release-guard-20260827",
        target_trade_date="20260827",
        expected_latest_forward=[
            {
                "account_id": account,
                "execution_trade_date": "20260826",
                "code_snapshot_sha256": "2" * 64,
                "artifact_sha256": artifact * 64,
            }
            for account, artifact in (("model_baseline", "3"), ("model_top20", "4"))
        ],
        controller_identity={
            "candidate_base_head": "1" * 40,
            "controller_source_head": "f" * 40,
            "component_paths": [
                "src/shaiwei/release_build_context.py",
                "src/shaiwei/release_guard.py",
                "src/shaiwei/daily_early_release_guard.py",
                "src/shaiwei/r2d_release_guard.py",
                "src/shaiwei/r2d_legacy_boundary.py",
            ],
            "component_sha256": "a" * 64,
        },
        legacy_noop_boundary={
            "mode": "PRIOR_DAY_NOOP",
            "status": "noop",
            "detail_trade_date": "20260826",
            "updated_on_target_date_not_before": "16:00:00",
            "require_target_daily_rows": 0,
            "require_target_shadow_rows": 0,
            "require_target_paper_rows": 0,
        },
    )
    document.update(updates)
    return document


class FakeEnvironment:
    def __init__(self):
        self.protocol = protocol()
        self.old = self.protocol.expected_running_release.model_dump()
        self.candidate = self.protocol.candidate.model_dump()
        self.current = deepcopy(self.old)
        self.previous = {
            "image": "shaiwei:scheduler-" + "e" * 16,
            "image_id": "sha256:" + "e" * 64,
            "code_snapshot_sha256": "e" * 64,
            "git_head": "e" * 40,
        }
        self.running = self._running(self.old, "legacy-container")
        self.git = {
            "status": " M ledger/daily_runs.csv\n?? docs/user-draft.md",
            "head": "f" * 40,
            "origin_main": "f" * 40,
            "controlled_changes": (),
        }
        self.forwards = {
            item.account_id: item.model_dump() for item in self.protocol.expected_latest_forward
        }
        self.ready = {
            "status": "PASS",
            "mode": "CROSS_SNAPSHOT_WITH_NEW_DATA",
            "available_new_trade_dates": ["20260826"],
        }
        self.health = {
            "status": "waiting_source",
            "detail": "20260826",
            "updated_at": "2026-08-26T08:01:00+00:00",
        }
        self.target_counts = {"daily": 0, "shadow": 0, "paper": 0}
        self.prepare_calls = 0
        self.start_calls = 0
        self.rollback_calls = 0
        self.start_error = False
        self.broken_candidate_mount = False

    @staticmethod
    def _running(identity, container_id, health="healthy"):
        authority = identity["lock_authority"]
        mounts = ["/workspace/data", "/workspace/ledger", "/workspace/logs"]
        if authority == "docker-named-volume-v1":
            mounts.insert(0, "/run/shaiwei-locks")
        return SchedulerIdentity(
            container_id=container_id,
            image_id=identity["image_id"],
            health=health,
            code_snapshot_sha256=identity["code_snapshot_sha256"],
            git_head=identity["git_head"],
            read_only_rootfs=True,
            mount_destinations=tuple(mounts),
            lock_authority=authority,
        )

    def git_state(self):
        return self.git

    def release_status(self):
        return {"status": "PASS", "state": {"current": self.current, "previous": self.previous}}

    def verify_candidate(self, _image):
        return self.candidate

    def running_scheduler(self):
        return self.running

    def latest_forward(self, account_id):
        return self.forwards[account_id]

    def readiness(self, _snapshot):
        return self.ready

    def scheduler_health(self):
        return self.health

    def target_write_counts(self, _target_trade_date):
        return self.target_counts

    def controller_evidence(self, _identity):
        return {
            "component_sha256": "a" * 64,
            "delta_paths": (
                "STATE.md",
                "src/shaiwei/r2d_release_guard.py",
                "tests/test_r2d_release_guard.py",
            ),
            "delta_sha256": "b" * 64,
        }

    def promote_no_start(self, _image):
        self.prepare_calls += 1
        self.previous = deepcopy(self.old)
        self.current = deepcopy(self.candidate)
        return {"status": "PROMOTE_PASS", "started": False}

    def start_current(self):
        self.start_calls += 1
        if self.start_error:
            raise base.release.ReleaseError("synthetic start failure")
        self.running = self._running(self.candidate, "candidate-container")
        if self.broken_candidate_mount:
            self.running = self.running.__class__(
                **{**self.running.__dict__, "mount_destinations": ("/workspace/data",)}
            )
        return {"status": "START_PASS"}

    def rollback_and_start(self):
        self.rollback_calls += 1
        self.current = deepcopy(self.old)
        self.previous = deepcopy(self.candidate)
        self.running = self._running(self.old, "restored-container")
        return {"status": "ROLLBACK_PASS"}


def local(day, hour, minute=0):
    return datetime(2026, 8, day, hour, minute, tzinfo=SHANGHAI)


def test_protocol_rejects_incomplete_or_ambiguous_release():
    document = protocol_document()
    document["candidate"]["lock_authority"] = "legacy-bind-flock-v0"
    with pytest.raises(ValueError, match="named-volume"):
        guard.GuardProtocol.model_validate(document)

    document = protocol_document()
    document["expected_latest_forward"] = document["expected_latest_forward"][:1]
    with pytest.raises(ValueError, match="exactly the Top30 and Top20"):
        guard.GuardProtocol.model_validate(document)


def test_prepare_allows_runtime_dirt_and_preserves_container(monkeypatch):
    env = FakeEnvironment()
    monkeypatch.setattr(guard, "_validate_fixture", lambda _protocol: None)
    result = guard.prepare_guard(env.protocol, now=local(25, 20), execute=True, environment=env)
    assert result["status"] == "PREPARED"
    assert (env.prepare_calls, env.start_calls) == (1, 0)
    assert env.running.container_id == "legacy-container"
    assert env.current == env.candidate and env.previous == env.old

    repeated = guard.prepare_guard(env.protocol, now=local(25, 20), execute=True, environment=env)
    assert repeated["status"] == "ALREADY_PREPARED"
    assert env.prepare_calls == 1


def test_prepare_rejects_controlled_source_or_mount_drift(monkeypatch):
    env = FakeEnvironment()
    monkeypatch.setattr(guard, "_validate_fixture", lambda _protocol: None)
    env.git["controlled_changes"] = ("src/shaiwei/release.py",)
    with pytest.raises(base.GuardError, match="controlled source tree"):
        guard.prepare_guard(env.protocol, now=local(25, 20), execute=True, environment=env)
    env.git["controlled_changes"] = ()
    env.running = env._running(env.old, "legacy-container")
    env.running = env.running.__class__(
        **{**env.running.__dict__, "mount_destinations": ("/workspace/data",)}
    )
    with pytest.raises(base.GuardError, match="healthy running release|mounts"):
        guard.prepare_guard(env.protocol, now=local(25, 20), execute=True, environment=env)


def test_prepare_rejects_controller_component_or_delta_drift(monkeypatch):
    env = FakeEnvironment()
    monkeypatch.setattr(guard, "_validate_fixture", lambda _protocol: None)
    env.controller_evidence = lambda _identity: {
        "component_sha256": "0" * 64,
        "delta_paths": (),
    }
    with pytest.raises(base.GuardError, match="component identity"):
        guard.prepare_guard(env.protocol, now=local(25, 20), execute=True, environment=env)

    env.controller_evidence = lambda _identity: {
        "component_sha256": "a" * 64,
        "delta_paths": ("src/shaiwei/pipeline/scheduler.py",),
    }
    with pytest.raises(base.GuardError, match="escapes the frozen allowlist"):
        guard.prepare_guard(env.protocol, now=local(25, 20), execute=True, environment=env)


def test_start_requires_prepared_state_and_waiting_source(monkeypatch):
    env = FakeEnvironment()
    monkeypatch.setattr(guard, "_validate_fixture", lambda _protocol: None)
    with pytest.raises(base.GuardError, match="prepared transition state"):
        guard.start_guard(env.protocol, now=local(26, 16, 5), execute=True, environment=env)
    env.promote_no_start(env.candidate["image"])
    env.health["status"] = "noop"
    with pytest.raises(base.GuardError, match="waiting_source"):
        guard.start_guard(env.protocol, now=local(26, 16, 5), execute=True, environment=env)
    assert env.start_calls == 0


def test_prepared_start_enforces_named_lock_runtime(monkeypatch):
    env = FakeEnvironment()
    monkeypatch.setattr(guard, "_validate_fixture", lambda _protocol: None)
    env.promote_no_start(env.candidate["image"])
    result = guard.start_guard(env.protocol, now=local(26, 16, 5), execute=True, environment=env)
    assert result["status"] == "STARTED"
    assert result["legacy_waiting_source"]["detail"] == "20260826"
    assert env.start_calls == 1
    assert env.running.lock_authority == "docker-named-volume-v1"
    assert len(env.running.mount_destinations) == 4


def test_recovery_start_accepts_fresh_prior_day_noop_and_zero_target_rows(monkeypatch):
    env = FakeEnvironment()
    env.protocol = guard.GuardProtocol.model_validate(recovery_protocol_document())
    env.forwards = {
        item.account_id: item.model_dump() for item in env.protocol.expected_latest_forward
    }
    env.ready["available_new_trade_dates"] = ["20260827"]
    env.health = {
        "status": "noop",
        "detail": "20260826",
        "updated_at": "2026-08-27T08:01:00+00:00",
    }
    env.current = deepcopy(env.candidate)
    env.previous = deepcopy(env.old)
    monkeypatch.setattr(guard, "_validate_fixture", lambda _protocol: None)

    with pytest.raises(base.GuardError, match="cannot repeat Phase A"):
        guard.prepare_guard(env.protocol, now=local(25, 20), execute=False, environment=env)
    result = guard.start_guard(
        env.protocol,
        now=local(27, 16, 5),
        execute=False,
        environment=env,
    )
    assert result["status"] == "READY_TO_START"
    assert result["legacy_noop_boundary"]["target_write_counts"] == {
        "daily": 0,
        "shadow": 0,
        "paper": 0,
    }


def test_recovery_start_rejects_any_target_date_attempt(monkeypatch):
    env = FakeEnvironment()
    env.protocol = guard.GuardProtocol.model_validate(recovery_protocol_document())
    env.forwards = {
        item.account_id: item.model_dump() for item in env.protocol.expected_latest_forward
    }
    env.ready["available_new_trade_dates"] = ["20260827"]
    env.health = {
        "status": "noop",
        "detail": "20260826",
        "updated_at": "2026-08-27T08:01:00+00:00",
    }
    env.target_counts["paper"] = 1
    env.current = deepcopy(env.candidate)
    env.previous = deepcopy(env.old)
    monkeypatch.setattr(guard, "_validate_fixture", lambda _protocol: None)

    with pytest.raises(base.GuardError, match="already written the target date"):
        guard.start_guard(
            env.protocol,
            now=local(27, 16, 5),
            execute=False,
            environment=env,
        )


@pytest.mark.parametrize("failure", ("start_error", "broken_candidate_mount"))
def test_failed_start_or_runtime_contract_restores_legacy_sequentially(monkeypatch, failure):
    env = FakeEnvironment()
    monkeypatch.setattr(guard, "_validate_fixture", lambda _protocol: None)
    env.promote_no_start(env.candidate["image"])
    setattr(env, failure, True)
    with pytest.raises(base.GuardError, match="previous release restored"):
        guard.start_guard(env.protocol, now=local(26, 16, 5), execute=True, environment=env)
    assert (env.start_calls, env.rollback_calls) == (1, 1)
    assert env.current == env.old
    assert env.running.container_id == "restored-container"


def _write_json(path: Path, document: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fixture_evidence_is_hash_and_identity_bound(monkeypatch, tmp_path):
    scope, tree_content = "5" * 64, "8" * 64
    report_path = tmp_path / ".release/r2d/report.json"
    tree_path = tmp_path / ".release/r2d/tree.json"
    receipt_path = tmp_path / ".release/r2d/receipt.json"
    report_sha = _write_json(report_path, {"scope_sha256": scope, "verdict": "PASS"})
    tree_sha = _write_json(tree_path, {"tree_sha256": tree_content})
    receipt_sha = _write_json(
        receipt_path,
        {
            "release_scope_sha256": scope,
            "report_sha256": report_sha,
            "evidence_tree_file_sha256": tree_sha,
            "evidence_tree_sha256": tree_content,
            "status": "PASS",
            "candidate": "shaiwei:scheduler-" + "1" * 16,
            "image_id": "sha256:" + "1" * 64,
        },
    )
    frozen = protocol(
        predecessor_fixture={
            "release_scope_sha256": scope,
            "report_path": ".release/r2d/report.json",
            "report_sha256": report_sha,
            "tree_path": ".release/r2d/tree.json",
            "tree_file_sha256": tree_sha,
            "tree_content_sha256": tree_content,
            "receipt_path": ".release/r2d/receipt.json",
            "receipt_sha256": receipt_sha,
        }
    )
    monkeypatch.setattr(guard, "PROJECT_ROOT", tmp_path)
    guard._validate_fixture(frozen)
    report_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(base.GuardError, match="hash or schema"):
        guard._validate_fixture(frozen)


def test_tracked_r2d_protocol_and_release_scope_are_exactly_bound():
    frozen = guard.load_protocol()
    release_path = (
        guard.PROJECT_ROOT / "config" / "r2d_scheduler_release_scope_v1.json"
    )
    release = json.loads(release_path.read_text(encoding="utf-8"))
    scope = release["scope"]
    canonical = json.dumps(scope, sort_keys=True, separators=(",", ":")).encode()

    assert release["schema_version"] == "r2d-scheduler-release-scope-v1"
    assert release["release_scope_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert release["release_scope_sha256"] == (
        "4145d6018a1cb38f48432677dce1e68558cdaf48ad5c3e81d12f7067eac58292"
    )
    assert scope["action"] == (
        "R2D_PROMOTE_NO_START_20260825_AND_START_20260826_ONCE"
    )
    assert scope["candidate"] == frozen.candidate.model_dump()
    assert scope["expected_running_release"] == (
        frozen.expected_running_release.model_dump()
    )
    assert scope["expected_latest_forward"] == [
        item.model_dump() for item in frozen.expected_latest_forward
    ]
    assert scope["phase_a"]["date"] == frozen.prepare_date
    assert scope["phase_b"]["date"] == frozen.target_trade_date
    assert scope["guard_protocol"]["sha256"] == hashlib.sha256(
        guard.PROTOCOL_PATH.read_bytes()
    ).hexdigest()
