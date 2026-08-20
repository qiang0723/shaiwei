"""Independent artifact-only audit for the production Head30 treatment."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.audit_statistics import independently_evaluate
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import Approval, ReleaseProtocol, ReleaseScope, mapping, write_once_document


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


def audit(*, release_path: Path, approval_path: Path, effect_root: Path, audit_root: Path, protocol_path: Path | None = None) -> dict[str, Any]:
    protocol = ReleaseProtocol.load(protocol_path)
    release = ReleaseScope.load(release_path, protocol)
    approval = Approval.load(approval_path, release)
    runtime = release.verify_runtime_identity()
    expected_files = {"authorization.json", "treatment_effect_started.json", "first_pass/bundle.json", "replay/bundle.json", "report.json"}
    actual_files = {path.relative_to(effect_root).as_posix() for path in effect_root.rglob("*") if path.is_file()}
    if actual_files != expected_files:
        raise ProtocolError("production-converter effect artifact file set differs")
    audit_root.mkdir(parents=True, exist_ok=True)
    if any(path.name != "audit.json" for path in audit_root.iterdir()):
        raise ProtocolError("production-converter audit root contains unexpected files")
    first_path, replay_path = effect_root / "first_pass/bundle.json", effect_root / "replay/bundle.json"
    first, replay = mapping(first_path), mapping(replay_path)
    report = mapping(effect_root / "report.json")
    rebuilt_first, rebuilt_replay = independently_evaluate(first), independently_evaluate(replay)
    first_sha, replay_sha = sha256_file(first_path), sha256_file(replay_path)
    checks = {
        "release_and_approval_identity": report.get("release_scope_sha256") == release.sha256 and report.get("approval_sha256") == approval.sha256,
        "runtime_identity": report.get("runtime_identity") == runtime,
        "protocol_identity": first.get("converter_protocol_sha256") == protocol.base.sha256 and first.get("release_engineering_sha256") == protocol.sha256,
        "first_pass_replay_physical_identity": first_sha == replay_sha,
        "first_pass_replay_semantic_identity": first == replay,
        "reported_bundle_identity": report.get("first_pass_bundle_sha256") == first_sha and report.get("replay_bundle_sha256") == replay_sha,
        "independent_first_reconstruction": _equivalent(rebuilt_first, first.get("result")),
        "independent_replay_reconstruction": _equivalent(rebuilt_replay, rebuilt_first),
        "reported_result_identity": report.get("result_sha256") == canonical_sha256(rebuilt_first) and report.get("decision") == rebuilt_first["decision"],
        "attempt_count": report.get("portfolio_attempts_consumed") == 1 and report.get("model_attempt_increment") == 0,
        "non_production": report.get("strategy_effective") == "PENDING_INDEPENDENT_AUDIT" and report.get("production_authorization") == "none",
        "no_failure_artifact": not (effect_root / "failure.json").exists(),
    }
    if not all(checks.values()):
        raise ProtocolError(f"production-converter independent audit failed: {[name for name, passed in checks.items() if not passed]}")
    document = {
        "schema_version": "m6-production-head30-real-audit-v1",
        "release_scope_sha256": release.sha256, "approval_sha256": approval.sha256,
        "report_sha256": sha256_file(effect_root / "report.json"), "bundle_sha256": first_sha,
        "checks": checks, "independent_result_sha256": canonical_sha256(rebuilt_first),
        "decision": rebuilt_first["decision"], "independent_audit": "PASS",
        "strategy_effective": rebuilt_first["decision"], "production_authorization": "none",
    }
    digest, reused = write_once_document(audit_root / "audit.json", document)
    return {"audit_sha256": digest, "reused": reused, "decision": document["decision"], "production_authorization": "none"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--effect-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(protocol_path=args.protocol, release_path=args.release, approval_path=args.approval, effect_root=args.effect_root, audit_root=args.audit_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
