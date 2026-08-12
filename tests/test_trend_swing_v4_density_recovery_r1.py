from hashlib import sha256
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT / "config/ts_v4_density_preflight_recovery_r1.yaml"


def _yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_v4_density_r1_binds_and_preserves_failed_parent() -> None:
    recovery = _yaml(RECOVERY)
    parent = recovery["frozen_parent"]
    failed = recovery["failed_attempt"]

    assert recovery["stage"] == "RESULT_BLIND_SERIALIZATION_RECOVERY_AUTHORIZED_ONCE"
    assert _sha256(ROOT / parent["release_path"]) == parent["release_sha256"]
    assert parent["immutable_and_not_rewritten"] is True
    assert failed["failure_stage"] == "SERIALIZATION_BEFORE_FIRST_ARTIFACT"
    assert failed["profile_report_written"] is False
    assert failed["event_artifact_written"] is False
    assert failed["daily_artifact_written"] is False
    assert failed["audit_written"] is False
    assert failed["result_values_observed"] is False
    assert failed["same_scope_rerun"] == "forbidden"


def test_v4_density_r1_has_exactly_one_non_research_delta() -> None:
    recovery = _yaml(RECOVERY)
    delta = recovery["single_recovery_delta"]
    inherited = recovery["inherited_without_change"]

    assert delta["new_writer"] == (
        "DuckDB_relation_select_with_bound_dates_then_write_parquet_to_explicit_path"
    )
    assert delta["data_logic_changed"] is False
    assert delta["state_machine_changed"] is False
    assert delta["arm_or_threshold_changed"] is False
    assert delta["alpha_key_projection_changed"] is False
    assert delta["output_scope"].endswith("ts-v4-density-preflight-r1")
    assert all(inherited.values())


def test_v4_density_r1_remains_result_blind_and_single_use() -> None:
    recovery = _yaml(RECOVERY)
    authority = recovery["authorization"]
    attempts = recovery["attempt_control"]

    assert authority["one_recovery_density_profile"] is True
    assert authority["one_recovery_independent_audit"] is True
    assert authority["alpha158_event_key_only"] is True
    assert all(
        authority[key] is False
        for key in (
            "post_entry_outcome_read",
            "alpha158_score_or_rank_read",
            "benchmark_value_read",
            "strategy_effect_or_backtest",
            "provider_or_external_network",
            "env_or_secret_read",
            "model_training_or_prediction",
            "paper_account_or_forward",
            "web_or_production_change",
        )
    )
    assert attempts["proposed_strategy_attempt_count"] == 4
    assert attempts["failed_serialization_attempt_count"] == 1
    assert attempts["recovery_density_profile_attempt_count"] == 1
    assert attempts["strategy_effect_attempt_count"] == 0
    assert attempts["same_recovery_scope_rerun"] == "forbidden"


def test_v4_density_r1_keeps_offline_production_isolation() -> None:
    isolation = _yaml(RECOVERY)["execution_isolation"]

    assert isolation["docker_network_mode"] == "none"
    assert isolation["project_env_mounted"] is False
    assert isolation["secrets_mounted"] is False
    assert isolation["production_scheduler_restart_or_change"] == "forbidden"
    assert isolation["mutable_output_mount_only"].endswith("ts-v4-density-preflight-r1")
