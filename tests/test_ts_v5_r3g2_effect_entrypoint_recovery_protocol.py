from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
PROTOCOL = ROOT / "config/ts_v5_r3g2_effect_entrypoint_recovery_v1.yaml"


def _load() -> dict:
    return yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))


def test_recovery_protocol_preserves_original_failure_and_forbids_rerun() -> None:
    document = _load()
    original = document["predecessor"]["original_release"]
    failure = document["predecessor"]["failure_receipt"]
    assert original["scope_sha256"] == (
        "961b62f288f61a6ae19f88ef04c0697f93f27bf52390ddb48b7c49064e19db75"
    )
    assert original["runner_invocation_consumed"] is True
    assert original["same_scope_retry_authorized"] is False
    assert failure["frozen_facts"]["effect_read_started"] is False
    assert failure["frozen_facts"]["strategy_effect_attempt_count"] == 0
    assert failure["frozen_facts"]["audit_invoked"] is False


def test_recovery_changes_only_entrypoints_and_requires_new_approval() -> None:
    document = _load()
    repair, release = document["repair"], document["release"]
    assert repair["economic_parameter_change"] is False
    assert repair["effect_protocol_change"] is False
    assert repair["data_or_score_lineage_change"] is False
    assert document["execution"]["effect_attempts_consumed_at_first_recovery_value_read"] == 3
    assert release["prior_approval_reuse"] is False
    assert release["exact_user_approval_required"] is True
    assert release["approval_action"] == (
        "TS_R3G2_BREAKOUT_RETEST_EFFECT_ENTRYPOINT_RECOVERY_ONCE_WITH_"
        "DISCOVERY_FIREWALL_REPLAY_AND_INDEPENDENT_AUDIT"
    )
