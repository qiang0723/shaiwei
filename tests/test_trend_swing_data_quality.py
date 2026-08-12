from shaiwei.research.trend_swing.data_quality import _summary


class _FakeConnection:
    description = [
        ("expected_member_days",),
        ("trade_day_count",),
        ("security_count",),
        ("snapshot_count",),
        ("bse_member_days",),
        ("bar_days",),
        ("suspended_missing_days",),
        ("unexplained_missing_bar_days",),
        ("adj_covered_bar_days",),
        ("cap_covered_bar_days",),
        ("industry_resolved_days",),
        ("ambiguous_industry_days",),
        ("st_member_days",),
        ("duplicate_key_days",),
        ("conflicting_key_days",),
        ("amount_covered_bar_days",),
    ]

    def execute(self, sql):
        self._describe = sql == "DESCRIBE expected"
        return self

    def fetchall(self):
        assert self._describe
        return [("ts_code",), ("trade_date",), ("snapshot_date",)]

    def fetchone(self):
        assert not self._describe
        return (100, 1, 100, 1, 0, 98, 2, 0, 98, 98, 99, 0, 3, 0, 0, 98)


def test_quality_summary_treats_full_day_suspension_as_explained_bar_coverage():
    result = _summary(_FakeConnection())
    assert result["stock_bar_or_suspension_coverage"] == 1.0
    assert result["market_cap_coverage_on_bars"] == 1.0
    assert result["industry_coverage"] == 0.99
    assert result["unexplained_missing_bar_days"] == 0
