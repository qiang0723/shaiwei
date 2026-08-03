from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.fundamental_dynamics_features import FEATURE_IDS
from shaiwei.research.fundamental_dynamics_recovery_contract import (
    FundamentalDynamicsRecoveryProtocol,
    verify_predecessor_data,
)
from shaiwei.research.fundamental_dynamics_recovery_gate import recovery_null_diagnostics
from shaiwei.research.fundamental_pit_contract import FundamentalPitError


PROTOCOL = PROJECT_ROOT / "config/f2_csi800_fundamental_dynamics_recovery_v2.yaml"


def _protocol() -> FundamentalDynamicsRecoveryProtocol:
    return FundamentalDynamicsRecoveryProtocol.load(PROTOCOL)


def test_recovery_is_disclosed_and_has_no_count_specific_allowance(tmp_path: Path):
    protocol = _protocol()
    change = protocol.document["recovery_change"]
    assert protocol.document["result_blind_claim"] is False
    assert change["count_specific_threshold_forbidden"] is True
    assert change["exact_missing_row_allowlist_forbidden"] is True
    assert protocol.document["gates"]["quality_no_consecutive_pair_rows"] == (
        "diagnostic_without_fixed_count_gate"
    )
    tampered = deepcopy(protocol.document)
    tampered["gates"]["feature_aggregate_coverage_minimum"] = 0.80
    path = tmp_path / "tampered.yaml"
    path.write_text(yaml.safe_dump(tampered, allow_unicode=True), encoding="utf-8")
    with pytest.raises(FundamentalPitError, match="gates"):
        FundamentalDynamicsRecoveryProtocol.load(path)


def test_predecessor_v1_no_go_and_all_artifacts_are_bound():
    evidence = verify_predecessor_data(_protocol())
    assert evidence["verdict"] == "NO_GO_F2_FUNDAMENTAL_DYNAMICS_DATA_FEATURE_GATE"
    assert evidence["known_quality_no_consecutive_pair_rows"] == 1
    assert evidence["feature_panel_sha256"] == (
        "d451663ce7f664df1b5408ef794ef38244fe3f814313544ec9625534ea164fd3"
    )


def test_unestimable_row_must_have_null_metadata_and_all_features():
    rows = []
    for current, predecessor, available, value in (
        (pd.NA, pd.NA, pd.NA, pd.NA),
        ("20171231", "20161231", "20180502", 0.1),
    ):
        row = {
            "current_end_date": current,
            "predecessor_end_date": predecessor,
            "available_date": available,
        }
        row.update({feature_id: value for feature_id in FEATURE_IDS})
        rows.append(row)
    diagnostics = recovery_null_diagnostics(pd.DataFrame(rows))
    assert diagnostics == {
        "pair_absent_rows": 1,
        "pair_absent_rows_with_nonnull_available_date": 0,
        "pair_absent_rows_with_any_nonnull_feature": 0,
        "pair_present_rows_missing_end_date": 0,
    }


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("available_date", "20180502", "pair_absent_rows_with_nonnull_available_date"),
        (FEATURE_IDS[0], 0.1, "pair_absent_rows_with_any_nonnull_feature"),
        ("current_end_date", "20171231", "pair_present_rows_missing_end_date"),
    ],
)
def test_illegal_recovery_rows_fail_closed(field: str, value: object, expected: str):
    row = {
        "current_end_date": pd.NA,
        "predecessor_end_date": pd.NA,
        "available_date": pd.NA,
        **{feature_id: pd.NA for feature_id in FEATURE_IDS},
    }
    row[field] = value
    diagnostics = recovery_null_diagnostics(pd.DataFrame([row]))
    assert diagnostics[expected] == 1


def test_recovery_compose_is_offline_release_bound_and_narrow():
    compose = yaml.safe_load((PROJECT_ROOT / "compose.research.yaml").read_text(encoding="utf-8"))
    service = compose["services"]["f2-fundamental-dynamics-recovery"]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert "env_file" not in service
    assert service["build"]["args"]["SHAIWEI_RELEASE_GIT_HEAD"] == (
        "${SHAIWEI_F2_RECOVERY_RELEASE_GIT_HEAD:-}"
    )
    writes = [volume for volume in service["volumes"] if volume.get("read_only") is False]
    assert [volume["source"] for volume in writes] == [
        "./data/research/f2_csi800_fundamental_dynamics_recovery_v2"
    ]
    makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
    assert 'SHAIWEI_F2_RECOVERY_RELEASE_GIT_HEAD="$(F2_RECOVERY_RELEASE_GIT_HEAD)"' in makefile
