"""汇总：R1 检出、阴性对照误放率 Clopper–Pearson 上界与预注册终态（协议 §7、§9）。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from scipy.stats import beta

from shaiwei.research.g1_calibration.protocol import ProtocolIdentity

DEPENDENCE_CAVEAT = (
    "所有种子共用同一份市场数据、同一组窗口与基线，评估并不独立；上界是乐观近似，"
    "只说明在本数据上门不会轻易放行噪声，不能外推。"
)


@dataclass(frozen=True)
class UnitOutcome:
    route: str
    strength: float | None
    seed: int | None
    cell_family: str
    experiment_id: str
    status: str  # JUDGED | EVIDENCE_ERROR
    main: bool = False
    layer_a: bool = False
    layer_b: bool = False
    failed_main: tuple[str, ...] = ()
    error_type: str = ""
    report_path: str = ""
    diagnostics: dict[str, object] = field(default_factory=dict)


def clopper_pearson_upper(passes: int, trials: int, confidence: float) -> float:
    if trials <= 0 or not 0 <= passes <= trials:
        raise ValueError("Clopper-Pearson needs 0 <= passes <= trials and trials > 0")
    if passes == trials:
        return 1.0
    return float(beta.ppf(confidence, passes + 1, trials - passes))


def _cells(outcomes: list[UnitOutcome]) -> dict[str, list[UnitOutcome]]:
    grouped: dict[str, list[UnitOutcome]] = defaultdict(list)
    for outcome in outcomes:
        grouped[outcome.cell_family].append(outcome)
    return dict(grouped)


def summarize(protocol: ProtocolIdentity, outcomes: list[UnitOutcome], *, planned_noise_seeds: int) -> dict[str, object]:
    config = protocol.config
    detection = config.detection
    incomplete: list[str] = []
    r1 = {}
    for strength in config.calibration.target_mean_rank_ic:
        units = [o for o in outcomes if o.route == "R1" and o.strength == strength]
        errors = [o.experiment_id for o in units if o.status != "JUDGED"]
        if len(units) != detection.seeds_per_strength or errors:
            incomplete.append(f"R1/{strength:.2f}: {len(units)} units, {len(errors)} evidence errors")
        passes = sum(o.main for o in units)
        r1[f"{strength:.2f}"] = {
            "seeds": len(units),
            "main_passes": passes,
            "layer_a_passes": sum(o.layer_a for o in units),
            "layer_b_passes": sum(o.layer_b for o in units),
            "detected": passes >= detection.min_passing_seeds,
        }
    negatives = [o for o in outcomes if o.route in {"N1", "N2"}]
    judged_negatives = [o for o in negatives if o.status == "JUDGED"]
    if len(negatives) != 2 * planned_noise_seeds or len(judged_negatives) != len(negatives):
        incomplete.append(f"negative controls: {len(judged_negatives)}/{2 * planned_noise_seeds} judged")
    false_passes = sum(o.main for o in judged_negatives)
    upper = (
        clopper_pearson_upper(false_passes, len(judged_negatives), config.false_pass_bound.confidence)
        if judged_negatives
        else None
    )
    increment_control = None
    if "N3" in config.routes:  # v2：N3 只按三个增量门判定，“放行”即任一种子三门全过
        n3 = [o for o in outcomes if o.route == "N3"]
        judged_n3 = [o for o in n3 if o.status == "JUDGED"]
        planned_n3 = len(config.routes["N3"].seed_values())
        if len(n3) != planned_n3 or len(judged_n3) != len(n3):
            incomplete.append(f"N3 increment control: {len(judged_n3)}/{planned_n3} judged")
        released = sum(o.main for o in judged_n3)
        increment_control = {
            "planned_seeds": planned_n3, "judged": len(judged_n3), "released": released,
            "judged_gates": list(config.routes["N3"].judged_gates or ()),
            "false_release_upper_bound": (
                clopper_pearson_upper(released, len(judged_n3), config.false_pass_bound.confidence) if judged_n3 else None
            ),
        }
        false_passes += released
    if incomplete:
        state = None
    elif false_passes:
        state = config.interpretation.any_negative_control_pass_is
    else:
        detected = [float(key) for key, value in r1.items() if value["detected"]]
        if any(value <= config.interpretation.calibrated_max_strength for value in detected):
            state = "G1_CALIBRATED"
        elif detected:
            state = "G1_BORDERLINE"
        else:
            state = "G1_UNDERPOWERED"
    if state is not None and state not in config.interpretation.terminal_states:
        raise ValueError(f"terminal state outside the frozen set: {state}")
    cells = {
        family: {
            "units": len(units),
            "judged": sum(o.status == "JUDGED" for o in units),
            "main_passes": sum(o.main for o in units),
            "layer_a_passes": sum(o.layer_a for o in units),
            "layer_b_passes": sum(o.layer_b for o in units),
            "evidence_errors": sorted({o.error_type for o in units if o.status != "JUDGED"}),
        }
        for family, units in sorted(_cells(outcomes).items())
    }
    return {
        "status": "COMPLETE" if state else "INCOMPLETE",
        "terminal_state": state,
        "incomplete_reasons": incomplete,
        "r1_detection": r1,
        "negative_controls": {
            "planned_seeds_per_control": planned_noise_seeds,
            "judged": len(judged_negatives),
            "main_passes": false_passes,
            "false_pass_upper_bound": upper,
            "confidence": config.false_pass_bound.confidence,
            "method": config.false_pass_bound.method,
            "dependence_caveat": DEPENDENCE_CAVEAT,
        },
        **({"increment_control": increment_control} if increment_control is not None else {}),
        "cells": cells,
        "interpretation_boundary": "终态只关于 g1-v1 在本数据、本窗口下的检出能力；R2–R5 只解释、不改变终态。",
    }
