from datetime import date

from shaiwei.config import load
from shaiwei.shadow.generation import model_spec_sha256, signal_segments


def test_forward_model_spec_is_deterministic_and_date_bound():
    settings = load()
    first = model_spec_sha256(settings, date(2026, 7, 15))
    assert first == model_spec_sha256(settings, date(2026, 7, 15))
    assert first != model_spec_sha256(settings, date(2026, 7, 16))
    segments = signal_segments(settings, date(2026, 7, 15))
    assert segments["train"] == ("2023-07-15", "2026-01-14")
    assert segments["valid"] == ("2026-01-15", "2026-07-15")
