"""File-backed synthetic metadata and composition tests; no live data or business."""

import csv
from datetime import timedelta
import hashlib
from io import StringIO
import json
from pathlib import Path

import pytest

from shaiwei.r2d_candidate_app import run_fixture_candidate
from shaiwei.r2d_candidate_contract import PHASES, CandidatePlan, StageError, digest
from shaiwei.r2d_candidate_metadata import (
    CSV_FIELDS, FixtureMetadataSnapshot, FixtureMetadataSpec, FixtureRuntimeWitness,
    OfflineMetadataReader,
)
from shaiwei.r2d_candidate_store import OfflineStageStore
from test_r2d_candidate_runner import World, fixture_directory as fixture_directory
from test_r2d_parking_rehearsal import first_day
from test_r2d_post_close_contract import change, dt

CALENDAR = "cal_date,is_open\n20260918,1\n20260919,0\n20260920,0\n20260921,1\n20260922,1\n"
APIS = ("tushare.daily", "tushare.adj_factor", "tushare.daily_basic", "tushare.index_daily")


def csv_text(kind, rows):
    stream = StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CSV_FIELDS[kind])
    writer.writerows(rows)
    return stream.getvalue()


class FileWorld(World):
    def __init__(self, directory, *, calendar=CALENDAR):
        rehearsal, observation, self.now = first_day()
        binding = change(rehearsal.post_close.binding, calendar_sha256=hashlib.sha256(calendar.encode()).hexdigest())
        rehearsal = change(rehearsal, post_close=change(rehearsal.post_close, binding=binding))
        self.plan = CandidatePlan(
            schema_version="r2d-candidate-offline-v1", mode="OFFLINE_FIXTURE_ONLY",
            rehearsal=rehearsal, max_readiness_checks=3,
        )
        self.store = OfflineStageStore(directory, self.plan)
        self.store.create()
        self.spec = FixtureMetadataSpec(schema_version="r2d-fixture-metadata-spec-v1",
                                        plan_sha256=digest(self.plan), ready_hour=16,
                                        ready_minute=0, max_catchup_trade_days=120)
        runtime = FixtureRuntimeWitness(**{key: value for key, value in
                                          change(observation, binding=binding).model_dump().items()
                                          if key in FixtureRuntimeWitness.model_fields})
        self.snapshot = FixtureMetadataSnapshot(
            schema_version="r2d-fixture-metadata-v1", mode="OFFLINE_FIXTURE_ONLY",
            spec_sha256=digest(self.spec), observed_at=self.now, runtime=runtime,
            calendar_csv=calendar,
            ingest_csv=csv_text("ingest", [(api, json.dumps({"end_date": "20260918"})) for api in APIS]),
            daily_csv=csv_text("daily", []), shadow_csv=csv_text("shadow", []), paper_csv=csv_text("paper", []),
            completed_receipts=(), full_first_day_acceptance_verified=False,
        )
        self.path = directory / "r3n-metadata.json"
        self.calls, self.receipts = [], []
        self.factory_calls = 0
        self.ready, self.crash_phase, self.receipt_change = True, None, None
        self.publish()

    def publish(self, **updates):
        self.snapshot = change(self.snapshot, **updates)
        self.path.write_text(self.snapshot.model_dump_json(), encoding="utf-8")

    def read_file(self):
        return OfflineMetadataReader(self.store.directory, self.spec, self.store).read(self.plan, now=self.now)

    def execute(self, **kwargs):
        receipt = super().execute(**kwargs)
        phase = receipt.phase
        code = self.plan.rehearsal.post_close.binding.candidate_code_sha256
        updates = dict(completed_receipts=tuple(self.receipts), observed_at=self.now)
        if phase == "DAILY":
            updates["daily_csv"] = csv_text("daily", [("20260921", "PASS")])
        if phase == "SHADOW":
            updates["shadow_csv"] = csv_text("shadow", [("20260921", "PASS", code)])
        accounts = [("PAPER_BASELINE", "model_baseline"), ("PAPER_TOP20", "model_top20")]
        if phase in {item[0] for item in accounts}:
            phases = {item.phase for item in self.receipts}
            updates["paper_csv"] = csv_text("paper", [("20260921", "PASS", code, account)
                                                      for stage, account in accounts if stage in phases])
        if phase == "FINAL_ACCEPTANCE":
            updates["full_first_day_acceptance_verified"] = True
        self.publish(**updates)
        return receipt

    def tick(self, ingress="scheduler"):
        return run_fixture_candidate(
            ingress=ingress, directory=self.store.directory, plan=self.plan,
            metadata_spec=self.spec, business_factory=self.factory, clock=lambda: self.now,
        )


def test_real_planner_and_csv_projection(fixture_directory, monkeypatch):
    import shaiwei.config as config
    import shaiwei.pipeline.daily as daily

    world = FileWorld(fixture_directory)
    original = daily.build_plan
    calls = []

    def observed(**kwargs):
        assert not isinstance(kwargs["daily_ledger_path"], Path)
        assert not isinstance(kwargs["ingest_ledger_path"], Path)
        calls.append(kwargs["now"])
        return original(**kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("must not load runtime settings or dispatch real business")

    monkeypatch.setattr(daily, "build_plan", observed)
    for module, name in ((config, "load"), (daily, "load"), (daily, "run_once"),
                         (daily, "create_client"), (daily, "load_latest_api")):
        monkeypatch.setattr(module, name, forbidden)
    evidence = world.read_file()
    assert evidence.observation.pending_trade_dates == ("20260921",)
    assert evidence.observation.calendar_next_trade_date == "20260921"
    assert evidence.observation.attempts.model_dump() == dict(daily=0, shadow=0, paper=0)
    assert calls == [world.now]
    assert world.factory_calls == 0 and world.store.load().sequence == 0


@pytest.mark.parametrize("now,pending,eligible", [
    ("2026-09-18T22:00:00+08:00", (), "20260918"),
    ("2026-09-19T22:00:00+08:00", (), "20260919"),
    ("2026-09-21T15:59:59+08:00", (), "20260920"),
])
def test_parked_uses_actual_cutoff_and_no_business(fixture_directory, now, pending, eligible):
    world = FileWorld(fixture_directory)
    world.now = dt(now)
    world.publish(observed_at=world.now)
    evidence = world.read_file()
    assert evidence.observation.pending_trade_dates == pending
    assert evidence.observation.eligible_trade_date == eligible
    before = world.path.read_bytes()
    assert world.tick().status == "PARKED"
    assert world.path.read_bytes() == before
    assert world.store.load().sequence == world.factory_calls == 0


def test_composed_full_cycle_and_reopen_without_replay(fixture_directory):
    world = FileWorld(fixture_directory)
    assert world.tick().status == "OFFLINE_FIRST_DAY_COMPLETE"
    assert world.calls == list(PHASES)
    world.reopen()
    assert world.tick().production_authorized is False
    assert world.calls == list(PHASES)
    evidence = world.read_file()
    assert evidence.observation.claim_state == "ACCEPTED"
    assert evidence.observation.pending_trade_dates == ()


def test_waiting_source_same_claim_and_file_refresh(fixture_directory):
    world = FileWorld(fixture_directory)
    world.ready = False
    assert world.tick().status == "WAITING_SOURCE"
    assert world.calls == ["READINESS"]
    world.now += timedelta(minutes=1)
    world.publish(observed_at=world.now)
    world.ready = True
    assert world.tick().status == "OFFLINE_FIRST_DAY_COMPLETE"
    assert world.store.load().readiness_checks == 2
    assert world.calls.count("DAILY") == 1


@pytest.mark.parametrize("ingress", ["daily", "shadow", "paper", "verify", "acceptance", "unknown"])
def test_composition_denies_before_any_file_access(fixture_directory, ingress, monkeypatch):
    world = FileWorld(fixture_directory)

    def forbidden(*args, **kwargs):
        raise AssertionError("must reject before opening anything")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(OfflineStageStore, "__init__", forbidden)
    with pytest.raises(StageError, match="INGRESS"):
        world.tick(ingress)


@pytest.mark.parametrize("kind", list(CSV_FIELDS))
@pytest.mark.parametrize("fault", ["extra", "duplicate", "missing", "longrow"])
def test_csv_whitelist_is_exact(fixture_directory, kind, fault):
    world = FileWorld(fixture_directory)
    value = getattr(world.snapshot, kind + "_csv")
    header, tail = value.split("\n", 1)
    if fault == "extra":
        value = header + ",effect\n" + tail
    elif fault == "duplicate":
        value = header + "," + header.split(",")[0] + "\n" + tail
    elif fault == "missing":
        value = header.split(",")[0] + "\n" + tail
    else:
        value += ",".join(["private-value"] * (len(CSV_FIELDS[kind]) + 1)) + "\n"
    world.publish(**{kind + "_csv": value})
    with pytest.raises(StageError, match="^OFFLINE_METADATA_INVALID$"):
        world.read_file()
    assert world.factory_calls == 0


@pytest.mark.parametrize("update", [
    {"spec_sha256": "f" * 64},
    {"calendar_csv": CALENDAR + "20260923,1\n"},
    {"observed_at": dt("2026-09-21T14:59:59+08:00")},
    {"observed_at": dt("2026-09-21T16:00:01+08:00")},
    {"daily_csv": "target_trade_date,status\n20260921,FAIL\n"},
    {"daily_csv": "target_trade_date,status\n20260922,PASS\n"},
    {"daily_csv": "target_trade_date,status\n20260230,PASS\n"},
    {"shadow_csv": "trade_date,status,code_snapshot_sha256\n20260921,PASS," + "c" * 64 + "\n"},
    {"full_first_day_acceptance_verified": True},
])
def test_metadata_mismatch_blocks_without_claim(fixture_directory, update):
    world = FileWorld(fixture_directory)
    world.publish(**update)
    with pytest.raises(StageError, match="METADATA"):
        world.tick()
    assert world.store.load().sequence == world.factory_calls == 0


@pytest.mark.parametrize("calendar", [
    CALENDAR.replace("20260920,0\n", ""),
    CALENDAR + "20260921,1\n",
    CALENDAR.replace("20260920,0", "20260920,1"),
    CALENDAR.replace("20260921,1", "20260921,0"),
    CALENDAR.replace("20260919,0", "20260919,2"),
])
def test_bad_calendar_even_with_matching_frozen_hash(fixture_directory, calendar):
    world = FileWorld(fixture_directory, calendar=calendar)
    with pytest.raises(StageError, match="OFFLINE_METADATA_INVALID"):
        world.read_file()


@pytest.mark.parametrize("value", ["20260921", "20260917", "bad-date"])
def test_bootstrap_does_not_hide_first_day_or_missing_calendar(fixture_directory, value):
    world = FileWorld(fixture_directory)
    world.publish(ingest_csv=csv_text("ingest", [(api, json.dumps({"end_date": value})) for api in APIS]))
    with pytest.raises(StageError, match="OFFLINE_METADATA_INVALID"):
        world.read_file()


@pytest.mark.parametrize("fault", ["effect", "duplicate_json", "bad_json", "wrong_mode", "oversized"])
def test_raw_json_failures_are_sanitized(fixture_directory, fault):
    world = FileWorld(fixture_directory)
    raw = world.snapshot.model_dump_json()
    if fault == "effect":
        raw = raw[:-1] + ',"effect":"private-value"}'
    elif fault == "duplicate_json":
        raw = raw[:-1] + ',"mode":"OFFLINE_FIXTURE_ONLY"}'
    elif fault == "bad_json":
        raw = "private-value-invalid-json"
    elif fault == "wrong_mode":
        raw = raw.replace("OFFLINE_FIXTURE_ONLY", "PRODUCTION")
    else:
        raw = "x" * (2 * 1024 * 1024 + 1)
    world.path.write_text(raw)
    with pytest.raises(StageError) as error:
        world.read_file()
    assert str(error.value) == "OFFLINE_METADATA_INVALID"


@pytest.mark.parametrize("phase", PHASES)
def test_composed_crash_retains_unknown_no_replay(fixture_directory, phase):
    world = FileWorld(fixture_directory)
    world.crash_phase = phase
    with pytest.raises(SystemExit):
        world.tick()
    before = list(world.calls)
    world.crash_phase = None
    world.reopen()
    with pytest.raises(StageError, match="MAY_HAVE_WRITTEN"):
        world.tick()
    assert world.calls == before
