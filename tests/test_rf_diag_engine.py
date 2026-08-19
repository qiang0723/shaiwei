from shaiwei.research.rf_diag.cli import main
from shaiwei.research.rf_diag.diagnose import assign_explanations
from shaiwei.research.rf_diag.fixture import fixture


def test_assign_explanations_covers_all_classes() -> None:
    assert fixture()["fixture_pass"] is True
    assert assign_explanations({
        "baostock_status": "", "suspend_d_record_count": 0,
        "lifecycle_edge": False, "formation_edge": False,
    }) == ("UNEXPLAINED_REMAINS",)


def test_cli_fixture_is_stable(capsys) -> None:
    assert main(["fixture"]) == 0
    assert '"fixture_pass": true' in capsys.readouterr().out
