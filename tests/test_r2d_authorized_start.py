"""Synthetic execution contracts: no Docker, real scope or production data."""
from dataclasses import replace
from datetime import timedelta
import json
import subprocess
import sys

import pytest
import yaml

from shaiwei import r2d_authorized_start as runner
from shaiwei import r2d_execution_contract as contract
from shaiwei import r2d_release_guard as guard
from shaiwei.r2d_metadata_environment import ObservedScheduler
from shaiwei.release_metadata import sha256
from test_r2d_release_guard import FakeEnvironment, recovery_protocol_document, local


class Environment(FakeEnvironment):
    def __init__(self, protocol):
        super().__init__()
        self.protocol = protocol
        self.current, self.previous = self.candidate, self.old
        self.running = self.observed(self.old, "c" * 64)
        self.forwards = {item.account_id: item.model_dump()
                         for item in protocol.expected_latest_forward}
        self.ready["available_new_trade_dates"] = ["20260827"]
        self.health = {"status": "noop", "detail": "20260826",
                       "updated_at": "2026-08-27T08:01:00+00:00"}
        self.hashes = ("d" * 64, "e" * 64)
        self.hook = lambda: None

    def observed(self, identity, container):
        value = self._running(identity, container)
        return ObservedScheduler(**{**value.__dict__,
            "mount_destinations": ("/workspace/data", "/workspace/ledger",
                                   "/workspace/logs", "/run/shaiwei-locks")},
            restart_count=0)

    def release_hashes(self):
        return self.hashes

    def start_once(self, callback):
        self.hook()
        callback()
        self.start_calls += 1
        if self.start_error:
            raise RuntimeError("synthetic unknown start")
        self.running = self.observed(self.candidate, "b" * 64)
        if self.broken_candidate_mount:
            self.running = replace(self.running, mount_destinations=("/workspace/data",))
        return {"audit_record_sha256": "a" * 64}


@pytest.fixture
def case(tmp_path, monkeypatch):
    document = recovery_protocol_document()
    document["controller_identity"]["component_paths"] = sorted(runner.REQUIRED_COMPONENTS)
    document["expected_legacy_mounts_before_prepare"].append("/run/shaiwei-locks")
    protocol = guard.GuardProtocol.model_validate(document)
    (tmp_path / "config").mkdir()
    path = tmp_path / "config/r2d_synthetic.yaml"
    path.write_text(yaml.safe_dump(protocol.model_dump(mode="json")))
    scope = contract.ExecutionScope(
        schema_version="r2d-execution-scope-v1", action="START_CURRENT_ONCE",
        protocol_path="config/r2d_synthetic.yaml", protocol_sha256=sha256(path),
        protocol=protocol.model_dump(mode="json"), git_head="f" * 40,
        origin_main="f" * 40, state_sha256="d" * 64, audit_sha256="e" * 64,
        legacy_container_id="c" * 64, compose_project="synthetic",
        rollback_policy="FORBID_AFTER_DISPATCH", health_max_age_seconds=3600)
    envelope = contract.ScopeEnvelope(scope=scope, scope_sha256=contract.scope_hash(scope))
    (tmp_path / "scope.json").write_text(envelope.model_dump_json())
    approval = contract.Approval(schema_version="r2d-execution-approval-v1",
        scope_sha256=envelope.scope_sha256,
        approval_text=contract.approval_text(envelope.scope_sha256))
    (tmp_path / "approval.json").write_text(approval.model_dump_json())
    monkeypatch.setattr(guard, "_validate_fixture", lambda _: None)
    env = Environment(protocol)
    def clock():
        return local(27, 16, 5)
    return tmp_path, envelope, env, clock


def invoke(case, **kwargs):
    root, _, env, clock = case
    return runner.run(scope_path="scope.json", approval_path="approval.json",
                      root=root, environment=env, clock=clock, **kwargs)


def receipt(case):
    root, envelope, _, _ = case
    return json.loads((root / ".release/r2d-executions" /
                       (envelope.scope_sha256 + ".receipt.json")).read_text())


def test_readonly_then_success_and_duplicate(case):
    assert invoke(case)["status"] == "READY_TO_START"
    assert not (case[0] / ".release").exists()
    assert invoke(case, execute=True)["status"] == "STARTED"
    assert receipt(case)["status"] == "STARTED"
    with pytest.raises(contract.ContractError, match="already consumed"):
        invoke(case, execute=True)
    assert case[2].start_calls == 1
    assert case[2].rollback_calls == 0


@pytest.mark.parametrize("kind", ["start_error", "broken_candidate_mount"])
def test_unknown_or_written_candidate_never_rolls_back(case, kind):
    setattr(case[2], kind, True)
    with pytest.raises((RuntimeError, guard.base.GuardError)):
        invoke(case, execute=True)
    assert receipt(case)["status"] == "UNKNOWN_AFTER_DISPATCH"
    assert receipt(case)["dispatch_barrier_written"] is True
    assert case[2].rollback_calls == 0
    with pytest.raises(contract.ContractError, match="already consumed"):
        invoke(case, execute=True)


@pytest.mark.parametrize("kind", ["container", "restart", "mount", "state", "audit",
                                 "future", "stale", "target_write", "git", "forward"])
def test_dynamic_drift_consumes_once_without_start(case, kind):
    env = case[2]
    if kind == "container":
        env.running = replace(env.running, container_id="a" * 64)
    elif kind == "restart":
        env.running = replace(env.running, restart_count=1)
    elif kind == "mount":
        env.running = replace(env.running, mount_destinations=("/workspace/data",))
    elif kind == "state":
        env.hashes = ("a" * 64, env.hashes[1])
    elif kind == "audit":
        env.hashes = (env.hashes[0], "a" * 64)
    elif kind == "future":
        env.health["updated_at"] = "2026-08-27T08:06:00+00:00"
    elif kind == "stale":
        env.health["updated_at"] = "2026-08-27T06:00:00+00:00"
    elif kind == "target_write":
        env.target_counts["paper"] = 1
    elif kind == "git":
        env.git["head"] = "a" * 40
    elif kind == "forward":
        env.forwards["model_baseline"]["artifact_sha256"] = "a" * 64
    with pytest.raises((contract.ContractError, guard.base.GuardError)):
        invoke(case, execute=True)
    assert receipt(case)["status"] == "BLOCKED_BEFORE_DISPATCH"
    assert env.start_calls == env.rollback_calls == 0


def test_final_deadline_after_preflight_blocks_dispatch(case):
    moment = [case[3]()]
    case[2].hook = lambda: moment.__setitem__(0, local(27, 19, 1))
    case = (*case[:3], lambda: moment[0])
    with pytest.raises(guard.base.GuardError):
        invoke(case, execute=True)
    assert case[2].start_calls == 0
    assert receipt(case)["status"] == "UNKNOWN_AFTER_DISPATCH"


@pytest.mark.parametrize("offset", [-10, 180, 1440])
def test_expired_or_early_window_has_no_claim(case, offset):
    case = (*case[:3], lambda: local(27, 16, 5) + timedelta(minutes=offset))
    with pytest.raises(guard.base.GuardError):
        invoke(case, execute=True)
    assert not (case[0] / ".release").exists()


def test_missing_approval_before_adapter(case, monkeypatch):
    monkeypatch.setattr(runner, "SecureEnvironment", lambda *_: pytest.fail("host accessed"))
    with pytest.raises(contract.ContractError, match="exact approval"):
        runner.run(root=case[0], scope_path="scope.json", execute=True)


def test_foreign_approval_and_tampered_scope(case):
    root = case[0]
    approval = json.loads((root / "approval.json").read_text())
    approval["scope_sha256"] = "0" * 64
    (root / "approval.json").write_text(json.dumps(approval))
    with pytest.raises(contract.ContractError, match="does not match"):
        invoke(case, execute=True)
    value = json.loads((root / "scope.json").read_text())
    value["scope"]["git_head"] = "0" * 40
    (root / "scope.json").write_text(json.dumps(value))
    with pytest.raises(contract.ContractError, match="scope hash"):
        invoke(case)
    assert not (root / ".release").exists()


def test_protocol_tamper_before_and_after_claim(case):
    root = case[0]
    path = root / "config/r2d_synthetic.yaml"
    case[2].hook = lambda: path.write_text(path.read_text() + "\n# drift\n")
    with pytest.raises(contract.ContractError, match="protocol file hash"):
        invoke(case, execute=True)
    assert case[2].start_calls == 0


def test_global_lock_rejects_other_execution_and_crash_claim(case):
    root, envelope, _, _ = case
    with contract.execution_claim(root, envelope, "a" * 64):
        other_scope = envelope.scope.model_copy(update={"git_head": "0" * 40})
        other = contract.ScopeEnvelope(scope=other_scope,
                                      scope_sha256=contract.scope_hash(other_scope))
        with pytest.raises(contract.ContractError, match="in progress"):
            with contract.execution_claim(root, other, "a" * 64):
                pytest.fail("concurrent execution")
    assert receipt(case)["status"] == "BLOCKED_BEFORE_DISPATCH"


def test_abandoned_claim_without_receipt_is_not_retryable(case):
    root, envelope, _, _ = case
    directory = root / ".release/r2d-executions"
    directory.mkdir(parents=True)
    contract.ExecutionClaim(directory, envelope, "a" * 64)
    with pytest.raises(contract.ContractError, match="already consumed"):
        invoke(case, execute=True)
    assert case[2].start_calls == 0


def test_cli_sanitizes_nested_errors(monkeypatch, capsys):
    def fail(**_):
        raise RuntimeError("synthetic-sensitive-sentinel")
    monkeypatch.setattr(runner, "run", fail)
    assert runner.main(["--scope", "scope.json", "--execute"]) == 2
    output = capsys.readouterr().out
    assert "RuntimeError" in output and "sentinel" not in output


@pytest.mark.parametrize("barrier", [False, True])
def test_real_child_crash_leaves_durable_unrepeatable_claim(case, barrier):
    root, envelope, _, _ = case
    code = (
        "import os,sys; from pathlib import Path; "
        "from shaiwei.r2d_execution_contract import load_scope,execution_claim; "
        "root=Path(sys.argv[1]); envelope=load_scope(root,'scope.json'); "
        "context=execution_claim(root,envelope,'a'*64); claim=context.__enter__(); "
        + ("claim.dispatch_barrier(); " if barrier else "") + "os._exit(17)"
    )
    result = subprocess.run([sys.executable, "-c", code, str(root)], capture_output=True)
    assert result.returncode == 17
    directory = root / ".release/r2d-executions"
    assert (directory / (envelope.scope_sha256 + ".claim.json")).is_file()
    assert not (directory / (envelope.scope_sha256 + ".receipt.json")).exists()
    assert (directory / (envelope.scope_sha256 + ".write-barrier.json")).exists() is barrier
    with pytest.raises(contract.ContractError, match="already consumed"):
        invoke(case, execute=True)
    assert case[2].start_calls == 0


def test_cli_to_actual_contract_success_and_rejection(case, monkeypatch, capsys):
    real_run = runner.run
    def bound(**kwargs):
        return real_run(**kwargs, root=case[0], environment=case[2], clock=case[3])
    monkeypatch.setattr(runner, "run", bound)
    argv = ["--scope", "scope.json", "--approval", "approval.json", "--execute"]
    assert runner.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "STARTED"
    assert runner.main(argv) == 2
    assert json.loads(capsys.readouterr().out)["error_class"] == "ContractError"
    assert case[2].start_calls == 1


def test_execution_resource_is_local_only_and_registered():
    from shaiwei.storage.lock_resources import R2D_RELEASE_EXECUTION, resource_spec
    assert resource_spec(R2D_RELEASE_EXECUTION).local_only
    assert resource_spec(R2D_RELEASE_EXECUTION).rank == 5


def test_secret_path_cannot_be_used_as_scope_or_approval(case):
    with pytest.raises(contract.ContractError, match="JSON file"):
        contract.load_scope(case[0], ".env")
    with pytest.raises(contract.ContractError, match="JSON file"):
        contract.validate_approval(case[0], ".env", case[1])


def test_execution_lock_symlink_is_rejected_without_opening(case):
    from shaiwei.storage.interprocess_lock import _lock_path
    from shaiwei.storage.lock_resources import R2D_RELEASE_EXECUTION
    directory = case[0] / ".release/r2d-executions"
    directory.mkdir(parents=True)
    _lock_path(directory, R2D_RELEASE_EXECUTION).symlink_to(directory / "missing-secret")
    with pytest.raises(ValueError, match="symlink"):
        invoke(case, execute=True)
    assert case[2].start_calls == 0


def test_candidate_tag_drift_in_final_callback_blocks_start(case):
    def drift():
        case[2].candidate = {**case[2].candidate, "image_id": "sha256:" + "0" * 64}
    case[2].hook = drift
    with pytest.raises(guard.base.GuardError, match="candidate image"):
        invoke(case, execute=True)
    assert case[2].start_calls == 0
    assert receipt(case)["status"] == "UNKNOWN_AFTER_DISPATCH"
