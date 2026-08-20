"""Independent artifact-only audit for the M6-5B 500k historical replay."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from shaiwei.research.model_attribution.contract import canonical_sha256, sha256_file
from shaiwei.research.production_conversion.contract import ProtocolError
from shaiwei.research.production_conversion.real_contract import mapping, write_once_document

from .audit_statistics import independently_evaluate
from .release_contract import Approval, ReleaseProtocol, ReleaseScope


EXPECTED_FILES = {
    "authorization.json", "effect_started.json", "first_pass/bundle.json",
    "replay/bundle.json", "report.json",
}


def _equivalent(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(_equivalent(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _equivalent(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def _target_checks(bundle: dict[str, Any]) -> bool:
    for window in bundle["windows"].values():
        for row in window["rebalances"]:
            targets = row["targets"]
            if (
                len(targets) != 30 or len(set(targets)) != 30
                or any(str(code).startswith("BJ") or str(code).endswith(".BJ") for code in targets)
                or row["target_sha256"] != canonical_sha256(targets)
            ):
                return False
    return True


def audit_loaded(
    *, release: Any, approval: Any, effect_root: Path, audit_root: Path,
) -> dict[str, Any]:
    """Audit sealed artifacts after a versioned adapter validates authority."""
    runtime = release.verify_runtime_identity()
    actual = {path.relative_to(effect_root).as_posix() for path in effect_root.rglob("*") if path.is_file()}
    if actual != EXPECTED_FILES:
        raise ProtocolError("M6-5B effect artifact file set differs")
    audit_root.mkdir(parents=True, exist_ok=True)
    if any(path.name != "audit.json" for path in audit_root.iterdir()):
        raise ProtocolError("M6-5B audit root contains unexpected files")
    first_path, replay_path = effect_root / "first_pass/bundle.json", effect_root / "replay/bundle.json"
    first, replay = mapping(first_path), mapping(replay_path)
    report = mapping(effect_root / "report.json")
    rebuilt_first = independently_evaluate(first)
    rebuilt_replay = independently_evaluate(replay)
    first_sha, replay_sha = sha256_file(first_path), sha256_file(replay_path)
    checks = {
        "release_and_approval_identity": report.get("release_scope_sha256") == release.sha256 and report.get("approval_sha256") == approval.sha256,
        "runtime_identity": report.get("runtime_identity") == runtime,
        "artifact_file_set_exact": actual == EXPECTED_FILES,
        "first_pass_replay_physical_identity": first_sha == replay_sha,
        "first_pass_replay_semantic_identity": first == replay,
        "reported_bundle_identity": report.get("first_pass_bundle_sha256") == first_sha and report.get("replay_bundle_sha256") == replay_sha,
        "target_identity": _target_checks(first) and _target_checks(replay),
        "independent_first_reconstruction": _equivalent(rebuilt_first, first.get("result")),
        "independent_replay_reconstruction": _equivalent(rebuilt_replay, rebuilt_first),
        "reported_result_identity": report.get("result_sha256") == canonical_sha256(rebuilt_first) and report.get("decision") == rebuilt_first["decision"],
        "attempt_count": report.get("family_attempts_before_run") == 1 and report.get("new_attempts_consumed") == 1 and report.get("total_family_attempts") == 2,
        "non_production": report.get("strategy_effective") == "PENDING_INDEPENDENT_AUDIT" and report.get("production_authorization") == "none",
        "no_failure_artifact": not (effect_root / "failure.json").exists(),
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise ProtocolError(f"M6-5B independent audit failed: {failed}")
    document = {
        "schema_version": "m6-head30-500k-independent-audit-v1",
        "release_scope_sha256": release.sha256, "approval_sha256": approval.sha256,
        "report_sha256": sha256_file(effect_root / "report.json"), "bundle_sha256": first_sha,
        "checks": checks, "independent_result_sha256": canonical_sha256(rebuilt_first),
        "decision": rebuilt_first["decision"], "independent_audit": "PASS",
        "strategy_effective": rebuilt_first["decision"], "production_authorization": "none",
    }
    digest, reused = write_once_document(audit_root / "audit.json", document)
    return {"audit_sha256": digest, "reused": reused, "decision": document["decision"]}


def audit(
    *, release_path: Path, approval_path: Path, effect_root: Path, audit_root: Path,
) -> dict[str, Any]:
    protocol = ReleaseProtocol.load()
    release = ReleaseScope.load(release_path, protocol)
    approval = Approval.load(approval_path, release)
    return audit_loaded(
        release=release, approval=approval, effect_root=effect_root, audit_root=audit_root,
    )


def main(argv: list[str] | None = None, *, auditor: Any = audit) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--effect-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = auditor(
        release_path=args.release,
        approval_path=args.approval,
        effect_root=args.effect_root,
        audit_root=args.audit_root,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
