from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
PATH = ROOT / "config/m6_csi800_topk20_conversion_engineering_v1.yaml"


def _load() -> dict:
    document = yaml.safe_load(PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m6_3b_predecessor_is_exact_pushed_and_preserved() -> None:
    predecessor = _load()["predecessor"]

    assert predecessor["git_commit"] == "931d6334d9996cc27fdcc1f327d6dac93fab005c"
    assert _sha256(ROOT / predecessor["config_path"]) == predecessor["config_sha256"]
    assert _sha256(ROOT / predecessor["document_path"]) == predecessor["document_sha256"]
    assert predecessor["preserve_without_rewrite"] is True


def test_m6_3b_is_synthetic_engineering_only() -> None:
    document = _load()
    authority = document["authority"]

    assert document["stage"] == "RESULT_BLIND_SYNTHETIC_ENGINEERING_ONLY"
    assert {key for key, value in authority.items() if value is True} == {
        "engineering_implementation_authorized",
        "synthetic_fixture_authorized",
        "immutable_engineering_image_build_authorized",
        "dependency_build_network_only",
    }
    assert authority["production_authorization"] == "none"
    assert authority["tushare_calls"] == authority["deepseek_calls"] == 0


def test_m6_3b_architecture_is_split_without_model_or_primary_audit_coupling() -> None:
    architecture = _load()["architecture"]

    assert architecture["package"] == "src/shaiwei/research/topk_conversion"
    assert set(architecture["modules"]) == {
        "schema",
        "contract",
        "execution",
        "metrics",
        "artifacts",
        "synthetic",
        "audit_statistics",
        "audit",
    }
    assert "shaiwei.research.model_attribution.models" in architecture[
        "forbidden_imports_in_execution_or_metrics"
    ]
    assert "shaiwei.research.topk_conversion.metrics" in architecture[
        "independent_auditor_forbidden_imports"
    ]
    assert architecture["new_production_module_soft_limit_lines"] == 400
    assert architecture["new_production_module_hard_limit_lines"] == 600


def test_m6_3b_fixture_and_failure_matrix_are_complete() -> None:
    document = _load()
    fixture = document["synthetic_contract"]

    assert fixture["seed"] == 20260807
    assert fixture["topk_values"] == [30, 20]
    assert fixture["daily_rows_per_window"] == 40
    assert fixture["fixture_cases"] == [
        "TOPK20_CONVERSION_SUPPORTED",
        "TOPK20_CONVERSION_NOT_SUPPORTED",
        "MIXED_NOT_CONCLUSIVE",
        "BLOCKED",
    ]
    assert len(document["failure_closed_checks"]) == 15


def test_m6_3b_docker_has_no_real_data_or_project_mount() -> None:
    docker = _load()["docker"]

    assert docker["compose_file"] == "compose.m6-topk-conversion.yaml"
    assert docker["network_mode"] == "none"
    assert docker["read_only_root"] is True
    assert docker["docker_socket_mounted"] is False
    assert docker["env_file_mounted"] is False
    assert docker["full_project_root_mounted"] is False
    assert docker["qlib_or_m6_effect_mounted"] is False
    assert docker["scheduler_change_or_restart"] is False


def test_m6_3b_stops_before_real_effect() -> None:
    document = _load()

    assert document["outputs"]["real_model_prediction_nav_trade_or_holding_outputs"] == 0
    assert document["outputs"]["experiment_ledger_rows"] == 0
    assert document["stop_condition"] == {
        "stop_after_engineering_go": True,
        "real_effect_release_requires_new_target_exact_scope_and_user_authorization": True,
        "no_authority_inheritance_from_m6_3a_or_m6_3b": True,
        "production_authorization": "none",
    }
