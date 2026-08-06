"""Shared immutable identifiers for the M6-2 runner and independent auditor."""

from __future__ import annotations


ARMS = (
    "clean_lgbm_control_v1",
    "ridge_alpha1_v1",
    "lgbm_ridge_rank_blend_50_50_v1",
)
ALTERNATIVES = ARMS[1:]
WINDOWS = ("W1", "W2", "W3", "W4", "W5", "W6")
SCENARIOS = ("1", "1.5", "2")
