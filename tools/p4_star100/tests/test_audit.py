from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tools.p4_star100.audit import (
    Star100AuditError,
    _set_changes,
    parse_initial_xlsx,
)


def _write_initial(path: Path, count: int = 100) -> None:
    frame = pd.DataFrame(
        {
            "指数代码\nIndex Code": [698] * count,
            "证券代码\nStock Code": range(688001, 688001 + count),
        }
    )
    frame.to_excel(path, index=False)


def test_initial_workbook_requires_exactly_one_hundred_unique_members(
    tmp_path: Path,
) -> None:
    path = tmp_path / "initial.xlsx"
    _write_initial(path)
    members = parse_initial_xlsx(path)
    assert len(members) == 100
    assert members[0] == "688001.SH"


def test_initial_workbook_fails_closed_on_incomplete_membership(tmp_path: Path) -> None:
    path = tmp_path / "initial.xlsx"
    _write_initial(path, count=99)
    with pytest.raises(Star100AuditError, match="not 100"):
        parse_initial_xlsx(path)


def test_secondary_set_changes_are_diagnostic_and_balanced() -> None:
    frame = pd.DataFrame(
        {
            "trade_date": ["20240131", "20240131", "20240229", "20240229"],
            "con_code": ["688001.SH", "688002.SH", "688002.SH", "688003.SH"],
        }
    )
    changes = _set_changes(frame)
    assert changes == [
        {
            "prior_snapshot_date": "20240131",
            "current_snapshot_date": "20240229",
            "out_count": 1,
            "in_count": 1,
            "balanced": True,
            "role": "TUSHARE_SECONDARY_NOT_FOR_VERDICT",
        }
    ]
