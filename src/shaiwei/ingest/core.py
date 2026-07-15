"""原始批次的事务式落盘入口：新文件 + 内容哈希 + 账本，禁止覆盖。"""

import os
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from shaiwei.ledger import append_ingest_batch, sha256_file

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_.=-]+$")
Recorder = Callable[..., str]


@dataclass(frozen=True)
class RawBatch:
    batch_id: str
    source_api: str
    row_count: int
    parquet_path: Path
    content_sha256: str


class RawBatchWriter:
    """Write one source response as a never-overwritten Parquet batch."""

    def __init__(
        self,
        data_root: Path,
        *,
        recorder: Recorder = append_ingest_batch,
        now: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.data_root = Path(data_root)
        self.recorder = recorder
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or (lambda: uuid.uuid4().hex)

    @staticmethod
    def _segment(value: object) -> str:
        rendered = str(value)
        if not _SAFE_SEGMENT.fullmatch(rendered):
            raise ValueError(f"unsafe partition segment: {rendered!r}")
        return rendered

    def write(
        self,
        *,
        source_api: str,
        params: dict,
        frame: pd.DataFrame,
        partitions: dict[str, object] | None = None,
        operator: str = "automation",
    ) -> RawBatch:
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("frame must be a pandas DataFrame")
        source, separator, api_name = source_api.partition(".")
        if not separator or not source or not api_name:
            raise ValueError("source_api must use '<source>.<api>' format")

        stamp = self.now().astimezone(timezone.utc)
        nonce = self._segment(self.id_factory())
        directory = self.data_root / "raw" / f"source={self._segment(source)}" / f"api={self._segment(api_name)}"
        for key, value in (partitions or {}).items():
            directory /= f"{self._segment(key)}={self._segment(value)}"
        directory /= f"ingest_date={stamp.date().isoformat()}"
        directory.mkdir(parents=True, exist_ok=True)

        filename = f"{stamp.strftime('%Y%m%dT%H%M%S.%fZ')}_{nonce}.parquet"
        final_path = directory / filename
        temp_path = directory / f".{filename}.tmp"
        try:
            frame.to_parquet(temp_path, index=False, compression="zstd")
            with temp_path.open("rb") as handle:
                os.fsync(handle.fileno())
            os.link(temp_path, final_path)  # atomic and fails rather than overwriting
        finally:
            temp_path.unlink(missing_ok=True)

        try:
            batch_id = self.recorder(
                source_api=source_api,
                params=params,
                row_count=len(frame),
                parquet_path=str(final_path),
                content_sha256=sha256_file(final_path),
                operator=operator,
            )
        except Exception:
            # A batch is committed only when both file and ledger row exist.
            final_path.unlink(missing_ok=True)
            raise

        return RawBatch(
            batch_id=batch_id,
            source_api=source_api,
            row_count=len(frame),
            parquet_path=final_path,
            content_sha256=sha256_file(final_path),
        )
