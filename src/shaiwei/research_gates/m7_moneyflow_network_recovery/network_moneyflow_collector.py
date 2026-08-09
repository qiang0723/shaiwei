"""Approved-scope Tushare moneyflow collector for one sealed M7 request plan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json

from shaiwei.research_gates.m7_moneyflow_recovery.contract import RecoveryError

from .live_clients import load_tushare_client
from .network_collect import collect_moneyflow_plan
from .network_runtime import (
    load_runtime_authority,
    load_runtime_plan,
    role_activation_id,
)
from .sealing import claim_role_once


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--plan-root", type=Path, required=True)
    parser.add_argument("--release-scope", type=Path, required=True)
    parser.add_argument("--approval-envelope", type=Path, required=True)
    parser.add_argument("--batch-root", type=Path, required=True)
    parser.add_argument("--claim-root", type=Path, required=True)
    parser.add_argument("--secret-file", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        authority = load_runtime_authority(
            args.project_root.resolve(strict=True),
            plan_root=args.plan_root.resolve(strict=True),
            release_scope=args.release_scope.resolve(strict=True),
            approval_envelope=args.approval_envelope.resolve(strict=True),
        )
        claim_role_once(
            args.claim_root,
            role="moneyflow_collector",
            release_scope_sha256=authority.release.sha256,
            run_id=role_activation_id(authority, "moneyflow_collector"),
        )
        plan = load_runtime_plan(authority)
        client = load_tushare_client(args.secret_file)
        result = collect_moneyflow_plan(
            authority.recovery,
            plan,
            release_scope_sha256=authority.release.sha256,
            client=client,
            batch_root=args.batch_root,
            claim_root=args.claim_root,
        )
    except (OSError, RecoveryError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__}))
        return 2
    print(
        canonical_json(
            {
                "status": "PASS",
                "role": "moneyflow_collector",
                "request_count": result["request_count"],
                "manifest_sha256": result["manifest_sha256"],
                "production_authorization": "none",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
