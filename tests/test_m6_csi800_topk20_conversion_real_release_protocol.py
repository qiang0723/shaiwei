from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from shaiwei.config import PROJECT_ROOT


PROTOCOL = PROJECT_ROOT / "config/m6_csi800_topk20_conversion_real_release_v1.yaml"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load() -> dict:
    document = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def test_m6_3c_binds_result_blind_predecessors_and_sealed_effect() -> None:
    document = _load()
    predecessors = document["predecessors"]
    for key in ("result_protocol", "engineering_protocol", "engineering_manifest"):
        assert _sha(PROJECT_ROOT / predecessors[key]["path"]) == predecessors[key]["sha256"]
    effect = predecessors["authoritative_m6_effect"]
    assert effect["file_count"] == 199
    assert effect["byte_count"] == 84_957_571
    assert effect["first_pass_bundle_sha256"] == effect["replay_bundle_sha256"]
    assert predecessors["authoritative_m6_audit"]["independent_audit"] == "PASS"
    assert predecessors["preserve_without_rewrite"] is True


def test_m6_3c_preapproval_authority_is_result_blind() -> None:
    authority = _load()["authority_before_exact_user_approval"]
    expected_true = {
        "result_blind_implementation_authorized",
        "synthetic_fixture_authorized",
        "immutable_release_image_build_authorized",
        "exact_release_scope_generation_authorized",
        "dependency_build_network_only",
        "sealed_effect_metadata_identity_read_authorized",
    }
    assert {key for key, value in authority.items() if value is True} == expected_true
    assert authority["sealed_effect_semantic_read_authorized"] is False
    assert authority["qlib_provider_mount_or_read_authorized"] is False
    assert authority["real_top20_backtest_authorized"] is False
    assert authority["production_authorization"] == "none"
    assert authority["tushare_calls"] == authority["deepseek_calls"] == 0


def test_m6_3c_changes_only_topk_and_creates_no_model_attempt() -> None:
    document = _load()
    pipeline = document["real_pipeline"]
    assert pipeline["changed_variable"] == {
        "path": "portfolio.topk",
        "control": 30,
        "treatment": 20,
    }
    assert pipeline["new_model_fit_count"] == 0
    assert pipeline["new_prediction_generation_count"] == 0
    assert pipeline["forbidden_topk_values"] == [10, 15, 25]
    counting = document["execution_counting"]
    assert counting["runner_invocation_count"] == 1
    assert counting["complete_internal_passes"] == ["first_pass", "replay"]
    assert counting["portfolio_attempt_count_consumed_at_first_top20_effect_read"] == 2
    assert counting["model_attempt_increment"] == counting["factor_g1_attempt_increment"] == 0


def test_m6_3c_requires_top30_compatibility_before_top20() -> None:
    gate = _load()["compatibility_before_top20_result"]
    assert gate["verify_effect_tree_identity_before_semantic_read"] is True
    assert gate["reproduce_all_top30_reports_byte_semantically"] is True
    assert gate["top30_mismatch_outcome"] == "BLOCKED_PRE_EFFECT"
    assert gate["no_inner_join_or_tolerance_fallback"] is True


def test_m6_3c_release_requires_exact_future_user_approval() -> None:
    document = _load()
    release = document["release_and_approval"]
    assert release["release_scope_kind"] == (
        "TOPK20_REAL_EFFECT_RELEASE_READY_NOT_EXECUTION_APPROVAL"
    )
    assert release["approval_action"] == (
        "M6_TOPK20_CONVERSION_EFFECT_ONCE_WITH_INTERNAL_REPLAY_AND_INDEPENDENT_AUDIT"
    )
    assert release["approval_must_bind_exact_release_scope_sha256"] is True
    assert release["scope_drift_invalidates_approval"] is True
    assert release["prior_authority_inheritance"] is False
    stop = document["stop_condition"]
    assert stop["stop_after_exact_release_scope_is_committed_and_pushed"] is True
    assert stop["explicit_user_authorization_of_full_scope_required"] is True
    assert stop["no_real_effect_or_qlib_read_before_approval"] is True


def test_m6_3c_docker_mounts_are_narrow_and_non_production() -> None:
    docker = _load()["docker"]
    assert docker["runtime_network_mode"] == "none"
    assert docker["read_only_root"] is True and docker["run_as_non_root"] is True
    assert docker["cap_drop_all"] is True and docker["no_new_privileges"] is True
    assert docker["env_file_mounted"] is False
    assert docker["docker_socket_mounted"] is False
    assert docker["full_project_root_mounted"] is False
    assert docker["production_ledger_mounted"] is False
    assert [row["target"] for row in docker["runner_mounts"]] == [
        "/qlib",
        "/m6-effect",
        "/inputs/m6-audit.json",
        "/inputs/release.json",
        "/inputs/approval.json",
        "/outputs",
    ]
    assert [row["target"] for row in docker["auditor_mounts"]] == [
        "/outputs",
        "/inputs/release.json",
        "/inputs/approval.json",
        "/audit",
    ]
