"""Result-blind, fixture-only metadata projection over the existing daily planner."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
import hashlib
from io import StringIO
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StrictBool

from shaiwei.r2d_candidate_contract import (
    CandidateEvidence, CandidatePlan, PhaseReceipt, StageError, digest, require,
)
from shaiwei.r2d_candidate_store import OfflineStageStore
from shaiwei.r2d_parking_rehearsal import FirstDayObservation
from shaiwei.r2d_post_close_contract import FrozenContract, ReleaseBinding, SHANGHAI, Sha256

MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
CSV_FIELDS = {
    "calendar": ("cal_date", "is_open"),
    "ingest": ("source_api", "params_json"),
    "daily": ("target_trade_date", "status"),
    "shadow": ("trade_date", "status", "code_snapshot_sha256"),
    "paper": ("execution_trade_date", "status", "code_snapshot_sha256", "account_id"),
}


class FixtureMetadataSpec(FrozenContract):
    schema_version: Literal["r2d-fixture-metadata-spec-v1"]
    plan_sha256: Sha256
    ready_hour: Annotated[int, Field(strict=True, ge=0, le=23)]
    ready_minute: Annotated[int, Field(strict=True, ge=0, le=59)]
    max_catchup_trade_days: Annotated[int, Field(strict=True, ge=1, le=120)]


class FixtureRuntimeWitness(FrozenContract):
    binding: ReleaseBinding
    handoff_completed_at: AwareDatetime
    candidate_floor_fixture_sha256: Sha256
    handoff_verified: StrictBool
    all_entrypoints_gated: StrictBool
    singleton_held: StrictBool


class FixtureMetadataSnapshot(FrozenContract):
    schema_version: Literal["r2d-fixture-metadata-v1"]
    mode: Literal["OFFLINE_FIXTURE_ONLY"]
    spec_sha256: Sha256
    observed_at: AwareDatetime
    runtime: FixtureRuntimeWitness
    calendar_csv: str
    ingest_csv: str
    daily_csv: str
    shadow_csv: str
    paper_csv: str
    completed_receipts: tuple[PhaseReceipt, ...]
    full_first_day_acceptance_verified: StrictBool


def _fixture_path(directory: Path) -> Path:
    root = Path(__file__).resolve().parents[2] / ".test-tmp"
    directory = directory.absolute()
    require(directory.is_relative_to(root) and directory != root, "FIXTURE_ROOT_REQUIRED")
    parts = directory.relative_to(root).parts
    require(".." not in parts, "FIXTURE_ROOT_REQUIRED")
    for item in (root, *(root.joinpath(*parts[:i]) for i in range(1, len(parts) + 1))):
        require(not item.is_symlink(), "FIXTURE_SYMLINK_FORBIDDEN")
    require(directory.is_dir(), "FIXTURE_DIRECTORY_MISSING")
    path = directory / "r3n-metadata.json"
    require(not path.is_symlink(), "FIXTURE_SYMLINK_FORBIDDEN")
    require(path.is_file(), "FIXTURE_METADATA_MISSING")
    require(path.stat().st_nlink == 1, "FIXTURE_HARDLINK_FORBIDDEN")
    return path


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _read_snapshot(directory: Path) -> FixtureMetadataSnapshot:
    path = _fixture_path(directory)
    before = path.stat()
    require(before.st_size <= MAX_SNAPSHOT_BYTES, "FIXTURE_METADATA_TOO_LARGE")
    with path.open("rb") as stream:
        payload = stream.read(MAX_SNAPSHOT_BYTES + 1)
    after = _fixture_path(directory).stat()
    def identity(stat):
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    require(identity(before) == identity(after), "FIXTURE_METADATA_CHANGED_DURING_READ")
    require(len(payload) == before.st_size, "FIXTURE_METADATA_SIZE_DIFFERS")
    json.loads(payload, object_pairs_hook=_unique_object)  # Reject ambiguous duplicate keys, including nested ones.
    return FixtureMetadataSnapshot.model_validate_json(payload)


def _rows(snapshot: FixtureMetadataSnapshot, kind: str):
    reader = csv.DictReader(StringIO(getattr(snapshot, kind + "_csv")), strict=True)
    require(tuple(reader.fieldnames or ()) == CSV_FIELDS[kind], "CSV_WHITELIST_DIFFERS")
    rows = list(reader)
    require(all(set(row) == set(CSV_FIELDS[kind]) and None not in row.values() for row in rows),
            "CSV_ROW_SHAPE_DIFFERS")
    if kind != "ingest":
        for row in rows:
            value = row[CSV_FIELDS[kind][0]]
            require(len(value) == 8 and value.isascii() and value.isdigit(), "CSV_DATE_INVALID")
            datetime.strptime(value, "%Y%m%d")
    return rows


def _calendar(rows, plan: CandidatePlan, bootstrap: str) -> str:
    protocol = plan.rehearsal.post_close
    dates = [row["cal_date"] for row in rows]
    require(dates == sorted(set(dates)), "CALENDAR_ORDER_OR_DUPLICATE")
    require(all(row["is_open"] in {"0", "1"} for row in rows), "CALENDAR_OPEN_FLAG_INVALID")
    available = {row["cal_date"]: row["is_open"] for row in rows}
    require(bootstrap <= protocol.closed_trade_date, "BOOTSTRAP_AFTER_CLOSED_DATE")
    current = datetime.strptime(bootstrap, "%Y%m%d")
    last = datetime.strptime(protocol.first_candidate_trade_date, "%Y%m%d")
    require(len(rows) >= (last - current).days + 1, "CALENDAR_COVERAGE_GAP")
    while current <= last:
        require(current.strftime("%Y%m%d") in available, "CALENDAR_COVERAGE_GAP")
        current += timedelta(days=1)
    require(available[protocol.closed_trade_date] == "1", "CLOSED_DATE_NOT_OPEN")
    following = [row["cal_date"] for row in rows
                 if row["is_open"] == "1" and row["cal_date"] > protocol.closed_trade_date]
    require(bool(following) and following[0] == protocol.first_candidate_trade_date, "FIRST_DATE_DIFFERS")
    return following[0]


class _CsvSnapshot:
    """Read-only in-memory file protocol used by build_plan; never resolves a disk path."""

    def __init__(self, text: str):
        self.text = text

    def is_file(self):
        return True

    def open(self, **kwargs):
        return StringIO(self.text, newline=kwargs.get("newline", ""))


def _date_plan(snapshot, rows, spec, now):
    import pandas as pd
    from shaiwei.pipeline.daily import REQUIRED_BOOTSTRAP_APIS, build_plan

    require({row["source_api"] for row in rows["ingest"]} == set(REQUIRED_BOOTSTRAP_APIS),
            "BOOTSTRAP_API_SET_DIFFERS")
    bootstrap_dates = []
    for row in rows["ingest"]:
        params = json.loads(row["params_json"], object_pairs_hook=_unique_object)
        require(isinstance(params, dict) and set(params) == {"end_date"}, "BOOTSTRAP_FIELDS_DIFFER")
        value = params["end_date"]
        require(isinstance(value, str) and len(value) == 8 and value.isascii() and value.isdigit(),
                "BOOTSTRAP_DATE_INVALID")
        datetime.strptime(value, "%Y%m%d")
        bootstrap_dates.append(value)
    settings = SimpleNamespace(daily=spec)
    planned = build_plan(
        now=now, settings=settings, trade_cal=pd.DataFrame(rows["calendar"]),
        ingest_ledger_path=_CsvSnapshot(snapshot.ingest_csv),
        daily_ledger_path=_CsvSnapshot(snapshot.daily_csv),
    )
    require(len(rows["ingest"]) == len(REQUIRED_BOOTSTRAP_APIS), "DUPLICATE_BOOTSTRAP_API")
    return planned, min(bootstrap_dates)


def _attempts(rows, plan, receipts):
    first = plan.rehearsal.post_close.first_candidate_trade_date
    expected_code = plan.rehearsal.post_close.binding.candidate_code_sha256
    counts = {}
    for kind in ("daily", "shadow", "paper"):
        date_field = CSV_FIELDS[kind][0]
        require(all(row[date_field] <= first for row in rows[kind]), "FUTURE_ATTEMPT")
        target = [row for row in rows[kind] if row[date_field] == first]
        counts[kind] = len(target)  # Count every attempt before checking its result.
        require(all(row["status"] == "PASS" for row in target), "NON_PASS_ATTEMPT")
        if kind != "daily":
            require(all(row["code_snapshot_sha256"] == expected_code for row in target),
                    "ATTEMPT_IDENTITY_DIFFERS")
        if kind == "paper":
            accounts = [row["account_id"] for row in target]
            require(len(accounts) == len(set(accounts))
                    and set(accounts) <= {"model_baseline", "model_top20"}, "PAPER_ACCOUNT_SET_DIFFERS")
            completed = {receipt.phase for receipt in receipts}
            expected = {account for phase, account in (("PAPER_BASELINE", "model_baseline"),
                        ("PAPER_TOP20", "model_top20")) if phase in completed}
            require(set(accounts) == expected, "PAPER_ACCOUNT_PROOF_DIFFERS")
    return counts


class OfflineMetadataReader:
    """No production fallback, business dispatch, config load, or snapshot writes."""

    def __init__(self, directory: Path, spec: FixtureMetadataSpec, store: OfflineStageStore):
        self.directory, self.store = directory, store
        self.spec = FixtureMetadataSpec.model_validate_json(spec.model_dump_json())

    def read(self, plan: CandidatePlan, *, now: datetime) -> CandidateEvidence:
        try:
            return self._read(plan, now)
        except Exception:
            raise StageError("OFFLINE_METADATA_INVALID") from None

    def _read(self, plan, now):
        require(now.tzinfo is not None and now.utcoffset() is not None, "NAIVE_CLOCK")
        plan = CandidatePlan.model_validate_json(plan.model_dump_json())
        require(self.spec.plan_sha256 == digest(plan) == digest(self.store.plan), "METADATA_PLAN_DIFFERS")
        protocol = plan.rehearsal.post_close
        dispatch = protocol.next_dispatch_not_before.astimezone(SHANGHAI)
        require((self.spec.ready_hour, self.spec.ready_minute) == (dispatch.hour, dispatch.minute),
                "PLANNER_DISPATCH_POLICY_DIFFERS")
        snapshot = _read_snapshot(self.directory)
        require(snapshot.spec_sha256 == digest(self.spec), "METADATA_SPEC_DIFFERS")
        require(0 <= (now - snapshot.observed_at).total_seconds() <= 3600, "STALE_METADATA")
        require(hashlib.sha256(snapshot.calendar_csv.encode()).hexdigest() == protocol.binding.calendar_sha256,
                "CALENDAR_HASH_DIFFERS")
        rows = {kind: _rows(snapshot, kind) for kind in CSV_FIELDS}
        planned, bootstrap = _date_plan(snapshot, rows, self.spec, now)
        next_date = _calendar(rows["calendar"], plan, bootstrap)
        require(planned.watermark <= protocol.first_candidate_trade_date, "WATERMARK_AFTER_FIRST_DATE")
        counts = _attempts(rows, plan, snapshot.completed_receipts)
        claimed = self.store.load().claimed  # Claim authority only; never manufacture independent END proofs.
        accepted = snapshot.full_first_day_acceptance_verified
        require(not accepted or claimed, "UNOWNED_ACCEPTANCE")
        observation = FirstDayObservation(
            **snapshot.runtime.model_dump(), observed_at=snapshot.observed_at,
            calendar_next_trade_date=next_date, eligible_trade_date=planned.eligible_target,
            pending_trade_dates=planned.missing_trade_dates, attempts=counts,
            claim_state="ACCEPTED" if accepted else "CLAIMED" if claimed else "UNCLAIMED",
            full_first_day_acceptance_verified=accepted,
        )
        return CandidateEvidence(observation=observation, completed_receipts=snapshot.completed_receipts)
