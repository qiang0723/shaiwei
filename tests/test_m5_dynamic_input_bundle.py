from __future__ import annotations

import dataclasses
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from shaiwei.research_gates.m5_dynamic.contract import (
    InputManifest,
    M5DataProtocol,
    M5GateError,
    sha256_file,
)
from shaiwei.research_gates.m5_dynamic.input_bundle import materialize_bundle


ROOT = Path(__file__).parents[1]


def _protocol_without_frozen_controls() -> M5DataProtocol:
    protocol = M5DataProtocol.load(
        ROOT / "config/m5_dynamic_fundamental_cross_pool_v1.yaml",
        build_path=ROOT / "config/m5_dynamic_fundamental_data_gate_build_v1.yaml",
        project_root=ROOT,
    )
    return dataclasses.replace(
        protocol,
        build_document={**protocol.build_document, "frozen_inputs": {}},
    )


def _manifest(tmp_path: Path) -> tuple[InputManifest, Path]:
    source = tmp_path / "data/raw/fixture.parquet"
    source.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"ts_code": ["990001.SH"], "value": [1.0]}).to_parquet(
        source, index=False
    )
    metadata = pq.read_metadata(source)
    item = {
        "relative_path": source.relative_to(tmp_path).as_posix(),
        "content_sha256": sha256_file(source),
        "row_count": metadata.num_rows,
        "bytes": source.stat().st_size,
        "schema_fields": list(metadata.schema.names),
    }
    document = {
        "sources": [{"source_api": "fixture", "batches": [item]}],
        "memberships": [],
    }
    return InputManifest(document=document, sha256="8" * 64), source


def _control_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    paths = tuple(tmp_path / name for name in ("input.json", "release.json", "approval.json"))
    for index, path in enumerate(paths):
        path.write_text(f"fixture-{index}\n", encoding="utf-8")
    return paths


def test_approved_input_bundle_is_hard_linked_write_once_and_value_blind(
    tmp_path: Path,
) -> None:
    protocol = _protocol_without_frozen_controls()
    manifest, source = _manifest(tmp_path)
    input_path, release_path, approval_path = _control_files(tmp_path)
    parent = tmp_path / "data/control/m5_2/input-bundles"

    first = materialize_bundle(
        protocol,
        manifest,
        project_root=tmp_path,
        bundle_parent=parent,
        input_manifest_path=input_path,
        release_scope_path=release_path,
        approval_envelope_path=approval_path,
    )
    second = materialize_bundle(
        protocol,
        manifest,
        project_root=tmp_path,
        bundle_parent=parent,
        input_manifest_path=input_path,
        release_scope_path=release_path,
        approval_envelope_path=approval_path,
    )

    linked = parent / manifest.sha256 / source.relative_to(tmp_path)
    assert first == second
    assert first["semantic_rows_read"] is False
    assert linked.stat().st_ino == source.stat().st_ino


def test_existing_bundle_tamper_fails_closed(tmp_path: Path) -> None:
    protocol = _protocol_without_frozen_controls()
    manifest, _ = _manifest(tmp_path)
    controls = _control_files(tmp_path)
    parent = tmp_path / "data/control/m5_2/input-bundles"
    materialize_bundle(
        protocol,
        manifest,
        project_root=tmp_path,
        bundle_parent=parent,
        input_manifest_path=controls[0],
        release_scope_path=controls[1],
        approval_envelope_path=controls[2],
    )
    (parent / manifest.sha256 / "bundle_manifest.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(M5GateError, match="identity differs"):
        materialize_bundle(
            protocol,
            manifest,
            project_root=tmp_path,
            bundle_parent=parent,
            input_manifest_path=controls[0],
            release_scope_path=controls[1],
            approval_envelope_path=controls[2],
        )
