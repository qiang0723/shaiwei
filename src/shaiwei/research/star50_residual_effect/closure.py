"""Close the sealed M4-1 evidence chain without recomputing research results."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.star50_residual_effect.audit import audit
from shaiwei.research.star50_residual_effect.contract import (
    EffectProtocol,
    EffectRelease,
    ResidualEffectError,
    project_path,
    sha256_file,
    verify_pushed_clean_state,
)
from shaiwei.research.star50_residual_effect.evidence import (
    append_ledgers,
    build_manifest,
    code_bundle_sha256,
    write_json,
)


CLOSURE_PROTOCOL_PATH = (
    PROJECT_ROOT / "config/m4_star50_residual_effect_evidence_closure_v1.yaml"
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@dataclass(frozen=True)
class EvidenceClosureProtocol:
    path: Path
    document: dict[str, Any]
    sha256: str

    @classmethod
    def load(cls, path: Path = CLOSURE_PROTOCOL_PATH) -> "EvidenceClosureProtocol":
        path = path.resolve()
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ResidualEffectError("M4-1R2 closure protocol is not a mapping")
        if document.get("closure_id") != "m4-star50-residual-effect-evidence-closure-v1":
            raise ResidualEffectError("M4-1R2 closure identity differs")
        if document.get("production_authorization") != "none":
            raise ResidualEffectError("M4-1R2 cannot authorize production")
        execution = document.get("execution_contract", {})
        required = {
            "report_reuse_branch_only": True,
            "feature_label_rankic_portfolio_or_return_recomputation": False,
            "effect_report_rewrite": False,
            "artifact_rewrite": False,
            "network_mode": "none",
            "secret_access": False,
            "model_training": False,
            "audit_required_before_effect_disclosure": True,
        }
        if any(execution.get(key) != value for key, value in required.items()):
            raise ResidualEffectError("M4-1R2 execution scope was broadened")
        sealed = document.get("sealed_result_contract", {})
        artifacts = sealed.get("artifacts", [])
        if len(artifacts) != 10 or len({row.get("path") for row in artifacts}) != 10:
            raise ResidualEffectError("M4-1R2 requires exactly ten sealed artifacts")
        return cls(path=path, document=document, sha256=sha256_file(path))

    def verify_sources(self, *, project_root: Path = PROJECT_ROOT) -> None:
        authority = self.document["source_authority"]
        for key, value in authority.items():
            if not key.endswith("_path"):
                continue
            hash_key = f"{key[:-5]}_sha256"
            path = project_path(str(value), project_root=project_root)
            if hash_key not in authority or sha256_file(path) != str(authority[hash_key]):
                raise ResidualEffectError(f"M4-1R2 source binding differs: {key}")

    def verify_state(
        self, *, project_root: Path = PROJECT_ROOT
    ) -> tuple[str, dict[str, Any]]:
        self.verify_sources(project_root=project_root)
        sealed = self.document["sealed_result_contract"]
        report_spec = sealed["effect_report"]
        report_path = project_path(report_spec["path"], project_root=project_root)
        if not report_path.is_file() or sha256_file(report_path) != report_spec["sha256"]:
            raise ResidualEffectError("M4-1R2 sealed report hash differs")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        for key, expected in sealed["required_report_identity"].items():
            if report.get(key) != expected:
                raise ResidualEffectError(f"M4-1R2 sealed report identity differs: {key}")

        expected_files = {report_spec["path"]}
        for row in sealed["artifacts"]:
            path = project_path(row["path"], project_root=project_root)
            if not path.is_file() or sha256_file(path) != row["sha256"]:
                raise ResidualEffectError(f"M4-1R2 sealed artifact differs: {row['path']}")
            expected_files.add(str(row["path"]))

        manifest_path = project_path(sealed["manifest_path"], project_root=project_root)
        result_root = project_path(sealed["result_root"], project_root=project_root)
        actual_files = {
            path.relative_to(project_root).as_posix() for path in result_root.rglob("*") if path.is_file()
        }
        if manifest_path.is_file():
            expected_files.add(str(sealed["manifest_path"]))
        if actual_files != expected_files:
            raise ResidualEffectError("M4-1R2 result-root file set differs")

        ledgers = self.document["ledger_contract"]
        run_spec, decision_spec = ledgers["run_ledger"], ledgers["decision_ledger"]
        run_path = project_path(run_spec["path"], project_root=project_root)
        decision_path = project_path(decision_spec["path"], project_root=project_root)
        run_rows, decision_rows = _read_csv(run_path), _read_csv(decision_path)
        initial = (
            len(run_rows) == int(run_spec["initial_data_rows"])
            and len(decision_rows) == int(decision_spec["initial_data_rows"])
            and sha256_file(run_path) == run_spec["initial_sha256"]
            and sha256_file(decision_path) == decision_spec["initial_sha256"]
            and not manifest_path.exists()
        )
        completed = (
            len(run_rows) == int(run_spec["final_data_rows"])
            and len(decision_rows) == int(decision_spec["final_data_rows"])
            and manifest_path.is_file()
        )
        if initial:
            return "INITIAL", report
        if completed:
            return "COMPLETED", report
        raise ResidualEffectError("M4-1R2 evidence state is partial or unexpected")


def close_evidence(
    effect_protocol_path: Path,
    closure_protocol_path: Path,
    execution_release_path: Path,
) -> dict[str, Any]:
    closure = EvidenceClosureProtocol.load(closure_protocol_path)
    effect_protocol = EffectProtocol.load(effect_protocol_path)
    source = closure.document["source_authority"]
    if effect_protocol.sha256 != source["effect_protocol_sha256"]:
        raise ResidualEffectError("M4-1R2 effect protocol binding differs")
    bundle = code_bundle_sha256()
    release = EffectRelease.load(
        execution_release_path,
        effect_protocol,
        code_bundle_sha256=bundle,
    )
    if release.document.get("closure_protocol_sha256") != closure.sha256:
        raise ResidualEffectError("M4-1R2 release does not bind the closure protocol")
    if release.document.get("report_reuse_only") is not True:
        raise ResidualEffectError("M4-1R2 release does not forbid research recomputation")
    verify_pushed_clean_state(release)
    effect_protocol.verify_upstream()
    before_state, report = closure.verify_state()

    identity = effect_protocol.document["identity"]
    report_path = project_path(identity["effect_report"])
    result_root = project_path(identity["result_root"])
    run_ledger = project_path(identity["run_ledger"])
    decision_ledger = project_path(identity["decision_ledger"])
    report_sha = sha256_file(report_path)
    reused = append_ledgers(
        report,
        report_sha,
        run_path=run_ledger,
        decision_path=decision_ledger,
    )
    manifest = build_manifest(report, report_path, report_sha, run_ledger, decision_ledger)
    manifest_sha, manifest_reused = write_json(manifest, result_root / "manifest.json")

    after_state, _ = closure.verify_state()
    if after_state != "COMPLETED":
        raise ResidualEffectError("M4-1R2 did not reach the completed evidence state")
    independent = audit(effect_protocol_path)
    if independent.get("status") != "PASS":
        raise ResidualEffectError("M4-1R2 independent audit did not pass")
    return {
        "schema_version": "m4-star50-residual-effect-evidence-closure-result-v1",
        "status": "PASS",
        "before_state": before_state,
        "after_state": after_state,
        "report_sha256": report_sha,
        "manifest_sha256": manifest_sha,
        "run_ledger_reused": reused["run"],
        "decision_ledgers_reused": reused["decisions"],
        "manifest_reused": manifest_reused,
        "independent_audit_status": independent["status"],
        "run_id": report["run_id"],
        "direction_pass_count": report["direction_pass_count"],
        "adapted_gate_pass_count": report["adapted_gate_pass_count"],
        "formal_g1_v1_status": report["formal_g1_v1_status"],
        "verdict": report["verdict"],
        "strategy_effective": report["strategy_effective"],
        "production_authorization": "none",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effect-protocol", type=Path, required=True)
    parser.add_argument("--closure-protocol", type=Path, required=True)
    parser.add_argument("--execution-release", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = close_evidence(
            args.effect_protocol,
            args.closure_protocol,
            args.execution_release,
        )
    except (OSError, ResidualEffectError, TypeError, ValueError) as error:
        print(json.dumps({"status": "FAIL", "error_class": type(error).__name__}, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
