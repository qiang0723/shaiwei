"""Repository-wide credential and generated-data leak gates."""

import os
import re
import subprocess

from dotenv import load_dotenv

from shaiwei.config import PROJECT_ROOT


SECRET_ENV_KEYS = (
    "TUSHARE_TOKEN",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_TOKEN",
    "FEISHU_WEBHOOK_URL",
    "FEISHU_SIGNING_SECRET",
)
FORBIDDEN_TRACKED_PREFIXES = ("data/", "logs/")
SECRET_SHAPES = {
    "llm_api_key": re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9]{20,}"),
    "feishu_webhook": re.compile(
        rb"https://open\.feishu\.cn/open-apis/bot/v2/hook/[0-9a-fA-F-]{32,}"
    ),
}


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    return [value.decode() for value in result.stdout.split(b"\0") if value]


def test_local_secrets_and_generated_data_are_not_tracked():
    tracked = _tracked_files()
    assert ".env" not in tracked
    assert not [path for path in tracked if path.startswith(FORBIDDEN_TRACKED_PREFIXES)]

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    configured_secrets = {
        key: os.environ[key].encode()
        for key in SECRET_ENV_KEYS
        if len(os.environ.get(key, "")) >= 8
    }
    findings: dict[str, list[str]] = {}
    for relative_path in tracked:
        payload = (PROJECT_ROOT / relative_path).read_bytes()
        for key, secret in configured_secrets.items():
            if secret in payload:
                findings.setdefault(key, []).append(relative_path)
        for name, pattern in SECRET_SHAPES.items():
            if pattern.search(payload):
                findings.setdefault(name, []).append(relative_path)
    # Report only credential category and file path, never the matched value.
    assert not findings, f"tracked credential material detected: {findings}"
