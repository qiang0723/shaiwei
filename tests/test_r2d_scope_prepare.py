"""ADR 0016 §11 E2：scope 生成与批准转录。合成环境，无 Docker、无真实 scope、无生产数据。"""

import json

import pytest
import yaml

from shaiwei import r2d_authorized_start as runner
from shaiwei import r2d_execution_contract as contract
from shaiwei import r2d_release_guard as guard
from shaiwei import r2d_scope_prepare as tool
from test_r2d_authorized_start import Environment
from test_r2d_release_guard import local, recovery_protocol_document


@pytest.fixture
def world(tmp_path, monkeypatch):
    document = recovery_protocol_document()
    document["controller_identity"]["component_paths"] = sorted(runner.REQUIRED_COMPONENTS)
    document["expected_legacy_mounts_before_prepare"].append("/run/shaiwei-locks")
    protocol = guard.GuardProtocol.model_validate(document)
    (tmp_path / "config").mkdir()
    (tmp_path / "config/r2d_synthetic.yaml").write_text(yaml.safe_dump(protocol.model_dump(mode="json")))
    monkeypatch.setattr(guard, "_validate_fixture", lambda _: None)
    return tmp_path, Environment(protocol)


def _prepare(world):
    root, env = world
    return tool.prepare(root, "config/r2d_synthetic.yaml", "synthetic", env)


def test_prepare_writes_one_bound_scope_and_returns_exact_approval_text(world):
    root, env = world
    result = _prepare(world)
    assert result["status"] == "SCOPE_PREPARED_NOT_APPROVED"
    envelope = contract.load_scope(root, result["scope_path"])
    scope = envelope.scope
    assert envelope.scope_sha256 == result["scope_sha256"] == contract.scope_hash(scope)
    assert scope.legacy_container_id == env.running.container_id
    assert (scope.state_sha256, scope.audit_sha256) == env.hashes
    assert scope.git_head == scope.origin_main == env.git["head"]
    assert scope.rollback_policy == "FORBID_AFTER_DISPATCH"
    assert result["approval_text"] == contract.approval_text(result["scope_sha256"])
    assert not (root / tool.APPROVAL_DIR).exists()
    with pytest.raises(contract.ContractError, match="already prepared"):
        _prepare(world)


def test_prepare_refuses_when_head_is_not_pushed(world):
    world[1].git["origin_main"] = "0" * 40
    with pytest.raises(contract.ContractError, match="origin/main"):
        _prepare(world)
    assert not (world[0] / tool.SCOPE_DIR).exists()


def test_prepare_refuses_protocol_without_noop_boundary_or_four_mounts(world):
    root, _ = world
    document = yaml.safe_load((root / "config/r2d_synthetic.yaml").read_text())
    document["expected_legacy_mounts_before_prepare"].remove("/run/shaiwei-locks")
    (root / "config/r2d_synthetic.yaml").write_text(yaml.safe_dump(document))
    with pytest.raises(contract.ContractError, match="four frozen mounts"):
        _prepare(world)


def test_record_approval_transcribes_only_the_exact_text(world):
    root, _ = world
    result = _prepare(world)
    for wrong in ("批准", result["approval_text"] + " ", result["approval_text"].replace("仅", "")):
        with pytest.raises(contract.ContractError, match="exact verbatim"):
            tool.record_approval(root, result["scope_path"], wrong)
    recorded = tool.record_approval(root, result["scope_path"], result["approval_text"])
    envelope = contract.load_scope(root, result["scope_path"])
    assert contract.validate_approval(root, recorded["approval_path"], envelope)
    with pytest.raises(contract.ContractError, match="already recorded"):
        tool.record_approval(root, result["scope_path"], result["approval_text"])


def test_prepared_scope_and_approval_drive_the_existing_authorized_start(world):
    root, env = world
    result = _prepare(world)
    recorded = tool.record_approval(root, result["scope_path"], result["approval_text"])
    outcome = runner.run(
        scope_path=result["scope_path"], approval_path=recorded["approval_path"], execute=True,
        root=root, environment=env, clock=lambda: local(27, 16, 5),
    )
    assert outcome["status"] == "STARTED"
    assert env.start_calls == 1 and env.rollback_calls == 0


def test_cli_reports_blocked_without_echoing_inputs(monkeypatch, capsys):
    def boom(*_args, **_kwargs):
        raise contract.ContractError("scope requires HEAD to equal the local origin/main")

    monkeypatch.setattr(tool, "prepare", boom)
    assert tool.main(["prepare", "--protocol", "config/r2d_x.yaml"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "BLOCKED" and payload["error_class"] == "ContractError"
