"""Fail-closed P2-2 contract and immutable-input verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import sha256_file
from shaiwei.transform.qlib_bin import QLIB_MANIFEST, qlib_tree_integrity


PROTOCOL_PATH = PROJECT_ROOT / "config/p2_star50_effect_v1.yaml"
COMPARATOR_INVENTORY_PATH = PROJECT_ROOT / "config/p2_star50_csi800_comparator_inventory_v1.json"


class EffectGateFailure(RuntimeError):
    """A frozen P2-2 condition failed and execution must stop."""


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_protocol() -> dict[str, Any]:
    protocol = yaml.safe_load(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if protocol.get("scope") != "one_preregistered_historical_effect_decision_only":
        raise EffectGateFailure("P2-2 protocol scope is not the frozen one-run effect decision")
    if protocol.get("production_authorization") != "none":
        raise EffectGateFailure("P2-2 must never authorize production")
    if protocol["verdict_contract"].get("production_authorization") != "none":
        raise EffectGateFailure("P2-2 verdict contract must never authorize production")
    return protocol


def _expected_paths(protocol: dict[str, Any]) -> dict[str, Path]:
    identity = protocol["identity"]
    return {
        "p2_1_manifest_sha256": PROJECT_ROOT / "config/p2_star50_engineering_manifest_v1.json",
        "p2_1_quality_report_sha256": PROJECT_ROOT
        / "data/research/star50/p2-star50-engineering-v1/quality_report.json",
        "p2_1_engineering_report_sha256": PROJECT_ROOT
        / "data/research/star50/p2-star50-engineering-v1/engineering_report.json",
        "market_parquet_sha256": PROJECT_ROOT / identity["market_dataset"],
        "member_days_parquet_sha256": PROJECT_ROOT / identity["member_day_dataset"],
        "benchmark_parquet_sha256": PROJECT_ROOT / identity["benchmark_dataset"],
        "v2_manifest_sha256": PROJECT_ROOT / "config/p2_star50_official_sources_v2.json",
        "v2_quality_report_sha256": PROJECT_ROOT
        / "data/research/star50/p2-star50-v2/quality_report.json",
        "v2_initial_set_sha256": PROJECT_ROOT
        / "data/research/star50/p2-star50-v2/initial_set.parquet",
        "v2_membership_events_sha256": PROJECT_ROOT
        / "data/research/star50/p2-star50-v2/membership_events.parquet",
        "v2_daily_membership_sha256": PROJECT_ROOT
        / "data/research/star50/p2-star50-v2/daily_membership.parquet",
    }


def verify_frozen_inputs(protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    """Rehash every P2-1/v2 input without rebuilding either upstream report."""
    protocol = protocol or load_protocol()
    expected = protocol["upstream_evidence"]
    actual: dict[str, str] = {}
    for field, path in _expected_paths(protocol).items():
        if not path.is_file():
            raise EffectGateFailure(f"missing frozen input: {path.relative_to(PROJECT_ROOT)}")
        actual[field] = sha256_file(path)
        if actual[field] != str(expected[field]):
            raise EffectGateFailure(f"frozen input hash drift: {field}")

    engineering = json.loads(
        _expected_paths(protocol)["p2_1_engineering_report_sha256"].read_text(encoding="utf-8")
    )
    required_engineering = {
        "input_gate_pass": True,
        "dataset_complete": True,
        "qlib_complete": True,
        "pipeline_fixture_pass": True,
        "idempotency_pass": True,
        "engineering_complete": True,
        "strategy_results_inspected": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": "GO",
    }
    mismatches = {
        key: {"expected": value, "actual": engineering.get(key)}
        for key, value in required_engineering.items()
        if engineering.get(key) != value
    }
    if mismatches:
        raise EffectGateFailure(f"P2-1 terminal status drift: {sorted(mismatches)}")

    provider = PROJECT_ROOT / protocol["identity"]["qlib_provider"]
    manifest_path = provider / QLIB_MANIFEST
    if not manifest_path.is_file():
        raise EffectGateFailure("P2-1 qlib manifest is missing")
    qlib_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    integrity = qlib_tree_integrity(provider)
    if integrity["artifact_sha256"] != str(expected["qlib_tree_sha256"]):
        raise EffectGateFailure("P2-1 qlib tree hash drift")
    if qlib_manifest.get("build_identity_sha256") != str(expected["qlib_build_identity_sha256"]):
        raise EffectGateFailure("P2-1 qlib build identity drift")
    if any(qlib_manifest.get(key) != value for key, value in integrity.items()):
        raise EffectGateFailure("P2-1 qlib manifest/integrity mismatch")

    inventory_hash = sha256_file(COMPARATOR_INVENTORY_PATH)
    gate = protocol["diversification_gate"]
    if inventory_hash != str(gate["comparator_inventory_sha256"]):
        raise EffectGateFailure("CSI800 comparator inventory hash drift")
    inventory = json.loads(COMPARATOR_INVENTORY_PATH.read_text(encoding="utf-8"))
    if inventory.get("bound_comparator") is not None or gate.get("bound_comparator") is not None:
        raise EffectGateFailure("unexpected CSI800 comparator binding differs from frozen inventory")

    return {
        "artifact_hashes": actual,
        "qlib": {
            **integrity,
            "build_identity_sha256": qlib_manifest["build_identity_sha256"],
        },
        "comparator_inventory_sha256": inventory_hash,
        "comparator_bound": False,
        "input_manifest_sha256": canonical_sha256(
            {
                "artifact_hashes": actual,
                "qlib": integrity,
                "qlib_build_identity_sha256": qlib_manifest["build_identity_sha256"],
                "comparator_inventory_sha256": inventory_hash,
            }
        ),
        "upstream_reports_recalculated": False,
    }


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def verify_pushed_clean_freeze(protocol: dict[str, Any] | None = None) -> str:
    protocol = protocol or load_protocol()
    if _git("status", "--porcelain"):
        raise EffectGateFailure("real P2-2 execution requires a clean worktree")
    head = _git("rev-parse", "HEAD")
    remote = _git("rev-parse", "origin/main")
    if head != remote:
        raise EffectGateFailure("real P2-2 execution requires HEAD == origin/main")
    parent = str(protocol["upstream_evidence"]["p2_1_final_commit"])
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", parent, head],
        cwd=PROJECT_ROOT,
        check=False,
    ).returncode:
        raise EffectGateFailure("P2-2 freeze commit is not descended from the accepted P2-1 commit")
    return head


def training_code_sha256() -> str:
    paths = sorted((PROJECT_ROOT / "tools/p2_star50_effect").glob("*.py"))
    paths.extend(
        [
            PROJECT_ROOT / "src/shaiwei/ledger.py",
            PROJECT_ROOT / "config/p2_star50_effect_v1.yaml",
        ]
    )
    return canonical_sha256(
        {path.relative_to(PROJECT_ROOT).as_posix(): sha256_file(path) for path in paths}
    )
