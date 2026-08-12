from hashlib import sha256
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "config/ts_v4_density_preflight_release_v1.yaml"


def _yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_v4_density_release_binds_immutable_v4_protocol_and_inputs() -> None:
    release = _yaml(RELEASE)
    predecessor = release["predecessor"]
    inputs = release["bound_inputs"]

    assert release["stage"] == "RESULT_BLIND_DENSITY_PREFLIGHT_AUTHORIZED_ONCE"
    assert predecessor["immutable_and_not_rewritten"] is True
    assert _sha256(ROOT / predecessor["protocol_path"]) == predecessor["protocol_sha256"]
    assert _sha256(ROOT / inputs["r3_manifest_path"]) == inputs["r3_manifest_sha256"]
    assert _sha256(ROOT / inputs["alpha158_path"]) == inputs["alpha158_sha256"]
    assert inputs["alpha158_allowed_columns"] == ["ts_code", "trade_date"]


def test_v4_density_release_has_exact_four_arms_and_adjacency() -> None:
    release = _yaml(RELEASE)

    assert [(arm["arm_id"], arm["pullback_depth_fraction"]) for arm in release["arms"]] == [
        ("TS4-D015", 0.015),
        ("TS4-D025", 0.025),
        ("TS4-D035", 0.035),
        ("TS4-D040", 0.04),
    ]
    assert release["adjacent_pairs"] == [
        ["TS4-D015", "TS4-D025"],
        ["TS4-D025", "TS4-D035"],
        ["TS4-D035", "TS4-D040"],
    ]


def test_v4_density_release_freezes_gate_and_purge() -> None:
    release = _yaml(RELEASE)
    gate = release["density_gate"]
    inputs = release["bound_inputs"]

    assert inputs["discovery_start"] == "20190102"
    assert inputs["discovery_end"] == "20211231"
    assert inputs["final_signal_date_purge_count"] == 16
    assert gate["per_arm_minimum_legal_events"] == 30
    assert gate["per_arm_minimum_distinct_signal_days"] == 20
    assert gate["per_arm_minimum_events_each_calendar_year"] == 5
    assert gate["required_calendar_years"] == [2019, 2020, 2021]
    assert gate["alpha158_event_key_coverage_required"] == 1.0
    assert gate["minimum_passing_adjacent_pair_count"] == 1
    assert gate["threshold_change_after_profile"] == "forbidden"
    official_days = [f"D{index:02d}" for index in range(20)]
    # OFFSET 16 keeps the seventeenth day from the end, so exactly 16 end days are purged.
    assert official_days[::-1][inputs["final_signal_date_purge_count"]] == "D03"


def test_v4_density_release_is_result_blind_and_one_shot() -> None:
    release = _yaml(RELEASE)
    authority = release["authorization"]
    attempts = release["attempt_control"]

    assert authority["one_result_blind_density_profile"] is True
    assert authority["alpha158_event_key_only"] is True
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
    ):
        assert authority[key] is False
    assert attempts == {
        "proposed_strategy_attempt_count": 4,
        "density_profile_attempt_count": 1,
        "independent_audit_attempt_count": 1,
        "strategy_effect_attempt_count": 0,
        "same_scope_profile_rerun": "forbidden",
        "same_scope_audit_rerun": "forbidden",
        "parameter_grid_expansion": "forbidden",
    }


def test_v4_density_release_cannot_authorize_effect_or_production() -> None:
    release = _yaml(RELEASE)
    isolation = release["execution_isolation"]
    successor = release["successor_control"]

    assert isolation["docker_network_mode"] == "none"
    assert isolation["project_env_mounted"] is False
    assert isolation["secrets_mounted"] is False
    assert isolation["production_scheduler_restart_or_change"] == "forbidden"
    assert all(value is False for key, value in successor.items() if key.endswith("authorizes_effect") or key.endswith("authorizes_benchmark_recovery") or key.endswith("authorizes_model_or_new_prediction") or key.endswith("authorizes_paper_web_or_production"))
    assert successor["effect_requires_separate_release_and_h00906_lineage_gate"] is True
