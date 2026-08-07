"""Immutable identifiers for the M6-3 TopK conversion workflow."""

from __future__ import annotations


ARMS = (
    "clean_lgbm_control_v1",
    "ridge_alpha1_v1",
    "lgbm_ridge_rank_blend_50_50_v1",
)
ALTERNATIVES = ARMS[1:]
WINDOWS = ("W1", "W2", "W3", "W4", "W5", "W6")
TOPK_KEYS = ("30", "20")
SCENARIOS = ("1", "1.5", "2")
STRESS_PERIODS = ("microcap_crash_2024", "volume_price_drawdown_2026h1")
REPORT_FIELDS = (
    "date",
    "gross_return",
    "benchmark_return",
    "recorded_cost",
    "turnover",
)
DECISIONS = (
    "BLOCKED",
    "TOPK20_CONVERSION_SUPPORTED",
    "TOPK20_CONVERSION_NOT_SUPPORTED",
    "MIXED_NOT_CONCLUSIVE",
)
