from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
import yaml

from shaiwei.research.capital_feasibility.delisting_independent_audit import (
    independently_evaluate,
)
from shaiwei.research.capital_feasibility.delisting_release_contract import (
    ACTION,
    FROZEN_COMPONENT_ASSET_IDENTITIES,
    FROZEN_COMPONENT_BUILD_SNAPSHOT_SHA256,
    FROZEN_REGISTRY_SHA256,
    IMAGE,
    ReleaseProtocol,
    ReleaseScope,
)
from shaiwei.research.capital_feasibility.delisting_release_fixture import (
    _synthetic,
    build_fixture,
)
from shaiwei.research.capital_feasibility.delisting_release_builder import (
    _component_identity,
)
from shaiwei.research.capital_feasibility.delisting_release_metrics import evaluate
from shaiwei.research.capital_feasibility.delisting_release_simulation import run_all
from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.production_conversion.contract import ProtocolError


ROOT = Path(__file__).parents[1]
COMPOSE = ROOT / "compose.m6-head30-delisting-risk-release.yaml"


def test_protocol_is_claim_first_post_hoc_and_non_production() -> None:
    protocol = ReleaseProtocol.load()
    claim = protocol.document["attempt_claim"]
    authority = protocol.document["authority_before_exact_user_approval"]

    assert protocol.document["execution"]["action"] == ACTION
    assert claim["family_attempts_before_run"] == 0
    assert claim["family_attempts_after_claim"] == 1
    assert claim["receipt_before_effect_read"] is True
    assert claim["same_scope_retry_authorized"] is False
    assert authority["real_target_read_authorized"] is False
    assert authority["real_price_read_authorized"] is False
    assert authority["real_effect_read_authorized"] is False
    assert authority["canonical_ledger_write_authorized"] is False
    assert authority["production_authorization"] == "none"
    assert len(protocol.recovery_sha256) == 64
    assert len(protocol.scope_runtime_recovery_sha256) == 64
    assert IMAGE == "shaiwei:m6-head30-delisting-risk-release-r2-v1"


def test_recovery_context_is_minimal_and_global_ignore_is_untouched() -> None:
    dedicated = ROOT / "Dockerfile.m6-head30-delisting-risk-release.dockerignore"
    lines = dedicated.read_text(encoding="utf-8").splitlines()
    allowed_docs = sorted(line[1:] for line in lines if line.startswith("!docs/") and line != "!docs/")

    assert allowed_docs == [
        "docs/EFFECT_ATTEMPT_CLAIM_GATE_ACCEPTANCE_20260823.md",
        "docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_EXECUTION_ADAPTER_ACCEPTANCE_20260823.md",
        "docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_METHOD_ACCEPTANCE_20260823.md",
    ]
    dockerfile = (ROOT / "Dockerfile.m6-head30-delisting-risk-release").read_text(
        encoding="utf-8"
    )
    assert all(f"COPY {path} ./{path}" in dockerfile for path in allowed_docs)
    assert "!docs/M6_CSI800_PRODUCTION_HEAD30_DELISTING_RISK_METHOD" not in (
        ROOT / ".dockerignore"
    ).read_text(encoding="utf-8")


def test_synthetic_risk_exit_is_pit_deterministic_and_independently_rebuilt() -> None:
    bundle, sources = _synthetic()
    first = run_all(bundle, sources)
    first["result"] = evaluate(first)
    replay = run_all(bundle, sources)
    replay["result"] = evaluate(replay)
    rebuilt = independently_evaluate(first)

    assert first == replay
    assert canonical_sha256(first["result"]) == canonical_sha256(rebuilt)
    assert first["result"]["risk_exit"]["order_count"] == 6
    for window in first["windows"].values():
        exits = [row for row in window["risk_trace"] if row["risk_orders"]]
        assert len(exits) == 1
        assert exits[0]["as_of"] < exits[0]["execution_date"]
        assert exits[0]["risk_orders"][0]["execution_reason"] == (
            "DELISTING_PRICE_RISK_EXIT"
        )


def test_independent_auditor_rejects_risk_decision_tampering() -> None:
    bundle, sources = _synthetic()
    result = run_all(bundle, sources)
    tampered = deepcopy(result)
    tampered["windows"]["W1"]["risk_trace"][0]["as_of"] = "20990101"

    with pytest.raises(ProtocolError, match="risk clock"):
        independently_evaluate(tampered)


def test_synthetic_release_fixture_claims_before_reader_and_blocks_retry(
    tmp_path: Path,
) -> None:
    result = build_fixture(tmp_path)

    assert result["status"] == "PASS"
    assert result["claim_before_effect_reader"] is True
    assert result["same_scope_retry_blocked"] is True
    assert result["canonical_ledger_write"] is False
    assert result["real_target_or_price_or_effect_read"] is False
    assert result["release_scope_loader_pass"] is True


def test_scope_loader_recomputes_scoped_build_identity(tmp_path: Path) -> None:
    build_fixture(tmp_path)
    path = tmp_path / "release-scope.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["scope"]["implementation"]["build_assets"][0]["sha256"] = "e" * 64
    document["release_scope_sha256"] = canonical_sha256(document["scope"])
    path.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ProtocolError, match="component build identity"):
        ReleaseScope.load(path, ReleaseProtocol.load())


def test_closed_scope_uses_its_frozen_registry_and_component_assets() -> None:
    protocol = ReleaseProtocol.load()
    release = ReleaseScope.load(
        ROOT / "config/m6_csi800_production_head30_delisting_risk_release_scope_r2_v1.json",
        protocol,
    )

    assert release.scope["implementation"]["registry_sha256"] == (
        FROZEN_REGISTRY_SHA256
    )
    assert tuple(
        (row["path"], row["sha256"])
        for row in release.scope["implementation"]["build_assets"]
    ) == FROZEN_COMPONENT_ASSET_IDENTITIES
    assert release.scope["implementation"]["component_build_snapshot_sha256"] == (
        FROZEN_COMPONENT_BUILD_SNAPSHOT_SHA256
    )


def test_closed_component_cannot_form_a_new_release() -> None:
    with pytest.raises(ProtocolError, match="component is closed"):
        _component_identity()


def test_compose_has_narrow_mounts_and_auditor_has_no_raw_or_r2() -> None:
    document = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    services = document["services"]
    runner = services["runner"]
    auditor = services["auditor"]

    assert services["fixture"]["image"].endswith("-r2-v1")
    assert "release_scope_r2_v1.json" in runner["volumes"][0]["source"]
    assert "delisting-risk-approval-r2.json" in runner["volumes"][1]["source"]

    for service in services.values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
    runner_mounts = {row["target"]: row for row in runner["volumes"]}
    auditor_mounts = {row["target"]: row for row in auditor["volumes"]}
    assert runner_mounts["/workspace/ledger/experiments.csv"]["read_only"] is False
    assert auditor_mounts["/workspace/ledger/experiments.csv"]["read_only"] is True
    assert "/inputs/r2" not in auditor_mounts
    assert "/workspace/data/raw" not in auditor_mounts
    assert all(".env" not in row["source"] for service in services.values() for row in service["volumes"])


def test_new_release_modules_stay_bounded_and_auditor_is_independent() -> None:
    modules = [
        ROOT / "src/shaiwei/research/capital_feasibility/delisting_release_contract.py",
        ROOT / "src/shaiwei/research/capital_feasibility/delisting_release_recovery_contract.py",
        ROOT / "src/shaiwei/research/capital_feasibility/delisting_release_builder.py",
        ROOT / "src/shaiwei/research/capital_feasibility/delisting_release_run.py",
        ROOT / "src/shaiwei/research/capital_feasibility/delisting_release_audit.py",
        ROOT / "src/shaiwei/research/capital_feasibility/delisting_release_fixture.py",
        ROOT / "src/shaiwei/research/capital_feasibility/delisting_release_simulation.py",
        ROOT / "src/shaiwei/research/capital_feasibility/delisting_independent_audit.py",
    ]
    assert all(len(path.read_text(encoding="utf-8").splitlines()) <= 400 for path in modules)
    auditor = (ROOT / "src/shaiwei/research/capital_feasibility/delisting_release_audit.py").read_text(
        encoding="utf-8"
    )
    assert "delisting_release_simulation" not in auditor
    assert "delisting_release_metrics" not in auditor
    assert "evaluate_risk_overlay" not in auditor
