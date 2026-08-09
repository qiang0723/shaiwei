"""Real-scale synthetic fixture for the M7 dual-track recovery gate."""

from __future__ import annotations

import argparse
import re
import tempfile
from dataclasses import replace
from pathlib import Path

import pandas as pd

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_json

from .audit_compute import recompute_audit_vector
from .claims import (
    RequestClaimIdentity,
    RetryableTransportError,
    SemanticResponseError,
    execute_claimed_request,
)
from .compute import compute_recovery_core
from .contract import RecoveryError, RecoveryProtocol, UNIVERSE_IDS
from .inputs import RecoveryInputs
from .planning import plan_moneyflow_requests, plan_status_requests


def _targets(count: int, *, trade_date: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trade_date": trade_date,
                "universe_id": UNIVERSE_IDS[index % len(UNIVERSE_IDS)],
                "ts_code": f"{688000 + index:06d}.SH",
                "segment": "2021H1",
            }
            for index in range(count)
        ]
    )


def _moneyflow_rows(protocol: RecoveryProtocol, targets: pd.DataFrame) -> pd.DataFrame:
    fields = protocol.moneyflow_fields
    records = []
    for index, row in enumerate(targets.itertuples(index=False)):
        record: dict[str, object] = {"ts_code": row.ts_code, "trade_date": row.trade_date}
        record.update(
            {field: float(index * 100 + offset + 1) for offset, field in enumerate(fields[2:])}
        )
        records.append(record)
    return pd.DataFrame(records, columns=fields)


def synthetic_inputs(protocol: RecoveryProtocol) -> RecoveryInputs:
    track_a = _targets(protocol.expected_track_a_rows, trade_date="20210104")
    track_b = _targets(protocol.expected_track_b_rows, trade_date="20210105")
    status = track_a.loc[:, ["ts_code", "trade_date"]].copy()
    status["trade_status"] = "0"
    moneyflow = _moneyflow_rows(protocol, track_b)
    return RecoveryInputs(
        track_a_targets=track_a,
        track_b_targets=track_b,
        daily_keys=track_b.loc[:, ["ts_code", "trade_date"]].copy(),
        independent_status=status,
        full_market_target_rows=moneyflow.copy(),
        targeted_rows=moneyflow.copy(),
        official_dates=("20201231", "20210104", "20210105"),
        full_market_response_row_counts=(len(moneyflow),),
        immutable_batch_integrity=True,
    )


def _assert_case(
    protocol: RecoveryProtocol,
    name: str,
    inputs: RecoveryInputs,
    expected_verdict: str,
) -> str:
    main = compute_recovery_core(protocol, inputs)
    audit = recompute_audit_vector(protocol, inputs)
    if main["audit_vector"] != audit:
        raise RecoveryError(f"synthetic {name} main and independent audit differ")
    if main["verdict"] != expected_verdict:
        raise RecoveryError(f"synthetic {name} verdict differs")
    return sha256_json(main)


def _mutations(clean: RecoveryInputs) -> list[tuple[str, RecoveryInputs]]:
    status_conflict = clean.independent_status.copy()
    status_conflict.loc[status_conflict.index[0], "trade_status"] = "1"
    status_missing = clean.independent_status.iloc[1:].copy()
    targeted_missing = clean.targeted_rows.iloc[1:].copy()
    full_missing = clean.full_market_target_rows.iloc[1:].copy()
    both_targeted_missing = clean.targeted_rows.iloc[1:].copy()
    content_conflict = clean.targeted_rows.copy()
    content_conflict.loc[content_conflict.index[0], "net_mf_amount"] += 1.0
    duplicate_target = pd.concat(
        [clean.track_a_targets, clean.track_a_targets.iloc[[0]]], ignore_index=True
    )
    invalid_target = clean.track_a_targets.copy()
    invalid_target.loc[invalid_target.index[0], "ts_code"] = "430001.BJ"
    return [
        ("status_trading_conflict", replace(clean, independent_status=status_conflict)),
        ("status_missing_unresolved", replace(clean, independent_status=status_missing)),
        ("moneyflow_one_shape_missing", replace(clean, targeted_rows=targeted_missing)),
        (
            "moneyflow_both_shapes_missing",
            replace(
                clean,
                full_market_target_rows=full_missing,
                targeted_rows=both_targeted_missing,
            ),
        ),
        ("moneyflow_content_conflict", replace(clean, targeted_rows=content_conflict)),
        ("duplicate_target_key", replace(clean, track_a_targets=duplicate_target)),
        ("invalid_or_bj_key", replace(clean, track_a_targets=invalid_target)),
        ("saturated_response", replace(clean, full_market_response_row_counts=(6000,))),
        ("immutable_batch_failure", replace(clean, immutable_batch_integrity=False)),
    ]


def _claim_scenarios() -> dict[str, int]:
    counters = {"duplicate": 0, "transport": 0, "semantic": 0}
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)

        def fetch_duplicate() -> str:
            counters["duplicate"] += 1
            return "ok"

        duplicate = RequestClaimIdentity("a" * 64, "b" * 64)
        execute_claimed_request(root, duplicate, fetch_duplicate, lambda value: value)
        try:
            execute_claimed_request(root, duplicate, fetch_duplicate, lambda value: value)
        except RecoveryError:
            pass
        else:
            raise RecoveryError("synthetic duplicate request claim did not stop")

        def fetch_transport() -> str:
            counters["transport"] += 1
            raise RetryableTransportError("synthetic transport")

        try:
            execute_claimed_request(
                root,
                RequestClaimIdentity("a" * 64, "c" * 64),
                fetch_transport,
                lambda value: value,
            )
        except RetryableTransportError:
            pass
        else:
            raise RecoveryError("synthetic transport cap did not stop")

        def fetch_semantic() -> str:
            counters["semantic"] += 1
            return "empty"

        def reject_semantic(value: str) -> str:
            raise SemanticResponseError(f"synthetic semantic rejection: {value}")

        try:
            execute_claimed_request(
                root,
                RequestClaimIdentity("a" * 64, "d" * 64),
                fetch_semantic,
                reject_semantic,
            )
        except SemanticResponseError:
            pass
        else:
            raise RecoveryError("synthetic semantic failure did not stop")
    if counters != {"duplicate": 1, "transport": 3, "semantic": 1}:
        raise RecoveryError("synthetic request attempt counts differ")
    return counters


def verify_fixture(protocol: RecoveryProtocol) -> dict[str, object]:
    clean = synthetic_inputs(protocol)
    status_plan = plan_status_requests(protocol, clean.track_a_targets, clean.official_dates)
    moneyflow_plan = plan_moneyflow_requests(protocol, clean.track_b_targets)
    hashes = {
        "complete_go": _assert_case(
            protocol, "complete_go", clean, "GO_M7_EVIDENCE_RECOVERY_DATA_ONLY"
        )
    }
    for name, inputs in _mutations(clean):
        hashes[name] = _assert_case(
            protocol, name, inputs, "NO_GO_M7_EVIDENCE_RECOVERY_INCOMPLETE"
        )
    counters = _claim_scenarios()
    first = compute_recovery_core(protocol, clean)
    second = compute_recovery_core(protocol, clean)
    serialized = canonical_json(first)
    if first != second or re.search(r"[0-9]{6}\.(?:SH|SZ|BJ)", serialized):
        raise RecoveryError("synthetic recovery determinism or aggregate-only output differs")
    return {
        "status": "PASS",
        "verdict": "GO_M7_EVIDENCE_RECOVERY_ENGINEERING_ONLY",
        "scenario_count": 13,
        "scenario_bundle_sha256": sha256_json(hashes),
        "clean_core_sha256": sha256_json(first),
        "main_audit_exact_match": True,
        "double_run_exact_match": True,
        "status_request_count": len(status_plan),
        "moneyflow_request_count": len(moneyflow_plan),
        "claim_attempt_counts": counters,
        "external_provider_call_count": 0,
        "real_security_key_read": False,
        "real_moneyflow_numeric_value_read": False,
        "adjusted_coverage_computed": False,
        "research_attempt_increment": 0,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve(strict=True)
        protocol = RecoveryProtocol.load(
            root / "config/m7_moneyflow_evidence_recovery_v1.yaml",
            engineering_path=root / "config/m7_moneyflow_evidence_recovery_engineering_v1.yaml",
            project_root=root,
        )
        result = verify_fixture(protocol)
    except (OSError, RecoveryError, TypeError, ValueError) as error:
        print(
            canonical_json(
                {"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}
            )
        )
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
