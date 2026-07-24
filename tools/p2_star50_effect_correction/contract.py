"""Fail-closed contract and immutable-input verification for P2-2C."""

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


PROTOCOL_PATH = PROJECT_ROOT / "config/p2_star50_effect_correction_v1.yaml"
INPUT_AUDIT_PATH = PROJECT_ROOT / "config/p2_star50_effect_correction_input_audit_v1.json"
ORIGINAL_PROTOCOL_PATH = PROJECT_ROOT / "config/p2_star50_effect_v1.yaml"


class CorrectionGateFailure(RuntimeError):
    """A P2-2C condition failed and the correction must stop."""


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
    if protocol.get("scope") != "single_audit_correction_of_three_method_defects_only":
        raise CorrectionGateFailure("P2-2C scope is not the frozen three-defect correction")
    if protocol.get("production_authorization") != "none":
        raise CorrectionGateFailure("P2-2C must never authorize production")
    expected_scope = [
        "train_valid_label_maturity_purge",
        "execution_open_limit_and_prior_close_clock",
        "bilateral_signal_date_five_percent_order_capacity",
    ]
    if protocol.get("correction_scope") != expected_scope:
        raise CorrectionGateFailure("P2-2C correction scope drifted")
    return protocol


def _tree_integrity(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise CorrectionGateFailure(f"immutable result root is missing: {root.relative_to(PROJECT_ROOT)}")
    files: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        files.append(
            {
                "path": path.relative_to(PROJECT_ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "file_count": len(files),
        "byte_count": sum(row["bytes"] for row in files),
        "canonical_tree_sha256": canonical_sha256(files),
    }


def _verify_base_contract_unchanged(protocol: dict[str, Any]) -> None:
    original = yaml.safe_load(ORIGINAL_PROTOCOL_PATH.read_text(encoding="utf-8"))
    for section in ("portfolio", "evaluation", "diversification_gate", "diagnostics", "verdict_contract"):
        if protocol[section] != original[section]:
            raise CorrectionGateFailure(f"frozen P2-2 section changed outside correction scope: {section}")
    for key, value in original["model"].items():
        if protocol["model"].get(key) != value:
            raise CorrectionGateFailure(f"frozen model setting changed outside label purge: {key}")
    for key, value in original["execution"].items():
        if protocol["execution"].get(key) != value:
            raise CorrectionGateFailure(f"frozen execution setting changed outside explicit corrections: {key}")


def verify_preflight_audit(protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    protocol = protocol or load_protocol()
    if sha256_file(INPUT_AUDIT_PATH) != protocol["preflight_evidence"]["input_audit_sha256"]:
        raise CorrectionGateFailure("tracked P2-2C input audit hash drift")
    audit = json.loads(INPUT_AUDIT_PATH.read_text(encoding="utf-8"))
    required = {
        "original_base_trade_count": 893,
        "original_base_buy_count": 498,
        "original_base_sell_count": 395,
        "original_buy_capacity_violation_count": 0,
        "original_sell_capacity_violation_count": 14,
        "minimum_first_member_bar_lead_trade_days": 74,
        "forbidden_bj_member_day_count": 0,
    }
    for key, expected in required.items():
        if audit["method_defect_baselines"].get(key) != expected:
            raise CorrectionGateFailure(f"P2-2C audit baseline drift: {key}")
    maximum = float(audit["method_defect_baselines"]["original_maximum_sell_capacity_ratio"])
    if abs(maximum - 0.11303799663393785) > 1e-15:
        raise CorrectionGateFailure("original maximum sell capacity audit drift")
    expected_purge = protocol["model"]["required_purged_last_signal_dates"]
    if audit["label_maturity"]["required_purged_last_signal_dates"] != expected_purge:
        raise CorrectionGateFailure("label-maturity audit dates drifted")
    if not audit["preflight_conclusion"]["only_three_authorized_corrections"]:
        raise CorrectionGateFailure("preflight did not close the correction scope")
    return audit


def verify_frozen_inputs(protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    """Rehash P2-1, original P2-2, qlib, and the tracked correction preflight."""
    protocol = protocol or load_protocol()
    _verify_base_contract_unchanged(protocol)
    audit = verify_preflight_audit(protocol)
    expected = protocol["upstream_evidence"]
    paths = {
        "p2_1_manifest_sha256": PROJECT_ROOT / "config/p2_star50_engineering_manifest_v1.json",
        "p2_1_quality_report_sha256": PROJECT_ROOT
        / "data/research/star50/p2-star50-engineering-v1/quality_report.json",
        "p2_1_engineering_report_sha256": PROJECT_ROOT
        / "data/research/star50/p2-star50-engineering-v1/engineering_report.json",
        "market_parquet_sha256": PROJECT_ROOT / protocol["identity"]["market_dataset"],
        "member_days_parquet_sha256": PROJECT_ROOT / protocol["identity"]["member_day_dataset"],
        "benchmark_parquet_sha256": PROJECT_ROOT / protocol["identity"]["benchmark_dataset"],
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
    actual: dict[str, str] = {}
    for field, path in paths.items():
        if not path.is_file():
            raise CorrectionGateFailure(f"missing frozen input: {path.relative_to(PROJECT_ROOT)}")
        actual[field] = sha256_file(path)
        if actual[field] != str(expected[field]):
            raise CorrectionGateFailure(f"frozen input hash drift: {field}")

    original = protocol["original_p2_2_evidence"]
    original_paths = {
        "effect_report_sha256": PROJECT_ROOT / "data/research/star50/p2-star50-effect-v1/effect_report.json",
        "tracked_manifest_sha256": PROJECT_ROOT / "config/p2_star50_effect_manifest_v1.json",
        "run_ledger_sha256": PROJECT_ROOT / "ledger/p2_star50_effect_runs.csv",
        "admission_ledger_sha256": PROJECT_ROOT / "ledger/p2_star50_effect_admissions.csv",
        "protocol_sha256": ORIGINAL_PROTOCOL_PATH,
        "model_code_sha256": PROJECT_ROOT / "tools/p2_star50_effect/model.py",
        "executor_code_sha256": PROJECT_ROOT / "tools/p2_star50_effect/executor.py",
        "run_code_sha256": PROJECT_ROOT / "tools/p2_star50_effect/run.py",
        "metrics_code_sha256": PROJECT_ROOT / "tools/p2_star50_effect/metrics.py",
    }
    original_actual = {field: sha256_file(path) for field, path in original_paths.items()}
    for field, digest in original_actual.items():
        if digest != str(original[field]):
            raise CorrectionGateFailure(f"original P2-2 immutable evidence drift: {field}")
    original_tree = _tree_integrity(PROJECT_ROOT / "data/research/star50/p2-star50-effect-v1")
    for field, value in original_tree.items():
        if value != original[f"original_result_{field}"]:
            raise CorrectionGateFailure(f"original P2-2 result tree drift: {field}")

    provider = PROJECT_ROOT / protocol["identity"]["qlib_provider"]
    manifest_path = provider / QLIB_MANIFEST
    qlib_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    qlib_integrity = qlib_tree_integrity(provider)
    if qlib_integrity["artifact_sha256"] != expected["qlib_tree_sha256"]:
        raise CorrectionGateFailure("P2-1 qlib tree hash drift")
    if qlib_manifest.get("build_identity_sha256") != expected["qlib_build_identity_sha256"]:
        raise CorrectionGateFailure("P2-1 qlib build identity drift")
    if any(qlib_manifest.get(key) != value for key, value in qlib_integrity.items()):
        raise CorrectionGateFailure("P2-1 qlib manifest/integrity mismatch")

    manifest = json.loads(original_paths["tracked_manifest_sha256"].read_text(encoding="utf-8"))
    if manifest["artifact_hashes"]["model_bundle_sha256"] != original["model_bundle_sha256"]:
        raise CorrectionGateFailure("original model bundle identity drift")
    if manifest["artifact_hashes"]["prediction_bundle_sha256"] != original["prediction_bundle_sha256"]:
        raise CorrectionGateFailure("original prediction bundle identity drift")

    evidence = {
        "artifact_hashes": actual,
        "original_p2_2_hashes": original_actual,
        "original_p2_2_result_tree": original_tree,
        "qlib": {**qlib_integrity, "build_identity_sha256": qlib_manifest["build_identity_sha256"]},
        "preflight_audit_sha256": sha256_file(INPUT_AUDIT_PATH),
        "preflight_audit": audit,
        "upstream_reports_recalculated": False,
        "original_p2_2_evidence_mutated": False,
    }
    evidence["input_manifest_sha256"] = canonical_sha256(
        {key: value for key, value in evidence.items() if key != "preflight_audit"}
    )
    return evidence


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
        raise CorrectionGateFailure("real P2-2C execution requires a clean worktree")
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "origin/main"):
        raise CorrectionGateFailure("real P2-2C execution requires HEAD == origin/main")
    for ancestor in (
        protocol["original_p2_2_evidence"]["freeze_commit"],
        protocol["original_p2_2_evidence"]["final_commit"],
        protocol["upstream_evidence"]["p2_1_final_commit"],
    ):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", str(ancestor), head],
            cwd=PROJECT_ROOT,
            check=False,
        ).returncode:
            raise CorrectionGateFailure(f"P2-2C freeze is not descended from {ancestor}")
    committed_protocol = subprocess.run(
        ["git", "show", f"HEAD:{PROTOCOL_PATH.relative_to(PROJECT_ROOT).as_posix()}"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    if hashlib.sha256(committed_protocol).hexdigest() != sha256_file(PROTOCOL_PATH):
        raise CorrectionGateFailure("P2-2C protocol is not the committed freeze version")
    return head


def correction_code_sha256() -> str:
    paths = sorted((PROJECT_ROOT / "tools/p2_star50_effect_correction").glob("*.py"))
    paths.extend(
        [
            PROJECT_ROOT / "src/shaiwei/ledger.py",
            PROTOCOL_PATH,
            INPUT_AUDIT_PATH,
            PROJECT_ROOT / "tools/p2_star50_effect/metrics.py",
        ]
    )
    return canonical_sha256(
        {path.relative_to(PROJECT_ROOT).as_posix(): sha256_file(path) for path in paths}
    )
