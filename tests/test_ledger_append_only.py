"""check-ledger：同时约束提交历史、暂存候选和工作树的账本追加性。"""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
EXCEPTIONS_PATH = ROOT / "config/ledger_append_only_exceptions_v1.json"
EXPECTED_EXCEPTIONS_SHA256 = "67b2dc3861d54b77a132f880c21d74856e25457d5487f23b7e4da8138f52adcb"
LEDGERS = [
    "ledger/experiments.csv",
    "ledger/ingest_batches.csv",
    "ledger/daily_runs.csv",
    "ledger/shadow_runs.csv",
    "ledger/shadow_reconciliations.csv",
    "ledger/factor_admissions.csv",
    "ledger/llm_factor_attempts.csv",
    "ledger/llm_factor_transports.csv",
    "ledger/llm_factor_attempts_v2.csv",
    "ledger/llm_factor_transports_v2.csv",
    "ledger/llm_factor_reviews.csv",
    "ledger/llm_factor_review_transports.csv",
    "ledger/m1_star50_factor_attempts.csv",
    "ledger/m1_star50_factor_transports.csv",
    "ledger/m1_star50_factor_reviews.csv",
    "ledger/m1_star50_factor_review_transports.csv",
    "ledger/m3_multi_pool_factor_attempts.csv",
    "ledger/m3_multi_pool_factor_transports.csv",
    "ledger/m3_multi_pool_factor_reviews.csv",
    "ledger/m3_multi_pool_factor_review_transports.csv",
    "ledger/paper_accounts.csv",
    "ledger/paper_events.csv",
    "ledger/paper_runs.csv",
    "ledger/g8_fund_evidence.csv",
]


def _git_text(spec: str) -> str | None:
    result = subprocess.run(
        ["git", "show", spec], cwd=ROOT, capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else None


def _git_bytes(spec: str) -> bytes | None:
    result = subprocess.run(["git", "show", spec], cwd=ROOT, capture_output=True)
    return result.stdout if result.returncode == 0 else None


def _rev_parse(spec: str) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", spec], cwd=ROOT, capture_output=True, text=True
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _exceptions() -> list[dict[str, str]]:
    assert _sha256(EXCEPTIONS_PATH.read_bytes()) == EXPECTED_EXCEPTIONS_SHA256
    document = json.loads(EXCEPTIONS_PATH.read_text(encoding="utf-8"))
    assert document["schema_version"] == "ledger-append-only-exceptions-v1"
    assert document["policy"] == "EXACT_ONE_TIME_NON_PREFIX_REPAIR_ONLY"
    return document["exceptions"]


def _assert_header_only(content: str, path: str, source: str) -> None:
    assert content.count("\n") == 1, (
        f"{path}: {source} 中新账本必须只含 schema 表头，不能夹带历史数据"
    )


def _assert_prefix(older: str, newer: str, message: str) -> None:
    assert newer.startswith(older), message


def _matching_exception(parent: str, commit: str, path: str) -> dict[str, str] | None:
    matches = [
        item
        for item in _exceptions()
        if (item["parent_commit"], item["commit"], item["path"])
        == (parent, commit, path)
    ]
    assert len(matches) <= 1, f"{path}: 非前缀例外记录重复"
    return matches[0] if matches else None


def test_git_baseline_exists():
    repo = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True
    )
    assert repo.returncode == 0 and repo.stdout.strip() == "true", "repository is not initialized"
    head = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"], capture_output=True, text=True
    )
    assert head.returncode == 0, "baseline commit is missing"


@pytest.mark.parametrize("path", LEDGERS)
def test_head_index_worktree_prefix_chain(path):
    """测试提交前真正会进入 commit 的 index，而非只看完整工作树。"""

    head = _git_text(f"HEAD:{path}")
    index = _git_text(f":{path}")
    assert index is not None, f"{path}: Git index 中缺少受控账本"
    working = (ROOT / path).read_text(encoding="utf-8")
    if head is None:
        _assert_header_only(index, path, "Git index")
    else:
        _assert_prefix(head, index, f"{path}: Git index 修改或删除了 HEAD 历史行")
    _assert_prefix(index, working, f"{path}: 工作树不是 Git index 的追加延伸")


@pytest.mark.parametrize("path", LEDGERS)
def test_parent_to_head_committed_prefix(path):
    """提交后复核父提交到 HEAD；非前缀变化只能命中精确的一次性例外。"""

    commit = _rev_parse("HEAD")
    parent = _rev_parse("HEAD^")
    assert commit is not None
    if parent is None:
        pytest.skip("root commit has no parent")
    before = _git_bytes(f"{parent}:{path}")
    after = _git_bytes(f"{commit}:{path}")
    assert after is not None, f"{path}: HEAD 中缺少受控账本"
    if before is None:
        _assert_header_only(after.decode("utf-8"), path, "HEAD")
        return
    if after.startswith(before):
        return
    exception = _matching_exception(parent, commit, path)
    assert exception is not None, f"{path}: HEAD 不是父提交的追加延伸且无精确例外"
    assert _sha256(before) == exception["parent_blob_sha256"]
    assert _sha256(after) == exception["commit_blob_sha256"]


def test_declared_non_prefix_exceptions_are_exact_and_immutable():
    exceptions = _exceptions()
    assert len(exceptions) == 1, "只允许已登记的单次基线纠偏，不允许扩大例外集合"
    required = {
        "commit",
        "commit_blob_sha256",
        "parent_commit",
        "parent_blob_sha256",
        "path",
        "reason_document",
        "reason_document_sha256",
        "receipt_path",
        "receipt_sha256",
    }
    for item in exceptions:
        assert set(item) == required
        assert item["path"] in LEDGERS and "*" not in item["path"]
        assert _rev_parse(item["commit"]) == item["commit"]
        assert _rev_parse(f"{item['commit']}^") == item["parent_commit"]
        before = _git_bytes(f"{item['parent_commit']}:{item['path']}")
        after = _git_bytes(f"{item['commit']}:{item['path']}")
        assert before is not None and after is not None
        assert not after.startswith(before), "前缀提交不需要例外"
        assert _sha256(before) == item["parent_blob_sha256"]
        assert _sha256(after) == item["commit_blob_sha256"]
        for path_key, sha_key in (
            ("receipt_path", "receipt_sha256"),
            ("reason_document", "reason_document_sha256"),
        ):
            evidence = ROOT / item[path_key]
            assert evidence.is_file()
            assert _sha256(evidence.read_bytes()) == item[sha_key]


def test_partial_index_staging_is_rejected_by_prefix_chain():
    """回归：旧 HEAD + 局部补录不能冒充完整工作树候选。"""

    head = "schema\nnatural-old\n"
    index = head + "historical-reconciliation\n"
    working = head + "natural-uncommitted\nhistorical-reconciliation\n"
    _assert_prefix(head, index, "fixture HEAD -> index should pass")
    with pytest.raises(AssertionError, match="工作树不是 Git index"):
        _assert_prefix(index, working, "工作树不是 Git index 的追加延伸")
