"""Run the M3-0 data/rule gate twice and bind deterministic evidence."""

from __future__ import annotations

import json
from typing import Any

from tools.m3_star_custom_pit.builder import BuildResult, build_membership
from tools.m3_star_custom_pit.contract import (
    PROJECT_ROOT,
    canonical_sha256,
    load_protocol,
    sha256_file,
    write_immutable_json,
    write_immutable_parquet,
)
from tools.m3_star_custom_pit.inputs import InputBundle, load_inputs


CODE_FILES = (
    "tools/m3_star_custom_pit/contract.py",
    "tools/m3_star_custom_pit/inputs.py",
    "tools/m3_star_custom_pit/quality.py",
    "tools/m3_star_custom_pit/builder.py",
    "tools/m3_star_custom_pit/run.py",
)


def _build_once(protocol: dict[str, Any]) -> tuple[InputBundle, BuildResult, dict[str, Any]]:
    inputs = load_inputs(protocol)
    result = build_membership(inputs, protocol)
    artifacts = {
        "formation_members": write_immutable_parquet(
            result.formation_members,
            PROJECT_ROOT / protocol["identity"]["formation_members"],
        ),
        "daily_members": write_immutable_parquet(
            result.daily_members,
            PROJECT_ROOT / protocol["identity"]["daily_members"],
        ),
    }
    return inputs, result, artifacts


def _artifact_identity(artifacts: dict[str, Any]) -> dict[str, Any]:
    return {
        key: {field: value[field] for field in ("path", "rows", "sha256")}
        for key, value in artifacts.items()
    }


def run() -> dict[str, Any]:
    protocol = load_protocol()
    first_inputs, first_result, first_artifacts = _build_once(protocol)
    second_inputs, second_result, second_artifacts = _build_once(protocol)
    first_identity = _artifact_identity(first_artifacts)
    second_identity = _artifact_identity(second_artifacts)
    idempotency_pass = all(
        (
            first_inputs.evidence["selected_input_sha256"]
            == second_inputs.evidence["selected_input_sha256"],
            canonical_sha256(first_result.metrics) == canonical_sha256(second_result.metrics),
            first_identity == second_identity,
            all(value["reused"] for value in second_artifacts.values()),
        )
    )
    if not idempotency_pass:
        raise RuntimeError("M3 build is not idempotent")

    code_hashes = {
        relative: sha256_file(PROJECT_ROOT / relative)
        for relative in CODE_FILES
    }
    required_gates = {
        field: bool(first_result.metrics[field])
        for field in (
            "source_gate_pass",
            "pit_gate_pass",
            "readiness_gate_pass",
            "output_gate_pass",
        )
    }
    required_gates["idempotency_pass"] = idempotency_pass
    gate_pass = all(required_gates.values())
    verdict = (
        protocol["verdict"]["go_label"]
        if gate_pass
        else protocol["verdict"]["no_go_label"]
    )
    report = {
        "schema_version": "m3-star-custom-pit-quality-v1",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": sha256_file(PROJECT_ROOT / "config/m3_star_custom_pit_v1.yaml"),
        "code_hashes": code_hashes,
        "code_bundle_sha256": canonical_sha256(code_hashes),
        "selected_input_sha256": first_inputs.evidence["selected_input_sha256"],
        "source_evidence": first_inputs.evidence,
        "metrics": first_result.metrics,
        "artifacts": first_identity,
        "idempotency_evidence": {
            "first_pass": first_identity,
            "second_pass": second_identity,
            "second_pass_reused_all": all(value["reused"] for value in second_artifacts.values()),
            "metrics_equal": canonical_sha256(first_result.metrics)
            == canonical_sha256(second_result.metrics),
            "selected_input_equal": first_inputs.evidence["selected_input_sha256"]
            == second_inputs.evidence["selected_input_sha256"],
        },
        **required_gates,
        "data_rule_gate_pass": gate_pass,
        "factor_results_inspected": False,
        "strategy_effective": "NOT_EVALUATED",
        "factor_protocol_authorized": protocol["verdict"]["factor_protocol_authorized_on_go"]
        if gate_pass
        else "none",
        "production_authorization": "none",
        "verdict": verdict,
    }
    report_path = PROJECT_ROOT / protocol["identity"]["quality_report"]
    report_artifact = write_immutable_json(report_path, report)
    manifest = {
        "schema_version": "m3-star-custom-pit-manifest-v1",
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": report["protocol_sha256"],
        "code_bundle_sha256": report["code_bundle_sha256"],
        "selected_input_sha256": report["selected_input_sha256"],
        "artifacts": {
            **first_identity,
            "quality_report": {
                "path": report_artifact["path"],
                "sha256": report_artifact["sha256"],
            },
        },
        "verdict": verdict,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "desensitization": {
            "absolute_paths_included": False,
            "credentials_included": False,
            "raw_or_derived_business_rows_included": False,
            "security_codes_included": False,
        },
    }
    manifest_path = PROJECT_ROOT / protocol["identity"]["tracked_manifest"]
    manifest_artifact = write_immutable_json(manifest_path, manifest)
    return {
        **report,
        "quality_report_sha256": report_artifact["sha256"],
        "manifest_sha256": manifest_artifact["sha256"],
    }


def main() -> int:
    report = run()
    fields = (
        "source_gate_pass",
        "pit_gate_pass",
        "readiness_gate_pass",
        "output_gate_pass",
        "idempotency_pass",
        "data_rule_gate_pass",
        "factor_results_inspected",
        "strategy_effective",
        "production_authorization",
        "verdict",
        "quality_report_sha256",
        "manifest_sha256",
    )
    print(json.dumps({field: report[field] for field in fields}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
