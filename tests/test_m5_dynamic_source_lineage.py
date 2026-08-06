from __future__ import annotations

import json
from pathlib import Path

import pytest

from shaiwei.research_gates.m5_dynamic.contract import (
    M5GateError,
    canonical_json,
    sha256_file,
    sha256_json,
)
from shaiwei.research_gates.m5_dynamic.lineage import assess_lineage
from shaiwei.research_gates.m5_dynamic.lineage_auditor import (
    audit_lineage_run,
    seal_lineage_audit,
)
from shaiwei.research_gates.m5_dynamic.lineage_commitment import (
    value_version_sha256,
)
from shaiwei.research_gates.m5_dynamic.lineage_contract import (
    PROTOCOL_SCOPE_SHA256,
    Observation,
    VersionEvidence,
)
from shaiwei.research_gates.m5_dynamic.lineage_projection import (
    GO_VERDICT,
    NO_GO_VERDICT,
    build_lineage_reports,
)
from shaiwei.research_gates.m5_dynamic.lineage_sealing import seal_lineage_run


INPUT_SHA = "1" * 64
RELEASE_SHA = "2" * 64
CODE_SHA = "3" * 64
APPROVAL_SHA = "4" * 64
AS_OF = "2025-06-30T16:00:00+08:00"


def _identity() -> dict[str, str]:
    return {
        "ts_code": "990001.SH",
        "f_ann_date": "20250315",
        "end_date": "20241231",
        "report_type": "1",
        "update_flag": "1",
    }


def _observation(
    total_assets: int,
    *,
    observed_at: str,
    batch: str,
    source_kind: str = "STANDARD",
) -> Observation:
    table = "balancesheet"
    return Observation.from_mapping(
        {
            "table": table,
            "source_kind": source_kind,
            "source_api": f"tushare.{table}{'_vip' if source_kind == 'VIP' else ''}",
            "statement_identity": _identity(),
            "business_values": {
                "accounts_receiv": 10,
                "inventories": 20,
                "total_assets": total_assets,
                "total_liab": 40,
                "total_cur_assets": 50,
                "total_cur_liab": 30,
            },
            "request_params_sha256": "a" * 64,
            "batch_id": batch,
            "content_sha256": sha256_json(batch),
            "local_observed_at": observed_at,
        }
    )


def _evidence(
    observation: Observation,
    *,
    version: str,
    effective_at: str,
    predecessor: str | None,
    tier: str = "E2_PROVIDER_DECLARED_VERSION",
) -> VersionEvidence:
    version_sha = sha256_json(version)
    return VersionEvidence.from_mapping(
        {
            "table": observation.table,
            "statement_identity": _identity(),
            "provider_version_id_sha256": version_sha,
            "value_version_sha256": value_version_sha256(observation),
            "predecessor_provider_version_id_sha256": (
                None if predecessor is None else sha256_json(predecessor)
            ),
            "evidence_tier": tier,
            "provider_revision_effective_at": effective_at,
            "evidence_content_sha256": sha256_json(f"content:{version}"),
            "evidence_locator_sha256": sha256_json(f"locator:{version}"),
        }
    )


def _two_versions() -> tuple[Observation, Observation]:
    return (
        _observation(
            100,
            observed_at="2025-03-16T01:00:00+00:00",
            batch="batch-old",
        ),
        _observation(
            101,
            observed_at="2025-04-02T01:00:00+00:00",
            batch="batch-new",
            source_kind="VIP",
        ),
    )


def _resolved() -> tuple[list[Observation], list[VersionEvidence]]:
    old, new = _two_versions()
    return [old, new], [
        _evidence(
            old,
            version="provider-v1",
            effective_at="2025-03-15T09:00:00+00:00",
            predecessor=None,
        ),
        _evidence(
            new,
            version="provider-v2",
            effective_at="2025-04-01T09:00:00+00:00",
            predecessor="provider-v1",
        ),
    ]


def _run(
    tmp_path: Path,
    observations: list[Observation],
    evidence: list[VersionEvidence],
):
    assessment = assess_lineage(observations, evidence, as_of=AS_OF)
    lineage, gate = build_lineage_reports(
        assessment,
        protocol_scope_sha256=PROTOCOL_SCOPE_SHA256,
        input_manifest_sha256=INPUT_SHA,
        release_scope_sha256=RELEASE_SHA,
        code_bundle_sha256=CODE_SHA,
        approval_event_sha256=APPROVAL_SHA,
        semantic_rows_read=False,
    )
    manifest = seal_lineage_run(tmp_path / "runs", lineage, gate)
    run_root = tmp_path / "runs" / manifest["run_id"]
    return assessment, lineage, gate, manifest, run_root


def _audit(
    observations: list[Observation],
    evidence: list[VersionEvidence],
    run_root: Path,
):
    return audit_lineage_run(
        observations,
        evidence,
        as_of=AS_OF,
        run_root=run_root,
        expected_protocol_scope_sha256=PROTOCOL_SCOPE_SHA256,
        expected_input_manifest_sha256=INPUT_SHA,
        expected_release_scope_sha256=RELEASE_SHA,
        expected_approval_event_sha256=APPROVAL_SHA,
    )


def test_exact_duplicate_is_losslessly_accepted() -> None:
    first = _observation(
        100,
        observed_at="2025-03-16T01:00:00+00:00",
        batch="batch-one",
    )
    second = _observation(
        100,
        observed_at="2025-03-17T01:00:00+00:00",
        batch="batch-two",
    )
    result = assess_lineage([first, second], [], as_of=AS_OF)

    assert result.historical_pass is True
    assert result.report["disposition_counts"]["LOSSLESS_EXACT_DUPLICATE"] == 1


def test_local_ingest_order_and_same_update_flag_cannot_resolve_history() -> None:
    observations = list(_two_versions())
    result = assess_lineage(observations, [], as_of=AS_OF)

    assert result.historical_pass is False
    assert result.groups[0].disposition == "FORWARD_ONLY_OBSERVED_VERSION"
    assert result.report["conflicting_identity_group_count"] == 1


def test_unique_authoritative_chain_resolves_without_source_priority() -> None:
    observations, evidence = _resolved()
    result = assess_lineage(observations, evidence, as_of=AS_OF)

    assert result.historical_pass is True
    assert result.groups[0].disposition == "PIT_VERSION_CHAIN_RESOLVED"
    assert result.report["disposition_counts"]["PIT_VERSION_CHAIN_RESOLVED"] == 1


def test_missing_effective_time_fails_closed() -> None:
    observations, evidence = _resolved()
    result = assess_lineage(observations, evidence[:1], as_of=AS_OF)

    assert result.groups[0].disposition == "UNRESOLVED_MISSING_EFFECTIVE_TIME"
    assert result.historical_pass is False


def test_simultaneous_divergent_versions_are_ambiguous() -> None:
    observations, evidence = _resolved()
    same_time = evidence[0].provider_revision_effective_at
    replacement = _evidence(
        observations[1],
        version="provider-v2",
        effective_at=same_time,
        predecessor="provider-v1",
    )
    result = assess_lineage(observations, [evidence[0], replacement], as_of=AS_OF)

    assert result.groups[0].disposition == "UNRESOLVED_AMBIGUOUS_ORDER"


def test_missing_predecessor_and_future_evidence_do_not_pass() -> None:
    observations, evidence = _resolved()
    broken = _evidence(
        observations[1],
        version="provider-v2",
        effective_at="2025-04-01T09:00:00+00:00",
        predecessor="provider-unknown",
    )
    broken_result = assess_lineage(observations, [evidence[0], broken], as_of=AS_OF)
    assert broken_result.groups[0].disposition == "UNRESOLVED_INCOMPLETE_CHAIN"

    future = _evidence(
        observations[1],
        version="provider-v2",
        effective_at="2025-08-01T09:00:00+00:00",
        predecessor="provider-v1",
    )
    future_result = assess_lineage(observations, [evidence[0], future], as_of=AS_OF)
    assert future_result.groups[0].disposition == "UNRESOLVED_MISSING_EFFECTIVE_TIME"
    assert future_result.report["future_evidence_count"] == 1


def test_unexplained_value_rollback_is_incomplete() -> None:
    observations, evidence = _resolved()
    rollback = _observation(
        100,
        observed_at="2025-04-03T01:00:00+00:00",
        batch="batch-rollback",
        source_kind="VIP",
    )

    result = assess_lineage([*observations, rollback], evidence, as_of=AS_OF)

    assert result.groups[0].disposition == "UNRESOLVED_INCOMPLETE_CHAIN"
    assert result.historical_pass is False


def test_observation_after_cutoff_and_preannouncement_evidence_fail_closed() -> None:
    future_observation = _observation(
        100,
        observed_at="2025-07-01T01:00:00+00:00",
        batch="batch-after-cutoff",
    )
    with pytest.raises(M5GateError, match="observation occurs after as_of"):
        assess_lineage([future_observation], [], as_of=AS_OF)

    observations, evidence = _resolved()
    impossible = _evidence(
        observations[0],
        version="provider-v1",
        effective_at="2025-03-14T09:00:00+00:00",
        predecessor=None,
    )
    result = assess_lineage(observations, [impossible, evidence[1]], as_of=AS_OF)
    assert result.groups[0].disposition == "UNRESOLVED_INCOMPLETE_CHAIN"


def test_sealing_is_byte_deterministic_and_auditor_is_independent(
    tmp_path: Path,
) -> None:
    observations, evidence = _resolved()
    _, lineage, gate, first, run_root = _run(tmp_path, observations, evidence)
    second = seal_lineage_run(tmp_path / "runs", lineage, gate)
    other = seal_lineage_run(tmp_path / "other", lineage, gate)
    audit = _audit(observations, evidence, run_root)
    sealed = seal_lineage_audit(tmp_path / "audits", audit)
    replay = seal_lineage_audit(tmp_path / "audits", audit)

    assert first == second == other
    assert first["verdict"] == GO_VERDICT
    assert sealed == replay
    assert sealed["status"] == "PASS"
    for filename in sorted(path.name for path in run_root.iterdir()):
        assert (run_root / filename).read_bytes() == (
            tmp_path / "other" / first["run_id"] / filename
        ).read_bytes()


def test_no_go_is_sealed_and_independently_reproduced(tmp_path: Path) -> None:
    observations = list(_two_versions())
    _, _, _, manifest, run_root = _run(tmp_path, observations, [])
    audit = _audit(observations, [], run_root)

    assert manifest["verdict"] == NO_GO_VERDICT
    assert audit["status"] == "PASS"
    assert audit["verdict"] == NO_GO_VERDICT


def test_tamper_and_forbidden_field_injection_fail_audit(tmp_path: Path) -> None:
    observations, evidence = _resolved()
    _, _, _, _, run_root = _run(tmp_path, observations, evidence)
    lineage_path = run_root / "source_lineage_report.json"
    gate_path = run_root / "lineage_gate_report.json"
    manifest_path = run_root / "run_manifest.json"
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    lineage["raw_value"] = "forbidden"
    lineage_path.write_text(canonical_json(lineage) + "\n", encoding="utf-8")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    gate["source_lineage_report"]["sha256"] = sha256_file(lineage_path)
    gate_path.write_text(canonical_json(gate) + "\n", encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["source_lineage_report"]["sha256"] = sha256_file(lineage_path)
    manifest["artifacts"]["lineage_gate_report"]["sha256"] = sha256_file(gate_path)
    manifest_path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")

    with pytest.raises(M5GateError, match="forbidden fields"):
        _audit(observations, evidence, run_root)


def test_partial_directory_fails_closed(tmp_path: Path) -> None:
    observations, evidence = _resolved()
    assessment = assess_lineage(observations, evidence, as_of=AS_OF)
    lineage, gate = build_lineage_reports(
        assessment,
        protocol_scope_sha256=PROTOCOL_SCOPE_SHA256,
        input_manifest_sha256=INPUT_SHA,
        release_scope_sha256=RELEASE_SHA,
        code_bundle_sha256=CODE_SHA,
        approval_event_sha256=APPROVAL_SHA,
        semantic_rows_read=False,
    )
    identity = {
        key: str(gate[key])
        for key in (
            "protocol_scope_sha256",
            "input_manifest_sha256",
            "release_scope_sha256",
            "code_bundle_sha256",
            "approval_event_sha256",
            "outcome_kind",
        )
    }
    partial = tmp_path / "runs" / sha256_json(identity)
    partial.mkdir(parents=True)
    (partial / "run_manifest.json").touch()

    with pytest.raises((M5GateError, json.JSONDecodeError)):
        seal_lineage_run(tmp_path / "runs", lineage, gate)


def test_independent_audit_does_not_import_primary_lineage_modules() -> None:
    root = Path(__file__).parents[1]
    for relative in (
        "src/shaiwei/research_gates/m5_dynamic/audit_lineage.py",
        "src/shaiwei/research_gates/m5_dynamic/lineage_auditor.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        for forbidden in (
            "from .lineage import",
            "from .lineage_commitment import",
            "from .lineage_sealing import",
        ):
            assert forbidden not in source
