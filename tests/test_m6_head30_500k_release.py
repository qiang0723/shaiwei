from __future__ import annotations

import ast
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.capital_feasibility.raw_manifest import REQUIRED_APIS, build_manifest_document
from shaiwei.research.capital_feasibility.release_contract import ReleaseProtocol
from shaiwei.research.capital_feasibility.release_fixture import build_fixture
from shaiwei.research.capital_feasibility.simulation import frozen_policy
from shaiwei.paper.engine import policy_sha256
from shaiwei.research.production_conversion.contract import ProtocolError


ROOT = PROJECT_ROOT


def test_recovery_protocol_preserves_result_blind_boundary() -> None:
    protocol = ReleaseProtocol.load()
    ruling = protocol.recovery["recovery_ruling"]
    assert ruling["family_attempts_before_future_authorized_real_run"] == 1
    assert ruling["total_family_attempts_after_future_authorized_real_run"] == 2
    assert ruling["result_metrics_remain_blind"] is True
    assert ruling["further_real_target_price_or_effect_read_before_approval"] is False
    assert protocol.document["production_authorization"] == "none"


def test_recovery_protocol_mutation_fails_closed(tmp_path: Path) -> None:
    base = yaml.safe_load((ROOT / "config/m6_csi800_production_head30_500k_release_v1.yaml").read_text())
    recovery = yaml.safe_load((ROOT / "config/m6_csi800_production_head30_500k_target_read_recovery_v1.yaml").read_text())
    recovery["recovery_ruling"]["family_attempts_before_future_authorized_real_run"] = 0
    base_path, recovery_path = tmp_path / "base.yaml", tmp_path / "recovery.yaml"
    base_path.write_text(yaml.safe_dump(base), encoding="utf-8")
    from shaiwei.research.model_attribution.contract import sha256_file
    recovery["base_protocol"]["sha256"] = sha256_file(base_path)
    recovery_path.write_text(yaml.safe_dump(recovery), encoding="utf-8")
    with pytest.raises(ProtocolError, match="recovery protocol"):
        ReleaseProtocol.load(base_path, recovery_path)


def test_synthetic_release_uses_paper_engine_and_replays() -> None:
    evidence = build_fixture()
    assert evidence["status"] == "PASS"
    assert evidence["execute_day_reused"] is True
    assert evidence["deterministic_replay"] is True
    assert evidence["independent_reconstruction"] is True
    assert evidence["real_target_read"] is False
    assert evidence["real_price_or_effect_read"] is False
    assert policy_sha256(frozen_policy()) == (
        "eaa341b5a3eee94347c7a8453a3e52f1986e3707abfbb6bb69a6d9298c320cc8"
    )


def test_raw_manifest_build_is_metadata_only(tmp_path: Path) -> None:
    rows = []
    for index, api in enumerate(REQUIRED_APIS):
        rows.append({
            "source_api": api, "params_json": json.dumps({"part": index}),
            "ingest_time": "2026-08-20T00:00:00Z",
            "parquet_path": f"data/raw/{api.replace('.', '-')}/missing.parquet",
            "row_count": "1", "content_sha256": "a" * 64,
        })
    ledger = tmp_path / "ledger.csv"
    pd.DataFrame(rows).to_csv(ledger, index=False)
    document = build_manifest_document(ledger, project_root=tmp_path)
    assert document["entry_count"] == len(REQUIRED_APIS)
    assert document["semantic_values_read"] is False


def test_compose_enforces_runner_and_auditor_isolation() -> None:
    compose = yaml.safe_load((ROOT / "compose.m6-head30-500k-release.yaml").read_text())
    services = compose["services"]
    runner = services["m6-head30-500k-release-runner"]
    auditor = services["m6-head30-500k-release-auditor"]
    for service in services.values():
        assert service["network_mode"] == "none"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert "no-new-privileges:true" in service["security_opt"]
        assert "env_file" not in service
    runner_mounts = {row["target"]: row for row in runner["volumes"]}
    assert runner_mounts["/workspace/data/raw"]["read_only"] is True
    assert runner_mounts["/inputs/r2"]["read_only"] is True
    assert runner_mounts["/outputs"]["read_only"] is False
    auditor_targets = {row["target"] for row in auditor["volumes"]}
    assert "/workspace/data/raw" not in auditor_targets
    assert "/inputs/r2" not in auditor_targets
    assert "/outputs" in auditor_targets and "/audit" in auditor_targets


def test_independent_auditor_has_no_primary_metric_or_runner_import() -> None:
    path = ROOT / "src/shaiwei/research/capital_feasibility/release_audit.py"
    tree = ast.parse(path.read_text())
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    )
    assert not any("release_metrics" in name or "simulation" in name or "release_run" in name for name in imports)


def test_new_production_modules_remain_bounded() -> None:
    root = ROOT / "src/shaiwei/research/capital_feasibility"
    names = [
        "release_contract.py", "raw_manifest.py", "sealed_inputs.py", "source_reader.py",
        "simulation.py", "release_metrics.py", "audit_statistics.py", "release_run.py",
        "release_audit.py", "release_fixture.py", "release_builder.py",
    ]
    for name in names:
        assert len((root / name).read_text().splitlines()) <= 400, name
