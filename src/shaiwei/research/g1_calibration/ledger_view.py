"""只读账本视图：只取到最后一个换行的完整前缀，读者无需持锁也不会读到并发追加的半行。

账本只追加，故完整前缀永远是某一时刻的一致快照。本模块不依赖 qlib/torch，供判定与独立审计共用。
"""

from __future__ import annotations

import csv
import io
from pathlib import Path


class IsolationError(RuntimeError):
    pass


def complete_text(path: Path) -> str:
    data = path.read_bytes()
    end = data.rfind(b"\n")
    return data[: end + 1].decode("utf-8") if end >= 0 else ""


def complete_rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(complete_text(path), newline="")))


def prefix_snapshot(path: Path, directory: Path) -> Path:
    """把完整前缀写成临时副本，交给按路径读取的冻结函数（如 `g1.family_trials`）。"""
    snapshot = directory / path.name
    snapshot.write_text(complete_text(path), encoding="utf-8", newline="")
    return snapshot
