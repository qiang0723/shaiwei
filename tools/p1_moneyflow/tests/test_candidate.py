import pytest

from tools.p1_moneyflow.candidate import main, parse_args


def test_dry_run_needs_no_report_or_data(capsys):
    assert main(["--trade-date", "20260723", "--dry-run"]) == 0
    assert '"request_count": 1' in capsys.readouterr().out


def test_execution_requires_evidence_path():
    with pytest.raises(SystemExit):
        parse_args(["--trade-date", "20260723"])
