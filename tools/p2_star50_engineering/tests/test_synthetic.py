from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.p2_star50_engineering.synthetic import (  # noqa: E402
    FIXTURE_PATH,
    _synthetic_frames,
    load_fixture,
)


def test_synthetic_fixture_is_deterministic_and_contains_no_official_member_code() -> None:
    fixture = load_fixture()
    first = _synthetic_frames(fixture)
    second = _synthetic_frames(fixture)
    assert FIXTURE_PATH.is_file()
    assert first[0].equals(second[0])
    assert first[1].equals(second[1])
    assert len(first[2]) == fixture["calendar_trade_days"] * fixture["instrument_count"]
