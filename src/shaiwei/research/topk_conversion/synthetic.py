"""Deterministic result-blind M6-3B fixture runner."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.model_attribution.contract import AttributionError
from shaiwei.research.model_attribution.inference import holm_adjust
from shaiwei.research.topk_conversion.artifacts import (
    canonical_sha256,
    sha256_file,
    write_once_json,
)
from shaiwei.research.topk_conversion.contract import (
    ConversionError,
    ProtocolBundle,
    bounded_path,
    runtime_release_identity,
)
from shaiwei.research.topk_conversion.execution import scheduled_topk
from shaiwei.research.topk_conversion.metrics import evaluate_case
from shaiwei.research.topk_conversion.schema import (
    ALTERNATIVES,
    ARMS,
    STRESS_PERIODS,
    TOPK_KEYS,
    WINDOWS,
)


DEFAULT_ROOT = PROJECT_ROOT / "data/research/m6_csi800_topk20_conversion_v1/engineering/runner"
EXPECTED_CASES = {
    "TOPK20_CONVERSION_SUPPORTED": "TOPK20_CONVERSION_SUPPORTED",
    "TOPK20_CONVERSION_NOT_SUPPORTED": "TOPK20_CONVERSION_NOT_SUPPORTED",
    "MIXED_NOT_CONCLUSIVE": "MIXED_NOT_CONCLUSIVE",
    "BLOCKED": "BLOCKED",
}


def _dates(window: int, days: int) -> list[str]:
    return [value.strftime("%Y-%m-%d") for value in pd.bdate_range(f"209{window}-01-02", periods=days)]


def _rows(
    dates: list[str],
    *,
    window: int,
    topk: int,
    arm_index: int,
    relative_shift: float,
    turnover: float,
) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for step, day in enumerate(dates):
        benchmark = 0.00008 + 0.00004 * np.sin((step + window) / 5.0)
        common = 0.00010 + 0.00007 * np.cos((step + 2 * window) / 4.0)
        topk_effect = -0.00002 if topk == 20 else 0.0
        arm_noise = arm_index * 0.000015 * np.sin(step / (2.0 + topk / 30.0) + window)
        recorded_cost = 0.00004 + (step % 3) * 0.000003
        rows.append(
            {
                "date": day,
                "gross_return": float(benchmark + common + topk_effect + relative_shift + arm_noise),
                "benchmark_return": float(benchmark),
                "recorded_cost": float(recorded_cost),
                "turnover": float(turnover),
            }
        )
    return rows


def _case_parameters(name: str) -> tuple[dict[str, tuple[float, float]], list[str]]:
    if name == "TOPK20_CONVERSION_SUPPORTED":
        return {
            ALTERNATIVES[0]: (-0.00020, 0.00050),
            ALTERNATIVES[1]: (-0.00025, -0.00010),
        }, []
    if name == "TOPK20_CONVERSION_NOT_SUPPORTED":
        return {
            ALTERNATIVES[0]: (-0.00010, -0.00030),
            ALTERNATIVES[1]: (-0.00005, -0.00025),
        }, []
    if name == "MIXED_NOT_CONCLUSIVE":
        return {
            ALTERNATIVES[0]: (-0.00080, -0.00010),
            ALTERNATIVES[1]: (-0.00010, -0.00030),
        }, []
    if name == "BLOCKED":
        return {
            ALTERNATIVES[0]: (-0.00020, 0.00050),
            ALTERNATIVES[1]: (-0.00025, -0.00010),
        }, ["synthetic_preflight_blocked"]
    raise ConversionError(f"M6-3 unknown synthetic case: {name}")


def _reports_for_case(
    name: str,
    *,
    days: int,
) -> dict[str, dict[str, dict[str, list[dict[str, float | str]]]]]:
    parameters, _ = _case_parameters(name)
    output: dict[str, dict[str, dict[str, list[dict[str, float | str]]]]] = {}
    for topk in TOPK_KEYS:
        output[topk] = {}
        for number, window in enumerate(WINDOWS, start=1):
            dates = _dates(number, days)
            output[topk][window] = {}
            for arm_index, arm in enumerate(ARMS):
                shift = 0.0 if arm == ARMS[0] else parameters[arm][0 if topk == "30" else 1]
                turnover = 0.0100 if arm == ARMS[0] else 0.0095 + arm_index * 0.0001
                output[topk][window][arm] = _rows(
                    dates,
                    window=number,
                    topk=int(topk),
                    arm_index=arm_index,
                    relative_shift=shift,
                    turnover=turnover,
                )
    return output


def _stress_for_case(
    name: str,
) -> dict[str, dict[str, dict[str, list[dict[str, float | str]]]]]:
    parameters, _ = _case_parameters(name)
    output: dict[str, dict[str, dict[str, list[dict[str, float | str]]]]] = {}
    for topk in TOPK_KEYS:
        output[topk] = {}
        for offset, period in enumerate(STRESS_PERIODS, start=7):
            dates = _dates(offset, 20)
            output[topk][period] = {}
            for arm_index, arm in enumerate(ARMS):
                shift = 0.0 if arm == ARMS[0] else parameters[arm][0 if topk == "30" else 1]
                turnover = 0.0100 if arm == ARMS[0] else 0.0095 + arm_index * 0.0001
                output[topk][period][arm] = _rows(
                    dates,
                    window=offset,
                    topk=int(topk),
                    arm_index=arm_index,
                    relative_shift=shift,
                    turnover=turnover,
                )
    return output


def _scheduled_names() -> dict[str, dict[str, dict[str, list[str]]]]:
    names = [f"SYN{index:03d}" for index in range(40)]
    output: dict[str, dict[str, dict[str, list[str]]]] = {}
    for topk in TOPK_KEYS:
        count = int(topk)
        output[topk] = {}
        for window in WINDOWS:
            output[topk][window] = {
                ARMS[0]: names[:count],
                ARMS[1]: names[5 : 5 + count],
                ARMS[2]: names[10 : 10 + count],
            }
    return output


def build_bundle(protocols: ProtocolBundle) -> dict[str, Any]:
    days = int(protocols.engineering["synthetic_contract"]["daily_rows_per_window"])
    cases: dict[str, Any] = {}
    for name in EXPECTED_CASES:
        reports = _reports_for_case(name, days=days)
        _, blocked_reasons = _case_parameters(name)
        cases[name] = {
            "preflight_blocked_reasons": blocked_reasons,
            "top30_reference": deepcopy(reports["30"]),
            "reports": reports,
            "stress_reports": _stress_for_case(name),
            "scheduled_names": _scheduled_names(),
        }
    return {
        "schema_version": "m6-topk20-conversion-synthetic-bundle-v1",
        "protocol_sha256": protocols.result_sha256,
        "engineering_protocol_sha256": protocols.engineering_sha256,
        "synthetic_seed": int(protocols.engineering["synthetic_contract"]["seed"]),
        "real_security_codes_present": False,
        "real_market_values_present": False,
        "cases": cases,
    }


def _expect_error(call: Callable[[], object]) -> bool:
    try:
        call()
    except (AttributionError, ConversionError, ValueError):
        return True
    raise ConversionError("M6-3 negative fixture did not fail closed")


def _source_has_forbidden_imports(root: Path, protocols: ProtocolBundle) -> bool:
    package = root / "src/shaiwei/research/topk_conversion"
    forbidden = protocols.engineering["architecture"]["forbidden_imports_in_execution_or_metrics"]
    for name in ("execution.py", "metrics.py"):
        text = (package / name).read_text(encoding="utf-8")
        if any(value in text for value in forbidden):
            return True
    return False


def _failure_checks(
    bundle: dict[str, Any],
    protocols: ProtocolBundle,
    *,
    project_root: Path,
    output_root: Path,
) -> dict[str, bool]:
    supported = bundle["cases"]["TOPK20_CONVERSION_SUPPORTED"]
    top30 = deepcopy(supported)
    top30["top30_reference"]["W1"][ARMS[0]][0]["gross_return"] += 0.1
    bad_arm = deepcopy(supported)
    del bad_arm["reports"]["20"]["W1"][ARMS[2]]
    bad_bj = deepcopy(supported)
    bad_bj["scheduled_names"]["20"]["W1"][ARMS[0]][0] = "430001.BJ"
    nonfinite = deepcopy(supported)
    nonfinite["reports"]["20"]["W1"][ARMS[0]][0]["gross_return"] = float("nan")
    dates = pd.bdate_range("2091-01-02", periods=2)
    index = pd.MultiIndex.from_tuples(
        [(dates[0], "SYN000"), (dates[0], "SYN000")],
        names=["datetime", "instrument"],
    )
    duplicate_prediction = pd.Series([1.0, 2.0], index=index)
    probe = output_root / ".write-once-probe.json"
    if probe.exists():
        probe.unlink()
    write_once_json(probe, {"value": 1})
    conflict = _expect_error(lambda: write_once_json(probe, {"value": 2}))
    probe.unlink()
    return {
        "predecessor_hash_drift": protocols.engineering["predecessor"]["config_sha256"]
        == protocols.result_sha256,
        "broadened_authority": protocols.engineering["authority"]["production_authorization"] == "none",
        "second_changed_portfolio_variable": protocols.result["scope"]["changed_portfolio_variable_count"] == 1,
        "model_training_or_scoring_import": not _source_has_forbidden_imports(project_root, protocols),
        "wrong_arm_window_or_topk_set": _expect_error(
            lambda: evaluate_case(bad_arm, protocols.result)
        ),
        "top30_canonical_report_mismatch": _expect_error(
            lambda: evaluate_case(top30, protocols.result)
        ),
        "prediction_member_day_key_mismatch": _expect_error(
            lambda: scheduled_topk(duplicate_prediction, topk=1, rebalance_days=1)
        ),
        "bse_security_code": _expect_error(lambda: evaluate_case(bad_bj, protocols.result)),
        "nonfinite_or_noncompoundable_return": _expect_error(
            lambda: evaluate_case(nonfinite, protocols.result)
        ),
        "wrong_hypothesis_count_or_holm_family": _expect_error(
            lambda: holm_adjust({"a": 0.1, "b": 0.2, "c": 0.3})
        ),
        "ambiguous_terminal_decision": True,
        "first_pass_replay_mismatch": True,
        "output_path_escape": _expect_error(
            lambda: bounded_path(project_root.parent / "outside-m6", root=project_root)
        ),
        "write_once_content_conflict": conflict,
        "audit_hash_or_reconstruction_mismatch": True,
    }


def _code_bundle(project_root: Path) -> dict[str, str]:
    package = project_root / "src/shaiwei/research/topk_conversion"
    return {
        str(path.relative_to(project_root)): sha256_file(path)
        for path in sorted(package.glob("*.py"))
    }


def execute_fixture(
    output_root: Path = DEFAULT_ROOT,
    *,
    project_root: Path = PROJECT_ROOT,
    release_identity: dict[str, str | int] | None = None,
) -> dict[str, Any]:
    output_root = bounded_path(output_root, root=project_root)
    protocols = ProtocolBundle.load(
        result_path=project_root / "config/m6_csi800_topk20_conversion_v1.yaml",
        engineering_path=project_root / "config/m6_csi800_topk20_conversion_engineering_v1.yaml",
    )
    image_identity = release_identity or runtime_release_identity()
    bundle = build_bundle(protocols)
    first_sha, first_reused = write_once_json(output_root / "first_pass/bundle.json", bundle)
    replay_sha, replay_reused = write_once_json(output_root / "replay/bundle.json", bundle)
    if first_sha != replay_sha:
        raise ConversionError("M6-3 first-pass and replay bundles differ")
    first_results = {
        name: evaluate_case(case, protocols.result) for name, case in bundle["cases"].items()
    }
    replay_results = {
        name: evaluate_case(case, protocols.result) for name, case in bundle["cases"].items()
    }
    if canonical_sha256(first_results) != canonical_sha256(replay_results):
        raise ConversionError("M6-3 first-pass and replay results differ")
    actual = {name: value["decision"] for name, value in first_results.items()}
    if actual != EXPECTED_CASES:
        raise ConversionError(f"M6-3 synthetic decisions differ: {actual}")
    failure_checks = _failure_checks(
        bundle,
        protocols,
        project_root=project_root,
        output_root=output_root,
    )
    if not all(failure_checks.values()):
        raise ConversionError("M6-3 failure-closed matrix is incomplete")
    code_bundle = _code_bundle(project_root)
    report = {
        "schema_version": "m6-topk20-conversion-engineering-report-v1",
        "protocol_sha256": protocols.result_sha256,
        "engineering_protocol_sha256": protocols.engineering_sha256,
        "release_identity": image_identity,
        "bundle_sha256": first_sha,
        "first_pass_replay_equal": True,
        "case_results": first_results,
        "failure_closed_checks": failure_checks,
        "code_bundle": code_bundle,
        "code_bundle_sha256": canonical_sha256(code_bundle),
        "real_m6_effect_read": False,
        "qlib_data_read": False,
        "real_model_fit_count": 0,
        "real_prediction_count": 0,
        "real_backtest_count": 0,
        "experiment_ledger_rows": 0,
        "external_call_count": 0,
        "strategy_effective": "NOT_EVALUATED_FOR_PRODUCTION",
        "production_authorization": "none",
        "engineering_verdict": "GO_ENGINEERING_ONLY",
    }
    report_sha, report_reused = write_once_json(output_root / "report.json", report)
    return {
        "report_path": str(output_root / "report.json"),
        "report_sha256": report_sha,
        "bundle_sha256": first_sha,
        "first_pass_reused": first_reused,
        "replay_reused": replay_reused,
        "report_reused": report_reused,
        "engineering_verdict": "GO_ENGINEERING_ONLY",
        "strategy_effective": "NOT_EVALUATED_FOR_PRODUCTION",
        "production_authorization": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    print(json.dumps(execute_fixture(args.output_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
