"""信号生成的数据时钟契约和不可覆盖 manifest。"""

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd


class DataClockError(RuntimeError):
    pass


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def assert_sentinels_ready(results: list[dict[str, object]], *, environment: str) -> None:
    by_name = {str(result["sentinel"]): str(result["status"]) for result in results}
    missing = {f"S{number}" for number in range(1, 11)} - set(by_name)
    if missing:
        raise DataClockError(f"sentinel results missing: {sorted(missing)}")
    required = {f"S{number}" for number in range(1, 10)}
    failed = sorted(name for name in required if by_name[name] != "PASS")
    if environment == "prod" and by_name["S10"] != "PASS":
        failed.append("S10")
    elif environment != "prod" and by_name["S10"] not in {"PASS", "NOT_APPLICABLE"}:
        failed.append("S10")
    if failed:
        raise DataClockError(f"signal generation blocked by sentinels: {failed}")


def write_signal_manifest(
    scores: pd.DataFrame,
    *,
    signal_date: date,
    topk: int,
    sentinel_results: list[dict[str, object]],
    data_complete_at: datetime,
    generated_at: datetime,
    data_snapshot_sha256: str,
    code_commit: str,
    code_snapshot_sha256: str,
    output_dir: Path,
    environment: str = "dev",
) -> tuple[Path, str]:
    required = {"instrument", "score"}
    if missing := required - set(scores.columns):
        raise ValueError(f"scores missing fields: {sorted(missing)}")
    if topk < 1:
        raise ValueError("topk must be positive")
    if generated_at.tzinfo is None or data_complete_at.tzinfo is None:
        raise ValueError("data clock timestamps must be timezone-aware")
    if generated_at < data_complete_at:
        raise DataClockError("signal cannot precede data completeness confirmation")
    assert_sentinels_ready(sentinel_results, environment=environment)
    ranked = scores.dropna(subset=["instrument", "score"]).copy()
    if ranked["instrument"].duplicated().any():
        raise ValueError("scores contain duplicate instruments")
    ranked = ranked.sort_values(["score", "instrument"], ascending=[False, True]).head(topk)
    if len(ranked) < topk:
        raise DataClockError(f"only {len(ranked)} valid scores for topk={topk}")
    target_weight = 1.0 / topk
    payload = {
        "schema_version": 1,
        "signal_date": signal_date.isoformat(),
        "data_complete_at": data_complete_at.astimezone(timezone.utc).isoformat(),
        "generated_at": generated_at.astimezone(timezone.utc).isoformat(),
        "data_snapshot_sha256": data_snapshot_sha256,
        "code_commit": code_commit,
        "code_snapshot_sha256": code_snapshot_sha256,
        "topk": topk,
        "orders": [
            {"rank": rank, "instrument": row.instrument, "score": float(row.score), "target_weight": target_weight}
            for rank, row in enumerate(ranked.itertuples(index=False), start=1)
        ],
    }
    signal_hash = hashlib.sha256(_canonical_json(payload)).hexdigest()
    document = {**payload, "signal_sha256": signal_hash}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{signal_date:%Y%m%d}.json"
    with path.open("x", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return path, signal_hash


def verify_signal_manifest(path: Path) -> str:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    claimed = document.pop("signal_sha256")
    actual = hashlib.sha256(_canonical_json(document)).hexdigest()
    if claimed != actual:
        raise ValueError(f"signal manifest hash mismatch: {path}")
    return actual


def reconcile_next_open(manifest_path: Path, execution: pd.DataFrame) -> pd.DataFrame:
    """Compare intended names with next-open availability and observed open deviation."""
    verify_signal_manifest(manifest_path)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    planned = pd.DataFrame(manifest["orders"])
    required = {"instrument", "executable", "actual_open", "reference_open"}
    if missing := required - set(execution.columns):
        raise ValueError(f"execution missing fields: {sorted(missing)}")
    result = planned.merge(execution.loc[:, list(required)], on="instrument", how="left", validate="one_to_one")
    result["executable"] = result["executable"].fillna(False).astype(bool)
    result["open_deviation"] = result["actual_open"] / result["reference_open"] - 1.0
    result["reconcile_status"] = "OK"
    result.loc[~result["executable"], "reconcile_status"] = "NOT_EXECUTABLE"
    result.loc[result["actual_open"].isna() | result["reference_open"].isna(), "reconcile_status"] = "MISSING_PRICE"
    return result
