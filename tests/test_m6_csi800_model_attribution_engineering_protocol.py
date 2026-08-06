from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
PATH = ROOT / "config/m6_csi800_model_attribution_engineering_v1.yaml"


def _document() -> dict:
    return yaml.safe_load(PATH.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m6_1_predecessor_is_exact_and_preserved() -> None:
    predecessor = _document()["predecessor"]
    assert predecessor["git_commit"] == "262d941baa97c4aae4ddf57ed2950529d307dca3"
    assert _sha256(ROOT / predecessor["config_path"]) == predecessor["config_sha256"]
    assert _sha256(ROOT / predecessor["document_path"]) == predecessor["document_sha256"]
    assert predecessor["preserve_without_rewrite"] is True


def test_m6_1_is_synthetic_engineering_only() -> None:
    document = _document()
    authority = document["authority"]
    assert document["stage"] == "RESULT_BLIND_ENGINEERING_ONLY"
    true_values = {key for key, value in authority.items() if value is True}
    assert true_values == {
        "engineering_implementation_authorized",
        "synthetic_fixture_authorized",
        "qlib_manifest_metadata_read_authorized",
        "qlib_calendar_read_authorized",
        "dependency_build_network_only",
    }
    assert authority["production_authorization"] == "none"
    assert authority["tushare_calls"] == authority["deepseek_calls"] == 0


def test_m6_1_architecture_is_split_and_bounded() -> None:
    architecture = _document()["architecture"]
    assert architecture["package"] == "src/shaiwei/research/model_attribution"
    assert set(architecture["modules"]) == {
        "contract",
        "clock",
        "models",
        "scoring",
        "inference",
        "synthetic",
        "audit",
    }
    assert architecture["new_production_module_soft_limit_lines"] == 400
    assert architecture["new_production_module_hard_limit_lines"] == 600
    assert architecture["no_new_runtime_dependency"] is True


def test_m6_1_fixture_and_failure_matrix_are_complete() -> None:
    document = _document()
    fixture = document["synthetic_contract"]
    assert fixture["seed"] == 20260806
    assert fixture["mature_score_days_per_window"] == 210
    assert fixture["instruments_per_day"] == 40
    assert fixture["fixture_cases"] == [
        "MODEL_STRUCTURE_SUPPORTED",
        "PORTFOLIO_CONVERSION_BOTTLENECK_INDICATED",
        "FEATURE_INFORMATION_BOTTLENECK_INDICATED",
        "MIXED_NOT_CONCLUSIVE",
        "BLOCKED",
    ]
    assert len(document["failure_closed_checks"]) == 12


def test_m6_1_docker_mounts_are_narrow_and_runtime_is_offline() -> None:
    docker = _document()["docker"]
    assert docker["network_mode"] == "none"
    assert docker["read_only_root"] is True
    assert docker["docker_socket_mounted"] is False
    assert docker["env_file_mounted"] is False
    assert docker["full_project_root_mounted"] is False
    assert docker["semantic_market_data_mounted"] is False
    assert docker["read_only_inputs"] == [
        "data/qlib_bin/_shaiwei_manifest.json",
        "data/qlib_bin/calendars/day.txt",
    ]
    assert docker["scheduler_change_or_restart"] is False


def test_m6_1_stops_before_real_release() -> None:
    document = _document()
    assert document["result_goal"]["strategy_effective_at_every_outcome"] == "NOT_EVALUATED"
    assert document["outputs"]["real_model_prediction_nav_trade_or_holding_outputs"] == 0
    assert document["stop_condition"] == {
        "stop_after_engineering_go": True,
        "m6_2_real_release_requires_new_target_and_explicit_authorization": True,
        "no_authority_inheritance_from_m6_0_or_m6_1": True,
    }
