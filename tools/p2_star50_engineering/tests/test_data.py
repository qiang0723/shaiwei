from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.p2_star50_engineering.data import membership_intervals_from_daily  # noqa: E402


def test_membership_intervals_preserve_exit_and_reentry() -> None:
    calendar = ["20200102", "20200103", "20200106", "20200107"]
    daily = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["20200102", "20200103", "20200107"]),
            "code": ["688001.SH", "688001.SH", "688001.SH"],
        }
    )
    intervals = membership_intervals_from_daily(daily, calendar)
    assert intervals.to_dict("records") == [
        {"instrument": "SH688001", "start": "20200102", "end": "20200103"},
        {"instrument": "SH688001", "start": "20200107", "end": "20200107"},
    ]
