from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from shaiwei.research_gates.m7_moneyflow.contract import canonical_json
from shaiwei.research_gates.m7_moneyflow_recovery.contract import (
    RecoveryError,
    RecoveryProtocol,
)
from shaiwei.research_gates.m7_moneyflow_network_recovery.network_contract import (
    NetworkReleaseProtocol,
)
from shaiwei.research_gates.m7_moneyflow_network_recovery.request_plan import (
    build_request_plan,
)
from shaiwei.research_gates.m7_moneyflow_network_recovery.request_plan_store import (
    read_request_plan,
    write_request_plan_once,
)


ROOT = Path(__file__).resolve().parents[1]


def _network() -> NetworkReleaseProtocol:
    return NetworkReleaseProtocol.load(
        ROOT / "config/m7_moneyflow_evidence_recovery_network_release_v1.yaml",
        project_root=ROOT,
    )


def _recovery() -> RecoveryProtocol:
    return RecoveryProtocol.load(
        ROOT / "config/m7_moneyflow_evidence_recovery_v1.yaml",
        engineering_path=ROOT / "config/m7_moneyflow_evidence_recovery_engineering_v1.yaml",
        project_root=ROOT,
    )


def _projected_targets() -> tuple[pd.DataFrame, pd.DataFrame]:
    universes = (
        "star-board-all-pit-v1",
        "star-board-midcap-pit-v1",
        "star-board-smallcap-pit-v1",
    )
    a_rows = [
        {
            "trade_date": "20210105",
            "source_date": "20210104",
            "universe_id": universes[index % 3],
            "ts_code": f"{680000 + index:06d}.SH",
            "segment": "2021H1",
        }
        for index in range(527)
    ]
    a_rows.extend(
        {
            **a_rows[index],
            "universe_id": universes[(index + 1) % 3],
        }
        for index in range(381)
    )
    b_rows = [
        {
            "trade_date": "20210105",
            "source_date": "20210104",
            "universe_id": "star-board-all-pit-v1",
            "ts_code": f"{681000 + index:06d}.SH",
            "segment": "2021H1",
        }
        for index in range(541)
    ]
    return pd.DataFrame(a_rows), pd.DataFrame(b_rows)


def test_exact_request_plan_has_frozen_grain_counts_and_identity() -> None:
    track_a, track_b = _projected_targets()
    plan = build_request_plan(
        _network(),
        _recovery(),
        projected_track_a=track_a,
        projected_track_b=track_b,
        official_dates=("20201231", "20210104", "20210105"),
    )
    assert len(plan.status_requests) == 527
    assert sum(len(item.required_dates) for item in plan.status_requests) == 527
    assert len(plan.full_market_requests) == 1
    assert len(plan.targeted_requests) == 541
    assert len({item.identity_sha256 for item in plan.moneyflow_requests}) == 542


def test_request_plan_store_round_trips_and_manifest_is_aggregate_only(
    tmp_path: Path,
) -> None:
    track_a, track_b = _projected_targets()
    plan = build_request_plan(
        _network(),
        _recovery(),
        projected_track_a=track_a,
        projected_track_b=track_b,
        official_dates=("20201231", "20210104", "20210105"),
    )
    root, manifest, manifest_sha = write_request_plan_once(
        tmp_path,
        plan,
        protocol_sha256=_network().sha256,
        tracked_root_relative="data/control/m7-recovery/request-plans",
        target_identity={
            "track_a": {"logical_sha256": "a" * 64, "physical_sha256": "b" * 64},
            "track_b": {"logical_sha256": "c" * 64, "physical_sha256": "d" * 64},
        },
        calendar_identity={"lineage_bundle_manifest_sha256": "e" * 64},
    )
    observed, observed_manifest = read_request_plan(
        root, expected_manifest_sha256=manifest_sha
    )
    assert observed == plan
    assert observed_manifest == manifest
    assert manifest["request_summary"]["status"]["required_key_count"] == 527
    assert manifest["request_summary"]["full_market"]["request_count"] == 1
    assert manifest["request_summary"]["targeted"]["request_count"] == 541
    assert re.search(r"[0-9]{6}\.(?:SH|SZ|BJ)", canonical_json(manifest)) is None
    assert manifest["provider_call_count"] == 0


def test_request_plan_is_write_once_and_tamper_evident(tmp_path: Path) -> None:
    track_a, track_b = _projected_targets()
    plan = build_request_plan(
        _network(),
        _recovery(),
        projected_track_a=track_a,
        projected_track_b=track_b,
        official_dates=("20210104",),
    )
    kwargs = {
        "protocol_sha256": _network().sha256,
        "tracked_root_relative": "data/control/m7-recovery/request-plans",
        "target_identity": {
            "track_a": {"logical_sha256": "a" * 64},
            "track_b": {"logical_sha256": "b" * 64},
        },
        "calendar_identity": {"lineage_bundle_manifest_sha256": "c" * 64},
    }
    root, _, manifest_sha = write_request_plan_once(tmp_path, plan, **kwargs)
    with pytest.raises(RecoveryError, match="already exists"):
        write_request_plan_once(tmp_path, plan, **kwargs)
    (root / "status_requests.parquet").write_bytes(b"tampered")
    with pytest.raises(RecoveryError, match="integrity differs"):
        read_request_plan(root, expected_manifest_sha256=manifest_sha)


def test_request_plan_rejects_bj_and_wrong_unique_count() -> None:
    track_a, track_b = _projected_targets()
    track_a.loc[track_a.index[0], "ts_code"] = "430001.BJ"
    with pytest.raises(RecoveryError, match="counts or exchange"):
        build_request_plan(
            _network(),
            _recovery(),
            projected_track_a=track_a,
            projected_track_b=track_b,
            official_dates=("20210104",),
        )
