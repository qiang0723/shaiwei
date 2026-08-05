from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from fastapi.testclient import TestClient
import pytest
import yaml

from shaiwei.web.api import create_app
from shaiwei.web.strategy_factory import load_strategy_factory
from shaiwei.web.strategy_factory_contract import StrategyFactoryContractError
from shaiwei.web.strategy_factory_projection import build_strategy_factory_projection


ROOT = Path(__file__).parents[1]
CONFIG = Path("config/m5_strategy_factory_v1.yaml")
OUTPUT = Path("data/web/research_snapshots/strategy_factory")


def _fixture_root(tmp_path: Path) -> Path:
    document = yaml.safe_load((ROOT / CONFIG).read_text(encoding="utf-8"))
    relative_paths = {CONFIG, Path(document["protocol"]["path"])}
    relative_paths.update(Path(item["path"]) for item in document["evidence_sources"])
    for relative in relative_paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    return tmp_path


def _replace_evidence_hash(root: Path, evidence_id: str) -> None:
    config_path = root / CONFIG
    document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    source = next(item for item in document["evidence_sources"] if item["evidence_id"] == evidence_id)
    source["sha256"] = hashlib.sha256((root / source["path"]).read_bytes()).hexdigest()
    config_path.write_text(yaml.safe_dump(document, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_projection_is_source_backed_deterministic_and_read_only(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    first = build_strategy_factory_projection(root, OUTPUT)
    snapshot = root / OUTPUT / first.snapshot_path
    pointer = root / OUTPUT / "latest.json"
    before = (snapshot.read_bytes(), pointer.read_bytes())

    second = build_strategy_factory_projection(root, OUTPUT)
    assert second == first
    assert (snapshot.read_bytes(), pointer.read_bytes()) == before

    bundle = load_strategy_factory(project_root=root, output_root=OUTPUT)
    summary = bundle.data["summary"]
    assert summary["registered_universe_count"] == 8
    assert summary["research_eligible_universe_count"] == 5
    assert summary["blocked_universe_count"] == 3
    assert summary["existing_production_strategy_count"] == 1
    assert summary["admitted_factor_count"] == 0
    assert summary["active_authorized_task_count"] == 0
    assert bundle.data["active_tasks"] == []
    assert bundle.data["invariants"]["external_calls_made"] == 0
    assert bundle.data["invariants"]["real_research_runs"] == 0


def test_projection_rejects_evidence_drift_and_symlinks(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    evidence = root / "docs/P0_FORWARD_ACCEPTANCE_20260722.md"
    evidence.write_text(evidence.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
    with pytest.raises(StrategyFactoryContractError, match="SHA-256"):
        build_strategy_factory_projection(root, OUTPUT)

    root = _fixture_root(tmp_path / "symlink")
    evidence = root / "docs/P0_FORWARD_ACCEPTANCE_20260722.md"
    target = root / "docs/target.md"
    target.write_bytes(evidence.read_bytes())
    evidence.unlink()
    evidence.symlink_to(target)
    with pytest.raises(StrategyFactoryContractError, match="symlink"):
        build_strategy_factory_projection(root, OUTPUT)


def test_projection_rejects_admission_and_m1_authority_conflicts(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path / "admission")
    ledger = root / "ledger/factor_admissions.csv"
    ledger.write_text(ledger.read_text(encoding="utf-8").replace(",false,", ",true,", 1), encoding="utf-8")
    _replace_evidence_hash(root, "factor_admissions")
    with pytest.raises(StrategyFactoryContractError, match="admission count"):
        build_strategy_factory_projection(root, OUTPUT)

    root = _fixture_root(tmp_path / "m1")
    registry_path = root / "config/m1_multi_universe_v1.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    registry["universes"][0]["display_name"] = "被篡改的股票池"
    registry_path.write_text(yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8")
    _replace_evidence_hash(root, "m1_registry")
    with pytest.raises(StrategyFactoryContractError, match="M1 identity drift"):
        build_strategy_factory_projection(root, OUTPUT)


def test_query_rejects_pointer_tamper(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    build_strategy_factory_projection(root, OUTPUT)
    pointer_path = root / OUTPUT / "latest.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["snapshot_sha256"] = "0" * 64
    pointer_path.chmod(0o644)
    pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    with pytest.raises(Exception, match="哈希不匹配"):
        load_strategy_factory(project_root=root, output_root=OUTPUT)


def test_strategy_factory_api_is_atomic_and_get_head_only(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    build_strategy_factory_projection(root, OUTPUT)
    client = TestClient(create_app(project_root=root))

    response = client.get("/api/v1/strategy-factory")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "web-v1"
    assert payload["data"]["summary"]["registered_program_count"] == 8
    assert payload["data"]["draft_template"]["status"] == "DRAFT_NOT_SUBMITTED"
    assert response.headers["etag"] == f'"{payload["meta"]["snapshot_id"]}"'

    head = client.head("/api/v1/strategy-factory")
    assert head.status_code == 200
    assert head.content == b""
    assert client.get("/api/v1/strategy-factory?sort=return").status_code == 422
    assert client.post("/api/v1/strategy-factory").status_code == 405
