from __future__ import annotations

from pathlib import Path

import pandas as pd

from shaiwei.research_gates.m7_moneyflow.audit_compute import recompute_quality_core
from shaiwei.research_gates.m7_moneyflow.compute import compute_quality_core
from shaiwei.research_gates.m7_moneyflow.contract import M7Protocol, sha256_json
from shaiwei.research_gates.m7_moneyflow.fixture import run_fixture, synthetic_inputs
from shaiwei.research_gates.m7_moneyflow.reader import KeyInputs


ROOT = Path(__file__).resolve().parents[1]


def _protocol() -> M7Protocol:
    return M7Protocol.load(
        ROOT / "config/m7_star_custom_pool_moneyflow_data_v1.yaml",
        build_path=ROOT / "config/m7_star_custom_pool_moneyflow_data_gate_build_v1.yaml",
        project_root=ROOT,
    )


def _replace_source(source: pd.DataFrame) -> KeyInputs:
    clean = synthetic_inputs()
    return KeyInputs(
        clean.membership,
        source,
        clean.official_dates,
        clean.quarantined_source_dates,
        clean.evidence,
    )


def test_value_free_fixture_replays_and_audits() -> None:
    result = run_fixture(_protocol())
    assert result["status"] == "PASS"
    assert result["independent_audit_pass"] is True
    assert result["numeric_moneyflow_value_columns_read"] == 0
    assert result["effect_test_count"] == 0


def test_clean_key_fixture_is_go_and_contains_no_security_list() -> None:
    protocol = _protocol()
    core = compute_quality_core(protocol, synthetic_inputs())
    assert core["verdict"] == "GO_M7_0_DATA_COMPATIBILITY_ONLY"
    assert all(gate["status"] == "PASS" for gate in core["gates"])
    serialized = str(core)
    assert "688000.SH" not in serialized


def test_duplicate_source_fails_closed_and_matches_independent_audit() -> None:
    protocol = _protocol()
    clean = synthetic_inputs()
    duplicate = pd.concat([clean.source_keys, clean.source_keys.iloc[[0]]], ignore_index=True)
    inputs = _replace_source(duplicate)
    main = compute_quality_core(protocol, inputs)
    audit = recompute_quality_core(protocol, inputs)
    assert main == audit
    assert sha256_json(main) == sha256_json(audit)
    assert main["verdict"] == "NO_GO_M7_0_DATA_COMPATIBILITY"
    assert next(g for g in main["gates"] if g["gate_id"] == "source_primary_key_unique")[
        "status"
    ] == "FAIL"


def test_sparse_source_fails_coverage_without_filling() -> None:
    protocol = _protocol()
    clean = synthetic_inputs()
    sparse = clean.source_keys.loc[
        ~(
            clean.source_keys["request_trade_date"].eq("20201231")
            & clean.source_keys["ts_code"].isin(
                [f"688{index:03d}.SH" for index in range(10)]
            )
        )
    ].copy()
    core = compute_quality_core(protocol, _replace_source(sparse))
    assert core["verdict"] == "NO_GO_M7_0_DATA_COMPATIBILITY"
    failed = {gate["gate_id"] for gate in core["gates"] if gate["status"] == "FAIL"}
    assert "worst_eligible_feature_date_coverage" in failed
    assert "minimum_matched_names" in failed


def test_quarantined_source_date_is_not_treated_as_missing_key_fill() -> None:
    protocol = _protocol()
    clean = synthetic_inputs()
    inputs = KeyInputs(
        clean.membership,
        clean.source_keys,
        clean.official_dates,
        frozenset({"20201231"}),
        clean.evidence,
    )
    core = compute_quality_core(protocol, inputs)
    assert core["completeness"]["quarantined_feature_date_count"] == 1
    assert core["completeness"]["maximum_consecutive_quarantined_source_dates"] == 1
    aggregate = core["completeness"]["aggregate_member_key_coverage_by_universe"]
    assert all(item["matched"] < item["denominator"] for item in aggregate)
