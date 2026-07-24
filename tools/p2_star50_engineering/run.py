"""Execute and ledger the frozen P2-1 engineering-only work package."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shaiwei.config import PROJECT_ROOT
from shaiwei.ledger import (
    append_p2_star50_engineering_admission,
    append_p2_star50_engineering_run,
    sha256_file,
)

from tools.p2_star50_engineering.contract import GateFailure
from tools.p2_star50_engineering.data import build_dataset, build_or_reuse_qlib
from tools.p2_star50_engineering.synthetic import run_synthetic_smoke


def _write_immutable_json(path: Path, value: dict[str, Any]) -> str:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != rendered:
        raise GateFailure(f"immutable report differs: {path.relative_to(PROJECT_ROOT)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    return sha256_file(path)


def run() -> dict[str, Any]:
    first_dataset = build_dataset()
    first_qlib = build_or_reuse_qlib(first_dataset)
    first_smoke = run_synthetic_smoke()
    protocol = first_dataset["protocol"]
    quality_path = PROJECT_ROOT / protocol["identity"]["quality_report"]
    smoke_path = PROJECT_ROOT / protocol["identity"]["synthetic_root"] / "smoke_report.json"
    first_hashes = {
        "quality_report_sha256": sha256_file(quality_path),
        "qlib_artifact_sha256": first_qlib["artifact_sha256"],
        "synthetic_smoke_sha256": sha256_file(smoke_path),
    }

    second_dataset = build_dataset()
    second_qlib = build_or_reuse_qlib(second_dataset)
    second_smoke = run_synthetic_smoke()
    second_hashes = {
        "quality_report_sha256": sha256_file(quality_path),
        "qlib_artifact_sha256": second_qlib["artifact_sha256"],
        "synthetic_smoke_sha256": sha256_file(smoke_path),
    }
    idempotency_pass = (
        first_hashes == second_hashes
        and second_qlib["provider_reused"] is True
        and first_smoke == second_smoke
    )
    if not idempotency_pass:
        raise GateFailure("P2-1 artifact replay is not idempotent")

    required = {
        "input_gate_pass": bool(first_dataset["quality"]["input_gate_pass"]),
        "dataset_complete": bool(first_dataset["quality"]["dataset_complete"]),
        "qlib_complete": bool(first_qlib["qlib_complete"]),
        "pipeline_fixture_pass": bool(first_smoke["pipeline_fixture_pass"]),
        "idempotency_pass": idempotency_pass,
    }
    engineering_complete = all(required.values())
    report = {
        "schema_version": "p2-star50-engineering-report-v1",
        "research_family": protocol["identity"]["research_family"],
        "protocol_sha256": sha256_file(PROJECT_ROOT / "config/p2_star50_engineering_v1.yaml"),
        "orchestrator_code_sha256": sha256_file(Path(__file__)),
        "upstream_artifact_hashes": first_dataset["quality"]["upstream_artifact_hashes"],
        "quality_report_sha256": first_hashes["quality_report_sha256"],
        "qlib": {
            "provider": protocol["identity"]["qlib_provider"],
            "artifact_file_count": int(first_qlib["artifact_file_count"]),
            "artifact_byte_count": int(first_qlib["artifact_byte_count"]),
            "artifact_sha256": first_qlib["artifact_sha256"],
            "build_identity_sha256": first_qlib["build_identity_sha256"],
        },
        "synthetic_smoke": {
            "fixture_id": first_smoke["fixture_id"],
            "fixture_sha256": first_smoke["fixture_sha256"],
            "report_sha256": first_hashes["synthetic_smoke_sha256"],
            "stage_status": first_smoke["stage_status"],
        },
        "idempotency_evidence": {
            "first_pass_hashes": first_hashes,
            "second_pass_hashes": second_hashes,
            "second_qlib_provider_reused": bool(second_qlib["provider_reused"]),
            "synthetic_report_byte_equal": first_smoke == second_smoke,
        },
        **required,
        "engineering_complete": engineering_complete,
        "strategy_results_inspected": False,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": "GO" if engineering_complete else "NO_GO",
    }
    report_path = PROJECT_ROOT / protocol["identity"]["engineering_report"]
    report_sha256 = _write_immutable_json(report_path, report)
    frozen_at = str(protocol["frozen_at"])
    ledger_fields = {
        "run_id": f"{protocol['identity']['research_family']}-{report_sha256[:12]}",
        "finished_at": frozen_at,
        "research_family": protocol["identity"]["research_family"],
        "protocol_sha256": report["protocol_sha256"],
        "input_gate_pass": str(report["input_gate_pass"]).lower(),
        "dataset_complete": str(report["dataset_complete"]).lower(),
        "qlib_complete": str(report["qlib_complete"]).lower(),
        "pipeline_fixture_pass": str(report["pipeline_fixture_pass"]).lower(),
        "idempotency_pass": str(report["idempotency_pass"]).lower(),
        "engineering_complete": str(report["engineering_complete"]).lower(),
        "strategy_results_inspected": "false",
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
        "verdict": report["verdict"],
        "quality_report_sha256": report["quality_report_sha256"],
        "engineering_report_sha256": report_sha256,
        "qlib_artifact_sha256": report["qlib"]["artifact_sha256"],
        "synthetic_smoke_sha256": report["synthetic_smoke"]["report_sha256"],
        "operator": "p2-star50-engineering",
    }
    append_p2_star50_engineering_run(**ledger_fields)
    append_p2_star50_engineering_admission(
        decision_id=(f"{protocol['identity']['research_family']}-boundary-{report_sha256[:12]}"),
        evaluated_at=frozen_at,
        research_family=protocol["identity"]["research_family"],
        protocol_sha256=report["protocol_sha256"],
        decision="P2_1_ENGINEERING_GO_ONLY",
        strategy_effective="NOT_EVALUATED",
        strategy_results_inspected="false",
        production_authorization="none",
        reason="P2-2 review required before any real training or effect inspection",
        engineering_report_sha256=report_sha256,
        operator="p2-star50-engineering",
    )
    return {**report, "engineering_report_sha256": report_sha256}


def main() -> int:
    report = run()
    print(
        json.dumps(
            {
                field: report[field]
                for field in (
                    "input_gate_pass",
                    "dataset_complete",
                    "qlib_complete",
                    "pipeline_fixture_pass",
                    "idempotency_pass",
                    "engineering_complete",
                    "strategy_results_inspected",
                    "strategy_effective",
                    "production_authorization",
                    "verdict",
                    "engineering_report_sha256",
                )
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
