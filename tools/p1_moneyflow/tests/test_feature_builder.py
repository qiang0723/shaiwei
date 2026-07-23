from pathlib import Path

import pandas as pd

from shaiwei.ledger import sha256_file
from tools.p1_moneyflow.feature_builder import write_content_addressed_parquet


def test_content_addressed_parquet_is_idempotent(tmp_path: Path):
    frame = pd.DataFrame([{"trade_date": "20260723", "value": 1.0}])
    first_path, first_hash, first_reused = write_content_addressed_parquet(
        frame, tmp_path, stem="candidate"
    )
    second_path, second_hash, second_reused = write_content_addressed_parquet(
        frame, tmp_path, stem="candidate"
    )
    assert first_path == second_path
    assert first_hash == second_hash == sha256_file(first_path)
    assert first_reused is False
    assert second_reused is True
