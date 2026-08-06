from __future__ import annotations

import csv
import dataclasses
from pathlib import Path

import pandas as pd
import pytest
import yaml

from shaiwei.research_gates.gate_registry.schema import EXPECTED_SCHEMA_FINGERPRINT
from shaiwei.research_gates.m5_dynamic.contract import (
    API_FIELDS,
    M5GateError,
    canonical_json,
    sha256_file,
    sha256_json,
)
from shaiwei.research_gates.m5_dynamic.lineage import assess_lineage
from shaiwei.research_gates.m5_dynamic.lineage_contract import (
    PROTOCOL_SCOPE_SHA256,
    LineageInputManifest,
    LineageProtocol,
    SOURCE_APIS,
)
from shaiwei.research_gates.m5_dynamic.lineage_inventory import build_lineage_input_manifest
from shaiwei.research_gates.m5_dynamic.lineage_input_bundle import materialize_lineage_bundle
from shaiwei.research_gates.m5_dynamic.lineage_reader import load_lineage_inputs
from shaiwei.research_gates.m5_dynamic.lineage_release import (
    APPROVER_SHA256,
    LineageApprovalEnvelope,
    LineageReleaseScope,
)
from shaiwei.research_gates.m5_dynamic.lineage_release_builder import (
    build_lineage_release_document,
)


ROOT = Path(__file__).parents[1]
CREATED_AT = "2026-08-06T04:00:00+00:00"


def _protocol() -> LineageProtocol:
    return LineageProtocol.load(
        protocol_path=ROOT / "config/m5_dynamic_fundamental_source_lineage_recovery_v3.yaml",
        build_path=ROOT / "config/m5_dynamic_fundamental_source_lineage_build_v3.yaml",
        scope_path=(ROOT / "config/m5_dynamic_fundamental_source_lineage_recovery_protocol_scope_v3.json"),
        project_root=ROOT,
    )


def _row(api: str, index: int, value: int) -> dict[str, object]:
    result: dict[str, object] = {}
    for field in API_FIELDS[api]:
        if field == "ts_code":
            result[field] = f"99{index:04d}.SH"
        elif field == "f_ann_date":
            result[field] = "20260131"
        elif field == "end_date":
            result[field] = "20251231"
        elif field in {"report_type", "update_flag"}:
            result[field] = "1"
        else:
            result[field] = float(value)
    return result


def _batch(tmp_path: Path, api: str, rows: list[dict[str, object]]) -> dict[str, object]:
    name = api.replace(".", "-")
    path = tmp_path / f"data/{name}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=API_FIELDS[api]).to_parquet(path, index=False)
    fields = list(pd.read_parquet(path).columns)
    batch_id = f"fixture-{name}"
    identity = {
        "batch_id": batch_id,
        "source_api": api,
        "params_json": canonical_json({"fixture": name}),
        "ingest_time": "2026-08-06T03:00:00+00:00",
        "relative_path": path.relative_to(tmp_path).as_posix(),
        "row_count": len(rows),
        "bytes": path.stat().st_size,
        "content_sha256": sha256_file(path),
        "operator": "synthetic-fixture",
    }
    return {
        "batch_id": batch_id,
        "batch_identity_sha256": sha256_json(identity),
        "relative_path": path.relative_to(tmp_path).as_posix(),
        "content_sha256": sha256_file(path),
        "request_params_sha256": sha256_json({"fixture": name}),
        "row_count": len(rows),
        "bytes": path.stat().st_size,
        "schema_fields": fields,
        "ingest_time": "2026-08-06T03:00:00+00:00",
    }


def _source(api: str, batch: dict[str, object]) -> dict[str, object]:
    batches = [batch]
    return {"source_api": api, "selection_sha256": sha256_json(batches), "batches": batches}


def _lineage_manifest(tmp_path: Path) -> Path:
    sources = []
    for api in SOURCE_APIS:
        table = api.removeprefix("tushare.").removesuffix("_vip")
        if table == "balancesheet":
            rows = [_row(api, index, 100 if api.endswith("_vip") else 99) for index in range(8)]
        elif table == "cashflow":
            rows = [_row(api, 100 + index, 200 if api.endswith("_vip") else 199) for index in range(15)]
        else:
            rows = [_row(api, 900, 1)]
        sources.append(_source(api, _batch(tmp_path, api, rows)))
    document = {
        "schema_version": "m5-source-lineage-input-v1",
        "created_at": CREATED_AT,
        "protocol_scope_sha256": PROTOCOL_SCOPE_SHA256,
        "semantic_rows_read": False,
        "prior_conflict_identity": {
            "case_id": "a2539149d588a0c19f9cb73331f19a66df63e301df03f56fbb2c8e5c74672068",
            "release_scope_sha256": ("8858912f14577a8911e47f0ec338cde82208fe818b4c7a921578e42aeeed6f65"),
            "conflict_group_count": 23,
            "conflict_groups_by_table": {"balancesheet": 8, "cashflow": 15, "income": 0},
        },
        "ledger_selection_scope": list(SOURCE_APIS),
        "anchor_sources": sources,
        "history_sources": sources,
        "authoritative_evidence": [],
    }
    path = tmp_path / "lineage-input.json"
    path.write_text(canonical_json(document) + "\n", encoding="utf-8")
    return path


def test_lineage_reader_recovers_exact_23_groups_without_claiming_history(
    tmp_path: Path,
) -> None:
    manifest = LineageInputManifest.load(_lineage_manifest(tmp_path))
    observations, evidence, source = load_lineage_inputs(manifest, input_root=tmp_path)
    result = assess_lineage(observations, evidence, as_of=CREATED_AT)

    assert source["anchor_conflicting_identity_group_count"] == 23
    assert result.report["conflicting_identity_group_count"] == 23
    assert result.report["disposition_counts"]["FORWARD_ONLY_OBSERVED_VERSION"] == 23
    assert result.historical_pass is False


def test_lineage_inventory_reads_only_metadata_and_binds_prior_anchor(tmp_path: Path) -> None:
    protocol = _protocol()
    source_manifest = LineageInputManifest.load(_lineage_manifest(tmp_path)).document
    prior = {
        "schema_version": "m5-data-input-v1",
        "semantic_rows_read": False,
        "sources": source_manifest["anchor_sources"],
    }
    prior_path = tmp_path / "prior-input.json"
    prior_path.write_text(canonical_json(prior) + "\n", encoding="utf-8")
    prior_release = {"scope": {"input_manifest_sha256": sha256_json(prior)}}
    release_path = tmp_path / "prior-release.json"
    release_path.write_text(canonical_json(prior_release) + "\n", encoding="utf-8")
    ledger_path = tmp_path / "ledger.csv"
    fieldnames = [
        "batch_id",
        "ingest_time",
        "source_api",
        "params_json",
        "row_count",
        "parquet_path",
        "content_sha256",
        "operator",
    ]
    with ledger_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for source in source_manifest["history_sources"]:
            for batch in source["batches"]:
                name = source["source_api"].replace(".", "-")
                writer.writerow(
                    {
                        "batch_id": batch["batch_id"],
                        "ingest_time": batch["ingest_time"],
                        "source_api": source["source_api"],
                        "params_json": canonical_json({"fixture": name}),
                        "row_count": batch["row_count"],
                        "parquet_path": batch["relative_path"],
                        "content_sha256": batch["content_sha256"],
                        "operator": "synthetic-fixture",
                    }
                )
    document = build_lineage_input_manifest(
        protocol,
        project_root=tmp_path,
        ledger_path=ledger_path,
        prior_manifest_path=prior_path,
        prior_release_path=release_path,
        created_at=CREATED_AT,
    )
    path = tmp_path / "inventory.json"
    path.write_text(canonical_json(document) + "\n", encoding="utf-8")

    loaded = LineageInputManifest.load(path)
    assert loaded.document["semantic_rows_read"] is False
    assert len(loaded.document["history_sources"]) == 6
    assert loaded.document["authoritative_evidence"] == []


def test_lineage_release_is_content_addressed_offline_and_unapproved(tmp_path: Path) -> None:
    protocol = _protocol()
    manifest = LineageInputManifest.load(_lineage_manifest(tmp_path))
    research = yaml.safe_load(
        (ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml").read_text(encoding="utf-8")
    )
    commit = "1" * 40
    prefix = f"data/control/m5_2/lineage-input-bundles/{manifest.sha256}-{commit[:7]}"
    document = build_lineage_release_document(
        protocol,
        manifest,
        source_proposal=research["source_proposal"],
        created_at=CREATED_AT,
        git_commit=commit,
        origin_main_commit=commit,
        code_bundle_sha256="2" * 64,
        requirements_lock_sha256="3" * 64,
        dockerfile_sha256="4" * 64,
        compose_sha256="5" * 64,
        auditor_code_sha256="6" * 64,
        image_id=f"sha256:{'7' * 64}",
        repo_digest=f"shaiwei-m5-lineage@sha256:{'7' * 64}",
        platform="linux/arm64",
        input_relative_path=prefix,
        output_relative_path="data/control/m5_2/lineage-output/release-fixture",
        audit_relative_path="data/control/m5_2/lineage-audit/release-fixture",
        registry_relative_path="data/control/m5_2/lineage-runtime/release-fixture",
    )
    path = tmp_path / "release.json"
    path.write_text(canonical_json(document) + "\n", encoding="utf-8")
    loaded = LineageReleaseScope.load(
        path,
        protocol,
        manifest,
        source_proposal=research["source_proposal"],
    )

    assert loaded.sha256 == sha256_json(loaded.scope)
    assert loaded.scope["container"]["network_mode"] == "none"
    assert loaded.scope["authority"]["lineage_execution_authorized"] is False
    assert loaded.scope["authority"]["real_data_read_authorized"] is False


def test_lineage_release_rejects_scope_drift(tmp_path: Path) -> None:
    protocol = _protocol()
    manifest = LineageInputManifest.load(_lineage_manifest(tmp_path))
    research = yaml.safe_load(
        (ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml").read_text(encoding="utf-8")
    )
    commit = "1" * 40
    document = build_lineage_release_document(
        protocol,
        manifest,
        source_proposal=research["source_proposal"],
        created_at=CREATED_AT,
        git_commit=commit,
        origin_main_commit=commit,
        code_bundle_sha256="2" * 64,
        requirements_lock_sha256="3" * 64,
        dockerfile_sha256="4" * 64,
        compose_sha256="5" * 64,
        auditor_code_sha256="6" * 64,
        image_id=f"sha256:{'7' * 64}",
        repo_digest=f"shaiwei-m5-lineage@sha256:{'7' * 64}",
        platform="linux/arm64",
        input_relative_path=f"data/control/m5_2/lineage-input-bundles/{manifest.sha256}-1111111",
        output_relative_path="data/control/m5_2/lineage-output/release-fixture",
        audit_relative_path="data/control/m5_2/lineage-audit/release-fixture",
        registry_relative_path="data/control/m5_2/lineage-runtime/release-fixture",
    )
    document["scope"]["authority"]["real_data_read_authorized"] = True
    document["release_scope_sha256"] = sha256_json(document["scope"])
    path = tmp_path / "release-drift.json"
    path.write_text(canonical_json(document) + "\n", encoding="utf-8")

    with pytest.raises(M5GateError, match="silently grants authority"):
        LineageReleaseScope.load(
            path,
            protocol,
            manifest,
            source_proposal=research["source_proposal"],
        )


def test_lineage_approval_and_bundle_are_exact_write_once(tmp_path: Path) -> None:
    protocol = _protocol()
    manifest_path = _lineage_manifest(tmp_path)
    manifest = LineageInputManifest.load(manifest_path)
    input_source = f"data/control/m5_2/lineage-input-bundles/{manifest.sha256}-1111111"
    release = LineageReleaseScope(
        document={},
        scope={"container": {"mounts": [{"source": input_source, "target": "/lineage-input", "mode": "ro"}]}},
        sha256="2" * 64,
    )
    approval_document = {
        "schema_version": "m5-source-lineage-approval-v1",
        "case_id": "6b6c849f4ded89f631e1af8127f0e7321898aa7f4ce0c2630806fc8c8ef7be16",
        "release_scope_sha256": release.sha256,
        "approval_event_seq": 4,
        "approval_event_sha256": "3" * 64,
        "approval_actor_sha256": APPROVER_SHA256,
        "registry_schema_fingerprint": EXPECTED_SCHEMA_FINGERPRINT,
        "lineage_execution_authorized": True,
    }
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(canonical_json(approval_document) + "\n", encoding="utf-8")
    approval = LineageApprovalEnvelope.load(approval_path, release)
    fake_protocol = dataclasses.replace(
        protocol,
        build_document={**protocol.build_document, "frozen_inputs": {}},
    )
    build_path = tmp_path / "build.yaml"
    release_path = tmp_path / "release.json"
    build_path.write_text("fixture: true\n", encoding="utf-8")
    release_path.write_text("{}\n", encoding="utf-8")
    bundle_root = tmp_path / input_source

    first = materialize_lineage_bundle(
        fake_protocol,
        manifest,
        release,
        approval,
        project_root=tmp_path,
        bundle_root=bundle_root,
        build_path=build_path,
        manifest_path=manifest_path,
        release_path=release_path,
        approval_path=approval_path,
    )
    second = materialize_lineage_bundle(
        fake_protocol,
        manifest,
        release,
        approval,
        project_root=tmp_path,
        bundle_root=bundle_root,
        build_path=build_path,
        manifest_path=manifest_path,
        release_path=release_path,
        approval_path=approval_path,
    )

    assert first == second
    assert first["semantic_rows_read"] is False
    assert (bundle_root / "bundle_manifest.json").is_file()
