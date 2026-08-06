"""Build only the metadata-level M5 lineage input manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contract import M5GateError, canonical_json
from .lineage_contract import LineageProtocol
from .lineage_inventory import build_lineage_input_manifest, write_manifest_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--build-contract", type=Path, required=True)
    parser.add_argument("--protocol-scope", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--prior-manifest", type=Path, required=True)
    parser.add_argument("--prior-release", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = LineageProtocol.load(
            protocol_path=args.protocol,
            build_path=args.build_contract,
            scope_path=args.protocol_scope,
            project_root=args.project_root,
        )
        document = build_lineage_input_manifest(
            protocol,
            project_root=args.project_root,
            ledger_path=args.ledger,
            prior_manifest_path=args.prior_manifest,
            prior_release_path=args.prior_release,
            created_at=args.created_at,
        )
        physical = write_manifest_once(args.output, document)
    except (M5GateError, OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(
        canonical_json(
            {
                "status": "PASS",
                "manifest_physical_sha256": physical,
                "anchor_batch_count": sum(len(item["batches"]) for item in document["anchor_sources"]),
                "history_batch_count": sum(len(item["batches"]) for item in document["history_sources"]),
                "semantic_rows_read": False,
                "authoritative_evidence_count": 0,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
