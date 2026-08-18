"""TS-v6-4 legacy Sharpe lineage for the frozen DSR trial set."""

from __future__ import annotations

import pandas as pd

from shaiwei.research.g1 import periodic_sharpe
from shaiwei.research.trend_swing.r3g2.effect_artifacts import tree_manifest
from shaiwei.research.trend_swing.v6_3.metrics import legacy_r3g2_sharpes
from shaiwei.research.trend_swing.v6_4.contract import (
    PARENT_POINT_HASH,
    V63_FIRST_PASS_BUNDLE_SHA256,
    V63_FIRST_PASS_ROOT,
    V64Error,
)


def legacy_sharpes() -> tuple[float, ...]:
    """Recompute the four sealed discovery Sharpes from bound artifacts only."""
    parent_sharpes = legacy_r3g2_sharpes()
    manifest = tree_manifest(V63_FIRST_PASS_ROOT)
    if manifest["bundle_sha256"] != V63_FIRST_PASS_BUNDLE_SHA256:
        raise V64Error("TS-v6-4 bound TS-v6-3 first-pass bundle differs")
    nav = pd.read_parquet(
        V63_FIRST_PASS_ROOT / "discovery" / PARENT_POINT_HASH / "base_1x" / "nav.parquet"
    )
    v63_sharpe = periodic_sharpe(nav["active_return"].astype(float).tolist(), minimum=252)
    return tuple(parent_sharpes) + (v63_sharpe,)
