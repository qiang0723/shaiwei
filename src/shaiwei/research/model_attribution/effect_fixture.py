"""Pure synthetic M6-2 runner and independent-auditor release fixture."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
from typing import Any

import numpy as np
import pandas as pd

from shaiwei.provenance import code_snapshot_sha256, git_head
from shaiwei.research.model_attribution.contract import canonical_sha256
from shaiwei.research.model_attribution.effect_artifacts import save_pass
from shaiwei.research.model_attribution.effect_audit import audit
from shaiwei.research.model_attribution.effect_contract import (
    APPROVAL_ACTION,
    EffectProtocol,
    write_once_document,
)
from shaiwei.research.model_attribution.effect_data import WindowModelOutput
from shaiwei.research.model_attribution.effect_execution import (
    scheduled_top30,
    score_overlap_diagnostics,
)
from shaiwei.research.model_attribution.effect_metrics import evaluate_effect
from shaiwei.research.model_attribution.effect_release import build_release_document
from shaiwei.research.model_attribution.effect_run import run
from shaiwei.research.model_attribution.effect_schema import ARMS, WINDOWS
from shaiwei.research.model_attribution.scoring import rank_blend


def _scores() -> dict[str, tuple[pd.Series, pd.Series, pd.Series, pd.Series]]:
    rng = np.random.default_rng(20260806)
    starts = ("2019-01-02", "2020-01-02", "2021-01-04", "2022-01-04", "2023-01-03", "2024-01-02")
    names = [f"SYN{number:03d}" for number in range(40)]
    output = {}
    for number, start in enumerate(starts, start=1):
        index = pd.MultiIndex.from_product(
            [pd.bdate_range(start, periods=210), names],
            names=["datetime", "instrument"],
        )
        latent = rng.normal(size=len(index))
        labels = pd.Series(latent + rng.normal(scale=0.55, size=len(index)), index=index, name="label")
        control = pd.Series(0.45 * latent + rng.normal(size=len(index)), index=index, name="score")
        ridge = pd.Series(0.75 * latent + rng.normal(scale=0.65, size=len(index)), index=index, name="score")
        output[f"W{number}"] = (control, ridge, rank_blend(control, ridge), labels)
    return output


def _report(dates: pd.DatetimeIndex, *, shift: float, phase: float) -> pd.DataFrame:
    step = np.arange(len(dates), dtype=float)
    gross = 0.00012 + shift + 0.0015 * np.sin(step / 7.0 + phase)
    benchmark = 0.00008 + 0.0008 * np.sin(step / 9.0)
    return pd.DataFrame(
        {
            "gross_return": gross,
            "benchmark_return": benchmark,
            "recorded_cost": np.full(len(dates), 0.00003),
            "turnover": np.full(len(dates), 0.02 + abs(shift)),
        },
        index=dates,
    )


def _evidence(
    protocol: EffectProtocol,
) -> tuple[
    dict[str, WindowModelOutput],
    dict[str, dict[str, pd.DataFrame]],
    dict[str, pd.DataFrame],
    dict[str, dict[str, dict[str, list[str]]]],
    dict[str, Any],
]:
    scores = _scores()
    outputs: dict[str, WindowModelOutput] = {}
    reports: dict[str, dict[str, pd.DataFrame]] = {}
    top30: dict[str, dict[str, dict[str, list[str]]]] = {}
    diagnostics: dict[str, Any] = {}
    for window in WINDOWS:
        control, ridge, blend, labels = scores[window]
        predictions = dict(zip(ARMS, (control, ridge, blend), strict=True))
        dates = pd.DatetimeIndex(sorted(control.index.get_level_values(0).unique()))
        reports[window] = {
            ARMS[0]: _report(dates, shift=0.0, phase=0.0),
            ARMS[1]: _report(dates, shift=0.00012, phase=0.2),
            ARMS[2]: _report(dates, shift=0.00008, phase=0.1),
        }
        outputs[window] = WindowModelOutput(
            window=window,
            segments={
                "train": ("synthetic", "synthetic"),
                "valid": ("synthetic", "synthetic"),
                "test": ("synthetic", "synthetic"),
            },
            mature_predictions=predictions,
            test_predictions=predictions,
            mature_labels=labels,
            stress_predictions={},
            model_artifacts={
                "clean_lgbm_control_v1.txt": f"synthetic-{window}-lgbm\n".encode(),
                "ridge_alpha1_v1.json": f'{{"synthetic":"{window}-ridge"}}\n'.encode(),
            },
        )
        top30[window] = {arm: scheduled_top30(predictions[arm]) for arm in ARMS}
        diagnostics[window] = score_overlap_diagnostics(predictions)
    stress_index = pd.MultiIndex.from_product(
        [pd.bdate_range("2026-01-02", periods=120), [f"SYN{number:03d}" for number in range(40)]],
        names=["datetime", "instrument"],
    )
    stress_control = pd.Series(np.linspace(-1, 1, len(stress_index)), index=stress_index, name="score")
    stress_predictions = {
        ARMS[0]: stress_control,
        ARMS[1]: stress_control + 0.01,
        ARMS[2]: stress_control + 0.005,
    }
    outputs["W6"] = WindowModelOutput(**{**outputs["W6"].__dict__, "stress_predictions": stress_predictions})
    stress_dates = pd.DatetimeIndex(sorted(stress_index.get_level_values(0).unique()))
    stress_reports = {
        ARMS[0]: _report(stress_dates, shift=0.0, phase=0.0),
        ARMS[1]: _report(stress_dates, shift=0.00012, phase=0.2),
        ARMS[2]: _report(stress_dates, shift=0.00008, phase=0.1),
    }
    effect = evaluate_effect(
        {window: outputs[window].mature_predictions for window in WINDOWS},
        {window: outputs[window].mature_labels for window in WINDOWS},
        reports,
        stress_reports,
        protocol.result,
    )
    summary = {
        "schema_version": "m6-model-attribution-pass-summary-v1",
        "protocol_sha256": protocol.sha256,
        "result_protocol_sha256": protocol.result_sha256,
        "model_fit_count": 12,
        "blend_model_fit_count": 0,
        "window_count": 6,
        "arm_count": 3,
        "score_diagnostics": diagnostics,
        "effect": effect,
        "strategy_effective": "NOT_YET_AUDITED",
        "production_authorization": "none",
    }
    return outputs, reports, stress_reports, top30, summary


def fixture_pass(root: Path, protocol: EffectProtocol) -> dict[str, Any]:
    outputs, reports, stress, top30, summary = _evidence(protocol)
    saved = save_pass(root, outputs, reports, stress, top30, summary)
    return {
        **saved,
        "summary_sha256": canonical_sha256(summary),
        "decision": summary["effect"]["inference"]["decision"],
    }


def execute_fixture(output_root: Path) -> dict[str, Any]:
    protocol = EffectProtocol.load()
    release_manifest = Path(os.environ["SHAIWEI_RELEASE_MANIFEST"])
    machine = {"aarch64": "arm64", "x86_64": "amd64"}.get(platform.machine(), platform.machine())
    release_document = build_release_document(
        protocol=protocol,
        created_at="2026-08-06T00:00:00+00:00",
        implementation_git_commit=git_head(),
        origin_main_commit=git_head(),
        code_snapshot=code_snapshot_sha256(),
        image_id="sha256:" + "1" * 64,
        image_platform=f"linux/{machine}",
        image_git_commit=git_head(),
        image_release_manifest_path=release_manifest,
    )
    release_path = output_root / "control" / "release.json"
    write_once_document(release_path, release_document)
    approval = {
        "schema_version": "m6-model-attribution-approval-v1",
        "release_scope_sha256": release_document["release_scope_sha256"],
        "action": APPROVAL_ACTION,
        "approved_at": "2026-08-06T00:01:00+00:00",
        "consumed": False,
        "real_qlib_feature_or_price_read_authorized": True,
        "real_label_or_effect_read_authorized": True,
        "real_model_fit_authorized": True,
        "real_prediction_authorized": True,
        "real_backtest_authorized": True,
        "formal_effect_output_write_authorized": True,
        "independent_audit_authorized": True,
        "experiment_ledger_write_authorized": False,
        "external_network_authorized": False,
        "env_or_secret_read_authorized": False,
        "production_authorization": "none",
    }
    approval_path = output_root / "control" / "approval.json"
    write_once_document(approval_path, approval)
    run_result = run(
        release_path=release_path,
        approval_path=approval_path,
        provider_root=output_root / "no-real-provider",
        output_root=output_root / "effect",
        pass_runner=fixture_pass,
        initializer=lambda _: None,
        input_verifier=lambda _root, _protocol, release: dict(release.scope["inputs"]),
    )
    audit_result = audit(
        release_path=release_path,
        approval_path=approval_path,
        effect_root=output_root / "effect",
        audit_root=output_root / "audit",
    )
    return {"runner": run_result, "auditor": audit_result, "real_data_read": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute_fixture(args.output_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
