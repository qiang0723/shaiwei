from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

from tools.p2_star50_v2.lineage import (
    LineageError,
    _membership_comparison,
    _validate_event_uniqueness,
    parse_adjustment_html,
    parse_effective_date,
    parse_initial_xlsx,
    parse_adjustment_word,
)


def test_parse_star50_table_ignores_other_index(tmp_path: Path) -> None:
    path = tmp_path / "notice.html"
    path.write_text(
        """
        <table><tr><td>600001</td><td>A</td><td>600002</td><td>B</td></tr></table>
        <table>
          <tr><td>688001</td><td>A</td><td>688101</td><td>B</td></tr>
          <tr><td>688002</td><td>C</td><td>689009</td><td>D</td></tr>
        </table>
        <table><tr><td>1</td><td>688999</td><td>reserve</td></tr></table>
        """,
        encoding="utf-8",
    )
    assert parse_adjustment_html(path) == [("688001", "688101"), ("688002", "689009")]


def test_after_close_normalizes_to_next_open_trade_date() -> None:
    text = "于2024年6月14日收市后生效"
    result = parse_effective_date(text, ["20240614", "20240617"])
    assert result.official_reference_date == "20240614"
    assert result.effective_date == "20240617"
    assert result.timing == "after_close"


def test_start_of_day_keeps_official_date() -> None:
    text = "决定于2020年12月14日调整科创50指数样本"
    result = parse_effective_date(text, ["20201214", "20201215"])
    assert result.effective_date == "20201214"
    assert result.timing == "start_of_day"


def test_initial_workbook_requires_exactly_fifty_unique_members(tmp_path: Path) -> None:
    path = tmp_path / "initial.xlsx"
    frame = pd.DataFrame({"证券代码\nSecurities Code": range(688001, 688051)})
    with pd.ExcelWriter(path) as writer:
        frame.to_excel(writer, sheet_name="000688", index=False)
    members = parse_initial_xlsx(path)
    assert len(members) == 50
    assert len(set(members)) == 50


def test_parse_word_compatible_wps_attachment(tmp_path: Path) -> None:
    path = tmp_path / "members.wps"
    document = """<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>科创50指数样本调整名单 688561 A 688183 B 科创50指数备选名单 1 688999 C</w:t></w:r></w:p></w:body>
    </w:document>""".encode()
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)
    assert parse_adjustment_word(path) == ([("688561", "688183")], False)


def test_duplicate_official_event_in_same_batch_fails_closed() -> None:
    events = pd.DataFrame(
        {
            "effective_date": [pd.Timestamp("2024-06-17"), pd.Timestamp("2024-06-17")],
            "out_code": ["688001.SH", "688001.SH"],
            "in_code": ["688101.SH", "688102.SH"],
        }
    )
    with pytest.raises(LineageError, match="duplicate official out code"):
        _validate_event_uniqueness(events)


def test_duplicate_tushare_row_fails_exact_set_crosscheck() -> None:
    official = {f"688{value:03d}.SH" for value in range(50)}
    secondary_rows = sorted(official) + [sorted(official)[0]]
    comparison = _membership_comparison("20240628", official, secondary_rows)
    assert comparison["tushare_count"] == 50
    assert comparison["tushare_row_count"] == 51
    assert comparison["tushare_duplicate_count"] == 1
    assert comparison["exact_match"] is False
