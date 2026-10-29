"""TP-F-0B 预检工程：冻结钉扎、签名规则、18 例 fixture、补遗 A1 分母、scope/逐字批准、单次执行与独立审计。"""

import dataclasses
import json
import shutil
from pathlib import Path

import pytest

from shaiwei.config import PROJECT_ROOT, load
from shaiwei.research.tp_f_0b import audit as audit_module
from shaiwei.research.tp_f_0b import panel as panel_module
from shaiwei.research.tp_f_0b import profile as profile_module
from shaiwei.research.tp_f_0b.contract import (
    ADDENDUM_DOCUMENT_RELATIVE,
    ADDENDUM_RELATIVE,
    DOCUMENT_RELATIVE,
    PROTOCOL_RELATIVE,
    TPFError,
    TPFScope,
    validate_bound_inputs,
)
from shaiwei.research.tp_f_0b.fields import evaluate_gates, final_verdict
from shaiwei.research.tp_f_0b.fixture import CAL, build_store, fixture
from shaiwei.research.tp_f_0b.registry import read_allowed, reproduce_sealed_registry
from shaiwei.research.tp_f_0b.release import main
from shaiwei.research.tp_f_0b.scope import Envelope, Scope, approval_text, load_approved, record_approval, scope_hash, verify
from shaiwei.research.tp_f_0b.signature import SignatureError, SignatureRule, census, signature

PANEL = panel_module.PanelParams(period=("", ""), warmup=100, entry_offset=1, exit_offset=11,
                                 qlib_features=("open", "close", "high", "low", "volume", "vwap"))


FROZEN = (PROTOCOL_RELATIVE, ADDENDUM_RELATIVE, DOCUMENT_RELATIVE, ADDENDUM_DOCUMENT_RELATIVE)


@pytest.fixture(scope="module")
def contract() -> TPFScope:
    return TPFScope.load()


@pytest.fixture(scope="module")
def rule(contract: TPFScope) -> SignatureRule:
    return SignatureRule.from_protocol(contract.document["identity_registry"]["joint_state_signature"])


def test_protocol_and_addendum_are_pinned_and_a1_changes_only_the_raw_basis(contract):
    gates = contract.document["gates"]
    change = contract.addendum["single_change"]
    assert change["thresholds_unchanged"] == {name: gates[name] for name in change["gates_affected"]}
    assert gates["raw_open_coverage_minimum"] == gates["raw_prev_close_join_minimum"] == 0.99
    assert contract.document["result_blind_baseline"]["tp_f_formulas_existing"] == 0
    assert contract.addendum["result_blind"]["tp_f_0b_real_profile_runs"] == 0


@pytest.mark.parametrize("relative", FROZEN)
def test_any_tampered_frozen_file_fails_closed(tmp_path, relative):
    for name in FROZEN:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PROJECT_ROOT / name, tmp_path / name)
    TPFScope.load(tmp_path)
    (tmp_path / relative).write_text((tmp_path / relative).read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(TPFError):
        TPFScope.load(tmp_path)


def test_bound_inputs_match_their_frozen_hashes(contract):
    checks = validate_bound_inputs(contract)
    assert len(checks) == 14 and "config/rf_0c_field_identity_preflight_v1.yaml" in checks


def test_sealed_rf_0b_registry_reproduces_byte_for_byte(contract):
    assert reproduce_sealed_registry(contract)["sections"]["alpha158_family"]["expression_count"] == 158


def test_ledgers_are_read_through_allowed_identity_columns_only(tmp_path):
    path = tmp_path / "ledger.csv"
    path.write_text("attempt_id,semantic_signature,discovery_rank_ic\na1,s1,0.9\n", encoding="utf-8")
    assert read_allowed(path, ["attempt_id", "semantic_signature"]) == [{"attempt_id": "a1", "semantic_signature": "s1"}]
    with pytest.raises(TPFError):
        read_allowed(path, ["attempt_id", "candidate_fingerprint"])


def test_signature_canonicalizes_both_syntaxes_and_fails_closed_on_baselines(rule):
    assert signature("Mean($close,20d)/$close", rule).canonical == signature("Div(Mean($close,20),close)", rule).canonical
    assert signature("Mul($volume,$close)", rule).canonical == signature("$close*$volume", rule).canonical
    assert signature("($close-$low)/($high-$low+1e-12)", rule).pullback_components == 1
    assert signature("Div($close,Ref($close,20d))", rule).trend_components == 1
    assert signature("Div($close,Mean($close,19d))", rule).trend_components == 0
    for bad in ("Mean($amount,5)", "__import__('os')", "$close if 1 else 2"):
        with pytest.raises(SignatureError):
            signature(bad, rule)
    assert census(["Div($close,Mean($close,30d))", "Mean($amount,5)"], rule, fail_closed=False)["parse_failures"] == 1
    with pytest.raises(SignatureError):
        census(["Mean($amount,5)"], rule, fail_closed=True)


def test_all_eighteen_adversarial_fixtures_pass():
    result = fixture()
    assert result["fixture_pass"] is True and result["adversarial_cases"] == 18
    assert result["inherited_rf_0c_classifier"]["fixture_pass"] is True


def test_fixture_fails_closed_when_the_machinery_is_weakened(monkeypatch):
    monkeypatch.setattr(panel_module, "ADJUSTMENT_RTOL", 1.0)
    with pytest.raises(TPFError, match="adj_factor_change_inside_lookback_window"):
        fixture()


def _profile(**overrides):
    base = {
        "raw_open_coverage": 0.995, "raw_prev_close_coverage": 0.995, "unclassified_missing_field_rows": 0,
        "class_counts": {"BSE_ROW": 0}, "qlib_feature_non_missing_on_traded_member_days": 0.999,
        "sw_l1_unique_industry_coverage": 0.992, "next_day_open_exists_on_traded_member_days": 0.998,
    }
    return {**base, **overrides}


def test_gates_and_verdict_precedence(contract):
    gates = contract.document["gates"]
    assert evaluate_gates(_profile(), gates)["pass"] is True
    for override in ({"raw_open_coverage": 0.985}, {"unclassified_missing_field_rows": 1}, {"class_counts": {"BSE_ROW": 1}},
                     {"sw_l1_unique_industry_coverage": 0.98}, {"next_day_open_exists_on_traded_member_days": 0.98}):
        assert evaluate_gates(_profile(**override), gates)["pass"] is False
    assert final_verdict({"pass": True}, "IDENTITY_SPACE_OPEN") == "GO_FORMAL_PROTOCOL"
    assert final_verdict({"pass": False}, "IDENTITY_SPACE_OPEN") == "BLOCKED_DATA"
    assert final_verdict({"pass": False}, "REJECT_DUPLICATE") == "REJECT_DUPLICATE"


FACTS = {"bound_inputs": {"a": "0" * 64}, "raw_artifact_bundle_sha256": "1" * 64, "qlib_artifact_sha256": "2" * 64,
         "qlib_directory_fingerprint": "3" * 64}


def _envelope(contract: TPFScope, control: Path) -> Envelope:
    scope = Scope(
        schema_version="tp-f-0b-scope-v1", protocol_id="tp-f-0b-data-identity-preflight-001", protocol_sha256=contract.sha256,
        protocol_document_sha256="4" * 64, addendum_sha256=contract.addendum_sha256, addendum_document_sha256="5" * 64,
        execution_id="tpf0b-0123456789ab-20261029T000000Z", git_head="6" * 40, image="shaiwei:tp-f-0b-0123456789ab",
        image_id="sha256:" + "7" * 64, code_snapshot_sha256="8" * 64, fixture_report_path="logs/tp-f-0b/fixture/x.json",
        fixture_report_sha256="9" * 64, prepared_at="2026-10-29T00:00:00+00:00", **FACTS,
    )
    envelope = Envelope(scope_sha256=scope_hash(scope), scope=scope)
    path = control / "scopes" / f"{envelope.scope_sha256}.scope.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(envelope.model_dump(mode="json")), encoding="utf-8")
    return envelope


def test_verbatim_approval_is_transcribed_once_and_drift_is_refused(tmp_path, contract):
    envelope = _envelope(contract, tmp_path)
    sha = envelope.scope_sha256
    with pytest.raises(TPFError, match="verbatim"):
        record_approval(sha, "批准", tmp_path)
    with pytest.raises(FileNotFoundError):
        load_approved(sha, tmp_path)
    record_approval(sha, approval_text(envelope), tmp_path)
    with pytest.raises(TPFError, match="already recorded"):
        record_approval(sha, approval_text(envelope), tmp_path)
    approved = load_approved(sha, tmp_path)
    verify(approved, contract, code="8" * 64, facts=FACTS)
    with pytest.raises(TPFError, match="qlib directory"):
        verify(approved, contract, code="8" * 64, facts={**FACTS, "qlib_directory_fingerprint": "f" * 64})
    with pytest.raises(TPFError, match="code"):
        verify(approved, contract, code="0" * 64, facts=FACTS)


def _synthetic_root(tmp_path: Path, contract: TPFScope) -> Path:
    root = tmp_path / "root"
    manifest = build_store(root)
    (root / contract.manifest_relative).parent.mkdir(parents=True, exist_ok=True)
    (root / contract.manifest_relative).write_text(json.dumps(manifest), encoding="utf-8")
    shutil.move(str(root / "data/qlib_bin"), str(root / contract.qlib_root_relative))
    return root


def test_single_execution_writes_once_and_the_independent_audit_recomputes(tmp_path, monkeypatch, contract):
    registry = {"sealed_base": {"reproduced_byte_for_byte": True},
                "extension_layers": {"public_factor_references": {}, "ts_v5_semantic_layer": {"attempts": 28, "x_hashes": []},
                                     "g1_v2_rejudge": {"new_identity": 0}},
                "joint_state_census": {"alpha158": {"joint_state": 0}}}
    monkeypatch.setattr(profile_module, "build_extension_registry", lambda *args, **kwargs: registry)
    monkeypatch.setattr(profile_module.PanelParams, "from_protocol",
                        classmethod(lambda cls, document: dataclasses.replace(PANEL, period=(CAL[0], CAL[115]))))
    root = _synthetic_root(tmp_path, contract)
    control, output, audits = tmp_path / "control", tmp_path / "out", tmp_path / "audit"
    envelope = _envelope(contract, control)
    record_approval(envelope.scope_sha256, approval_text(envelope), control)
    limits = load().limit_rules.model_dump()
    common = {"control": control, "root": PROJECT_ROOT, "facts": lambda _: FACTS, "code": "8" * 64, "limits": limits}
    run = dict(scope_sha256=envelope.scope_sha256, execution_id=envelope.scope.execution_id, release={}, root=root,
               output_root=output, limits=limits)
    result = profile_module.run_once(contract, **run)
    assert result["verdict"] == "BLOCKED_DATA" and result["identity_verdict"] == "IDENTITY_SPACE_OPEN"
    directory = output / envelope.scope.execution_id
    assert sorted(path.name for path in directory.iterdir()) == [
        "field_profile.json", "identity_registry.json", "manifest.json", "profile.json", "semantic_read_started.json"]
    assert json.loads((directory / "profile.json").read_text())["internal_deterministic_replay_pass"] is True
    with pytest.raises(TPFError, match="same-scope rerun"):
        profile_module.run_once(contract, **run)
    monkeypatch.setattr(audit_module, "compute", lambda scope, **kwargs: profile_module.compute(scope, root=root, limits=limits))
    report = audit_module.audit_once(envelope.scope_sha256, **{**common, "evidence_root": output, "audit_root": audits})
    assert report["independent_audit"] == "PASS"
    with pytest.raises(TPFError, match="same-scope audit rerun"):
        audit_module.audit_once(envelope.scope_sha256, **{**common, "evidence_root": output, "audit_root": audits})
    (directory / "field_profile.json").chmod(0o644)
    (directory / "field_profile.json").write_text("{}", encoding="utf-8")
    with pytest.raises(TPFError, match="field_profile_recomputed"):
        audit_module.audit_once(envelope.scope_sha256, **{**common, "evidence_root": output, "audit_root": tmp_path / "audit2"})


def test_cli_refuses_fixture_output_outside_its_directory(tmp_path):
    with pytest.raises(SystemExit):
        main(["fixture", "--output", str(tmp_path / "fixture.json")])
