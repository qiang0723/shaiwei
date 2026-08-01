"""Frozen contract and immutable artifact helpers for the M3-0 data gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
import uuid

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = PROJECT_ROOT / "config/m3_star_custom_pit_v1.yaml"


class GateFailure(RuntimeError):
    """Fail closed when source, PIT, readiness, or artifact evidence differs."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def load_protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    protocol = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    expected = {
        "schema_version": "m3-star-custom-pit-protocol-v1",
        "protocol_id": "m3-star-custom-pit-data-rule-gate-v1",
        "scope": "data_and_rule_feasibility_only",
        "factor_results_inspected": False,
        "llm_execution_authorized": False,
        "model_training_authorized": False,
        "backtest_authorized": False,
        "signal_authorized": False,
        "production_authorization": "none",
        "scheduler_changes_authorized": False,
    }
    mismatches = {
        key: {"expected": value, "actual": protocol.get(key)}
        for key, value in expected.items()
        if protocol.get(key) != value
    }
    if mismatches:
        raise GateFailure(f"M3 protocol boundary differs: {sorted(mismatches)}")

    identities = protocol["identity"]["universe_ids"]
    if identities != {
        "all": "star-board-all-pit-v1",
        "midcap": "star-board-midcap-pit-v1",
        "smallcap": "star-board-smallcap-pit-v1",
    }:
        raise GateFailure("M3 universe identities differ from the frozen set")
    if protocol["identity"]["identity_kind"] != "CUSTOM_RULE_BASED":
        raise GateFailure("M3 pools must remain CUSTOM_RULE_BASED")
    if protocol["identity"]["official_index_code"] is not None:
        raise GateFailure("M3 custom pools cannot claim an official index code")
    if protocol["sources"]["bse_suffix_forbidden"] != ".BJ":
        raise GateFailure("M3 protocol must forbid .BJ")
    if protocol["formation"]["formation_clock"] != "last_open_trade_day_close":
        raise GateFailure("M3 formation clock differs")
    if protocol["formation"]["effective_clock"] != "next_open_trade_day":
        raise GateFailure("M3 effective clock differs")
    if protocol["formation"]["listing_age"] != "12_calendar_months":
        raise GateFailure("M3 listing-age rule differs")
    if protocol["size"]["partition"] != "deterministic_three_way_array_split":
        raise GateFailure("M3 size partition differs")
    if protocol["verdict"]["production_authorization"] != "none":
        raise GateFailure("M3 verdict cannot authorize production")

    upstream = protocol["upstream"]
    for field, hash_field in (
        ("registry", "registry_sha256"),
        ("foundation_protocol", "foundation_protocol_sha256"),
    ):
        target = PROJECT_ROOT / upstream[field]
        if not target.is_file() or sha256_file(target) != upstream[hash_field]:
            raise GateFailure(f"M3 upstream evidence mismatch: {field}")
    return protocol


def write_immutable_parquet(frame: pd.DataFrame, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    frame.to_parquet(staging, index=False, compression="zstd")
    digest = sha256_file(staging)
    reused = path.is_file()
    if reused:
        if sha256_file(path) != digest:
            staging.unlink()
            raise GateFailure(f"immutable artifact differs: {path.relative_to(PROJECT_ROOT)}")
        staging.unlink()
    else:
        staging.replace(path)
    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "rows": int(len(frame)),
        "sha256": digest,
        "reused": reused,
    }


def write_immutable_json(path: Path, value: dict[str, Any]) -> dict[str, Any]:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    reused = path.is_file()
    if reused and path.read_text(encoding="utf-8") != rendered:
        raise GateFailure(f"immutable report differs: {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not reused:
        path.write_text(rendered, encoding="utf-8")
    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
        "reused": reused,
    }
