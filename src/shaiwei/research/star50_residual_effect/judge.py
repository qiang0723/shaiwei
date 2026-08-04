"""Frozen STAR50-adapted factor effect judge for M4-1."""

from __future__ import annotations

from typing import Any

import numpy as np

from shaiwei.research.g1 import G1Error, deflated_sharpe_probability, newey_west_mean_t
from shaiwei.research.star50_residual_effect.contract import ResidualEffectError


def judge_candidates(
    results: list[dict[str, Any]],
    directions: dict[str, dict[str, Any]],
    protocol: dict[str, Any],
    integrity: dict[str, bool],
) -> list[dict[str, Any]]:
    specs = {row["candidate_id"]: row for row in protocol["candidates"]}
    thresholds = protocol["adapted_effect_gates"]
    evaluation = protocol["evaluation"]
    sharpes = tuple(float(row["selection_sharpe"]) for row in results)
    judged: list[dict[str, Any]] = []
    result_map = {str(row["candidate"]): row for row in results}
    for candidate, direction in directions.items():
        if not direction["direction_pass"]:
            judged.append(
                {
                    "candidate": candidate,
                    "direction": direction,
                    "oos_effect_read": False,
                    "adapted_gate_decision": "REJECT_DIRECTION",
                    "failed_gates": ["pre_registered_direction"],
                    "formal_g1_v1_status": evaluation["formal_g1_v1_status"],
                }
            )
            continue
        result = result_map[candidate]
        oriented_windows = list(result["oos_window_rank_ic"].values())
        positive = sum(value > 0 for value in oriented_windows)
        retention = float(np.mean(oriented_windows) / abs(float(direction["mean_rank_ic"])))
        hac_t = newey_west_mean_t(
            result["daily_oos_rank_ic"],
            lags=int(evaluation["newey_west_lags"]),
            minimum=int(evaluation["minimum_daily_rank_ic_observations_oos_total"]),
        )
        enough_sharpes = len(sharpes) >= int(
            thresholds["minimum_valid_same_family_selection_sharpes"]
        )
        if enough_sharpes:
            dsr, dsr_details = deflated_sharpe_probability(
                result["daily_net_excess_returns"],
                trial_sharpes=sharpes,
                trial_count=int(thresholds["same_family_trial_count"]),
                minimum=int(evaluation["minimum_daily_rank_ic_observations_oos_total"]),
            )
            global_dsr, _ = deflated_sharpe_probability(
                result["daily_net_excess_returns"],
                trial_sharpes=sharpes,
                trial_count=int(thresholds["global_related_attempt_count_sensitivity"]),
                minimum=int(evaluation["minimum_daily_rank_ic_observations_oos_total"]),
            )
        else:
            dsr, global_dsr, dsr_details = 0.0, 0.0, {}
        turnover_ratio = float(result["candidate_turnover"] / result["baseline_turnover"])
        spec = specs[candidate]
        gates = {
            "pit_and_shift": all(integrity.values()),
            "complexity": int(spec["expression_tokens"])
            <= int(thresholds["maximum_expression_tokens"])
            and int(spec["ast_nodes"]) <= int(thresholds["maximum_ast_nodes"]),
            "economic_rationale": len(str(spec["economic_rationale"]).strip())
            >= int(thresholds["minimum_economic_rationale_chars"]),
            "library_correlation": float(result["max_library_abs_spearman"])
            < float(thresholds["maximum_existing_library_abs_spearman"]),
            "rolling_window_sign": positive
            >= int(evaluation["minimum_positive_oriented_rank_ic_windows"]),
            "rank_ic_retention": retention
            >= float(evaluation["minimum_mean_oos_to_discovery_rank_ic_retention"]),
            "stress_drawdown": max(result["stress_max_drawdown"].values())
            <= float(evaluation["maximum_stress_drawdown"]),
            "turnover": turnover_ratio
            <= float(thresholds["maximum_turnover_ratio_to_alpha158"]),
            "incremental_net_icir": float(result["candidate_net_icir"])
            > float(result["baseline_net_icir"]),
            "incremental_net_excess": float(result["candidate_net_excess"])
            > float(result["baseline_net_excess"]),
            "cost_2x": float(result["cost_2x_net_excess"])
            >= float(thresholds["candidate_cost_2x_net_excess_minimum"]),
            "extra_10bp_each_side": float(result["extra_10bp_net_excess"])
            >= float(thresholds["candidate_extra_10bp_net_excess_minimum"]),
            "valid_trial_sharpes": enough_sharpes,
            "deflated_sharpe": dsr >= float(thresholds["minimum_deflated_sharpe_probability"]),
            "newey_west_t": hac_t >= float(evaluation["minimum_newey_west_t"]),
        }
        failed = [name for name, passed in gates.items() if not passed]
        judged.append(
            {
                "candidate": candidate,
                "direction": direction,
                "oos_effect_read": True,
                "oos_window_rank_ic": result["oos_window_rank_ic"],
                "positive_oriented_windows": positive,
                "rank_ic_retention": retention,
                "newey_west_t": hac_t,
                "stress_max_drawdown": result["stress_max_drawdown"],
                "baseline_turnover": result["baseline_turnover"],
                "candidate_turnover": result["candidate_turnover"],
                "turnover_ratio": turnover_ratio,
                "baseline_net_icir": result["baseline_net_icir"],
                "candidate_net_icir": result["candidate_net_icir"],
                "baseline_net_excess": result["baseline_net_excess"],
                "candidate_net_excess": result["candidate_net_excess"],
                "cost_2x_net_excess": result["cost_2x_net_excess"],
                "extra_10bp_net_excess": result["extra_10bp_net_excess"],
                "selection_sharpe": result["selection_sharpe"],
                "same_family_trial_count": int(thresholds["same_family_trial_count"]),
                "same_family_dsr_probability": dsr,
                "global_273_dsr_sensitivity": global_dsr,
                "dsr_details": dsr_details,
                "max_library_abs_spearman": result["max_library_abs_spearman"],
                "gates": gates,
                "failed_gates": failed,
                "adapted_gate_decision": "PASS" if not failed else "REJECT",
                "formal_g1_v1_status": evaluation["formal_g1_v1_status"],
            }
        )
    return judged


def safe_judge_candidates(
    results: list[dict[str, Any]],
    directions: dict[str, dict[str, Any]],
    protocol: dict[str, Any],
    integrity: dict[str, bool],
) -> list[dict[str, Any]]:
    try:
        return judge_candidates(results, directions, protocol, integrity)
    except (G1Error, ZeroDivisionError, ValueError) as error:
        raise ResidualEffectError("M4-1 statistical gate evaluation failed") from error
