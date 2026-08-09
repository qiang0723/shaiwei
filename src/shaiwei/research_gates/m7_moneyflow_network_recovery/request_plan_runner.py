"""One-shot offline builder for the exact M7 recovery provider request plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_file, sha256_json

from shaiwei.research_gates.m7_moneyflow_recovery.contract import (
    RecoveryError,
    RecoveryProtocol,
)
from shaiwei.research_gates.m7_moneyflow_recovery.projection_sealing import (
    logical_target_sha256,
)
from shaiwei.research_gates.m7_moneyflow_recovery.target_projection import OUTPUT_COLUMNS

from .network_contract import NetworkReleaseProtocol
from .request_plan import build_request_plan
from .request_plan_store import write_request_plan_once


DATE_RE = re.compile(r"^[0-9]{8}$")
CALENDAR_MANIFEST = "predecessor/config/m7_star_custom_pool_moneyflow_data_input_v1.json"


def _target_identity(
    network: NetworkReleaseProtocol,
    *,
    target_root: Path,
    track: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frozen = network.document["frozen_predecessors"][f"{track}_target"]
    path = target_root / str(frozen["file"])
    if path.is_symlink() or not path.is_file():
        raise RecoveryError("recovery network target file is missing")
    physical = sha256_file(path)
    frame = pd.read_parquet(path, columns=list(OUTPUT_COLUMNS)).astype("string")
    logical = logical_target_sha256(frame)
    member_rows = len(frame)
    unique_keys = len(frame.drop_duplicates(["ts_code", "source_date"]))
    if (
        physical != frozen["physical_sha256"]
        or logical != frozen["logical_sha256"]
        or member_rows != int(frozen["member_rows"])
        or unique_keys != int(frozen["unique_source_keys"])
    ):
        raise RecoveryError("recovery network target identity differs")
    return frame, {
        "member_rows": member_rows,
        "unique_source_keys": unique_keys,
        "physical_sha256": physical,
        "logical_sha256": logical,
    }


def _official_dates(
    network: NetworkReleaseProtocol,
    *,
    lineage_root: Path,
) -> tuple[tuple[str, ...], dict[str, Any]]:
    bundle_manifest = lineage_root / "bundle_manifest.json"
    if (
        bundle_manifest.is_symlink()
        or sha256_file(bundle_manifest) != network.lineage_bundle_manifest_sha256
    ):
        raise RecoveryError("recovery request-plan lineage bundle identity differs")
    manifest_path = lineage_root / CALENDAR_MANIFEST
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise RecoveryError("recovery request-plan calendar manifest is missing")
    serialized = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(serialized)
    batches = manifest.get("source_batches") if isinstance(manifest, dict) else None
    audit = manifest.get("source_audit") if isinstance(manifest, dict) else None
    if not isinstance(batches, list) or not isinstance(audit, dict):
        raise RecoveryError("recovery request-plan calendar manifest shape differs")
    dates = tuple(str(item.get("trade_date", "")) for item in batches)
    if (
        list(dates) != sorted(set(dates))
        or any(DATE_RE.fullmatch(day) is None for day in dates)
        or len(dates) != int(audit["selected_source_date_count"])
        or dates[0] != str(audit["selected_source_start_date"])
        or dates[-1] != str(audit["selected_source_end_date"])
    ):
        raise RecoveryError("recovery request-plan official dates differ")
    return dates, {
        "lineage_bundle_manifest_sha256": sha256_file(bundle_manifest),
        "calendar_manifest_relative_path": CALENDAR_MANIFEST,
        "calendar_manifest_physical_sha256": hashlib.sha256(serialized.encode()).hexdigest(),
        "official_date_count": len(dates),
        "official_date_min": dates[0],
        "official_date_max": dates[-1],
        "official_dates_logical_sha256": sha256_json(list(dates)),
    }


def build_real_request_plan(
    project_root: Path,
    *,
    target_root: Path,
    lineage_root: Path,
    output_root: Path,
    tracked_root_relative: str,
) -> dict[str, Any]:
    network = NetworkReleaseProtocol.load(
        project_root / "config/m7_moneyflow_evidence_recovery_network_release_v1.yaml",
        project_root=project_root,
    )
    recovery = RecoveryProtocol.load(
        project_root / "config/m7_moneyflow_evidence_recovery_v1.yaml",
        engineering_path=project_root / "config/m7_moneyflow_evidence_recovery_engineering_v1.yaml",
        project_root=project_root,
    )
    track_a, a_identity = _target_identity(network, target_root=target_root, track="track_a")
    track_b, b_identity = _target_identity(network, target_root=target_root, track="track_b")
    official_dates, calendar_identity = _official_dates(network, lineage_root=lineage_root)
    plan = build_request_plan(
        network,
        recovery,
        projected_track_a=track_a,
        projected_track_b=track_b,
        official_dates=official_dates,
    )
    root, manifest, manifest_sha = write_request_plan_once(
        output_root,
        plan,
        protocol_sha256=network.sha256,
        tracked_root_relative=tracked_root_relative,
        target_identity={"track_a": a_identity, "track_b": b_identity},
        calendar_identity=calendar_identity,
    )
    return {
        "status": "PASS",
        "verdict": "GO_M7_RECOVERY_EXACT_REQUEST_PLAN_ONLY",
        "plan_id": manifest["plan_id"],
        "manifest_sha256": manifest_sha,
        "plan_root_name": root.name,
        "request_summary": manifest["request_summary"],
        "security_codes_in_output": False,
        "moneyflow_numeric_value_columns_read": 0,
        "provider_call_count": 0,
        "external_network_used": False,
        "production_authorization": "none",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--lineage-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--tracked-root-relative", required=True)
    args = parser.parse_args(argv)
    try:
        result = build_real_request_plan(
            args.project_root.resolve(strict=True),
            target_root=args.target_root.resolve(strict=True),
            lineage_root=args.lineage_root.resolve(strict=True),
            output_root=args.output_root,
            tracked_root_relative=args.tracked_root_relative,
        )
    except (OSError, RecoveryError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
