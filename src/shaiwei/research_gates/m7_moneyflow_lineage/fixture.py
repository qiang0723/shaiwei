"""Fully synthetic fixture for all lineage categories and the DuckDB audit."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json, sha256_json

from .audit_compute import recompute_lineage_core
from .compute import compute_lineage_core
from .contract import CATEGORIES, UNIVERSE_IDS, LineageError, LineageProtocol
from .reader import LineageInputs


OFFICIAL_DATES = (
    "20201231",
    "20210104",
    "20210105",
    "20210106",
    "20210107",
    "20210108",
    "20210111",
    "20210112",
    "20210113",
    "20210114",
    "20210115",
    "20210118",
)
CODES = tuple(f"688{index:03d}.SH" for index in range(11))


def synthetic_inputs() -> LineageInputs:
    membership = pd.DataFrame(
        [
            {
                "trade_date": OFFICIAL_DATES[index + 1],
                "formation_date": "20201231",
                "universe_id": universe,
                "ts_code": CODES[index],
                "segment": "2021H1",
            }
            for universe in UNIVERSE_IDS
            for index in range(11)
        ]
    )
    moneyflow = pd.DataFrame(
        [{"ts_code": CODES[10], "trade_date": OFFICIAL_DATES[10], "request_trade_date": OFFICIAL_DATES[10]}]
    )
    daily = pd.DataFrame(
        [
            {"ts_code": CODES[2], "trade_date": OFFICIAL_DATES[2]},
            {"ts_code": CODES[3], "trade_date": OFFICIAL_DATES[3]},
        ]
    )
    suspension = pd.DataFrame(
        [
            {
                "ts_code": CODES[6],
                "trade_date": OFFICIAL_DATES[6],
                "primary_full_day": 1,
                "primary_intraday": 1,
            },
            {
                "ts_code": CODES[7],
                "trade_date": OFFICIAL_DATES[7],
                "primary_full_day": 1,
                "primary_intraday": 0,
            },
            {
                "ts_code": CODES[8],
                "trade_date": OFFICIAL_DATES[8],
                "primary_full_day": 0,
                "primary_intraday": 1,
            },
        ]
    )
    independent = pd.DataFrame(
        [
            {
                "ts_code": CODES[1],
                "trade_date": OFFICIAL_DATES[1],
                "independent_nontrading": 1,
                "independent_trading": 1,
                "invalid_status_rows": 0,
            },
            {
                "ts_code": CODES[2],
                "trade_date": OFFICIAL_DATES[2],
                "independent_nontrading": 1,
                "independent_trading": 0,
                "invalid_status_rows": 0,
            },
            {
                "ts_code": CODES[4],
                "trade_date": OFFICIAL_DATES[4],
                "independent_nontrading": 0,
                "independent_trading": 1,
                "invalid_status_rows": 0,
            },
            {
                "ts_code": CODES[5],
                "trade_date": OFFICIAL_DATES[5],
                "independent_nontrading": 1,
                "independent_trading": 0,
                "invalid_status_rows": 0,
            },
        ]
    )
    return LineageInputs(
        membership=membership,
        moneyflow_keys=moneyflow,
        daily_keys=daily,
        suspension=suspension,
        independent_status=independent,
        official_dates=OFFICIAL_DATES,
        quarantined_source_dates=frozenset({OFFICIAL_DATES[0]}),
        evidence={
            "numeric_moneyflow_value_columns_read": 0,
            "numeric_daily_value_columns_read": 0,
        },
    )


def verify_fixture(protocol: LineageProtocol) -> dict[str, object]:
    inputs = synthetic_inputs()
    main = compute_lineage_core(protocol, inputs)
    audit = recompute_lineage_core(protocol, inputs)
    if main != audit:
        raise LineageError("lineage synthetic main and audit differ")
    expected = {category: 3 for category in CATEGORIES}
    if main["lineage_partition"]["category_counts"] != expected:
        raise LineageError("lineage synthetic category partition differs")
    if main["dataset_and_grain"]["membership_row_count"] != 33:
        raise LineageError("lineage synthetic membership count differs")
    if main["dataset_and_grain"]["missing_row_count"] != 30:
        raise LineageError("lineage synthetic missing count differs")
    if main["verdict"] != "NO_GO_M7_GAP_LINEAGE_INCOMPLETE":
        raise LineageError("lineage synthetic conflict verdict differs")
    if main["authority"]["adjusted_or_counterfactual_coverage_computed"] is not False:
        raise LineageError("lineage fixture computed forbidden adjusted coverage")
    return {
        "status": "PASS",
        "fixture_sha256": sha256_json(main),
        "category_count": len(CATEGORIES),
        "main_audit_exact_match": True,
        "numeric_moneyflow_value_columns_read": 0,
        "strategy_effective": "NOT_EVALUATED",
        "production_authorization": "none",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = args.project_root.resolve(strict=True)
        protocol = LineageProtocol.load(
            root / "config/m7_moneyflow_gap_lineage_v1.yaml",
            project_root=root,
        )
        result = verify_fixture(protocol)
    except (LineageError, OSError, TypeError, ValueError) as error:
        print(canonical_json({"status": "FAIL", "error_class": type(error).__name__, "message": str(error)}))
        return 2
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
