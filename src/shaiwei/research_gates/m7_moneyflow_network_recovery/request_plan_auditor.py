"""Independent audit of one sealed real M7 recovery request plan."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_file, sha256_json
from shaiwei.research_gates.m7_moneyflow_recovery.contract import RecoveryError
from shaiwei.research_gates.m7_moneyflow_recovery.target_projection import OUTPUT_COLUMNS

from .network_contract import NetworkReleaseProtocol
from .sealing import read_canonical, write_canonical_once


CODE_RE = re.compile(r"[0-9]{6}\.(?:SH|SZ|BJ)")
DATE_RE = re.compile(r"[0-9]{8}")
PLAN_COLUMNS = {
    "status": (
        "request_sha256",
        "ts_code",
        "start_date",
        "end_date",
        "required_dates_json",
    ),
    "full_market": ("request_sha256", "trade_date"),
    "targeted": ("request_sha256", "ts_code", "start_date", "end_date"),
}


def _target(
    network: NetworkReleaseProtocol,
    target_root: Path,
    track: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frozen = network.document["frozen_predecessors"][f"{track}_target"]
    path = target_root / str(frozen["file"])
    frame = pq.read_table(path, columns=list(OUTPUT_COLUMNS)).to_pandas().astype("string")
    normalized = frame.loc[:, OUTPUT_COLUMNS].sort_values(list(OUTPUT_COLUMNS))
    logical = sha256_json(normalized.to_dict("records"))
    keys = frame.loc[:, ["ts_code", "source_date"]].drop_duplicates()
    if (
        path.is_symlink()
        or sha256_file(path) != frozen["physical_sha256"]
        or logical != frozen["logical_sha256"]
        or len(frame) != int(frozen["member_rows"])
        or len(keys) != int(frozen["unique_source_keys"])
        or not keys["ts_code"].str.fullmatch(r"[0-9]{6}\.SH").all()
    ):
        raise RecoveryError("recovery request-plan audit target identity differs")
    keys = keys.rename(columns={"source_date": "trade_date"}).astype("string")
    return keys, {
        "member_rows": len(frame),
        "unique_source_keys": len(keys),
        "physical_sha256": sha256_file(path),
        "logical_sha256": logical,
    }


def _frame(plan_root: Path, manifest: dict[str, Any], name: str) -> pd.DataFrame:
    item = manifest["plan_files"][name]
    relative_name = str(item["relative_name"])
    if relative_name != PurePosixPath(relative_name).name:
        raise RecoveryError("recovery request-plan audit path is unsafe")
    path = plan_root / relative_name
    metadata = pq.read_metadata(path)
    columns = PLAN_COLUMNS[name]
    if (
        path.is_symlink()
        or sha256_file(path) != item["physical_sha256"]
        or path.stat().st_size != int(item["bytes"])
        or metadata.num_rows != int(item["row_count"])
        or list(metadata.schema.names) != list(columns)
        or item["schema_fields"] != list(columns)
    ):
        raise RecoveryError("recovery request-plan audit file identity differs")
    frame = pq.read_table(path).to_pandas().astype("string")
    records = [
        {column: str(value) for column, value in row.items()}
        for row in frame.loc[:, columns].to_dict("records")
    ]
    if sha256_json(records) != item["logical_sha256"]:
        raise RecoveryError("recovery request-plan audit logical identity differs")
    return frame


def _official_dates(plan_root: Path, manifest: dict[str, Any]) -> tuple[str, ...]:
    item = manifest["official_dates_file"]
    relative_name = str(item["relative_name"])
    if relative_name != PurePosixPath(relative_name).name:
        raise RecoveryError("recovery request-plan audit date path is unsafe")
    path = plan_root / relative_name
    document = read_canonical(path)
    dates = tuple(map(str, document.get("official_dates", ())))
    if (
        path.is_symlink()
        or sha256_file(path) != item["physical_sha256"]
        or len(dates) != int(item["date_count"])
        or list(dates) != sorted(set(dates))
        or any(DATE_RE.fullmatch(day) is None for day in dates)
    ):
        raise RecoveryError("recovery request-plan audit official dates differ")
    return dates


def _plan_identity(
    network: NetworkReleaseProtocol,
    plan_root: Path,
    manifest: dict[str, Any],
    dates: tuple[str, ...],
) -> None:
    target = manifest["target_identity"]
    expected = sha256_json(
        {
            "schema_version": "m7-moneyflow-recovery-request-plan-v1",
            "protocol_sha256": network.sha256,
            "target_a_logical_sha256": target["track_a"]["logical_sha256"],
            "target_b_logical_sha256": target["track_b"]["logical_sha256"],
            "official_dates_sha256": sha256_json(list(dates)),
        }
    )
    if (
        manifest.get("protocol_sha256") != network.sha256
        or manifest.get("plan_id") != expected
        or plan_root.name != expected
    ):
        raise RecoveryError("recovery request-plan audit plan identity differs")


def _status_audit(
    frame: pd.DataFrame,
    target_keys: set[tuple[str, str]],
    official_dates: tuple[str, ...],
) -> dict[str, Any]:
    positions = {day: index for index, day in enumerate(official_dates)}
    observed_groups: set[tuple[str, str, str, tuple[str, ...]]] = set()
    expanded: list[tuple[str, str]] = []
    identities: list[str] = []
    maximum = 0
    for row in frame.itertuples(index=False):
        dates_value = json.loads(str(row.required_dates_json))
        dates = tuple(map(str, dates_value)) if isinstance(dates_value, list) else ()
        if (
            not dates
            or str(row.start_date) != dates[0]
            or str(row.end_date) != dates[-1]
            or any(day not in positions for day in dates)
            or any(positions[right] != positions[left] + 1 for left, right in zip(dates, dates[1:]))
        ):
            raise RecoveryError("recovery request-plan audit status window differs")
        identity = sha256_json(
            {
                "source_api": "baostock.history_k_data_plus",
                "ts_code": str(row.ts_code),
                "start_date": str(row.start_date),
                "end_date": str(row.end_date),
                "required_dates": list(dates),
            }
        )
        if identity != str(row.request_sha256):
            raise RecoveryError("recovery request-plan audit status identity differs")
        group = (str(row.ts_code), dates[0], dates[-1], dates)
        observed_groups.add(group)
        expanded.extend((str(row.ts_code), day) for day in dates)
        identities.append(identity)
        maximum = max(maximum, len(dates))
    expected_groups: set[tuple[str, str, str, tuple[str, ...]]] = set()
    targets = pd.DataFrame(sorted(target_keys), columns=("ts_code", "trade_date"))
    for code, cell in targets.groupby("ts_code", sort=True):
        dates = cell["trade_date"].astype(str).sort_values(key=lambda s: s.map(positions)).tolist()
        current = [dates[0]]
        for day in dates[1:]:
            if positions[day] == positions[current[-1]] + 1:
                current.append(day)
            else:
                expected_groups.add((str(code), current[0], current[-1], tuple(current)))
                current = [day]
        expected_groups.add((str(code), current[0], current[-1], tuple(current)))
    if (
        len(expanded) != len(set(expanded))
        or set(expanded) != target_keys
        or observed_groups != expected_groups
    ):
        raise RecoveryError("recovery request-plan audit status coverage differs")
    return {
        "request_count": len(frame),
        "required_key_count": len(expanded),
        "maximum_window_key_count": maximum,
        "request_identity_bundle_sha256": sha256_json(identities),
    }


def _moneyflow_audit(
    full: pd.DataFrame,
    targeted: pd.DataFrame,
    target_keys: set[tuple[str, str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    full_identities = []
    full_dates = []
    for row in full.itertuples(index=False):
        params = {"trade_date": str(row.trade_date)}
        identity = sha256_json(
            {"source_api": "tushare.moneyflow", "shape": "full_market_by_trade_date", "params": params}
        )
        if identity != str(row.request_sha256):
            raise RecoveryError("recovery request-plan audit full-market identity differs")
        full_identities.append(identity)
        full_dates.append(str(row.trade_date))
    targeted_identities = []
    targeted_keys = []
    for row in targeted.itertuples(index=False):
        params = {
            "ts_code": str(row.ts_code),
            "start_date": str(row.start_date),
            "end_date": str(row.end_date),
        }
        identity = sha256_json(
            {"source_api": "tushare.moneyflow", "shape": "one_security_one_date", "params": params}
        )
        if identity != str(row.request_sha256) or params["start_date"] != params["end_date"]:
            raise RecoveryError("recovery request-plan audit targeted identity differs")
        targeted_identities.append(identity)
        targeted_keys.append((params["ts_code"], params["start_date"]))
    expected_dates = {day for _, day in target_keys}
    if (
        len(full_dates) != len(set(full_dates))
        or set(full_dates) != expected_dates
        or len(targeted_keys) != len(set(targeted_keys))
        or set(targeted_keys) != target_keys
    ):
        raise RecoveryError("recovery request-plan audit moneyflow coverage differs")
    return (
        {
            "request_count": len(full),
            "request_identity_bundle_sha256": sha256_json(full_identities),
        },
        {
            "request_count": len(targeted),
            "request_identity_bundle_sha256": sha256_json(targeted_identities),
        },
    )


def audit_request_plan(
    project_root: Path,
    *,
    target_root: Path,
    plan_root: Path,
) -> dict[str, Any]:
    network = NetworkReleaseProtocol.load(
        project_root / "config/m7_moneyflow_evidence_recovery_network_release_v1.yaml",
        project_root=project_root,
    )
    manifest_path = plan_root / "request_plan_manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise RecoveryError("recovery request-plan audit manifest is missing")
    manifest = read_canonical(manifest_path)
    dates = _official_dates(plan_root, manifest)
    _plan_identity(network, plan_root, manifest, dates)
    a_keys, a_identity = _target(network, target_root, "track_a")
    b_keys, b_identity = _target(network, target_root, "track_b")
    status = _status_audit(
        _frame(plan_root, manifest, "status"),
        set(a_keys.itertuples(index=False, name=None)),
        dates,
    )
    full, targeted = _moneyflow_audit(
        _frame(plan_root, manifest, "full_market"),
        _frame(plan_root, manifest, "targeted"),
        set(b_keys.itertuples(index=False, name=None)),
    )
    summary = manifest["request_summary"]
    official_summary = {
        "date_count": len(dates),
        "date_min": min(dates),
        "date_max": max(dates),
        "logical_sha256": sha256_json(list(dates)),
    }
    if (
        status != summary["status"]
        or full != summary["full_market"]
        or targeted != summary["targeted"]
        or official_summary != summary["official_dates"]
        or {"track_a": a_identity, "track_b": b_identity} != manifest["target_identity"]
    ):
        raise RecoveryError("recovery request-plan audit aggregate differs")
    audit = {
        "schema_version": "m7-moneyflow-recovery-request-plan-audit-v1",
        "audit_status": "PASS",
        "protocol_sha256": network.sha256,
        "plan_id": manifest["plan_id"],
        "plan_manifest_sha256": sha256_file(manifest_path),
        "status_requests": status,
        "full_market": full,
        "targeted": targeted,
        "official_dates_logical_sha256": sha256_json(list(dates)),
        "exact_key_coverage": True,
        "maximal_consecutive_status_windows": True,
        "security_codes_in_audit": False,
        "moneyflow_numeric_value_columns_read": 0,
        "provider_call_count": 0,
        "external_network_used": False,
        "production_authorization": "none",
        "verdict": "GO_M7_RECOVERY_EXACT_REQUEST_PLAN_AUDIT_ONLY",
    }
    if CODE_RE.search(canonical_json(audit)):
        raise RecoveryError("recovery request-plan audit leaks a security code")
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--target-root", type=Path, required=True)
    parser.add_argument("--plan-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        audit = audit_request_plan(
            args.project_root.resolve(strict=True),
            target_root=args.target_root.resolve(strict=True),
            plan_root=args.plan_root.resolve(strict=True),
        )
        audit_sha = write_canonical_once(
            args.audit_root / str(audit["plan_id"]) / "request_plan_audit.json", audit
        )
    except (OSError, RecoveryError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__}))
        return 2
    print(
        canonical_json(
            {
                "status": "PASS",
                "plan_id": audit["plan_id"],
                "audit_sha256": audit_sha,
                "request_counts": {
                    name: audit[f"{name}_requests" if name == "status" else name][
                        "request_count"
                    ]
                    for name in ("status", "full_market", "targeted")
                },
                "provider_call_count": 0,
                "external_network_used": False,
                "production_authorization": "none",
                "verdict": audit["verdict"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
