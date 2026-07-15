from pathlib import Path

import pandas as pd


def test_fund_comparator_is_frozen_balanced_and_nonempty():
    path = Path(__file__).resolve().parents[1] / "templates/fund_comparator.csv"
    funds = pd.read_csv(path, dtype=str, keep_default_na=False)

    assert len(funds) == 6
    assert funds["代码"].is_unique
    assert set(funds["份额类别"]) == {"A"}
    assert funds.groupby("标的指数").size().to_dict() == {"中证800": 3, "中证A500": 3}
    assert set(funds["数据日期"]) == {"2026-07-15"}
    assert funds["来源"].str.startswith("https://").all()
    assert funds["固定运作费率合计"].str.endswith("%").all()
