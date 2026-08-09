from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config/m7_moneyflow_recovery_target_projection_v1.yaml"
PROTOCOL_SHA256 = "0f7f1a604dd5b767dbb4811ddb0c5bd4a776a30d086d8995eab735110c0a910a"
PROTOCOL_V2 = ROOT / "config/m7_moneyflow_recovery_target_projection_v2.yaml"
PROTOCOL_V2_SHA256 = "345316477d789b255aeb259adcf3411a5f8c7889ed4eecd6f0a34d7e33dac1fd"


def _document() -> dict[str, object]:
    value = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _document_v2() -> dict[str, object]:
    value = yaml.safe_load(PROTOCOL_V2.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_projection_protocol_identity_is_frozen() -> None:
    assert hashlib.sha256(PROTOCOL.read_bytes()).hexdigest() == PROTOCOL_SHA256


def test_projection_protocol_v2_corrects_only_predecessor_identity() -> None:
    assert hashlib.sha256(PROTOCOL_V2.read_bytes()).hexdigest() == PROTOCOL_V2_SHA256
    document = _document_v2()
    supersession = document["supersession"]
    assert supersession["superseded_protocol_sha256"] == PROTOCOL_SHA256
    assert supersession["v1_execution_authorized"] is False
    assert supersession["v1_execution_occurred"] is False
    assert (
        document["frozen_predecessors"]["lineage_report"]["core_sha256"]
        == "df5de3990428e630eb2f56380601f3bee12fee2d2220a99c48c286e3701beeca"
    )


def test_projection_protocol_preserves_feature_and_source_date() -> None:
    contract = _document()["projection_contract"]
    assert contract["intended_grain"] == "feature_trade_date_x_universe_id_x_ts_code"
    assert contract["query_grain"] == "source_date_x_ts_code"
    assert contract["preserve_feature_and_source_dates_separately"] is True
    assert contract["tracked_columns"] == [
        "trade_date",
        "source_date",
        "universe_id",
        "ts_code",
        "segment",
    ]
    assert contract["track_a"]["expected_member_rows"] == 908
    assert contract["track_b"]["expected_member_rows"] == 541


def test_projection_protocol_is_offline_key_only_and_preapproval() -> None:
    execution = _document()["execution_contract"]
    authority = _document()["construction_authority"]
    assert execution["current_execution_authorized"] is False
    assert execution["network_mode"] == "none"
    assert execution["provider_call_count"] == 0
    assert execution["moneyflow_numeric_value_columns_read"] == 0
    assert execution["pre_read_claim_before_semantic_rows"] is True
    assert authority["projector_auditor_and_release_engineering_authorized"] is True
    assert authority["exact_release_scope_generation_authorized"] is True
    assert authority["real_security_key_read_authorized"] is False
    assert authority["real_projection_execution_authorized"] is False
    assert authority["live_provider_call_authorized"] is False
    assert authority["secret_read_authorized"] is False
    assert authority["external_network_authorized"] is False
    assert authority["production_authorization"] == "none"


def test_projection_protocol_requires_independent_exact_match_and_new_approval() -> None:
    contract = _document()["projection_contract"]
    stop = _document()["next_stop"]
    assert contract["main_classifier"] == "frozen_pandas_r2"
    assert contract["independent_auditor"] == "frozen_duckdb_r2_classified_relation"
    assert contract["main_and_auditor_target_hashes_must_match"] is True
    assert stop["protocol_must_be_pushed_before_implementation"] is True
    assert stop["implementation_must_be_pushed_before_release_scope"] is True
    assert stop["user_must_approve_exact_release_scope_before_real_projection"] is True
