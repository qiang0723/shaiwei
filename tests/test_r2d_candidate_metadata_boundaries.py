"""Adversarial fixture paths, immutable capture, planner gaps and independent proofs."""

from contextlib import contextmanager
from datetime import timedelta
import json
from pathlib import Path

import pytest

from shaiwei.r2d_candidate_contract import PhaseReceipt, StageError
from shaiwei.r2d_candidate_metadata import OfflineMetadataReader
from test_r2d_candidate_metadata import APIS, CALENDAR, FileWorld, csv_text
from test_r2d_candidate_runner import fixture_directory as fixture_directory
from test_r2d_post_close_contract import change


@pytest.mark.parametrize("fault", ["project", "test_root", "traversal", "directory_link", "file_link", "hardlink"])
def test_reader_path_boundary_before_open(fixture_directory, fault, monkeypatch):
    world = FileWorld(fixture_directory)
    directory = fixture_directory
    if fault == "project":
        directory = Path(__file__).resolve().parents[1]
    elif fault == "test_root":
        directory = fixture_directory.parent
    elif fault == "traversal":
        directory = fixture_directory / ".." / fixture_directory.name
    elif fault == "directory_link":
        directory = fixture_directory / "directory-link"
        directory.symlink_to(fixture_directory, target_is_directory=True)
    else:
        retained = world.path.with_name("retained-original.json")
        world.path.rename(retained)
        if fault == "file_link":
            world.path.symlink_to(retained)
        else:
            world.path.hardlink_to(retained)

    opened = []

    def forbidden(*args, **kwargs):
        opened.append(args)
        raise AssertionError("invalid path must fail before bytes are read")

    monkeypatch.setattr(Path, "open", forbidden)
    reader = OfflineMetadataReader(directory, world.spec, world.store)
    with pytest.raises(StageError, match="^OFFLINE_METADATA_INVALID$"):
        reader.read(world.plan, now=world.now)
    assert opened == []  # A sanitized exception must not conceal an attempted read.


def test_capture_changed_during_read_rejected(fixture_directory, monkeypatch):
    world = FileWorld(fixture_directory)
    original = Path.open

    @contextmanager
    def intercepted(path, *args, **kwargs):
        with original(path, *args, **kwargs) as stream:
            yield stream
        if path == world.path and args == ("rb",):
            with original(path, "ab") as writer:
                writer.write(b" ")

    monkeypatch.setattr(Path, "open", intercepted)
    with pytest.raises(StageError, match="^OFFLINE_METADATA_INVALID$"):
        world.read_file()


@pytest.mark.parametrize("missing", ["metadata", "journal"])
def test_missing_file_not_recreated(fixture_directory, missing):
    world = FileWorld(fixture_directory)
    path = world.path if missing == "metadata" else world.store.path
    path.rename(path.with_name("retained-" + path.name))
    with pytest.raises(StageError):
        world.tick()
    assert not path.exists()
    assert world.factory_calls == 0


@pytest.mark.parametrize("spec_change", [{"ready_hour": 17}, {"plan_sha256": "f" * 64}])
def test_planning_spec_must_match_plan(fixture_directory, spec_change):
    world = FileWorld(fixture_directory)
    world.spec = change(world.spec, **spec_change)
    with pytest.raises(StageError, match="METADATA"):
        world.tick()
    assert world.store.load().sequence == 0


def test_full_calendar_does_not_hide_old_pending_date(fixture_directory):
    calendar = CALENDAR.replace("cal_date,is_open\n", "cal_date,is_open\n20260917,1\n")
    world = FileWorld(fixture_directory, calendar=calendar)
    world.publish(ingest_csv=csv_text("ingest", [(api, json.dumps({"end_date": "20260917"})) for api in APIS]))
    assert world.read_file().observation.pending_trade_dates == ("20260918", "20260921")
    with pytest.raises(ValueError, match="OLD_OR_MULTIPLE_PENDING"):
        world.tick()
    assert world.store.load().sequence == 0


@pytest.mark.parametrize("rows", [
    [(APIS[0], '{"end_date":"20260918"}')],
    [(api, '{"end_date":"20260918"}') for api in (*APIS, APIS[0])],
    [(api, '{"end_date":"20260918","path":"private-value"}') for api in APIS],
    [(api, '{"end_date":"20260918","end_date":"20260921"}') for api in APIS],
])
def test_bootstrap_exact_white_list(fixture_directory, rows):
    world = FileWorld(fixture_directory)
    world.publish(ingest_csv=csv_text("ingest", rows))
    with pytest.raises(StageError, match="OFFLINE_METADATA_INVALID"):
        world.read_file()


@pytest.mark.parametrize("fault", ["swapped", "duplicate", "unknown", "failed"])
def test_paper_accounts_cannot_substitute_count_for_proof(fixture_directory, fault):
    world = FileWorld(fixture_directory)
    code = world.plan.rehearsal.post_close.binding.candidate_code_sha256
    receipt = PhaseReceipt(plan_sha256="a" * 64, trade_date="20260921", phase="PAPER_BASELINE",
                           begin_sha256="b" * 64, evidence_sha256="c" * 64, outcome="PASS")
    rows = [("20260921", "PASS", code, "model_baseline")]
    if fault == "swapped":
        rows[0] = (*rows[0][:3], "model_top20")
    elif fault == "duplicate":
        rows *= 2
    elif fault == "unknown":
        rows[0] = (*rows[0][:3], "unknown")
    else:
        rows[0] = ("20260921", "FAIL", code, "model_baseline")
    world.publish(paper_csv=csv_text("paper", rows), completed_receipts=(receipt,))
    with pytest.raises(StageError, match="OFFLINE_METADATA_INVALID"):
        world.read_file()


def test_missing_independent_receipt_after_completion_not_rebuilt_from_journal(fixture_directory):
    world = FileWorld(fixture_directory)
    world.tick()
    world.publish(completed_receipts=world.snapshot.completed_receipts[:-1])
    with pytest.raises(StageError, match="INDEPENDENT_PHASE_PROOF_DIFFERS"):
        world.tick()
    assert len(world.calls) == 10


def test_identity_is_rechecked_before_next_phase(fixture_directory):
    world = FileWorld(fixture_directory)
    original = world.execute

    def drifting(**kwargs):
        receipt = original(**kwargs)
        if receipt.phase == "DAILY":
            runtime = world.snapshot.runtime
            world.publish(runtime=change(runtime, binding=change(runtime.binding, state_sha256="0" * 64)))
        return receipt

    world.execute = drifting
    with pytest.raises(StageError, match="RUNTIME_IDENTITY_DRIFT"):
        world.tick()
    assert world.calls == ["READINESS", "DAILY"]


def test_naive_clock_and_stale_capture_do_not_get_retimestamped(fixture_directory):
    world = FileWorld(fixture_directory)
    world.now = world.now.replace(tzinfo=None)
    with pytest.raises(StageError, match="OFFLINE_METADATA_INVALID"):
        world.read_file()
    world.now = world.snapshot.observed_at + timedelta(seconds=3601)
    with pytest.raises(StageError, match="OFFLINE_METADATA_INVALID"):
        world.read_file()
    assert world.store.load().sequence == 0
