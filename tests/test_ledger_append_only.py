"""check-ledger：账本只准尾部追加。用 git HEAD 版本作为前缀基准，历史行必须逐字节保留。"""
import subprocess
from pathlib import Path
import pytest

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
    "ledger/paper_accounts.csv",
    "ledger/paper_events.csv",
    "ledger/paper_runs.csv",
    "ledger/g8_fund_evidence.csv",
]


def test_git_baseline_exists():
    repo = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True
    )
    assert repo.returncode == 0 and repo.stdout.strip() == "true", "repository is not initialized"
    head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], capture_output=True, text=True)
    assert head.returncode == 0, "baseline commit is missing"

@pytest.mark.parametrize("path", LEDGERS)
def test_append_only(path):
    r = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True, text=True)
    if r.returncode != 0:
        # A ledger introduced by the current commit has no historical prefix
        # yet.  It must contain only its schema header; subsequent commits are
        # checked byte-for-byte against that committed baseline.
        assert Path(path).read_text(encoding="utf-8").count("\n") == 1
        return
    old = r.stdout
    new = Path(path).read_text(encoding="utf-8")
    assert new.startswith(old), f"{path}: 历史行被修改或删除 —— 账本只准追加"
