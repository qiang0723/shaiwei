from pathlib import Path

from shaiwei import r2d_release_guard as guard


PREPARE = Path("config/r2d_scheduler_release_guard_r3b_prepare_v1.yaml")
START = Path("config/r2d_scheduler_release_guard_r3b_start_v1.yaml")


def test_r3b_protocols_share_identity_and_split_authority() -> None:
    prepare = guard.load_protocol(PREPARE)
    start = guard.load_protocol(START)

    assert prepare.schema_version == "r2d-scheduler-release-guard-v1"
    assert prepare.legacy_noop_boundary is None
    assert start.schema_version == "r2d-scheduler-release-guard-r2-v1"
    assert start.legacy_noop_boundary is not None
    assert start.legacy_noop_boundary.detail_trade_date == "20260830"
    assert prepare.prepare_date == start.prepare_date == "20260830"
    assert prepare.target_trade_date == start.target_trade_date == "20260831"
    assert prepare.candidate == start.candidate
    assert prepare.expected_running_release == start.expected_running_release
    assert prepare.expected_latest_forward == start.expected_latest_forward
    assert prepare.predecessor_fixture == start.predecessor_fixture
    assert prepare.predecessor_fixture.format == "r3a"
    assert prepare.controller_identity == start.controller_identity
    assert len(prepare.controller_identity.component_paths) == 6


def test_r3b_candidate_and_r3a_evidence_are_exactly_frozen() -> None:
    frozen = guard.load_protocol(PREPARE)

    assert frozen.candidate.image == "shaiwei:scheduler-97d8c05eab2a1e8c"
    assert frozen.candidate.image_id == (
        "sha256:b64ae11b76c4005876781085c1bdfa08dc500153cd5645594de2fb90b7cc5ebe"
    )
    assert frozen.predecessor_fixture.release_scope_sha256 == (
        "49a322aefb9039126c7590f0b07d60fcad3f1398fa7f2ca6412e52dc3d427017"
    )
    assert {item.execution_trade_date for item in frozen.expected_latest_forward} == {
        "20260828"
    }
