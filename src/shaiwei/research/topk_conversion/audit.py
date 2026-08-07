"""Independent artifact audit for M6-3B synthetic engineering."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.topk_conversion.artifacts import (
    canonical_sha256,
    load_json,
    sha256_file,
    write_once_json,
)
from shaiwei.research.topk_conversion.audit_statistics import independently_evaluate
from shaiwei.research.topk_conversion.contract import (
    ConversionError,
    ProtocolBundle,
    bounded_path,
)


DEFAULT_RUNNER_ROOT = (
    PROJECT_ROOT / "data/research/m6_csi800_topk20_conversion_v1/engineering/runner"
)
DEFAULT_AUDIT_ROOT = (
    PROJECT_ROOT / "data/research/m6_csi800_topk20_conversion_v1/engineering/audit"
)


def _equivalent(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(_equivalent(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_equivalent(a, b) for a, b in zip(left, right, strict=True))
    return left == right


def _verify_code_bundle(report: dict[str, Any], project_root: Path) -> bool:
    bundle = report.get("code_bundle")
    if not isinstance(bundle, dict) or not bundle:
        return False
    for relative, digest in bundle.items():
        path = bounded_path(project_root / str(relative), root=project_root)
        if not path.is_file() or sha256_file(path) != digest:
            return False
    return canonical_sha256(bundle) == report.get("code_bundle_sha256")


def audit(
    runner_root: Path = DEFAULT_RUNNER_ROOT,
    audit_root: Path = DEFAULT_AUDIT_ROOT,
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    runner_root = bounded_path(runner_root, root=project_root)
    audit_root = bounded_path(audit_root, root=project_root)
    protocols = ProtocolBundle.load(
        result_path=project_root / "config/m6_csi800_topk20_conversion_v1.yaml",
        engineering_path=project_root / "config/m6_csi800_topk20_conversion_engineering_v1.yaml",
    )
    first_path = runner_root / "first_pass/bundle.json"
    replay_path = runner_root / "replay/bundle.json"
    report_path = runner_root / "report.json"
    first, replay, report = load_json(first_path), load_json(replay_path), load_json(report_path)
    first_sha, replay_sha = sha256_file(first_path), sha256_file(replay_path)
    case_results: dict[str, Any] = {}
    case_checks: dict[str, bool] = {}
    for name, case in first.get("cases", {}).items():
        rebuilt = independently_evaluate(case, protocols.result)
        saved = report.get("case_results", {}).get(name)
        case_results[name] = rebuilt
        case_checks[name] = _equivalent(rebuilt, saved)
    tampered = deepcopy(report.get("case_results", {}))
    first_case = next(iter(tampered))
    current_decision = tampered[first_case]["decision"]
    tampered[first_case]["decision"] = (
        "TOPK20_CONVERSION_SUPPORTED"
        if current_decision == "BLOCKED"
        else "BLOCKED"
    )
    checks = {
        "protocol_identity": first.get("protocol_sha256") == protocols.result_sha256
        and report.get("protocol_sha256") == protocols.result_sha256,
        "engineering_identity": first.get("engineering_protocol_sha256")
        == protocols.engineering_sha256
        and report.get("engineering_protocol_sha256") == protocols.engineering_sha256,
        "first_pass_replay_physical_identity": first_sha == replay_sha,
        "first_pass_replay_semantic_identity": first == replay,
        "bundle_identity": report.get("bundle_sha256") == first_sha,
        "four_decision_cases": set(case_checks)
        == set(protocols.engineering["synthetic_contract"]["fixture_cases"])
        and all(case_checks.values()),
        "failure_matrix": len(report.get("failure_closed_checks", {})) == 15
        and all(report.get("failure_closed_checks", {}).values()),
        "result_blind": report.get("real_m6_effect_read") is False
        and report.get("qlib_data_read") is False
        and report.get("real_model_fit_count") == 0
        and report.get("real_prediction_count") == 0
        and report.get("real_backtest_count") == 0,
        "non_production": report.get("strategy_effective")
        == "NOT_EVALUATED_FOR_PRODUCTION"
        and report.get("production_authorization") == "none"
        and report.get("experiment_ledger_rows") == 0,
        "no_external_calls": report.get("external_call_count") == 0,
        "code_bundle": _verify_code_bundle(report, project_root),
        "tamper_detection": not _equivalent(case_results, tampered),
    }
    if not all(checks.values()):
        failed = [key for key, value in checks.items() if not value]
        raise ConversionError(f"M6-3 independent audit failed: {failed}")
    audit_document = {
        "schema_version": "m6-topk20-conversion-engineering-audit-v1",
        "report_sha256": sha256_file(report_path),
        "bundle_sha256": first_sha,
        "checks": checks,
        "case_checks": case_checks,
        "independent_reconstruction_sha256": canonical_sha256(case_results),
        "independent_audit": "PASS",
        "strategy_effective": "NOT_EVALUATED_FOR_PRODUCTION",
        "production_authorization": "none",
    }
    audit_path = audit_root / "audit.json"
    audit_sha, reused = write_once_json(audit_path, audit_document)
    return {
        "audit_path": str(audit_path),
        "audit_sha256": audit_sha,
        "report_sha256": audit_document["report_sha256"],
        "bundle_sha256": first_sha,
        "reused": reused,
        "independent_audit": "PASS",
        "strategy_effective": "NOT_EVALUATED_FOR_PRODUCTION",
        "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner-root", type=Path, default=DEFAULT_RUNNER_ROOT)
    parser.add_argument("--audit-root", type=Path, default=DEFAULT_AUDIT_ROOT)
    args = parser.parse_args()
    print(json.dumps(audit(args.runner_root, args.audit_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
