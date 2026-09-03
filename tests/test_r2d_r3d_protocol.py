from pathlib import Path

from shaiwei import r2d_release_guard as guard


PREDECESSOR = Path("config/r2d_scheduler_release_guard_r3b_prepare_v1.yaml")
RECOVERY = Path("config/r2d_scheduler_release_guard_r3d_prepare_v1.yaml")


def test_r3d_prepare_rebinds_only_dates_and_forward_evidence() -> None:
    predecessor = guard.load_protocol(PREDECESSOR)
    recovery = guard.load_protocol(RECOVERY)

    assert recovery.prepare_date == "20260903"
    assert recovery.target_trade_date == "20260904"
    assert {item.execution_trade_date for item in recovery.expected_latest_forward} == {"20260903"}
    assert recovery.candidate == predecessor.candidate
    assert recovery.expected_running_release == predecessor.expected_running_release
    assert recovery.predecessor_fixture == predecessor.predecessor_fixture
    assert (
        recovery.controller_identity.candidate_base_head
        == predecessor.controller_identity.candidate_base_head
    )
    assert recovery.controller_identity.component_paths == predecessor.controller_identity.component_paths
    assert recovery.controller_identity.controller_source_head == "cffa10027320c4cbe710a3737f35b1d3e5e01962"
    assert (
        recovery.controller_identity.component_sha256
        == "3605916b90f6a21d9746e9200cd04b94ba2c020a1b69d3ac9c7f596c2a5c8aad"
    )
    assert set(recovery.expected_legacy_mounts_before_prepare) == {
        "/run/shaiwei-locks",
        "/workspace/data",
        "/workspace/ledger",
        "/workspace/logs",
    }
