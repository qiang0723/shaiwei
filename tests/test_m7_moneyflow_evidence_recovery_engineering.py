from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
import yaml

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_file
from shaiwei.research_gates.m7_moneyflow_recovery.audit_compute import (
    recompute_audit_vector,
)
from shaiwei.research_gates.m7_moneyflow_recovery.claims import (
    RequestClaimIdentity,
    RetryableTransportError,
    SemanticResponseError,
    execute_claimed_request,
)
from shaiwei.research_gates.m7_moneyflow_recovery.compute import (
    compute_recovery_core,
)
from shaiwei.research_gates.m7_moneyflow_recovery.contract import (
    RecoveryError,
    RecoveryProtocol,
)
from shaiwei.research_gates.m7_moneyflow_recovery.fixture import (
    synthetic_inputs,
    verify_fixture,
)
from shaiwei.research_gates.m7_moneyflow_recovery.planning import (
    plan_moneyflow_requests,
    plan_status_requests,
)


ROOT = Path(__file__).resolve().parents[1]


def _protocol() -> RecoveryProtocol:
    return RecoveryProtocol.load(
        ROOT / "config/m7_moneyflow_evidence_recovery_v1.yaml",
        engineering_path=ROOT / "config/m7_moneyflow_evidence_recovery_engineering_v1.yaml",
        project_root=ROOT,
    )


def _gate(core: dict[str, object], gate_id: str) -> dict[str, object]:
    return next(item for item in core["gates"] if item["gate_id"] == gate_id)


def test_real_scale_synthetic_fixture_is_deterministic_and_aggregate_only() -> None:
    result = verify_fixture(_protocol())
    assert result["status"] == "PASS"
    assert result["verdict"] == "GO_M7_EVIDENCE_RECOVERY_ENGINEERING_ONLY"
    assert result["scenario_count"] == 13
    assert result["status_request_count"] == 908
    assert result["moneyflow_request_count"] == 542
    assert result["main_audit_exact_match"] is True
    assert result["double_run_exact_match"] is True
    assert result["external_provider_call_count"] == 0
    assert result["real_security_key_read"] is False
    assert result["real_moneyflow_numeric_value_read"] is False
    assert result["adjusted_coverage_computed"] is False


def test_exact_target_planners_cover_each_key_once_and_reject_invalid_dates() -> None:
    protocol = _protocol()
    inputs = synthetic_inputs(protocol)
    status = plan_status_requests(protocol, inputs.track_a_targets, inputs.official_dates)
    observed = {
        (request.ts_code, day) for request in status for day in request.required_dates
    }
    expected = set(
        inputs.track_a_targets[["ts_code", "trade_date"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    assert observed == expected
    assert len(status) == 908
    moneyflow = plan_moneyflow_requests(protocol, inputs.track_b_targets)
    assert sum(item.shape == "full_market_by_trade_date" for item in moneyflow) == 1
    assert sum(item.shape == "one_security_one_date" for item in moneyflow) == 541
    with pytest.raises(RecoveryError, match="outside official dates"):
        plan_status_requests(protocol, inputs.track_a_targets, ("20210105",))


def test_complete_core_matches_independent_duckdb_audit_and_keeps_old_authority() -> None:
    protocol = _protocol()
    inputs = synthetic_inputs(protocol)
    first = compute_recovery_core(protocol, inputs)
    second = compute_recovery_core(protocol, inputs)
    assert first == second
    assert first["audit_vector"] == recompute_audit_vector(protocol, inputs)
    assert first["verdict"] == "GO_M7_EVIDENCE_RECOVERY_DATA_ONLY"
    assert first["authority"] == {
        "adjusted_or_counterfactual_coverage_computed": False,
        "candidate_definition_count": 0,
        "effect_test_count": 0,
        "research_attempt_increment": 0,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }
    assert re.search(r"[0-9]{6}\.(?:SH|SZ|BJ)", canonical_json(first)) is None


@pytest.mark.parametrize("mode", ["trading", "missing"])
def test_track_a_conflict_and_unresolved_fail_closed(mode: str) -> None:
    protocol = _protocol()
    clean = synthetic_inputs(protocol)
    status = clean.independent_status.copy()
    if mode == "trading":
        status.loc[status.index[0], "trade_status"] = "1"
    else:
        status = status.iloc[1:].copy()
    inputs = replace(clean, independent_status=status)
    core = compute_recovery_core(protocol, inputs)
    assert core["audit_vector"] == recompute_audit_vector(protocol, inputs)
    assert core["verdict"] == "NO_GO_M7_EVIDENCE_RECOVERY_INCOMPLETE"
    assert _gate(core, "track_a_conflict_and_unresolved_zero_pass")["status"] == "FAIL"


@pytest.mark.parametrize("mode", ["one_missing", "both_missing", "mismatch"])
def test_track_b_shape_presence_and_content_fail_closed(mode: str) -> None:
    protocol = _protocol()
    clean = synthetic_inputs(protocol)
    full = clean.full_market_target_rows.copy()
    targeted = clean.targeted_rows.copy()
    if mode == "one_missing":
        targeted = targeted.iloc[1:].copy()
    elif mode == "both_missing":
        full = full.iloc[1:].copy()
        targeted = targeted.iloc[1:].copy()
    else:
        targeted.loc[targeted.index[0], "net_mf_amount"] += 1.0
    inputs = replace(clean, full_market_target_rows=full, targeted_rows=targeted)
    core = compute_recovery_core(protocol, inputs)
    assert core["audit_vector"] == recompute_audit_vector(protocol, inputs)
    assert core["verdict"] == "NO_GO_M7_EVIDENCE_RECOVERY_INCOMPLETE"
    assert _gate(
        core, "track_b_request_shape_presence_and_content_agreement_pass"
    )["status"] == "FAIL"


def test_duplicate_bj_saturation_and_batch_integrity_each_fail_closed() -> None:
    protocol = _protocol()
    clean = synthetic_inputs(protocol)
    duplicate = pd.concat(
        [clean.track_a_targets, clean.track_a_targets.iloc[[0]]], ignore_index=True
    )
    bj = clean.track_a_targets.copy()
    bj.loc[bj.index[0], "ts_code"] = "430001.BJ"
    cases = [
        replace(clean, track_a_targets=duplicate),
        replace(clean, track_a_targets=bj),
        replace(clean, full_market_response_row_counts=(6000,)),
        replace(clean, immutable_batch_integrity=False),
    ]
    for inputs in cases:
        core = compute_recovery_core(protocol, inputs)
        assert core["audit_vector"] == recompute_audit_vector(protocol, inputs)
        assert core["verdict"] == "NO_GO_M7_EVIDENCE_RECOVERY_INCOMPLETE"


def test_duplicate_claim_stops_before_loader_and_transport_is_bounded(tmp_path: Path) -> None:
    calls = 0

    def fetch() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    identity = RequestClaimIdentity("a" * 64, "b" * 64)
    result = execute_claimed_request(tmp_path, identity, fetch, lambda value: value)
    assert result.value == "ok"
    assert result.attempt_count == 1
    with pytest.raises(RecoveryError, match="already claimed"):
        execute_claimed_request(tmp_path, identity, fetch, lambda value: value)
    assert calls == 1

    transport_calls = 0

    def transport_failure() -> str:
        nonlocal transport_calls
        transport_calls += 1
        raise RetryableTransportError("synthetic")

    with pytest.raises(RetryableTransportError):
        execute_claimed_request(
            tmp_path,
            RequestClaimIdentity("a" * 64, "c" * 64),
            transport_failure,
            lambda value: value,
        )
    assert transport_calls == 3


def test_semantic_failure_is_never_retried(tmp_path: Path) -> None:
    calls = 0

    def fetch() -> str:
        nonlocal calls
        calls += 1
        return "empty"

    def reject(value: str) -> str:
        raise SemanticResponseError(value)

    with pytest.raises(SemanticResponseError):
        execute_claimed_request(
            tmp_path,
            RequestClaimIdentity("a" * 64, "d" * 64),
            fetch,
            reject,
        )
    assert calls == 1


def test_existing_planners_ingestors_and_lineage_cores_are_byte_unchanged() -> None:
    expected = {
        "src/shaiwei/transform/availability.py": "503a3f04fdfd1795479999905508dea25cf38b837d65a46edf15f9f71f13d23d",
        "src/shaiwei/ingest/baostock.py": "4279972ecd10d7bf3972aadd38dd826574db0bfd4edc38565a12b7e3e5f40333",
        "tools/p1_moneyflow/contract.py": "52ab4fdbe02e797f48a40da9abd61ab646c153bce02d3004f5f4e5a57fcc2620",
        "src/shaiwei/research_gates/m7_moneyflow_lineage/compute.py": "4217e81d55565f946defc15246eb7fd51c824f189c53eb1ac4576848d89e1931",
        "src/shaiwei/research_gates/m7_moneyflow_lineage/audit_compute.py": "07cf58b51d0d0ba9235f0ff09eeb0b262ca4c6dace45f6dbb4b3e1491308cff4",
    }
    assert {path: sha256_file(ROOT / path) for path in expected} == expected


def test_recovery_docker_contract_is_offline_read_only_and_unmounted() -> None:
    compose = yaml.safe_load(
        (ROOT / "compose.m7-moneyflow-evidence-recovery.yaml").read_text(encoding="utf-8")
    )
    service = compose["services"]["m7-evidence-recovery-fixture"]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert service["user"] == "65532:65532"
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    serialized = canonical_json(service)
    for forbidden in ("volumes", ".env", "docker.sock", "/workspace"):
        assert forbidden not in serialized


def test_recovery_modules_stay_below_architecture_soft_limit() -> None:
    package = ROOT / "src/shaiwei/research_gates/m7_moneyflow_recovery"
    counts = {
        path.name: len(path.read_text(encoding="utf-8").splitlines())
        for path in package.glob("*.py")
    }
    assert counts
    assert max(counts.values()) <= 400
