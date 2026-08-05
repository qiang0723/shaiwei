"""Build the immutable, source-backed M5-0 strategy-factory projection."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError
import yaml

from shaiwei.web.strategy_factory_contract import (
    StrategyFactoryCatalog,
    StrategyFactoryContractError,
    StrategyFactoryPointer,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = Path("config/m5_strategy_factory_v1.yaml")
DEFAULT_OUTPUT = Path("data/web/research_snapshots/strategy_factory")


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_file(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise StrategyFactoryContractError(f"evidence path is not project-relative: {relative}")
    cursor = root
    for part in path.parts:
        cursor /= part
        if cursor.is_symlink():
            raise StrategyFactoryContractError(f"evidence path contains a symlink: {relative}")
    candidate = cursor.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise StrategyFactoryContractError(f"evidence path escapes project root: {relative}") from error
    if not candidate.is_file():
        raise StrategyFactoryContractError(f"evidence file is missing: {relative}")
    return candidate


def load_strategy_factory_catalog(
    project_root: Path = PROJECT_ROOT,
    config_path: Path = DEFAULT_CONFIG,
) -> tuple[StrategyFactoryCatalog, bytes]:
    root = project_root.resolve()
    path = _safe_file(root, str(config_path))
    payload = path.read_bytes()
    try:
        document = yaml.safe_load(payload)
        catalog = StrategyFactoryCatalog.model_validate(document)
    except (yaml.YAMLError, ValidationError, ValueError) as error:
        raise StrategyFactoryContractError(f"invalid strategy-factory catalog: {error}") from error
    return catalog, payload


def _read_evidence(
    root: Path,
    catalog: StrategyFactoryCatalog,
) -> tuple[dict[str, bytes], dict[str, str]]:
    payloads: dict[str, bytes] = {}
    hashes: dict[str, str] = {}
    protocol_path = _safe_file(root, catalog.protocol.path)
    protocol_payload = protocol_path.read_bytes()
    if _sha256(protocol_payload) != catalog.protocol.sha256:
        raise StrategyFactoryContractError("M5 protocol SHA-256 differs from the frozen catalog")
    hashes[catalog.protocol.path] = catalog.protocol.sha256
    for source in catalog.evidence_sources:
        payload = _safe_file(root, source.path).read_bytes()
        actual = _sha256(payload)
        if actual != source.sha256:
            raise StrategyFactoryContractError(
                f"evidence SHA-256 differs from the catalog: {source.evidence_id}"
            )
        payloads[source.evidence_id] = payload
        hashes[source.path] = actual
    return payloads, hashes


def _validate_m1_identity(catalog: StrategyFactoryCatalog, payload: bytes) -> None:
    try:
        registry = yaml.safe_load(payload)
        rows = registry["universes"]
    except (yaml.YAMLError, KeyError, TypeError) as error:
        raise StrategyFactoryContractError("frozen M1 registry cannot be parsed") from error
    if not isinstance(rows, list):
        raise StrategyFactoryContractError("frozen M1 universe list is invalid")
    identities = {row.get("universe_id"): row for row in rows if isinstance(row, dict)}
    if len(identities) != len(rows):
        raise StrategyFactoryContractError("frozen M1 registry repeats a universe identity")
    for universe in catalog.universes:
        source = identities.get(universe.universe_id)
        if source is None:
            raise StrategyFactoryContractError(f"M1 identity is missing: {universe.universe_id}")
        expected = (
            source.get("display_name"),
            source.get("identity_kind"),
            source.get("official_index_code"),
            source.get("bse_included"),
        )
        actual = (
            universe.display_name,
            universe.identity_kind,
            universe.official_index_code,
            False,
        )
        if expected != actual:
            raise StrategyFactoryContractError(f"M1 identity drift: {universe.universe_id}")


def _admitted_factor_count(payload: bytes) -> tuple[int, int]:
    try:
        rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
    except (UnicodeDecodeError, csv.Error) as error:
        raise StrategyFactoryContractError("factor admission ledger cannot be parsed") from error
    required = {"decision_id", "admitted"}
    if not rows or not required <= set(rows[0]):
        raise StrategyFactoryContractError("factor admission ledger schema is invalid")
    decision_ids = [row["decision_id"] for row in rows]
    if any(not value for value in decision_ids) or len(decision_ids) != len(set(decision_ids)):
        raise StrategyFactoryContractError("factor admission ledger contains duplicate decisions")
    admitted = 0
    for row in rows:
        value = row["admitted"].strip().lower()
        if value not in {"true", "false"}:
            raise StrategyFactoryContractError("factor admission ledger has an invalid admitted value")
        admitted += int(value == "true")
    return admitted, len(rows)


def _matrix(catalog: StrategyFactoryCatalog) -> list[dict[str, object]]:
    cells: list[dict[str, object]] = []
    for family in catalog.research_families:
        for universe in catalog.universes:
            programs = [
                item
                for item in catalog.programs
                if item.family_id == family.family_id and universe.universe_id in item.universe_ids
            ]
            cells.append(
                {
                    "family_id": family.family_id,
                    "universe_id": universe.universe_id,
                    "program_ids": [item.program_id for item in programs],
                    "authoritative_outcomes": [item.authoritative_outcome for item in programs]
                    or ["NOT_EVALUATED"],
                    "evidence_tiers": [item.evidence_tier for item in programs]
                    or ["NOT_EVALUATED"],
                }
            )
    return cells


def _projection_data(catalog: StrategyFactoryCatalog, admitted: int, admission_rows: int) -> dict[str, object]:
    expected = catalog.expected_counts
    if admitted != expected.admitted_factor_count:
        raise StrategyFactoryContractError("formal factor admission count differs from the frozen catalog")
    rejected = sum(item.authoritative_outcome == "REJECT" for item in catalog.programs)
    stopped = sum(item.authoritative_outcome == "STOPPED_CONTRACT" for item in catalog.programs)
    blocked = [item for item in catalog.universes if not item.research_draft_eligible]
    return {
        "summary": {
            "overall_status": "WARN",
            "decision": "5个股票池具备研究草案条件；3个池仍受数据或PIT证据阻断。",
            **catalog.expected_counts.model_dump(mode="json"),
            "authoritative_reject_program_count": rejected,
            "stopped_contract_program_count": stopped,
            "factor_admission_decision_count": admission_rows,
        },
        "attention": {
            "blocked_universe_ids": [item.universe_id for item in blocked],
            "rejected_program_ids": [
                item.program_id for item in catalog.programs if item.authoritative_outcome == "REJECT"
            ],
            "stopped_program_ids": [
                item.program_id
                for item in catalog.programs
                if item.authoritative_outcome == "STOPPED_CONTRACT"
            ],
            "formal_library_empty": admitted == 0,
        },
        "universes": [item.model_dump(mode="json") for item in catalog.universes],
        "research_families": [item.model_dump(mode="json") for item in catalog.research_families],
        "programs": [item.model_dump(mode="json") for item in catalog.programs],
        "matrix": _matrix(catalog),
        "active_tasks": [],
        "draft_template": catalog.draft_template.model_dump(mode="json"),
        "invariants": {
            "source_backed": True,
            "web_read_only": True,
            "browser_draft_only": True,
            "performance_sorting": False,
            "external_calls_made": 0,
            "real_research_runs": 0,
            "bse_count": 0,
            "production_authorization": "none",
        },
    }


def build_strategy_factory_document(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    root = project_root.resolve()
    catalog, catalog_payload = load_strategy_factory_catalog(root)
    payloads, evidence_hashes = _read_evidence(root, catalog)
    _validate_m1_identity(catalog, payloads["m1_registry"])
    admitted, admission_rows = _admitted_factor_count(payloads["factor_admissions"])
    source_identity = {
        "catalog_sha256": _sha256(catalog_payload),
        "builder_sha256": _sha256(Path(__file__).read_bytes()),
        "evidence_hashes": evidence_hashes,
    }
    data = _projection_data(catalog, admitted, admission_rows)
    identity = {
        "protocol_id": catalog.protocol.protocol_id,
        "catalog_id": catalog.catalog_id,
        "published_at": catalog.published_at,
        "source_identity": source_identity,
        "data": data,
    }
    snapshot_id = _sha256(_canonical(identity))
    return {
        "schema_version": "m5-strategy-factory-snapshot-v1",
        "protocol_id": catalog.protocol.protocol_id,
        "catalog_id": catalog.catalog_id,
        "snapshot_id": snapshot_id,
        "generated_at": catalog.published_at,
        "timezone": catalog.timezone,
        "source_identity": source_identity,
        "data": data,
    }


def _safe_output(root: Path, output_root: Path) -> Path:
    output = (root / output_root).resolve() if not output_root.is_absolute() else output_root.resolve()
    try:
        output.relative_to(root)
    except ValueError as error:
        raise StrategyFactoryContractError("strategy-factory output must stay inside the project") from error
    cursor = root
    for part in output.relative_to(root).parts:
        cursor /= part
        if cursor.exists() and cursor.is_symlink():
            raise StrategyFactoryContractError("strategy-factory output contains a symlink")
    output.mkdir(parents=True, exist_ok=True)
    return output


def _write_once(path: Path, payload: bytes) -> bool:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != payload:
            raise StrategyFactoryContractError(f"write-once projection conflict: {path.name}") from None
        return False
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return True


def build_strategy_factory_projection(
    project_root: Path = PROJECT_ROOT,
    output_root: Path = DEFAULT_OUTPUT,
) -> StrategyFactoryPointer:
    root = project_root.resolve()
    document = build_strategy_factory_document(root)
    output = _safe_output(root, output_root)
    snapshots = output / "snapshots"
    snapshots.mkdir(exist_ok=True)
    if snapshots.is_symlink():
        raise StrategyFactoryContractError("strategy-factory snapshot directory is a symlink")
    snapshot_bytes = _canonical(document)
    snapshot_id = document["snapshot_id"]
    snapshot_name = f"{snapshot_id}.json"
    _write_once(snapshots / snapshot_name, snapshot_bytes)
    pointer = StrategyFactoryPointer(
        schema_version="m5-strategy-factory-pointer-v1",
        protocol_id="m5-strategy-factory-contract-v1",
        snapshot_id=snapshot_id,
        snapshot_path=f"snapshots/{snapshot_name}",
        snapshot_sha256=_sha256(snapshot_bytes),
    )
    _write_once(output / "latest.json", _canonical(pointer.model_dump(mode="json")))
    return pointer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the immutable M5-0 strategy-factory projection")
    parser.add_argument("command", choices=["build"])
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)
    pointer = build_strategy_factory_projection(args.project_root)
    print(json.dumps({"status": "PASS", **pointer.model_dump(mode="json")}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
