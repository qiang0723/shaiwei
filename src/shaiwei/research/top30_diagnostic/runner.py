"""One-shot, Top20-blind runner for the M6 Top30 diagnostic matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from shaiwei.research.model_attribution.contract import ProtocolBundle as M6ProtocolBundle
from shaiwei.research.model_attribution.contract import sha256_file
from shaiwei.research.model_attribution.effect_data import initialize_effect_qlib
from shaiwei.research.model_attribution.effect_execution import (
    backtest_signal as original_backtest_signal,
)
from shaiwei.research.model_attribution.effect_execution import scheduled_top30
from shaiwei.research.top30_diagnostic.contract import (
    Approval,
    Protocol,
    ReleaseScope,
    mapping,
    runtime_identity,
    tree_identity,
    write_once_document,
)
from shaiwei.research.top30_diagnostic.exact import (
    DiagnosticError,
    canonical_sha256,
    exact_rows,
)


FrameBacktester = Callable[[pd.Series], pd.DataFrame]
IdentityVerifier = Callable[[Path, Path, Path, Protocol, ReleaseScope], dict[str, Any]]
RuntimeVerifier = Callable[[ReleaseScope, str], dict[str, str]]


def _prediction(path: Path) -> pd.Series:
    frame = pd.read_parquet(path)
    if list(frame.columns) != ["datetime", "instrument", "score"]:
        raise DiagnosticError("Top30 diagnostic prediction schema differs")
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    frame["instrument"] = frame["instrument"].astype(str)
    value = frame.set_index(["datetime", "instrument"])["score"].sort_index()
    value = pd.to_numeric(value, errors="raise").astype(float)
    codes = value.index.get_level_values("instrument").astype(str)
    if value.empty or value.index.has_duplicates or not np.isfinite(value.to_numpy()).all():
        raise DiagnosticError("Top30 diagnostic prediction is empty, duplicated, or nonfinite")
    if codes.str.startswith("BJ").any() or codes.str.endswith(".BJ").any():
        raise DiagnosticError("Top30 diagnostic prediction contains .BJ")
    return value


def _report(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    expected = ["datetime", "gross_return", "benchmark_return", "recorded_cost", "turnover"]
    if list(frame.columns) != expected:
        raise DiagnosticError("Top30 diagnostic canonical report schema differs")
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    result = frame.set_index("datetime").sort_index()
    for column in result:
        result[column] = pd.to_numeric(result[column], errors="raise").astype(float)
    return result


def verify_inputs(
    provider_root: Path,
    m6_effect_root: Path,
    failed_effect_root: Path,
    protocol: Protocol,
    release: ReleaseScope,
) -> dict[str, Any]:
    expected = release.scope["inputs"]
    metadata = M6ProtocolBundle.load().verify_metadata_inputs(
        provider_root / "_shaiwei_manifest.json", provider_root / "calendars/day.txt"
    )
    qlib = {
        "qlib_manifest_sha256": metadata["qlib_manifest_sha256"],
        "qlib_tree_sha256": metadata["qlib_tree_sha256"],
        "qlib_file_count": metadata["qlib_file_count"],
        "calendar_sha256": sha256_file(provider_root / "calendars/day.txt"),
        "calendar_row_count": metadata["calendar_row_count"],
    }
    if qlib != expected["qlib"]:
        raise DiagnosticError("Top30 diagnostic Qlib identity differs")
    sealed_identity = tree_identity(m6_effect_root)
    if sealed_identity != expected["sealed_m6_effect"]:
        raise DiagnosticError("Top30 diagnostic sealed M6 effect identity differs")
    failed_identity = tree_identity(failed_effect_root)
    if failed_identity != expected["failed_m6_3c_effect"]:
        raise DiagnosticError("Top30 diagnostic failed release evidence differs")
    case = protocol.document["frozen_diagnostic_case"]
    for key in ("prediction", "canonical_report", "canonical_schedule"):
        row = case[key]
        path = m6_effect_root / Path(row["path"]).relative_to(
            "data/research/m6_csi800_model_attribution_v1/effect"
        )
        if sha256_file(path) != row["sha256"] or path.stat().st_size != row["byte_count"]:
            raise DiagnosticError(f"Top30 diagnostic {key} identity differs")
    failure = mapping(failed_effect_root / "failure.json")
    if (
        failure.get("top20_effect_started") is not False
        or failure.get("portfolio_attempts_consumed") != 0
        or failure.get("same_release_retry_authorized") is not False
    ):
        raise DiagnosticError("Top30 diagnostic predecessor failure state differs")
    return {"qlib": qlib, "sealed_m6_effect": sealed_identity, "failed_m6_3c_effect": failed_identity}


def _require_empty(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise DiagnosticError("Top30 diagnostic output exists before the one-shot run")


def _case_paths(root: Path, protocol: Protocol) -> tuple[Path, Path, Path]:
    prefix = Path("data/research/m6_csi800_model_attribution_v1/effect")
    case = protocol.document["frozen_diagnostic_case"]
    return tuple(
        root / Path(case[key]["path"]).relative_to(prefix)
        for key in ("prediction", "canonical_report", "canonical_schedule")
    )


def _original_backtester(protocol: Protocol) -> FrameBacktester:
    case = protocol.document["frozen_diagnostic_case"]
    m6 = M6ProtocolBundle.load().result

    def execute(signal: pd.Series) -> pd.DataFrame:
        return original_backtest_signal(
            signal, start=str(case["start"]), end=str(case["end"]), protocol=m6
        )

    return execute


def _new_backtester(protocol: Protocol) -> FrameBacktester:
    from shaiwei.research.topk_conversion.contract import ProtocolBundle
    from shaiwei.research.topk_conversion.execution import backtest_signal

    case = protocol.document["frozen_diagnostic_case"]
    conversion = ProtocolBundle.load().result

    def execute(signal: pd.Series) -> pd.DataFrame:
        return backtest_signal(
            signal,
            start=str(case["start"]),
            end=str(case["end"]),
            protocol=conversion,
            topk=30,
        )

    return execute


def _run_adapter(signal: pd.Series, backtester: FrameBacktester) -> dict[str, Any]:
    first = exact_rows(backtester(signal))
    second = exact_rows(backtester(signal))
    return {
        "replay_1": {"rows": first, "rows_sha256": canonical_sha256(first)},
        "replay_2": {"rows": second, "rows_sha256": canonical_sha256(second)},
        "internal_exact_equal": first == second,
    }


def run(
    *,
    lane: str,
    protocol_path: Path,
    release_path: Path,
    approval_path: Path,
    provider_root: Path,
    m6_effect_root: Path,
    failed_effect_root: Path,
    output_root: Path,
    identity_verifier: IdentityVerifier = verify_inputs,
    runtime_verifier: RuntimeVerifier = runtime_identity,
    initializer: Callable[[Path], None] = initialize_effect_qlib,
    original_factory: Callable[[Protocol], FrameBacktester] = _original_backtester,
    new_factory: Callable[[Protocol], FrameBacktester] = _new_backtester,
) -> dict[str, Any]:
    if lane not in {"original", "current"}:
        raise DiagnosticError("Top30 diagnostic lane differs")
    protocol = Protocol.load(protocol_path)
    release = ReleaseScope.load(release_path, protocol)
    approval = Approval.load(approval_path, release)
    runtime = runtime_verifier(release, lane)
    inputs = identity_verifier(
        provider_root, m6_effect_root, failed_effect_root, protocol, release
    )
    _require_empty(output_root)
    write_once_document(
        output_root / "authorization.json",
        {
            "schema_version": "m6-top30-diagnostic-run-authorization-v1",
            "diagnostic_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "action": approval.document["action"],
            "lane": lane,
            "top20_authorized": False,
            "production_authorization": "none",
        },
    )
    started = False
    try:
        count = 2 if lane == "original" else 4
        write_once_document(
            output_root / "diagnostic_started.json",
            {
                "diagnostic_scope_sha256": release.sha256,
                "lane": lane,
                "top30_backtest_count": count,
                "top20_backtest_count": 0,
                "same_release_retry_authorized": False,
            },
        )
        started = True
        prediction_path, report_path, schedule_path = _case_paths(m6_effect_root, protocol)
        signal = _prediction(prediction_path)
        canonical = exact_rows(_report(report_path))
        schedule = scheduled_top30(signal, rebalance_days=10)
        if schedule != mapping(schedule_path):
            raise DiagnosticError("Top30 diagnostic schedule differs")
        initializer(provider_root)
        adapters = {"original_execution": _run_adapter(signal, original_factory(protocol))}
        if lane == "current":
            adapters["new_execution"] = _run_adapter(signal, new_factory(protocol))
        bundle = {
            "schema_version": "m6-top30-compatibility-diagnostic-lane-bundle-v1",
            "diagnostic_scope_sha256": release.sha256,
            "approval_sha256": approval.sha256,
            "lane": lane,
            "runtime_identity": runtime,
            "inputs": inputs,
            "canonical_rows": canonical,
            "canonical_rows_sha256": canonical_sha256(canonical),
            "canonical_schedule_sha256": canonical_sha256(schedule),
            "adapters": adapters,
            "top30_backtest_count": count,
            "top20_backtest_count": 0,
            "research_attempt_increment": 0,
            "strategy_effective": "NOT_EVALUATED_FOR_PRODUCTION",
            "production_authorization": "none",
        }
        digest, reused = write_once_document(output_root / "bundle.json", bundle)
        return {"bundle_sha256": digest, "reused": reused, "lane": lane}
    except Exception as error:
        write_once_document(
            output_root / "failure.json",
            {
                "schema_version": "m6-top30-compatibility-diagnostic-failure-v1",
                "diagnostic_scope_sha256": release.sha256,
                "approval_sha256": approval.sha256,
                "lane": lane,
                "diagnostic_started": started,
                "same_release_retry_authorized": False,
                "top20_effect_started": False,
                "portfolio_attempts_consumed": 0,
                "error_type": type(error).__name__,
                "error_message": str(error)[:500],
                "strategy_effective": "NOT_EVALUATED_FOR_PRODUCTION",
                "production_authorization": "none",
            },
        )
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", choices=("original", "current"), required=True)
    parser.add_argument("--protocol", dest="protocol_path", type=Path, required=True)
    parser.add_argument("--release", dest="release_path", type=Path, required=True)
    parser.add_argument("--approval", dest="approval_path", type=Path, required=True)
    parser.add_argument("--provider-root", type=Path, required=True)
    parser.add_argument("--m6-effect-root", type=Path, required=True)
    parser.add_argument("--failed-effect-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(**vars(args)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
