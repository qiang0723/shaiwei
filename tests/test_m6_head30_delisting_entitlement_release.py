from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
import yaml

from shaiwei.paper.risk_exit_engine import execute_paper_day
from shaiwei.research.capital_feasibility.delisting_release_fixture import _synthetic
from shaiwei.research.capital_feasibility.delisting_release_simulation import run_all
from shaiwei.research.capital_feasibility.entitlement_release.contract import (
    ACTION,
    COMPONENT_ID,
    IMAGE,
    ReleaseProtocol,
    ReleaseScope,
)
from shaiwei.research.capital_feasibility.entitlement_release.fixture import build_fixture
from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.production_conversion.contract import ProtocolError


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.m6-head30-delisting-entitlement-release.yaml"


def test_protocol_freezes_ordinal_two_parent_and_no_real_authority() -> None:
    protocol = ReleaseProtocol.load()
    claim = protocol.document["attempt_claim"]
    authority = protocol.document["authority_before_exact_user_approval"]

    assert claim["attempt_ordinal"] == 2
    assert claim["parent_experiment_id"] == "6797875cf3c0"
    assert claim["family_attempts_before_run"] == 1
    assert claim["family_attempts_after_claim"] == 2
    assert protocol.document["release"]["approval_action"] == ACTION
    assert protocol.document["release"]["component_id"] == COMPONENT_ID
    assert IMAGE.endswith("entitlement-release-v1")
    assert authority["real_effect_read_authorized"] is False
    assert authority["canonical_ledger_write_authorized"] is False
    assert authority["production_authorization"] == "none"


def test_protocol_rejects_authority_broadening(tmp_path: Path) -> None:
    document = yaml.safe_load(ReleaseProtocol.load().path.read_text(encoding="utf-8"))
    document["authority_before_exact_user_approval"]["real_effect_read_authorized"] = True
    path = tmp_path / "changed.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")

    with pytest.raises(ProtocolError, match="authority was broadened"):
        ReleaseProtocol.load(path)


def test_legacy_simulation_default_and_explicit_executor_are_identical() -> None:
    bundle, sources = _synthetic()

    assert run_all(bundle, sources) == run_all(
        bundle,
        sources,
        day_executor=execute_paper_day,
    )


def test_synthetic_fixture_proves_detached_round_trip_and_claim_lineage(
    tmp_path: Path,
) -> None:
    result = build_fixture(tmp_path)

    assert result["status"] == "PASS"
    assert result["detached_entitlement_round_trip_pass"] is True
    assert result["attempt_ordinal"] == 2
    assert result["parent_experiment_id"] == "6797875cf3c0"
    assert result["internal_replay_pass"] is True
    assert result["independent_reconstruction_pass"] is True
    assert result["real_target_or_price_or_effect_read"] is False
    assert result["canonical_ledger_write"] is False


def test_scope_loader_rejects_component_identity_tampering(tmp_path: Path) -> None:
    build_fixture(tmp_path)
    path = tmp_path / "release-scope.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    changed = deepcopy(document)
    changed["scope"]["implementation"]["build_assets"][0]["sha256"] = "e" * 64
    changed["release_scope_sha256"] = canonical_sha256(changed["scope"])
    path.write_text(json.dumps(changed, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ProtocolError, match="component identity"):
        ReleaseScope.load(path, ReleaseProtocol.load())


def test_compose_is_isolated_and_auditor_has_no_raw_or_r2() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    services = document["services"]
    runner = services["runner"]
    auditor = services["auditor"]

    for service in services.values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert all(".env" not in row["source"] for row in service["volumes"])
    runner_mounts = {row["target"]: row for row in runner["volumes"]}
    auditor_mounts = {row["target"]: row for row in auditor["volumes"]}
    assert runner_mounts["/workspace/ledger/experiments.csv"]["read_only"] is False
    assert auditor_mounts["/workspace/ledger/experiments.csv"]["read_only"] is True
    assert "/inputs/r2" not in auditor_mounts
    assert "/workspace/data/raw" not in auditor_mounts


def test_successor_modules_are_bounded_and_auditor_stays_artifact_only() -> None:
    root = ROOT / "src/shaiwei/research/capital_feasibility/entitlement_release"
    modules = list(root.glob("*.py"))
    assert modules
    assert all(len(path.read_text(encoding="utf-8").splitlines()) <= 400 for path in modules)
    auditor = (root / "audit.py").read_text(encoding="utf-8")
    assert "delisting_release_simulation" not in auditor
    assert "delisting_release_metrics" not in auditor
    assert "execute_entitlement_recovery_day" not in auditor
