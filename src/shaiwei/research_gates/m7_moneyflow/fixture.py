"""Synthetic, value-free engineering fixture for the M7 runner and auditor."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from .audit_compute import recompute_quality_core
from .compute import compute_quality_core
from .contract import UNIVERSE_IDS, M7GateError, M7Protocol, canonical_json, sha256_json
from .reader import KeyInputs


FEATURE_DATES = (
    "20210104",
    "20210701",
    "20220104",
    "20220701",
    "20230103",
    "20230703",
    "20240102",
    "20240701",
    "20250102",
    "20250701",
    "20260105",
)
OFFICIAL_DATES = ("20201231", *FEATURE_DATES, "20260630")


def synthetic_inputs() -> KeyInputs:
    all_codes = [f"688{index:03d}.SH" for index in range(60)]
    codes = {
        UNIVERSE_IDS[0]: all_codes,
        UNIVERSE_IDS[1]: all_codes[:20],
        UNIVERSE_IDS[2]: all_codes[20:40],
    }
    memberships = []
    for index, feature_date in enumerate(OFFICIAL_DATES[1:]):
        formation_date = OFFICIAL_DATES[index]
        for universe, members in codes.items():
            memberships.extend(
                {
                    "trade_date": feature_date,
                    "formation_date": formation_date,
                    "universe_id": universe,
                    "ts_code": code,
                    "segment": "synthetic",
                }
                for code in members
            )
    source_rows = []
    for source_date in OFFICIAL_DATES[:-1]:
        source_rows.extend(
            {
                "ts_code": code,
                "trade_date": source_date,
                "request_trade_date": source_date,
            }
            for code in all_codes
        )
    return KeyInputs(
        membership=pd.DataFrame(memberships),
        source_keys=pd.DataFrame(source_rows),
        official_dates=OFFICIAL_DATES,
        quarantined_source_dates=frozenset(),
        evidence={
            "source_batch_count": len(OFFICIAL_DATES) - 1,
            "source_row_count": len(source_rows),
            "source_bytes": 0,
            "raw_projected_columns": ["ts_code", "trade_date"],
            "numeric_moneyflow_value_columns_read": 0,
            "membership_projected_columns": [
                "trade_date",
                "formation_date",
                "universe_id",
                "ts_code",
                "segment",
            ],
        },
    )


def _assert_replay_and_audit(protocol: M7Protocol, inputs: KeyInputs) -> dict[str, Any]:
    first = compute_quality_core(protocol, inputs)
    replay = compute_quality_core(protocol, inputs)
    audit = recompute_quality_core(protocol, inputs)
    if first != replay or sha256_json(first) != sha256_json(replay):
        raise M7GateError("M7 synthetic runner replay differs")
    if first != audit or sha256_json(first) != sha256_json(audit):
        raise M7GateError("M7 independent synthetic audit differs")
    return first


def run_fixture(protocol: M7Protocol) -> dict[str, Any]:
    clean = synthetic_inputs()
    clean_result = _assert_replay_and_audit(protocol, clean)
    if clean_result["verdict"] != protocol.document["verdict"]["go"]:
        raise M7GateError("M7 clean synthetic fixture did not pass")
    duplicate_source = clean.source_keys.copy()
    duplicate_source = pd.concat([duplicate_source, duplicate_source.iloc[[0]]], ignore_index=True)
    duplicate_result = _assert_replay_and_audit(
        protocol,
        KeyInputs(
            clean.membership,
            duplicate_source,
            clean.official_dates,
            clean.quarantined_source_dates,
            clean.evidence,
        ),
    )
    if duplicate_result["verdict"] != protocol.document["verdict"]["no_go"]:
        raise M7GateError("M7 duplicate source fixture did not fail closed")
    sparse_source = clean.source_keys.loc[
        ~(
            clean.source_keys["request_trade_date"].eq("20201231")
            & clean.source_keys["ts_code"].isin([f"688{index:03d}.SH" for index in range(10)])
        )
    ].copy()
    sparse_result = _assert_replay_and_audit(
        protocol,
        KeyInputs(
            clean.membership,
            sparse_source,
            clean.official_dates,
            clean.quarantined_source_dates,
            clean.evidence,
        ),
    )
    if sparse_result["verdict"] != protocol.document["verdict"]["no_go"]:
        raise M7GateError("M7 sparse source fixture did not fail closed")
    return {
        "status": "PASS",
        "clean_core_sha256": sha256_json(clean_result),
        "duplicate_core_sha256": sha256_json(duplicate_result),
        "sparse_core_sha256": sha256_json(sparse_result),
        "runner_replay_pass": True,
        "independent_audit_pass": True,
        "semantic_rows_read": False,
        "numeric_moneyflow_value_columns_read": 0,
        "effect_test_count": 0,
        "generation_attempt_increment": 0,
        "production_authorization": "none",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("config/m7_star_custom_pool_moneyflow_data_v1.yaml"),
    )
    parser.add_argument(
        "--build-contract",
        type=Path,
        default=Path("config/m7_star_custom_pool_moneyflow_data_gate_build_v1.yaml"),
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        protocol = M7Protocol.load(
            args.protocol,
            build_path=args.build_contract,
            project_root=args.project_root,
        )
        result = run_fixture(protocol)
    except (M7GateError, OSError, TypeError, ValueError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
