from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config/ts_v5_r3g2_benchmark_lineage_v1.yaml"
RECOVERY = ROOT / "config/ts_v5_r3g2_benchmark_transport_recovery_r1.yaml"
RECOVERY_R2 = ROOT / "config/ts_v5_r3g2_benchmark_transport_recovery_r2.yaml"
COMPOSE = ROOT / "compose.ts-v5-r3g2-benchmark.yaml"
DOCKERFILE = ROOT / "Dockerfile.ts-v5-r3g2-benchmark"


def _load() -> dict:
    return yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))


def test_protocol_binds_H00906_and_forbids_price_proxy() -> None:
    document = _load()
    benchmark = document["benchmark"]
    assert document["status"] == "RESULT_BLIND_BENCHMARK_LINEAGE_PROTOCOL_FROZEN"
    assert benchmark["logical_identifier"] == "CSI_H00906_TOTAL_RETURN"
    assert benchmark["index_code"] == "H00906"
    assert benchmark["price_index_code"] == "000906"
    assert benchmark["price_index_substitution"] == "forbidden"
    assert benchmark["locally_derived_dividend_proxy"] == "forbidden"


def test_protocol_covers_current_roles_without_reusing_partial_year() -> None:
    document = _load()
    benchmark = document["benchmark"]
    assert benchmark["required_start_date"] == "20190101"
    assert benchmark["required_end_date"] == "20260811"
    assert benchmark["r3g_roles"] == {
        "selectable_discovery": ["20210104", "20231229"],
        "frozen_stability_holdout": ["20240102", "20251231"],
        "current_partial_year_monitor": ["20260105", "20260811"],
    }
    assert benchmark["partial_year_role"] == (
        "NOT_FOR_SELECTION_NOT_FOR_VERDICT_PARTIAL_YEAR"
    )


def test_protocol_has_fixed_official_requests_and_zero_effect_authority() -> None:
    document = _load()
    authority = document["authority"]
    sources = document["official_sources"]
    assert sources["daily_history"]["query"] == {
        "indexCode": "H00906",
        "startDate": "20190101",
        "endDate": "20260811",
    }
    assert sources["daily_history"]["logical_request_count"] == 2
    assert sources["daily_history"]["responses_must_be_canonically_identical_before_persist"]
    assert authority["exactly_one_official_factsheet_request"]
    assert authority["exactly_two_identical_official_history_requests"]
    assert authority["read_candidate_or_post_entry_return"] is False
    assert authority["parameter_search_or_effect_comparison"] is False
    assert authority["model_training_prediction_or_backtest"] is False
    assert authority["tushare_or_other_secret_read"] is False
    assert authority["paper_web_scheduler_or_production_change"] is False


def test_protocol_fails_closed_on_coverage_identity_or_drift() -> None:
    document = _load()
    gate = document["quality_gate"]
    assert gate["date_set_equals_official_open_days"]
    assert gate["duplicate_index_date_key_maximum"] == 0
    assert gate["unexpected_index_code_maximum"] == 0
    assert gate["missing_official_open_date_maximum"] == 0
    assert gate["non_official_date_maximum"] == 0
    assert gate["response_drift_between_two_requests"] == "forbidden"
    assert document["verdicts"]["strategy_effective"] == "NOT_EVALUATED"
    assert document["verdicts"]["production_authorization"] == "none"


def test_container_contract_has_no_secret_mount_and_offline_audit() -> None:
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    base = compose["x-r3g2-benchmark-base"]
    services = compose["services"]
    serialized = COMPOSE.read_text(encoding="utf-8")
    assert "env_file" not in serialized
    assert ".env" not in serialized
    assert base["read_only"] is True
    assert base["cap_drop"] == ["ALL"]
    assert all("ledger/ingest_batches.csv" in str(volume) or "data" in str(volume) for volume in base["volumes"])
    assert services["ts-v5-r3g2-benchmark-audit"]["network_mode"] == "none"
    assert "scheduler" not in services


def test_release_image_is_pinned_to_frozen_r3g1_parent() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert dockerfile.startswith("FROM shaiwei:ts-v5-r3g1-recent-density-r2\n")
    assert (
        'shaiwei.parent.image.id="sha256:'
        '3b81e501c134e7d91217d6102f4d033e16047310b89496dd1296d1684c9a42d9"'
        in dockerfile
    )
    assert "COPY src ./src" in dockerfile
    assert "COPY config ./config" in dockerfile
    assert "COPY tests ./tests" in dockerfile


def test_transport_recovery_only_moves_public_bytes_to_host() -> None:
    recovery = yaml.safe_load(RECOVERY.read_text(encoding="utf-8"))
    failed = recovery["failed_scope"]
    authority = recovery["recovery_authority"]
    assert recovery["status"] == "RESULT_UNKNOWN_TRANSPORT_RECOVERY_FROZEN"
    assert failed["completed_http_response_count"] == 0
    assert failed["history_request_attempt_count"] == 0
    assert failed["persisted_file_count"] == 0
    assert failed["same_scope_retry_authorized"] is False
    assert authority["host_transport_only"] is True
    assert authority["maximum_transport_attempts_per_logical_request"] == 1
    assert authority["docker_offline_evaluation_once"] is True
    assert authority["docker_offline_independent_audit_once"] is True
    assert authority["env_or_secret_read"] is False
    assert authority["extra_source_or_substitute"] is False
    assert authority["read_candidate_or_post_entry_return"] is False
    assert recovery["post_transfer"]["evaluation_network_mode"] == "none"
    assert recovery["post_transfer"]["audit_network_mode"] == "none"


def test_transport_r2_adds_only_output_preflight() -> None:
    recovery = yaml.safe_load(RECOVERY_R2.read_text(encoding="utf-8"))
    failure = recovery["r1_failure"]
    preflight = recovery["r2_preflight"]
    authority = recovery["r2_authority"]
    assert recovery["status"] == "RESULT_UNKNOWN_HOST_OUTPUT_PREFLIGHT_RECOVERY_FROZEN"
    assert failure["curl_exit_code"] == 23
    assert failure["persisted_file_count"] == 0
    assert failure["history_request_attempt_count"] == 0
    assert failure["same_r1_retry_authorized"] is False
    assert all(preflight.values())
    assert authority["inherits_exact_three_public_requests_from_r1"] is True
    assert authority["maximum_transport_attempts_per_logical_request"] == 1
    assert authority["env_or_secret_read"] is False
    assert authority["read_candidate_or_post_entry_return"] is False
