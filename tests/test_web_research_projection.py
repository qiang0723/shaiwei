import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from shaiwei.web.api import create_app
from shaiwei.web.query import WebQueryError
from shaiwei.web.research_projection import (
    ResearchProjectionBundle,
    experiment_summary,
    factor_admission_history,
    factor_catalog,
    factor_compare,
    factor_detail,
    factor_id,
    load_research_projection,
)


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _version(
    factor_identity: str,
    version: str,
    *,
    authority: str,
    recorded_at: str,
    fingerprint_suffix: str = "shared",
) -> dict[str, object]:
    fingerprint = {
        key: fingerprint_suffix
        for key in (
            "research_family",
            "universe_id",
            "benchmark_id",
            "label_id",
            "horizon_id",
            "neutralization_id",
            "window_set_id",
            "stress_set_id",
            "portfolio_policy_id",
            "cost_policy_id",
            "decision_rule_version",
            "candidate_code_sha256",
            "data_snapshot_sha256",
            "comparison_policy_id",
        )
    }
    unavailable = {
        key: {"status": "NOT_EVALUATED", "recomputed": False}
        for key in (
            "coverage_ratio",
            "quantile_returns_and_monotonicity",
            "factor_autocorrelation",
            "candidate_pool_correlation",
        )
    }
    return {
        "factor_id": factor_identity,
        "factor_version": version,
        "recorded_at": recorded_at,
        "recorded_decision": "REJECTED",
        "lifecycle_status": "REJECTED",
        "authority_status": authority,
        "trial_count": 18,
        "failed_gates": ["economic_rationale"],
        "decision_id": f"decision-{version}",
        "decision_rule_version": "g1-v1",
        "evidence_sha256": "a" * 64,
        "report_sha256": "b" * 64,
        "evidence_status": "VERIFIED",
        "fingerprint": fingerprint,
        "detail": {
            "identity": {"candidate_experiment_id": version},
            "frozen_definition_and_direction": {"feature_or_formula": "fixture"},
            "pit_shift_and_complexity": {"pit_sentinel_pass": True},
            "g1_statistics_and_all_gates": {
                "statistics": {"hac_t": -1.0},
                "gates": {f"g{i}": False for i in range(15)},
            },
            "six_oos_window_rank_ic": {f"W{i}": -0.01 for i in range(1, 7)},
            "stress_max_drawdown": {"stress": 0.1},
            "turnover_and_incremental_portfolio": {"candidate_turnover": 1.0},
            "cost_and_slippage_stress": {"cost_2x_net_excess": -0.1},
            "library_max_abs_correlation": 0.0,
            **unavailable,
        },
        "source_refs": [f"factor_admission:decision-{version}"],
        "evidence_hashes": ["a" * 64, "b" * 64],
    }


def _bundle() -> ResearchProjectionBundle:
    first_id = factor_id("fixture-family", "fixture-a")
    second_id = factor_id("fixture-family", "fixture-b")
    historical = _version(
        first_id,
        "old-version",
        authority="SUPERSEDED_ENGINEERING_GENERATION",
        recorded_at="2026-07-23T00:00:00+00:00",
    )
    current_a = _version(
        first_id,
        "current-a",
        authority="AUTHORITATIVE_CURRENT",
        recorded_at="2026-07-24T00:00:00+00:00",
    )
    current_b = _version(
        second_id,
        "current-b",
        authority="AUTHORITATIVE_CURRENT",
        recorded_at="2026-07-24T00:00:01+00:00",
    )
    stage1_history = _version(
        second_id,
        "stage1-history",
        authority="HISTORICAL_NON_AUTHORITATIVE",
        recorded_at="2026-07-22T00:00:00+00:00",
    )
    experiment = {
        "experiment_kind": "p2_effect_original",
        "experiment_id": "p2-old",
        "recorded_at": "2026-07-24T00:00:00+00:00",
        "research_family": "p2-star50-effect-v1",
        "evidence_tier": "P2_EFFECT_INVALIDATED",
        "authority_status": "INVALIDATED_METHOD",
        "lifecycle_status": "REJECTED",
        "model_or_engine": "fixture",
        "engine_version": "fixture",
        "seed": "42",
        "train_period": "fixture",
        "valid_period": "fixture",
        "code_snapshot_sha256": "c" * 64,
        "data_snapshot_sha256": "d" * 64,
        "decision": {
            "numeric_results_status": "REPRODUCIBLE_NOT_AUTHORITATIVE",
            "authoritative_successor_kind": "p2_effect_correction",
            "authoritative_successor_id": "p2-new",
        },
        "failed_reasons": ["INVALIDATED_METHOD"],
        "evidence_status": "VERIFIED",
        "source_refs": ["p2_effect_original:p2-old"],
        "evidence_hashes": ["e" * 64],
    }
    correction = {
        **experiment,
        "experiment_kind": "p2_effect_correction",
        "experiment_id": "p2-new",
        "research_family": "p2-star50-effect-correction-v1",
        "evidence_tier": "P2_EFFECT_AUTHORITATIVE",
        "authority_status": "AUTHORITATIVE_CURRENT",
        "decision": {
            "historical_effect_gate": "NO_GO",
            "strategy_effective": "REJECT",
            "production_authorization": "none",
            "original_p2_2_model_valid": False,
            "original_p2_2_execution_valid": False,
        },
    }
    d1_reviewed = {
        **experiment,
        "experiment_kind": "research_experiment",
        "experiment_id": "d1-reviewed",
        "research_family": "d1-llm-dsl-v1",
        "evidence_tier": "D1_DISCOVERY_ATTEMPT_WITH_REVIEW_OVERLAY",
        "authority_status": "AUTHORITATIVE_STOP",
        "lifecycle_status": "REVIEW_STOPPED",
        "decision": {
            "review_overlay": "STOP_SEMANTIC_CONTRACT_VIOLATION",
            "g1_run": False,
            "strategy_effective": "NOT_EVALUATED",
        },
    }
    d1_unreviewed = {
        **d1_reviewed,
        "experiment_id": "d1-unreviewed",
        "authority_status": "DISCOVERY_ONLY",
        "lifecycle_status": "DISCOVERY_EVALUATED",
        "decision": {
            "review_overlay": "NOT_APPLICABLE",
            "g1_run": False,
            "strategy_effective": "NOT_EVALUATED",
        },
    }
    data = {
        "schema_version": "web-v1",
        "protocol_id": "p3-factor-experiment-query-v1",
        "snapshot_id": "f" * 64,
        "generated_at": "2026-07-24T00:00:01+00:00",
        "timezone": "Asia/Shanghai",
        "factors": [
            {
                "factor_id": first_id,
                "identity_kind": "FAMILY_SCOPED_EXACT_FORMULA_SHA256",
                "research_family": "fixture-family",
                "data_category": "moneyflow",
                "feature_or_formula": "fixture-a",
                "versions": [historical, current_a],
            },
            {
                "factor_id": second_id,
                "identity_kind": "FAMILY_SCOPED_EXACT_FORMULA_SHA256",
                "research_family": "fixture-family",
                "data_category": "moneyflow",
                "feature_or_formula": "fixture-b",
                "versions": [stage1_history, current_b],
            },
        ],
        "experiments": {
            "research_experiment": {
                "d1-reviewed": d1_reviewed,
                "d1-unreviewed": d1_unreviewed,
            },
            "p2_engineering_run": {},
            "p2_effect_original": {"p2-old": experiment},
            "p2_effect_correction": {"p2-new": correction},
        },
        "invariants": {
            "raw_json_returned": False,
            "daily_series_returned": False,
            "performance_recalculated": False,
            "formal_library_count": 0,
        },
    }
    return ResearchProjectionBundle(
        snapshot_id="f" * 64,
        generated_at=data["generated_at"],
        protocol_id=data["protocol_id"],
        data=data,
        source_hashes={},
    )


def _write_projection(root: Path, bundle: ResearchProjectionBundle) -> None:
    directory = root / "data/web/research_snapshots" / bundle.snapshot_id
    directory.mkdir(parents=True)
    payload = _canonical(bundle.data)
    manifest = {
        "schema_version": "research-projection-manifest-v1",
        "protocol_id": bundle.protocol_id,
        "snapshot_id": bundle.snapshot_id,
        "generated_at": bundle.generated_at,
        "bundle_file": "bundle.json",
        "bundle_bytes": len(payload),
        "bundle_sha256": hashlib.sha256(payload).hexdigest(),
        "source_hashes": {},
    }
    (directory / "bundle.json").write_bytes(payload)
    (directory / "manifest.json").write_bytes(_canonical(manifest))


def test_factor_queries_preserve_authority_history_and_not_evaluated_sections():
    bundle = _bundle()
    catalog = factor_catalog(bundle)
    assert catalog["counters"] == {
        "formal_library_count": 0,
        "researched_factor_count": 2,
        "authoritative_rejected_count": 2,
        "historical_only_count": 0,
    }
    first = bundle.data["factors"][0]
    detail = factor_detail(bundle, first["factor_id"])
    assert detail["factor_version"] == "current-a"
    for section in (
        "coverage_ratio",
        "quantile_returns_and_monotonicity",
        "factor_autocorrelation",
        "candidate_pool_correlation",
    ):
        assert detail["sections"][section] == {
            "status": "NOT_EVALUATED",
            "recomputed": False,
        }
    history = factor_admission_history(bundle, first["factor_id"])
    assert [row["factor_version"] for row in history["items"]] == [
        "old-version",
        "current-a",
    ]
    historical = factor_catalog(bundle, as_of="2026-07-23")
    assert historical["counters"]["historical_only_count"] == 2
    assert historical["historical_response_banner"]


def test_factor_compare_fails_closed_for_old_or_incomparable_versions():
    bundle = _bundle()
    compared = factor_compare(bundle, ["current-a", "current-b"])
    assert compared["sorted_by_performance"] is False
    with pytest.raises(WebQueryError) as old:
        factor_compare(bundle, ["old-version", "current-b"])
    assert old.value.code == "CONFLICT"
    bundle.data["factors"][1]["versions"][1]["fingerprint"]["universe_id"] = "other"
    with pytest.raises(WebQueryError) as mismatch:
        factor_compare(bundle, ["current-a", "current-b"])
    assert mismatch.value.code == "CONFLICT"


def test_projection_loader_api_and_invalidated_experiment_are_typed(tmp_path: Path):
    expected = _bundle()
    _write_projection(tmp_path, expected)
    loaded = load_research_projection(tmp_path)
    old = experiment_summary(loaded, "p2_effect_original", "p2-old")
    assert old["authority_status"] == "INVALIDATED_METHOD"
    assert old["decision"]["numeric_results_status"] == "REPRODUCIBLE_NOT_AUTHORITATIVE"
    corrected = experiment_summary(loaded, "p2_effect_correction", "p2-new")
    assert corrected["authority_status"] == "AUTHORITATIVE_CURRENT"
    assert corrected["decision"]["historical_effect_gate"] == "NO_GO"
    reviewed = experiment_summary(loaded, "research_experiment", "d1-reviewed")
    unreviewed = experiment_summary(loaded, "research_experiment", "d1-unreviewed")
    assert reviewed["decision"]["review_overlay"] == "STOP_SEMANTIC_CONTRACT_VIOLATION"
    assert unreviewed["decision"]["review_overlay"] == "NOT_APPLICABLE"
    assert loaded.data["factors"][0]["versions"][0]["authority_status"] == (
        "SUPERSEDED_ENGINEERING_GENERATION"
    )
    assert loaded.data["factors"][1]["versions"][0]["authority_status"] == (
        "HISTORICAL_NON_AUTHORITATIVE"
    )
    client = TestClient(create_app(tmp_path))
    response = client.get("/api/v1/factors")
    assert response.status_code == 200
    assert response.json()["data"]["counters"]["researched_factor_count"] == 2
    assert response.json()["meta"]["as_of"] == "2026-07-24"
    historical_response = client.get("/api/v1/factors?as_of=2026-07-23")
    assert historical_response.status_code == 200
    assert historical_response.json()["meta"]["as_of"] == "2026-07-23"
    assert historical_response.json()["data"]["historical_response_banner"]
    assert client.head("/api/v1/factors").status_code == 200
    assert client.post("/api/v1/factors").status_code == 405
    raw = response.text.lower()
    assert "params_json" not in raw
    assert "result_json" not in raw
    detail = client.get(f"/api/v1/factors/{expected.data['factors'][0]['factor_id']}")
    assert detail.status_code == 200
    assert len(detail.content) < 1_048_576


def test_projection_manifest_tampering_and_symbolic_link_fail_closed(tmp_path: Path):
    expected = _bundle()
    _write_projection(tmp_path, expected)
    directory = tmp_path / "data/web/research_snapshots" / expected.snapshot_id
    (directory / "bundle.json").write_bytes(b"{}")
    with pytest.raises(WebQueryError) as tampered:
        load_research_projection(tmp_path)
    assert tampered.value.code == "EVIDENCE_MISMATCH"

    other = tmp_path / "other"
    other.mkdir()
    output = tmp_path / "data/web/research_snapshots"
    for child in directory.iterdir():
        child.unlink()
    directory.rmdir()
    output.rmdir()
    output.symlink_to(other, target_is_directory=True)
    with pytest.raises(WebQueryError) as linked:
        load_research_projection(tmp_path)
    assert linked.value.code == "NOT_READY"
