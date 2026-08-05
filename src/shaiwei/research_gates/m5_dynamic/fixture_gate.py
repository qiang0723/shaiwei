"""Offline container smoke gate using only fabricated M5 inputs and a temporary registry."""

from __future__ import annotations

import tempfile
from pathlib import Path

from shaiwei.research_gates.gate_registry.integrity import verify_registry_integrity
from shaiwei.research_gates.gate_registry.models import GateIdentity, canonical_json
from shaiwei.research_gates.gate_registry.service import GateRegistryService
from shaiwei.research_gates.gate_registry.storage import GateRegistryStore

from .auditor import audit_run, seal_audit
from .contract import PROTOCOL_SCOPE_SHA256, M5DataProtocol
from .fixture import synthetic_inputs
from .runner import build_gate_result, seal_run


def _identity(protocol: M5DataProtocol) -> GateIdentity:
    proposal = protocol.document["source_proposal"]
    return GateIdentity(
        proposal_id=proposal["proposal_id"],
        proposal_request_sha256=proposal["proposal_request_sha256"],
        canonical_proposal_sha256=proposal["canonical_proposal_sha256"],
        proposal_head_event_sha256=proposal["required_head_event_sha256"],
        proposal_export_sha256=proposal["proposal_export_sha256"],
        protocol_scope_sha256=PROTOCOL_SCOPE_SHA256,
        protocol_sha256=protocol.sha256,
        proposal_expires_at=proposal["expires_at"],
        candidate_ids=protocol.candidate_ids,
    )


def run_fixture(project_root: Path) -> dict[str, object]:
    protocol = M5DataProtocol.load(
        project_root / "config/m5_dynamic_fundamental_cross_pool_v1.yaml",
        build_path=project_root / "config/m5_dynamic_fundamental_data_gate_build_v1.yaml",
        project_root=project_root,
    )
    frames, memberships = synthetic_inputs(protocol)
    input_sha, release_sha, code_sha, approval_sha = (character * 64 for character in "1234")
    panel, report = build_gate_result(
        protocol,
        frames,
        memberships,
        input_manifest_sha256=input_sha,
        release_scope_sha256=release_sha,
        code_bundle_sha256=code_sha,
        approval_event_sha256=approval_sha,
        semantic_rows_read=False,
    )
    with tempfile.TemporaryDirectory(prefix="m5-fixture-") as temporary:
        root = Path(temporary)
        manifest = seal_run(root / "runs", panel, report)
        run_root = root / "runs" / manifest["run_id"]
        audit = audit_run(
            protocol,
            frames,
            memberships,
            run_root=run_root,
            expected_input_manifest_sha256=input_sha,
            expected_release_scope_sha256=release_sha,
            expected_approval_event_sha256=approval_sha,
        )
        sealed_audit = seal_audit(root / "audits", audit)
        store = GateRegistryStore(root / "registry.sqlite3")
        service = GateRegistryService(store)
        identity = _identity(protocol)
        service.import_case(
            identity,
            actor="M5_FIXTURE_BUILDER",
            idempotency_key="fixture-import",
            recorded_at="2026-08-05T12:00:00+00:00",
        )
        service.advance(
            identity.case_id,
            "PROTOCOL_FROZEN",
            {
                "protocol_scope_sha256": identity.protocol_scope_sha256,
                "protocol_sha256": identity.protocol_sha256,
            },
            expected_event_seq=1,
            actor="M5_FIXTURE_BUILDER",
            idempotency_key="fixture-protocol",
            recorded_at="2026-08-05T12:01:00+00:00",
        )
        service.advance(
            identity.case_id,
            "DATA_GATE_RELEASE_READY",
            {"release_scope_sha256": release_sha},
            expected_event_seq=2,
            actor="M5_FIXTURE_BUILDER",
            idempotency_key="fixture-release",
            recorded_at="2026-08-05T12:02:00+00:00",
        )
        with store.read() as connection:
            verify_registry_integrity(connection)
            table_count = connection.execute(
                "SELECT count(*) FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchone()[0]
        return {
            "status": "PASS",
            "execution_kind": manifest["execution_kind"],
            "data_gate_verdict": manifest["verdict"],
            "independent_audit_status": sealed_audit["status"],
            "candidate_count": manifest["candidate_count"],
            "universe_count": manifest["universe_count"],
            "evaluation_unit_count": manifest["evaluation_unit_count"],
            "registry_table_count": table_count,
            "formal_registry_initialized": False,
            "real_financial_rows_read": False,
            "effect_test_count": 0,
            "production_authorization": "none",
        }


def main() -> int:
    result = run_fixture(Path.cwd())
    print(canonical_json(result))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
