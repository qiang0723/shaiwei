from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from shaiwei.research_gates.m7_moneyflow.audit_compute import (
    recompute_quality_core,
    recompute_quality_core_all_a_source,
)
from shaiwei.research_gates.m7_moneyflow.compute import (
    compute_quality_core,
    compute_quality_core_all_a_source,
)
from shaiwei.research_gates.m7_moneyflow.consumption import (
    execute_after_pre_read_claim,
)
from shaiwei.research_gates.m7_moneyflow.contract import (
    M7GateError,
    M7Protocol,
    sha256_json,
)
from shaiwei.research_gates.m7_moneyflow.fixture import run_fixture, synthetic_inputs
from shaiwei.research_gates.m7_moneyflow.reader import KeyInputs


ROOT = Path(__file__).resolve().parents[1]


def _protocol() -> M7Protocol:
    return M7Protocol.load(
        ROOT / "config/m7_star_custom_pool_moneyflow_data_v1.yaml",
        build_path=ROOT / "config/m7_star_custom_pool_moneyflow_data_gate_build_v1.yaml",
        project_root=ROOT,
    )


def _with_source_row(code: str) -> KeyInputs:
    clean = synthetic_inputs()
    source = pd.concat(
        [
            clean.source_keys,
            pd.DataFrame(
                [
                    {
                        "ts_code": code,
                        "trade_date": "20201231",
                        "request_trade_date": "20201231",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    return KeyInputs(
        clean.membership,
        source,
        clean.official_dates,
        clean.quarantined_source_dates,
        clean.evidence,
    )


def _gate(core: dict[str, object], gate_id: str) -> dict[str, object]:
    return next(item for item in core["gates"] if item["gate_id"] == gate_id)


def test_legacy_v1_fixture_hashes_are_unchanged() -> None:
    result = run_fixture(_protocol())
    assert result["clean_core_sha256"] == (
        "fba879c245988e427abc9d4d4b71a2a541c29edf2cceb84fd2811b0a689a9209"
    )
    assert result["duplicate_core_sha256"] == (
        "4578ae15911dfedb608f5d66bb341764e006578243e99c3e5aef9dc29a113094"
    )
    assert result["sparse_core_sha256"] == (
        "4c3a04d4a33fdeb7f85b4bf53a1f7e1f32e111eb024cdcf1da8d58dd3afee120"
    )


def test_successor_accepts_sz_source_without_changing_membership_domain() -> None:
    protocol = _protocol()
    inputs = _with_source_row("123456.SZ")
    legacy_main = compute_quality_core(protocol, inputs)
    legacy_audit = recompute_quality_core(protocol, inputs)
    assert legacy_main == legacy_audit
    assert _gate(legacy_main, "required_keys_valid")["status"] == "FAIL"

    successor_main = compute_quality_core_all_a_source(protocol, inputs)
    successor_audit = recompute_quality_core_all_a_source(protocol, inputs)
    assert successor_main == successor_audit
    assert sha256_json(successor_main) == sha256_json(successor_audit)
    assert successor_main["validity"]["source_malformed_key_count"] == 0
    assert _gate(successor_main, "required_keys_valid")["status"] == "PASS"
    assert successor_main["verdict"] == "GO_M7_0_DATA_COMPATIBILITY_ONLY"


@pytest.mark.parametrize("code", ["123456.BJ", "123456.XX", "bad-code"])
def test_successor_rejects_bse_and_malformed_source_codes(code: str) -> None:
    protocol = _protocol()
    inputs = _with_source_row(code)
    main = compute_quality_core_all_a_source(protocol, inputs)
    audit = recompute_quality_core_all_a_source(protocol, inputs)
    assert main == audit
    assert _gate(main, "required_keys_valid")["status"] == "FAIL"
    if code.endswith(".BJ"):
        assert _gate(main, "bse_absent")["status"] == "FAIL"


def test_successor_keeps_star_membership_sh_only() -> None:
    protocol = _protocol()
    clean = synthetic_inputs()
    membership = clean.membership.copy()
    membership.loc[membership.index[0], "ts_code"] = "123456.SZ"
    inputs = KeyInputs(
        membership,
        clean.source_keys,
        clean.official_dates,
        clean.quarantined_source_dates,
        clean.evidence,
    )
    main = compute_quality_core_all_a_source(protocol, inputs)
    audit = recompute_quality_core_all_a_source(protocol, inputs)
    assert main == audit
    assert main["validity"]["membership_malformed_key_count"] == 1
    assert _gate(main, "required_keys_valid")["status"] == "FAIL"


def _identity(role: str = "runner") -> dict[str, str]:
    return {
        "protocol_sha256": "a" * 64,
        "release_scope_sha256": "b" * 64,
        "approval_sha256": "c" * 64,
        "role": role,
        "run_id": "d" * 64,
    }


def test_duplicate_claim_fails_before_semantic_loader(tmp_path: Path) -> None:
    calls: list[str] = []

    def loader() -> str:
        calls.append("semantic-read")
        return "loaded"

    claim, result = execute_after_pre_read_claim(tmp_path, _identity(), loader)
    assert result == "loaded"
    assert claim["same_identity_retry_authorized"] is False
    assert calls == ["semantic-read"]
    with pytest.raises(M7GateError, match="already consumed"):
        execute_after_pre_read_claim(tmp_path, _identity(), loader)
    assert calls == ["semantic-read"]


def test_failed_first_loader_still_consumes_identity(tmp_path: Path) -> None:
    calls = 0

    def failing_loader() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("synthetic loader failure")

    with pytest.raises(RuntimeError, match="synthetic loader failure"):
        execute_after_pre_read_claim(tmp_path, _identity(), failing_loader)
    with pytest.raises(M7GateError, match="already consumed"):
        execute_after_pre_read_claim(tmp_path, _identity(), failing_loader)
    assert calls == 1


def test_runner_and_auditor_have_independent_consumption_roles(tmp_path: Path) -> None:
    calls: list[str] = []
    execute_after_pre_read_claim(tmp_path, _identity("runner"), lambda: calls.append("runner"))
    execute_after_pre_read_claim(tmp_path, _identity("auditor"), lambda: calls.append("auditor"))
    assert calls == ["runner", "auditor"]
