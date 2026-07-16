"""Assemble the frozen G0 decision from matching immutable evidence reports."""

import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median

import pandas as pd

from shaiwei.backtest.metrics import g0_backtest_summary
from shaiwei.config import PROJECT_ROOT, Settings, load
from shaiwei.ledger import EXPERIMENTS, ingest_snapshot_sha256, verify_ingest_batches
from shaiwei.provenance import code_snapshot_sha256
from shaiwei.shadow.manifest import verify_signal_manifest
from shaiwei.transform.qlib_bin import QLIB_MANIFEST, verify_qlib_tree_manifest


def _latest_matching(directory: Path, pattern: str, data_hash: str, code_hash: str) -> tuple[Path, dict]:
    for path in sorted(directory.glob(pattern), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("data_snapshot_sha256") == data_hash and payload.get("code_snapshot_sha256") == code_hash:
            return path, payload
    raise FileNotFoundError(f"no matching {pattern} report in {directory}")


def _finite(value: object, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a finite number") from error
    if not math.isfinite(number) or (positive and number <= 0):
        qualifier = "positive finite" if positive else "finite"
        raise ValueError(f"{name} must be {qualifier}")
    return number


def validate_sentinel_report(report: dict, *, environment: str) -> dict[str, object]:
    results = report.get("results")
    if not isinstance(results, list) or len(results) != 10:
        raise ValueError("sentinel report must contain exactly S1-S10")
    names = [str(result.get("sentinel")) for result in results if isinstance(result, dict)]
    required_names = [f"S{number}" for number in range(1, 11)]
    if names != required_names:
        raise ValueError(f"sentinel report order/names differ from frozen S1-S10: {names}")
    by_name = {result["sentinel"]: result for result in results}
    for name, result in by_name.items():
        status = result.get("status")
        if status not in {"PASS", "FAIL", "NOT_APPLICABLE"}:
            raise ValueError(f"{name} has invalid status: {status!r}")
        anomalies = result.get("anomalies", [])
        if not isinstance(anomalies, list):
            raise ValueError(f"{name} anomalies must be a list")
        if status in {"PASS", "NOT_APPLICABLE"} and anomalies:
            raise ValueError(f"{name} claims {status} but still contains anomalies")
    computed_failures = [name for name in required_names if by_name[name]["status"] == "FAIL"]
    if report.get("required_failures") != computed_failures:
        raise ValueError("sentinel required_failures does not match S1-S10 detail")
    required_pass = all(by_name[f"S{number}"]["status"] == "PASS" for number in range(1, 10))
    s10_status = by_name["S10"]["status"]
    s10_pass = s10_status == "PASS" or (environment != "prod" and s10_status == "NOT_APPLICABLE")
    return {
        "condition_pass": required_pass and s10_pass and not computed_failures,
        "required_failures": computed_failures,
        "s4_units": by_name["S4"],
    }


def validate_baseline_report(report: dict, settings: Settings) -> dict[str, object]:
    windows = report.get("windows")
    if not isinstance(windows, list):
        raise ValueError("baseline report windows must be a list")
    expected_names = [window.name for window in settings.evaluation.g0_windows]
    actual_names = [str(window.get("window")) for window in windows if isinstance(window, dict)]
    if actual_names != expected_names:
        raise ValueError(f"baseline windows differ from preregistration: {actual_names}")
    expected_scenarios = {f"{multiplier:g}" for multiplier in settings.backtest.cost_scenarios}
    if "1.5" not in expected_scenarios:
        raise ValueError("frozen G0 requires the 1.5x cost scenario")
    for window in windows:
        if int(window.get("prediction_rows", 0)) <= 0:
            raise ValueError(f"{window['window']} has no predictions")
        scenarios = window.get("cost_scenarios")
        if not isinstance(scenarios, dict) or set(scenarios) != expected_scenarios:
            raise ValueError(f"{window['window']} cost scenarios differ from frozen configuration")
        for scenario, metrics in scenarios.items():
            if not isinstance(metrics, dict):
                raise ValueError(f"{window['window']} scenario {scenario} has no metrics")
            for metric in ("strategy_return", "benchmark_return", "cumulative_excess", "reported_cost_sum"):
                _finite(metrics.get(metric), f"{window['window']}.{scenario}.{metric}")
    recomputed = g0_backtest_summary(windows)
    if report.get("g0_backtest") != recomputed:
        raise ValueError("declared g0_backtest does not equal the result recomputed from six windows")
    return recomputed


def validate_alphagen_report(report: dict) -> dict[str, object]:
    summary = report.get("summary")
    candidates = report.get("candidates")
    if not isinstance(summary, dict) or not isinstance(candidates, dict) or not candidates:
        raise ValueError("AlphaGen benchmark must contain at least one evaluated candidate")
    if int(summary.get("candidate_count", -1)) != len(candidates):
        raise ValueError("AlphaGen candidate_count does not match candidate detail")
    failed_count = sum(bool(result.get("error")) for result in candidates.values() if isinstance(result, dict))
    if failed_count != int(summary.get("failed_candidate_count", -1)):
        raise ValueError("AlphaGen failed_candidate_count does not match candidate detail")
    elapsed = _finite(summary.get("elapsed_seconds"), "AlphaGen elapsed_seconds", positive=True)
    setup_elapsed = _finite(summary.get("setup_elapsed_seconds"), "AlphaGen setup_elapsed_seconds", positive=True)
    evolution_elapsed = _finite(
        summary.get("evolution_elapsed_seconds"), "AlphaGen evolution_elapsed_seconds", positive=True
    )
    peak_memory = _finite(summary.get("peak_memory_bytes"), "AlphaGen peak_memory_bytes", positive=True)
    if elapsed < setup_elapsed + evolution_elapsed:
        raise ValueError("AlphaGen total elapsed time is smaller than setup plus evolution")
    if int(summary.get("input_label_rows", 0)) <= 0 or int(summary.get("input_exposure_rows", 0)) <= 0:
        raise ValueError("AlphaGen benchmark input row counts must be positive")
    values = []
    minimum_daily_ic = int(summary.get("min_daily_ic_observations", 0))
    if minimum_daily_ic < 60:
        raise ValueError("AlphaGen benchmark lacks a credible minimum daily IC observation gate")
    for expression, result in candidates.items():
        if not isinstance(result, dict):
            raise ValueError(f"AlphaGen candidate {expression!r} result must be an object")
        if not result.get("error") and int(result.get("daily_ic_count", 0)) < minimum_daily_ic:
            raise ValueError(f"AlphaGen candidate {expression!r} bypassed the minimum daily IC gate")
        values.append(_finite(result.get("rank_ic"), f"AlphaGen candidate {expression!r} rank_ic"))
    rank_ic = summary.get("rank_ic")
    if not isinstance(rank_ic, dict):
        raise ValueError("AlphaGen summary is missing rank_ic distribution")
    expected_rank_ic = {"min": min(values), "median": median(values), "max": max(values)}
    for key, expected in expected_rank_ic.items():
        actual = _finite(rank_ic.get(key), f"AlphaGen rank_ic.{key}")
        if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError(f"AlphaGen rank_ic.{key} does not match candidate detail")
    if not str(summary.get("decision", "")).strip():
        raise ValueError("AlphaGen benchmark decision is empty")
    return {**summary, "elapsed_seconds": elapsed, "peak_memory_bytes": int(peak_memory)}


def validate_qlib_cache(root: Path, *, data_hash: str, code_hash: str, settings: Settings) -> dict[str, object]:
    manifest_path = Path(root) / QLIB_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("data_snapshot_sha256") != data_hash or manifest.get("code_snapshot_sha256") != code_hash:
        raise ValueError("qlib manifest does not match the current data/code snapshots")
    required_files = [
        Path(root) / "calendars/day.txt",
        Path(root) / "instruments/all.txt",
        Path(root) / f"instruments/{settings.baseline.instrument}.txt",
        Path(root) / f"instruments/{settings.alphagen_benchmark.instrument}.txt",
    ]
    if missing := [str(path) for path in required_files if not path.is_file() or path.stat().st_size == 0]:
        raise ValueError(f"qlib cache required files are missing/empty: {missing}")
    features = Path(root) / "features"
    if not features.is_dir() or not any(path.is_dir() for path in features.iterdir()):
        raise ValueError("qlib cache contains no instrument feature directories")
    integrity = verify_qlib_tree_manifest(root, data_hash=data_hash, code_hash=code_hash)
    return {"manifest_path": str(manifest_path), **integrity}


def validate_shadow_manifest(
    path: Path,
    *,
    data_hash: str,
    code_hash: str,
    expected_topk: int,
) -> tuple[dict[str, object], dict]:
    signal_hash = verify_signal_manifest(path)
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1:
        raise ValueError("unsupported shadow manifest schema")
    if document.get("data_snapshot_sha256") != data_hash or document.get("code_snapshot_sha256") != code_hash:
        raise ValueError("shadow manifest does not match the current data/code snapshots")
    if int(document.get("topk", 0)) != expected_topk:
        raise ValueError("shadow topk differs from frozen configuration")
    orders = document.get("orders")
    if not isinstance(orders, list) or len(orders) != expected_topk:
        raise ValueError("shadow order count does not equal topk")
    ranks = [order.get("rank") for order in orders if isinstance(order, dict)]
    instruments = [str(order.get("instrument", "")) for order in orders if isinstance(order, dict)]
    if ranks != list(range(1, expected_topk + 1)):
        raise ValueError("shadow ranks are not contiguous from one")
    if any(not instrument for instrument in instruments) or len(set(instruments)) != expected_topk:
        raise ValueError("shadow instruments must be non-empty and unique")
    weights = [_finite(order.get("target_weight"), "shadow target_weight", positive=True) for order in orders]
    for order in orders:
        _finite(order.get("score"), "shadow score")
    if not math.isclose(sum(weights), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("shadow target weights do not sum to one")
    data_complete_at = datetime.fromisoformat(str(document.get("data_complete_at")))
    generated_at = datetime.fromisoformat(str(document.get("generated_at")))
    date.fromisoformat(str(document.get("signal_date")))
    if data_complete_at.tzinfo is None or generated_at.tzinfo is None or generated_at < data_complete_at:
        raise ValueError("shadow data clock is invalid")
    return {
        "manifest_path": str(path),
        "signal_sha256": signal_hash,
        "topk": expected_topk,
        "order_count": len(orders),
    }, document


def _json_cell(value: object) -> dict:
    try:
        decoded = json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _has_result(rows: pd.DataFrame, expected: dict, *, feature: str | None = None) -> bool:
    if feature is not None:
        rows = rows.loc[rows["feature_or_formula"].eq(feature)]
    return any(_json_cell(value) == expected for value in rows["result_json"])


def main() -> int:
    settings = load()
    data_hash = ingest_snapshot_sha256()
    code_hash = code_snapshot_sha256()
    missing: list[str] = []
    evidence: dict[str, object] = {}
    try:
        integrity = verify_ingest_batches()
    except (FileNotFoundError, OSError, ValueError) as error:
        integrity = {"status": "FAIL", "error": f"{type(error).__name__}: {error}"}
        missing.append("immutable ingest batch integrity verification failed")
    else:
        integrity = {"status": "PASS", **integrity}
        if integrity["batch_count"] == 0:
            missing.append("ingest ledger has no committed data batches")
    evidence["ingest_integrity"] = integrity

    reports: dict[str, tuple[Path, dict]] = {}
    for name, directory, pattern in (
        ("sentinel", PROJECT_ROOT / "logs/sentinels", "*.json"),
        ("baseline", PROJECT_ROOT / "logs/backtest", "stage0_baseline_*.json"),
        ("alphagen", PROJECT_ROOT / "logs/benchmark", "alphagen_cpu_*.json"),
    ):
        try:
            reports[name] = _latest_matching(directory, pattern, data_hash, code_hash)
        except FileNotFoundError as error:
            missing.append(str(error))

    if "sentinel" in reports:
        path, sentinel = reports["sentinel"]
        try:
            validated = validate_sentinel_report(sentinel, environment=settings.runtime.environment)
        except (KeyError, TypeError, ValueError) as error:
            evidence["sentinels"] = {"report_path": str(path), "validation_status": "FAIL", "error": str(error)}
            missing.append("matching sentinel report failed semantic validation")
        else:
            evidence["sentinels"] = {"report_path": str(path), "validation_status": "PASS", **validated}

    if "baseline" in reports:
        path, baseline = reports["baseline"]
        try:
            validated = validate_baseline_report(baseline, settings)
        except (KeyError, TypeError, ValueError) as error:
            evidence["backtest"] = {"report_path": str(path), "validation_status": "FAIL", "error": str(error)}
            missing.append("matching baseline report failed semantic validation")
        else:
            evidence["backtest"] = {"report_path": str(path), "validation_status": "PASS", **validated}

    if "alphagen" in reports:
        path, alphagen = reports["alphagen"]
        try:
            validated = validate_alphagen_report(alphagen)
        except (KeyError, TypeError, ValueError) as error:
            evidence["alphagen_cpu"] = {"report_path": str(path), "validation_status": "FAIL", "error": str(error)}
            missing.append("matching AlphaGen report failed semantic validation")
        else:
            evidence["alphagen_cpu"] = {"report_path": str(path), "validation_status": "PASS", **validated}

    try:
        qlib_evidence = validate_qlib_cache(
            settings.runtime.data_root / "qlib_bin",
            data_hash=data_hash,
            code_hash=code_hash,
            settings=settings,
        )
    except (FileNotFoundError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        evidence["qlib_cache"] = {"validation_status": "FAIL", "error": f"{type(error).__name__}: {error}"}
        missing.append("qlib cache is missing, corrupt, or not bound to the current snapshots")
    else:
        evidence["qlib_cache"] = {"validation_status": "PASS", **qlib_evidence}

    try:
        experiments = pd.read_csv(EXPERIMENTS, dtype=str, keep_default_na=False)
        matching = experiments.loc[
            experiments["code_sha256"].eq(code_hash) & experiments["data_snapshot_sha256"].eq(data_hash)
        ]
    except (FileNotFoundError, KeyError, OSError, pd.errors.ParserError) as error:
        matching = pd.DataFrame(columns=["candidate_source", "feature_or_formula", "params_json", "result_json"])
        missing.append(f"experiment ledger cannot be reconciled: {type(error).__name__}: {error}")
    baseline_rows = matching.loc[matching["candidate_source"].eq("Alpha158")]
    shadow_rows = matching.loc[matching["candidate_source"].eq("Alpha158-shadow")]
    alphagen_rows = matching.loc[matching["candidate_source"].eq("AlphaGen-GP")]

    expected_windows = [window.name for window in settings.evaluation.g0_windows]
    verified_windows = []
    if "baseline" in reports and evidence.get("backtest", {}).get("validation_status") == "PASS":
        for result in reports["baseline"][1]["windows"]:
            if _has_result(baseline_rows, result):
                verified_windows.append(result["window"])
    if verified_windows != expected_windows:
        missing.append(f"experiment ledger is missing exact baseline results: {sorted(set(expected_windows) - set(verified_windows))}")

    signal_evidence = None
    signal_document = None
    for manifest in sorted((PROJECT_ROOT / "signals").glob("*.json"), reverse=True):
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if document.get("data_snapshot_sha256") != data_hash or document.get("code_snapshot_sha256") != code_hash:
            continue
        try:
            signal_evidence, signal_document = validate_shadow_manifest(
                manifest,
                data_hash=data_hash,
                code_hash=code_hash,
                expected_topk=settings.backtest.topk,
            )
        except (KeyError, OSError, TypeError, ValueError):
            continue
        break
    shadow_ledger_bound = False
    if signal_evidence is None or signal_document is None:
        missing.append("no semantically valid shadow manifest matches the current data and code snapshots")
    else:
        signal_hash = signal_evidence["signal_sha256"]
        for value in shadow_rows["result_json"]:
            result = _json_cell(value)
            try:
                score_rows = int(result.get("score_rows", 0))
            except (TypeError, ValueError):
                continue
            if result.get("signal_sha256") == signal_hash and score_rows >= settings.backtest.topk:
                shadow_ledger_bound = True
                break
        if not shadow_ledger_bound:
            missing.append("shadow manifest is not bound to an exact matching experiment-ledger result")
        evidence["shadow"] = {**signal_evidence, "ledger_bound": shadow_ledger_bound}

    verified_alphagen_candidates = 0
    alphagen_summary_bound = False
    if "alphagen" in reports and evidence.get("alphagen_cpu", {}).get("validation_status") == "PASS":
        alphagen = reports["alphagen"][1]
        verified_alphagen_candidates = sum(
            _has_result(alphagen_rows, result, feature=expression)
            for expression, result in alphagen["candidates"].items()
        )
        alphagen_summary_bound = _has_result(alphagen_rows, alphagen["summary"], feature="BENCHMARK_SUMMARY")
        if verified_alphagen_candidates != len(alphagen["candidates"]):
            missing.append("experiment ledger does not contain every exact AlphaGen candidate result")
        if not alphagen_summary_bound:
            missing.append("experiment ledger has no exact AlphaGen benchmark summary")
    else:
        missing.append("validated AlphaGen evidence cannot be reconciled to the experiment ledger")

    evidence["experiment_ledger"] = {
        "matching_rows": len(matching),
        "baseline_rows": len(baseline_rows),
        "verified_baseline_windows": verified_windows,
        "shadow_rows": len(shadow_rows),
        "shadow_manifest_bound": shadow_ledger_bound,
        "alphagen_candidate_rows": int(alphagen_rows["feature_or_formula"].ne("BENCHMARK_SUMMARY").sum()),
        "verified_alphagen_candidates": verified_alphagen_candidates,
        "alphagen_summary_rows": int(alphagen_rows["feature_or_formula"].eq("BENCHMARK_SUMMARY").sum()),
        "alphagen_summary_bound": alphagen_summary_bound,
    }

    sentinels_pass = bool(evidence.get("sentinels", {}).get("condition_pass", False))
    backtest = evidence.get("backtest", {})
    windows_pass = bool(backtest.get("window_condition_pass", False))
    cost_pass = bool(backtest.get("cost_1_5_condition_pass", False))
    g0_formula_pass = sentinels_pass and windows_pass and cost_pass
    stage0_complete = g0_formula_pass and not missing
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "code_snapshot_sha256": code_hash,
        "data_snapshot_sha256": data_hash,
        "status": "PASS" if stage0_complete else "FAIL",
        "g0": {
            "sentinels_condition_pass": sentinels_pass,
            "window_condition_pass": windows_pass,
            "cost_1_5_condition_pass": cost_pass,
            "pass": g0_formula_pass,
        },
        "hands_on_verification": {
            "vwap_units_evidence_present": bool(
                evidence.get("sentinels", {}).get("validation_status") == "PASS"
                and evidence.get("sentinels", {}).get("s4_units", {}).get("status") == "PASS"
            ),
            "alphagen_cpu_evidence_present": evidence.get("alphagen_cpu", {}).get("validation_status") == "PASS",
        },
        "missing_evidence": missing,
        "evidence": evidence,
        "stage0_complete": stage0_complete,
        "next_phase_authorized": False,
    }
    output_dir = PROJECT_ROOT / "logs/audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"g0_{datetime.now(timezone.utc):%Y%m%dT%H%M%S.%fZ}.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({**payload, "report_path": str(output)}, ensure_ascii=False, sort_keys=True))
    return 0 if stage0_complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
