import pytest

from shaiwei.research.trend_swing.ts_b.cli import main
from shaiwei.research.trend_swing.ts_b.contract import TSBError, TSBScope
from shaiwei.research.trend_swing.ts_b.fixture import fixture
from shaiwei.research.trend_swing.ts_b.inputs import TSBAdapter


def test_holdout_gate_fires_on_losing_synthetic() -> None:
    scope = TSBScope.load()
    from shaiwei.research.trend_swing.ts_b.fixture import _run_synthetic

    losing = _run_synthetic(scope, losing=True)
    assert losing["gate"]["passed"] is False


def test_discovery_partition_is_physically_unreachable(tmp_path) -> None:
    scope = TSBScope.load()
    adapter = TSBAdapter(scope, tmp_path)
    adapter._preflight = {"sealed": True}
    with pytest.raises(TSBError, match="forbidden"):
        adapter.load_partition("discovery")


def test_fixture_and_cli_are_stable(capsys) -> None:
    assert fixture()["fixture_pass"] is True
    assert main(["fixture"]) == 0
    assert '"fixture_pass": true' in capsys.readouterr().out
