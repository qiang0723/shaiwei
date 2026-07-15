"""Pure backtest evidence aggregation without importing the qlib runtime."""

import pandas as pd


def g0_backtest_summary(window_results: list[dict], baseline_multiplier: float = 1.0) -> dict[str, object]:
    baseline_key = f"{baseline_multiplier:g}"
    positive = sum(result["cost_scenarios"][baseline_key]["cumulative_excess"] > 0 for result in window_results)
    combined = {}
    if window_results:
        scenario_keys = window_results[0]["cost_scenarios"]
        for key in scenario_keys:
            combined[key] = float(
                pd.Series(
                    [1.0 + result["cost_scenarios"][key]["cumulative_excess"] for result in window_results]
                ).prod()
                - 1.0
            )
    return {
        "window_count": len(window_results),
        "positive_excess_windows": positive,
        "combined_cumulative_excess": combined,
        "window_condition_pass": len(window_results) == 6 and positive >= 4,
        "cost_1_5_condition_pass": combined.get("1.5", float("-inf")) >= 0,
    }
