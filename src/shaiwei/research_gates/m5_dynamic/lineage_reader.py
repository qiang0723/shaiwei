"""Read only manifest-bound statement observations after exact lineage approval."""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from .contract import API_FIELDS, IDENTITY_FIELDS, STATEMENT_FIELDS, M5GateError, sha256_file
from .lineage_commitment import value_version_sha256
from .lineage_contract import LineageInputManifest, Observation, VersionEvidence
from .statement_scope import is_frozen_annual_statement_row


def _bound_file(root: Path, relative: str) -> Path:
    candidate = root / relative
    if candidate.is_symlink():
        raise M5GateError("M5 lineage input cannot be a symlink")
    try:
        path = candidate.resolve(strict=True)
        path.relative_to(root.resolve(strict=True))
    except (FileNotFoundError, ValueError) as exc:
        raise M5GateError("M5 lineage input is missing or escapes mount") from exc
    if not path.is_file():
        raise M5GateError("M5 lineage input is not a regular file")
    return path


def _verify(path: Path, batch: dict[str, Any]) -> None:
    metadata = pq.read_metadata(path)
    if (
        sha256_file(path) != batch["content_sha256"]
        or int(metadata.num_rows) != int(batch["row_count"])
        or os.stat(path).st_size != int(batch["bytes"])
        or list(metadata.schema.names) != list(batch["schema_fields"])
    ):
        raise M5GateError("M5 lineage manifest-bound batch differs")


def _observation(
    row: dict[str, Any],
    *,
    source_api: str,
    batch: dict[str, Any],
) -> Observation:
    table = source_api.removeprefix("tushare.").removesuffix("_vip")
    source_kind = "VIP" if source_api.endswith("_vip") else "STANDARD"
    return Observation.from_mapping(
        {
            "table": table,
            "source_kind": source_kind,
            "source_api": source_api,
            "statement_identity": {field: row[field] for field in IDENTITY_FIELDS},
            "business_values": {field: row[field] for field in STATEMENT_FIELDS[table]},
            "request_params_sha256": batch["request_params_sha256"],
            "batch_id": batch["batch_id"],
            "content_sha256": batch["content_sha256"],
            "local_observed_at": batch["ingest_time"],
        }
    )


def _read_source_batches(
    sources: list[dict[str, Any]],
    *,
    input_root: Path,
    identity_allowlist: set[tuple[str, tuple[str, ...]]] | None,
) -> list[Observation]:
    observations = []
    for source in sources:
        api = source["source_api"]
        table = api.removeprefix("tushare.").removesuffix("_vip")
        columns = list(API_FIELDS[api])
        for batch in source["batches"]:
            path = _bound_file(input_root, batch["relative_path"])
            _verify(path, batch)
            frame = pd.read_parquet(path, columns=columns)
            for row in frame.to_dict("records"):
                if not is_frozen_annual_statement_row(row):
                    continue
                identity = tuple(str(row[field]).replace("-", "") for field in IDENTITY_FIELDS)
                key = (table, identity)
                if identity_allowlist is None or key in identity_allowlist:
                    observations.append(_observation(row, source_api=api, batch=batch))
    return observations


def _conflict_keys(observations: list[Observation]) -> set[tuple[str, tuple[str, ...]]]:
    versions: dict[tuple[str, tuple[str, ...]], set[str]] = defaultdict(set)
    for item in observations:
        versions[(item.table, item.statement_identity)].add(value_version_sha256(item))
    return {key for key, values in versions.items() if len(values) > 1}


def load_lineage_inputs(
    manifest: LineageInputManifest,
    *,
    input_root: Path,
) -> tuple[list[Observation], list[VersionEvidence], dict[str, Any]]:
    anchor = _read_source_batches(
        manifest.document["anchor_sources"],
        input_root=input_root,
        identity_allowlist=None,
    )
    keys = _conflict_keys(anchor)
    counts = Counter(table for table, _ in keys)
    prior = manifest.document["prior_conflict_identity"]
    if len(keys) != prior["conflict_group_count"] or dict(sorted(counts.items())) != {
        key: value for key, value in sorted(prior["conflict_groups_by_table"].items()) if value
    }:
        raise M5GateError("M5 lineage anchor conflict identity changed")
    history = _read_source_batches(
        manifest.document["history_sources"],
        input_root=input_root,
        identity_allowlist=keys,
    )
    history_versions: dict[tuple[str, tuple[str, ...]], set[str]] = defaultdict(set)
    for item in history:
        history_versions[(item.table, item.statement_identity)].add(value_version_sha256(item))
    anchor_versions: dict[tuple[str, tuple[str, ...]], set[str]] = defaultdict(set)
    for item in anchor:
        key = (item.table, item.statement_identity)
        if key in keys:
            anchor_versions[key].add(value_version_sha256(item))
    if set(history_versions) != keys or any(
        not anchor_versions[key] <= history_versions[key] for key in keys
    ):
        raise M5GateError("M5 lineage history does not preserve anchor variants")
    evidence = [VersionEvidence.from_mapping(item) for item in manifest.document["authoritative_evidence"]]
    return (
        history,
        evidence,
        {
            "semantic_rows_read": True,
            "anchor_conflicting_identity_group_count": len(keys),
            "history_observation_count": len(history),
            "history_batch_count": sum(
                len(source["batches"]) for source in manifest.document["history_sources"]
            ),
            "authoritative_evidence_count": len(evidence),
        },
    )
