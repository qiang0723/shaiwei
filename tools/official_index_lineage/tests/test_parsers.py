from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tools.official_index_lineage.contract import DataGateError
from tools.official_index_lineage.parsers import (
    methodology_checks,
    parse_adjustment_material,
    parse_effective_date,
    parse_initial_xlsx,
)


def test_initial_workbook_requires_exact_200(tmp_path: Path) -> None:
    path = tmp_path / "initial.xlsx"
    frame = pd.DataFrame({"证券代码": [f"688{number:03d}" for number in range(200)]})
    with pd.ExcelWriter(path) as writer:
        frame.to_excel(writer, sheet_name="000699", index=False)
    members = parse_initial_xlsx(path, "000699", 200)
    assert len(members) == len(set(members)) == 200


def test_initial_workbook_rejects_wrong_count(tmp_path: Path) -> None:
    path = tmp_path / "initial.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"证券代码": ["688001"]}).to_excel(
            writer, sheet_name="000699", index=False
        )
    with pytest.raises(DataGateError, match="count differs"):
        parse_initial_xlsx(path, "000699", 200)


def test_structured_adjustment_selects_only_target_index(tmp_path: Path) -> None:
    path = tmp_path / "adjust.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(
            {"指数代码": ["000699", "000688"], "证券代码": ["688001", "688099"]}
        ).to_excel(writer, sheet_name="调出", index=False)
        pd.DataFrame(
            {"指数代码": ["000699", "000688"], "证券代码": ["688201", "688199"]}
        ).to_excel(writer, sheet_name="调入", index=False)
    result = parse_adjustment_material(path, "000699")
    assert result is not None
    assert result.pairs == (("688001", "688201"),)


def test_text_adjustment_and_explicit_no_change(tmp_path: Path) -> None:
    pairs = tmp_path / "pairs.html"
    pairs.write_text(
        "<html><body>科创200指数样本调整名单 调出 调入 688001 688201 "
        "科创200指数备选名单</body></html>",
        encoding="utf-8",
    )
    parsed = parse_adjustment_material(pairs, "000699")
    assert parsed is not None and parsed.pairs == (("688001", "688201"),)
    no_change = tmp_path / "none.html"
    no_change.write_text("科创200指数样本无变动", encoding="utf-8")
    parsed_none = parse_adjustment_material(no_change, "000699")
    assert parsed_none is not None and parsed_none.explicit_no_change is True


def test_effective_date_normalizes_after_close() -> None:
    result = parse_effective_date(
        "调整于2025年3月14日收市后生效",
        ["20250314", "20250317", "20250318"],
    )
    assert result.official_reference_date == "20250314"
    assert result.effective_date == "20250317"
    assert result.timing == "after_close"


def test_effective_date_ambiguity_fails_closed() -> None:
    with pytest.raises(DataGateError, match="missing or ambiguous"):
        parse_effective_date("没有生效日期", ["20250317"])


def test_methodology_lineage_checks_both_rule_versions() -> None:
    checks = methodology_checks(
        "2024年7月 版本号 V1.0 指数代码：000699 上市时间超过 6 个月 样本每季度调整一次",
        "修订科创200，2025年3月17日实施，并采用新老样本划断",
        "2025年2月 版本号 V1.1 指数代码：000699 上市时间超过 12 个月",
    )
    assert all(checks.values())
