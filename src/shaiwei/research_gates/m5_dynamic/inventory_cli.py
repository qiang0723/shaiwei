"""Build only the metadata-level M5 input manifest; never reads Parquet column values."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contract import M5DataProtocol, M5GateError, canonical_json
from .input_inventory import build_input_manifest, write_manifest_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--build-contract", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protocol = M5DataProtocol.load(
            args.protocol,
            build_path=args.build_contract,
            project_root=args.project_root,
        )
        document = build_input_manifest(
            protocol,
            project_root=args.project_root,
            ledger_path=args.ledger,
            created_at=args.created_at,
        )
        physical_sha256 = write_manifest_once(args.output, document)
    except (M5GateError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(
        canonical_json(
            {
                "status": "PASS",
                "manifest_physical_sha256": physical_sha256,
                "source_count": len(document["sources"]),
                "batch_count": sum(len(item["batches"]) for item in document["sources"]),
                "membership_count": len(document["memberships"]),
                "semantic_rows_read": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
