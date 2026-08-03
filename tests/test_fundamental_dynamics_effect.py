from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.research.fundamental_dynamics_effect_contract import (
    FundamentalDynamicsEffectProtocol,
)
from shaiwei.research.fundamental_effect.contract import FundamentalEffectError
from shaiwei.research.fundamental_effect.runtime import F2_RUNTIME


PROTOCOL = PROJECT_ROOT / "config/f2_csi800_fundamental_effect_v1.yaml"
CANDIDATES = (
    "fundamental_asset_growth_v1",
    "fundamental_revenue_growth_v1",
    "fundamental_operating_profit_change_v1",
    "fundamental_net_income_change_v1",
    "fundamental_operating_cashflow_change_v1",
    "fundamental_cash_balance_change_v1",
)


def test_protocol_is_bound_to_frozen_candidates_and_cumulative_trials(tmp_path: Path) -> None:
    protocol = FundamentalDynamicsEffectProtocol.load(PROTOCOL)
    assert tuple(item.name for item in protocol.candidates) == CANDIDATES
    assert tuple(item.direction for item in protocol.candidates) == (-1, 1, 1, 1, 1, 1)
    assert protocol.document["multiple_testing"]["cumulative_trial_count_after_complete_run"] == 12
    assert F2_RUNTIME.multiple_testing_families == tuple(
        protocol.document["multiple_testing"]["related_trial_families"]
    )

    tampered = deepcopy(protocol.document)
    tampered["candidate_policy"][0]["pre_registered_direction"] = 1
    path = tmp_path / "tampered.yaml"
    path.write_text(yaml.safe_dump(tampered, allow_unicode=True), encoding="utf-8")
    with pytest.raises(FundamentalEffectError, match="protocol hash differs"):
        FundamentalDynamicsEffectProtocol.load(path)


def test_compose_service_is_offline_release_bound_and_has_narrow_writes() -> None:
    compose = yaml.safe_load((PROJECT_ROOT / "compose.research.yaml").read_text(encoding="utf-8"))
    service = compose["services"]["f2-fundamental-effect"]
    assert service["network_mode"] == "none"
    assert service["read_only"] is True
    assert "env_file" not in service
    assert service["build"]["args"]["SHAIWEI_RELEASE_GIT_HEAD"] == (
        "${SHAIWEI_F2_EFFECT_RELEASE_GIT_HEAD:-}"
    )
    writable = [volume["source"] for volume in service["volumes"] if volume.get("read_only") is False]
    assert writable == [
        "./data/research/f2_csi800_fundamental_effect_v1",
        "./ledger/experiments.csv",
        "./ledger/factor_admissions.csv",
    ]
    makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
    assert 'SHAIWEI_F2_EFFECT_RELEASE_GIT_HEAD="$(F2_EFFECT_RELEASE_GIT_HEAD)"' in makefile
