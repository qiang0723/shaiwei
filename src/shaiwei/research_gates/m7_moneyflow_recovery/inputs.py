"""Typed in-memory inputs for the synthetic M7 recovery gate."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RecoveryInputs:
    track_a_targets: pd.DataFrame
    track_b_targets: pd.DataFrame
    daily_keys: pd.DataFrame
    independent_status: pd.DataFrame
    full_market_target_rows: pd.DataFrame
    targeted_rows: pd.DataFrame
    official_dates: tuple[str, ...]
    full_market_response_row_counts: tuple[int, ...]
    immutable_batch_integrity: bool
