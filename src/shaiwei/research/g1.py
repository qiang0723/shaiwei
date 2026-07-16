"""Fail-closed, pre-registered G1 factor-admission judge."""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import math
import os
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Iterator

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from shaiwei.config import PROJECT_ROOT, G1Admission, Settings, load
from shaiwei.ledger import (
    EXPERIMENTS,
    FACTOR_ADMISSIONS,
    append_factor_admission,
    portable_artifact_path,
    sha256_file,
)

EULER_MASCHERONI = 0.5772156649015329
NORMAL = NormalDist()


class G1Error(RuntimeError):
    pass


class StrictEvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ComplexityEvidence(StrictEvidenceModel):

    expression_tokens: int = Field(ge=1)
    ast_nodes: int = Field(ge=1)


class IntegrityEvidence(StrictEvidenceModel):

    pit_sentinel_pass: bool
    shift_sentinel_pass: bool
    test_report_path: str = Field(min_length=1)
    test_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    max_library_abs_spearman: float = Field(ge=0, le=1)


class RankICEvidence(StrictEvidenceModel):

    in_sample: float
    oos_windows: dict[str, float]
    daily_oos: list[float]


class PortfolioEvidence(StrictEvidenceModel):

    baseline_turnover: float = Field(gt=0)
    candidate_turnover: float = Field(ge=0)
    baseline_net_icir: float
    candidate_net_icir: float
    baseline_net_excess: float
    candidate_net_excess: float
    cost_2x_net_excess: float
    slippage_2x_net_excess: float
    daily_net_excess_returns: list[float]


class G1Evidence(StrictEvidenceModel):

    schema_version: int = Field(default=1, ge=1, le=1)
    candidate_experiment_id: str = Field(min_length=1)
    research_family: str = Field(min_length=1)
    code_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    economic_rationale: str = Field(min_length=1)
    complexity: ComplexityEvidence
    integrity: IntegrityEvidence
    rank_ic: RankICEvidence
    stress_max_drawdown: dict[str, float]
    portfolio: PortfolioEvidence


@dataclass(frozen=True)
class FamilyTrials:
    candidate: dict[str, str]
    candidate_params: dict[str, object]
    candidate_result: dict[str, object]
    trial_count: int
    valid_trial_sharpes: tuple[float, ...]
    ledger_sha256: str


@dataclass(frozen=True)
class AdmissionDecision:
    decision_id: str
    admitted: bool
    failed_gates: tuple[str, ...]
    report_path: Path
    report_sha256: str
    reused: bool


def _finite_array(values: list[float], *, name: str, minimum: int) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or len(array) < minimum:
        raise G1Error(f"{name} requires at least {minimum} observations")
    if not np.isfinite(array).all():
        raise G1Error(f"{name} contains non-finite observations")
    return array


def periodic_sharpe(returns: list[float], *, minimum: int) -> float:
    array = _finite_array(returns, name="daily_net_excess_returns", minimum=minimum)
    standard_deviation = float(array.std(ddof=1))
    if standard_deviation <= 0:
        raise G1Error("daily_net_excess_returns must have positive sample variance")
    return float(array.mean() / standard_deviation)


def newey_west_mean_t(values: list[float], *, lags: int, minimum: int) -> float:
    """Bartlett-kernel HAC t-statistic for a time-series mean."""
    array = _finite_array(values, name="daily_oos_rank_ic", minimum=minimum)
    if lags >= len(array):
        raise G1Error("Newey-West lag must be smaller than observation count")
    centered = array - array.mean()
    long_run_variance = float(centered @ centered / len(array))
    for lag in range(1, lags + 1):
        covariance = float(centered[lag:] @ centered[:-lag] / len(array))
        long_run_variance += 2.0 * (1.0 - lag / (lags + 1.0)) * covariance
    if not math.isfinite(long_run_variance) or long_run_variance <= 0:
        raise G1Error("daily_oos_rank_ic has non-positive HAC variance")
    return float(array.mean() / math.sqrt(long_run_variance / len(array)))


def expected_maximum_sharpe(trial_sharpes: tuple[float, ...], trial_count: int) -> float:
    if trial_count < 1:
        raise G1Error("trial_count must be positive")
    if trial_count == 1:
        return 0.0
    if len(trial_sharpes) < 2:
        raise G1Error("at least two valid trial Sharpes are required")
    trial_std = float(np.asarray(trial_sharpes, dtype=float).std(ddof=1))
    if not math.isfinite(trial_std):
        raise G1Error("trial Sharpe dispersion is non-finite")
    first = NORMAL.inv_cdf(1.0 - 1.0 / trial_count)
    second = NORMAL.inv_cdf(1.0 - 1.0 / (trial_count * math.e))
    return trial_std * ((1.0 - EULER_MASCHERONI) * first + EULER_MASCHERONI * second)


def deflated_sharpe_probability(
    returns: list[float],
    *,
    trial_sharpes: tuple[float, ...],
    trial_count: int,
    minimum: int,
) -> tuple[float, dict[str, float]]:
    array = _finite_array(returns, name="daily_net_excess_returns", minimum=minimum)
    observed = periodic_sharpe(returns, minimum=minimum)
    centered = array - array.mean()
    second_moment = float(np.mean(centered**2))
    if second_moment <= 0:
        raise G1Error("daily_net_excess_returns must have positive variance")
    skewness = float(np.mean(centered**3) / second_moment**1.5)
    kurtosis = float(np.mean(centered**4) / second_moment**2)
    benchmark = expected_maximum_sharpe(trial_sharpes, trial_count)
    denominator_squared = 1.0 - skewness * observed + ((kurtosis - 1.0) / 4.0) * observed**2
    if not math.isfinite(denominator_squared) or denominator_squared <= 0:
        raise G1Error("Deflated Sharpe denominator is non-positive")
    z_score = (observed - benchmark) * math.sqrt(len(array) - 1) / math.sqrt(
        denominator_squared
    )
    probability = float(NORMAL.cdf(z_score))
    return probability, {
        "observed_periodic_sharpe": observed,
        "expected_maximum_periodic_sharpe": benchmark,
        "skewness": skewness,
        "kurtosis": kurtosis,
        "z_score": z_score,
    }


def _load_json_object(value: str, *, field: str, experiment_id: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise G1Error(f"experiment {experiment_id} has invalid {field}") from error
    if not isinstance(parsed, dict):
        raise G1Error(f"experiment {experiment_id} {field} must be an object")
    return parsed


def family_trials(
    research_family: str,
    candidate_experiment_id: str,
    *,
    experiments_path: Path = EXPERIMENTS,
) -> FamilyTrials:
    with experiments_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    experiment_ids = [row["experiment_id"] for row in rows]
    if len(experiment_ids) != len(set(experiment_ids)):
        raise G1Error("experiment ledger contains duplicate experiment_id values")
    candidate: dict[str, str] | None = None
    candidate_params: dict[str, object] = {}
    candidate_result: dict[str, object] = {}
    family_rows: list[tuple[dict[str, str], dict[str, object], dict[str, object]]] = []
    for row in rows:
        experiment_id = row["experiment_id"]
        params = _load_json_object(row["params_json"], field="params_json", experiment_id=experiment_id)
        result = _load_json_object(row["result_json"], field="result_json", experiment_id=experiment_id)
        if params.get("g1_research_family") == research_family:
            family_rows.append((row, params, result))
        if experiment_id == candidate_experiment_id:
            candidate, candidate_params, candidate_result = row, params, result
    if candidate is None:
        raise G1Error(f"candidate experiment is absent from the ledger: {candidate_experiment_id}")
    if candidate_params.get("g1_research_family") != research_family:
        raise G1Error("candidate experiment is not bound to the requested research family")
    sharpes: list[float] = []
    for _, _, result in family_rows:
        value = result.get("selection_sharpe")
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            sharpes.append(float(value))
    return FamilyTrials(
        candidate=candidate,
        candidate_params=candidate_params,
        candidate_result=candidate_result,
        trial_count=len(family_rows),
        valid_trial_sharpes=tuple(sharpes),
        ledger_sha256=sha256_file(experiments_path),
    )


def _spec_sha256(settings: Settings) -> str:
    payload = {
        "g1_admission": settings.g1_admission.model_dump(mode="json"),
        "windows": [window.name for window in settings.evaluation.g0_windows],
        "stress_periods": [period.name for period in settings.evaluation.stress_periods],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def _resolve_evidence_artifact(path: str) -> Path:
    artifact = Path(path)
    return artifact if artifact.is_absolute() else PROJECT_ROOT / artifact


def _verify_integrity_binding(evidence: G1Evidence, trials: FamilyTrials) -> None:
    expected_candidate_bindings = {
        "code_snapshot_sha256": trials.candidate["code_sha256"],
        "data_snapshot_sha256": trials.candidate["data_snapshot_sha256"],
    }
    actual_candidate_bindings = {
        "code_snapshot_sha256": evidence.code_snapshot_sha256,
        "data_snapshot_sha256": evidence.data_snapshot_sha256,
    }
    if actual_candidate_bindings != expected_candidate_bindings:
        raise G1Error("evidence code/data snapshot does not match the candidate experiment")
    report_path = _resolve_evidence_artifact(evidence.integrity.test_report_path)
    if not report_path.is_file():
        raise G1Error("factor PIT/shift test report is missing")
    if sha256_file(report_path) != evidence.integrity.test_report_sha256:
        raise G1Error("factor PIT/shift test report hash mismatch")
    report = _load_json_object(
        report_path.read_text(encoding="utf-8"),
        field="factor test report",
        experiment_id=evidence.candidate_experiment_id,
    )
    expected_report = {
        "candidate_experiment_id": evidence.candidate_experiment_id,
        "code_snapshot_sha256": evidence.code_snapshot_sha256,
        "data_snapshot_sha256": evidence.data_snapshot_sha256,
        "pit_sentinel_pass": evidence.integrity.pit_sentinel_pass,
        "shift_sentinel_pass": evidence.integrity.shift_sentinel_pass,
    }
    differences = {
        field for field, expected in expected_report.items() if report.get(field) != expected
    }
    if differences:
        raise G1Error(f"factor PIT/shift report binding differs: {sorted(differences)}")


def _gate(actual: object, passed: bool, rule: str) -> dict[str, object]:
    return {"actual": actual, "passed": bool(passed), "rule": rule}


def _evaluate_gates(
    settings: Settings,
    evidence: G1Evidence,
    trials: FamilyTrials,
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    threshold: G1Admission = settings.g1_admission
    expected_windows = [window.name for window in settings.evaluation.g0_windows]
    expected_stress = [period.name for period in settings.evaluation.stress_periods]
    actual_windows = set(evidence.rank_ic.oos_windows)
    actual_stress = set(evidence.stress_max_drawdown)
    if actual_windows != set(expected_windows):
        raise G1Error("oos_windows must exactly match the six frozen evaluation windows")
    if actual_stress != set(expected_stress):
        raise G1Error("stress_max_drawdown must exactly match the frozen stress periods")
    if evidence.rank_ic.in_sample == 0:
        raise G1Error("in-sample RankIC cannot be zero because it freezes factor direction")

    direction = 1.0 if evidence.rank_ic.in_sample > 0 else -1.0
    oriented_windows = [direction * evidence.rank_ic.oos_windows[name] for name in expected_windows]
    positive_windows = sum(value > 0 for value in oriented_windows)
    mean_oriented_oos = float(np.mean(oriented_windows))
    retention = mean_oriented_oos / abs(evidence.rank_ic.in_sample)
    oriented_daily_ic = [direction * value for value in evidence.rank_ic.daily_oos]
    hac_t = newey_west_mean_t(
        oriented_daily_ic,
        lags=threshold.hac_lags,
        minimum=threshold.min_observations,
    )
    candidate_sharpe = periodic_sharpe(
        evidence.portfolio.daily_net_excess_returns,
        minimum=threshold.min_observations,
    )
    ledger_candidate_sharpe = trials.candidate_result.get("selection_sharpe")
    if not isinstance(ledger_candidate_sharpe, (int, float)) or not math.isfinite(
        float(ledger_candidate_sharpe)
    ):
        raise G1Error("candidate experiment lacks a finite selection_sharpe")
    if not math.isclose(candidate_sharpe, float(ledger_candidate_sharpe), rel_tol=1e-9, abs_tol=1e-12):
        raise G1Error("candidate daily returns do not reproduce ledger selection_sharpe")
    enough_trial_sharpes = len(trials.valid_trial_sharpes) >= threshold.min_valid_trial_sharpes
    if enough_trial_sharpes:
        dsr, dsr_details = deflated_sharpe_probability(
            evidence.portfolio.daily_net_excess_returns,
            trial_sharpes=trials.valid_trial_sharpes,
            trial_count=trials.trial_count,
            minimum=threshold.min_observations,
        )
    else:
        dsr = 0.0
        dsr_details = {
            "observed_periodic_sharpe": candidate_sharpe,
            "expected_maximum_periodic_sharpe": None,
            "skewness": None,
            "kurtosis": None,
            "z_score": None,
        }

    formula = trials.candidate["feature_or_formula"].strip()
    rationale_length = len(evidence.economic_rationale.strip())
    params_tokens = trials.candidate_params.get("expression_tokens")
    params_nodes = trials.candidate_params.get("ast_nodes")
    complexity_bound = (
        params_tokens == evidence.complexity.expression_tokens
        and params_nodes == evidence.complexity.ast_nodes
    )
    worst_stress = max(evidence.stress_max_drawdown.values())
    if any(not math.isfinite(value) or value < 0 for value in evidence.stress_max_drawdown.values()):
        raise G1Error("stress drawdowns must be finite non-negative fractions")
    turnover_ratio = evidence.portfolio.candidate_turnover / evidence.portfolio.baseline_turnover

    gates = {
        "pit_and_shift": _gate(
            {
                "pit": evidence.integrity.pit_sentinel_pass,
                "shift": evidence.integrity.shift_sentinel_pass,
            },
            evidence.integrity.pit_sentinel_pass and evidence.integrity.shift_sentinel_pass,
            "both PIT and shift sentinels PASS",
        ),
        "complexity": _gate(
            {
                "formula_present": bool(formula),
                "expression_tokens": evidence.complexity.expression_tokens,
                "ast_nodes": evidence.complexity.ast_nodes,
                "ledger_binding": complexity_bound,
            },
            bool(formula)
            and complexity_bound
            and evidence.complexity.expression_tokens <= threshold.max_expression_tokens
            and evidence.complexity.ast_nodes <= threshold.max_ast_nodes,
            f"tokens<={threshold.max_expression_tokens}; ast_nodes<={threshold.max_ast_nodes}; ledger-bound",
        ),
        "economic_rationale": _gate(
            rationale_length,
            rationale_length >= threshold.min_economic_rationale_chars,
            f"human rationale length>={threshold.min_economic_rationale_chars}",
        ),
        "library_correlation": _gate(
            evidence.integrity.max_library_abs_spearman,
            evidence.integrity.max_library_abs_spearman
            < threshold.max_library_abs_correlation,
            f"max |Spearman rho|<{threshold.max_library_abs_correlation}",
        ),
        "rolling_window_sign": _gate(
            positive_windows,
            positive_windows >= threshold.min_positive_windows,
            f"positive oriented OOS windows>={threshold.min_positive_windows}/{len(expected_windows)}",
        ),
        "rank_ic_retention": _gate(
            retention,
            retention >= threshold.min_rank_ic_retention,
            f"mean oriented OOS RankIC / |IS RankIC|>={threshold.min_rank_ic_retention}",
        ),
        "stress_drawdown": _gate(
            worst_stress,
            worst_stress <= threshold.max_stress_drawdown,
            f"every frozen stress-period drawdown<={threshold.max_stress_drawdown}",
        ),
        "turnover": _gate(
            turnover_ratio,
            turnover_ratio <= threshold.max_turnover_ratio,
            f"candidate/base turnover<={threshold.max_turnover_ratio}",
        ),
        "incremental_net_icir": _gate(
            evidence.portfolio.candidate_net_icir - evidence.portfolio.baseline_net_icir,
            evidence.portfolio.candidate_net_icir > evidence.portfolio.baseline_net_icir,
            "candidate net ICIR minus same-budget baseline > 0",
        ),
        "incremental_net_excess": _gate(
            evidence.portfolio.candidate_net_excess - evidence.portfolio.baseline_net_excess,
            evidence.portfolio.candidate_net_excess > evidence.portfolio.baseline_net_excess,
            "candidate net excess minus same-budget baseline > 0",
        ),
        "cost_2x": _gate(
            evidence.portfolio.cost_2x_net_excess,
            evidence.portfolio.cost_2x_net_excess >= 0,
            "net excess at cost +100% >= 0",
        ),
        "slippage_2x": _gate(
            evidence.portfolio.slippage_2x_net_excess,
            evidence.portfolio.slippage_2x_net_excess >= 0,
            "net excess with doubled slippage >= 0",
        ),
        "valid_trial_sharpes": _gate(
            len(trials.valid_trial_sharpes),
            enough_trial_sharpes,
            f"valid trial Sharpes>={threshold.min_valid_trial_sharpes}; failed attempts still count in N",
        ),
        "deflated_sharpe": _gate(
            dsr,
            dsr >= threshold.dsr_probability_threshold,
            f"DSR probability>={threshold.dsr_probability_threshold}",
        ),
        "hac_t": _gate(
            hac_t,
            hac_t >= threshold.hac_t_threshold,
            f"Newey-West({threshold.hac_lags}) oriented daily RankIC t>={threshold.hac_t_threshold}",
        ),
    }
    statistics = {
        "direction": int(direction),
        "positive_oos_windows": positive_windows,
        "mean_oriented_oos_rank_ic": mean_oriented_oos,
        "rank_ic_retention": retention,
        "hac_t": hac_t,
        "turnover_ratio": turnover_ratio,
        "trial_count": trials.trial_count,
        "valid_trial_sharpes": len(trials.valid_trial_sharpes),
        "dsr_probability": dsr,
        **dsr_details,
    }
    return gates, statistics


def _read_admissions(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@contextmanager
def _decision_lock(output_dir: Path) -> Iterator[None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / ".admission.lock").open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _existing_decision(
    admissions_path: Path,
    *,
    candidate_experiment_id: str,
    evidence_sha256: str,
    spec_sha256: str,
    ledger_sha256: str,
) -> AdmissionDecision | None:
    for row in reversed(_read_admissions(admissions_path)):
        if (
            row["candidate_experiment_id"] == candidate_experiment_id
            and row["evidence_sha256"] == evidence_sha256
            and row["spec_sha256"] == spec_sha256
            and row["experiment_ledger_sha256"] == ledger_sha256
        ):
            report_path = Path(row["report_path"])
            if not report_path.is_absolute():
                report_path = PROJECT_ROOT / report_path
            if not report_path.is_file() or sha256_file(report_path) != row["report_sha256"]:
                raise G1Error("existing admission report is missing or corrupt")
            failed = tuple(filter(None, row["failed_gates"].split("|")))
            return AdmissionDecision(
                decision_id=row["decision_id"],
                admitted=row["admitted"] == "true",
                failed_gates=failed,
                report_path=report_path,
                report_sha256=row["report_sha256"],
                reused=True,
            )
    return None


def evaluate_g1(
    evidence_path: Path,
    *,
    settings: Settings | None = None,
    experiments_path: Path = EXPERIMENTS,
    admissions_path: Path = FACTOR_ADMISSIONS,
    output_dir: Path | None = None,
) -> AdmissionDecision:
    settings = settings or load()
    output_dir = output_dir or PROJECT_ROOT / "logs" / "g1"
    evidence_sha256 = sha256_file(evidence_path)
    evidence = G1Evidence.model_validate_json(evidence_path.read_text(encoding="utf-8"))
    trials = family_trials(
        evidence.research_family,
        evidence.candidate_experiment_id,
        experiments_path=experiments_path,
    )
    _verify_integrity_binding(evidence, trials)
    spec_sha256 = _spec_sha256(settings)
    with _decision_lock(output_dir):
        if existing := _existing_decision(
            admissions_path,
            candidate_experiment_id=evidence.candidate_experiment_id,
            evidence_sha256=evidence_sha256,
            spec_sha256=spec_sha256,
            ledger_sha256=trials.ledger_sha256,
        ):
            return existing
        gates, statistics = _evaluate_gates(settings, evidence, trials)
        failed = tuple(name for name, gate in gates.items() if not gate["passed"])
        admitted = not failed
        key = hashlib.sha256(
            (
                evidence.candidate_experiment_id
                + evidence_sha256
                + spec_sha256
                + trials.ledger_sha256
            ).encode()
        ).hexdigest()
        decision_id = key[:12]
        report_path = output_dir / (
            f"{evidence.candidate_experiment_id}-{evidence_sha256[:12]}-"
            f"{spec_sha256[:12]}-{trials.ledger_sha256[:12]}.json"
        )
        report = {
            "schema_version": 1,
            "decision_id": decision_id,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "status": "PASS" if admitted else "REJECT",
            "candidate": {
                "experiment_id": evidence.candidate_experiment_id,
                "research_family": evidence.research_family,
                "candidate_source": trials.candidate["candidate_source"],
                "feature_or_formula": trials.candidate["feature_or_formula"],
                "economic_rationale": evidence.economic_rationale,
            },
            "bindings": {
                "evidence_path": portable_artifact_path(evidence_path),
                "evidence_sha256": evidence_sha256,
                "spec_version": settings.g1_admission.spec_version,
                "spec_sha256": spec_sha256,
                "experiment_ledger_sha256": trials.ledger_sha256,
                "candidate_code_sha256": trials.candidate["code_sha256"],
                "candidate_data_snapshot_sha256": trials.candidate["data_snapshot_sha256"],
                "factor_test_report_path": evidence.integrity.test_report_path,
                "factor_test_report_sha256": evidence.integrity.test_report_sha256,
            },
            "statistics": statistics,
            "gates": gates,
            "failed_gates": list(failed),
            "admitted": admitted,
        }
        payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if report_path.exists():
            existing_report = json.loads(report_path.read_text(encoding="utf-8"))
            for field, expected in report["bindings"].items():
                if existing_report.get("bindings", {}).get(field) != expected:
                    raise G1Error(f"existing deterministic report binding differs: {field}")
            report = existing_report
            admitted = bool(report["admitted"])
            failed = tuple(report["failed_gates"])
            decision_id = str(report["decision_id"])
        else:
            temporary = report_path.with_name(f".{report_path.name}.{uuid.uuid4().hex}.tmp")
            try:
                temporary.write_text(payload, encoding="utf-8")
                with temporary.open("rb") as handle:
                    os.fsync(handle.fileno())
                os.link(temporary, report_path)
            finally:
                temporary.unlink(missing_ok=True)
        report_sha256 = sha256_file(report_path)
        append_factor_admission(
            path=admissions_path,
            decision_id=decision_id,
            evaluated_at=str(report["evaluated_at"]),
            candidate_experiment_id=evidence.candidate_experiment_id,
            research_family=evidence.research_family,
            evidence_sha256=evidence_sha256,
            spec_sha256=spec_sha256,
            experiment_ledger_sha256=trials.ledger_sha256,
            trial_count=trials.trial_count,
            valid_trial_sharpes=len(trials.valid_trial_sharpes),
            report_path=portable_artifact_path(report_path),
            report_sha256=report_sha256,
            admitted=admitted,
            failed_gates="|".join(failed),
        )
        return AdmissionDecision(
            decision_id=decision_id,
            admitted=admitted,
            failed_gates=failed,
            report_path=report_path,
            report_sha256=report_sha256,
            reused=False,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--evidence", type=Path)
    source.add_argument("--print-schema", action="store_true")
    args = parser.parse_args(argv)
    if args.print_schema:
        print(json.dumps(G1Evidence.model_json_schema(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.evidence is None:
        parser.error("--evidence is required unless --print-schema is used")
    decision = evaluate_g1(args.evidence)
    print(
        json.dumps(
            {
                "decision_id": decision.decision_id,
                "status": "PASS" if decision.admitted else "REJECT",
                "failed_gates": decision.failed_gates,
                "report_path": str(decision.report_path),
                "report_sha256": decision.report_sha256,
                "reused": decision.reused,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
