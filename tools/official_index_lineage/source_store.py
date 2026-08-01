"""Serial, content-addressed retrieval for allow-listed official index sources."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from shaiwei.config import PROJECT_ROOT


class OfficialSourceError(RuntimeError):
    """Official material cannot be retrieved without weakening the frozen policy."""


@dataclass(frozen=True)
class SourceRecord:
    source_url: str
    final_url: str
    source_file_sha256: str
    byte_count: int
    media_type: str
    retrieved_at: str
    stored_name: str
    purpose: str
    parent_url: str | None
    title: str | None


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _suffix(url: str, media_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    allowed = {".html", ".shtml", ".pdf", ".xls", ".xlsx", ".doc", ".docx", ".wps"}
    if suffix in allowed:
        return suffix
    if "html" in media_type:
        return ".html"
    if "pdf" in media_type:
        return ".pdf"
    return ".bin"


class ContentAddressedFetcher:
    """Fetch official files with bounded retries, redirects and immutable storage."""

    _MARKER = b"\n__SHAIWEI_FETCH_METADATA__"

    def __init__(self, protocol: dict[str, object]) -> None:
        policy = protocol["official_source_policy"]
        identity = protocol["identity"]
        self.allowed_domains = set(policy["primary_domains"])
        self.interval = float(policy["minimum_request_interval_seconds"])
        self.attempts = int(policy["maximum_attempts"])
        self.retry_base = float(policy["retry_base_seconds"])
        self.maximum_bytes = int(policy["maximum_file_bytes"])
        self.raw_root = PROJECT_ROOT / str(identity["raw_source_root"])
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.raw_root / "retrieval_index.json"
        self.schema_version = "official-index-source-retrieval-v1"
        self.index_code = str(identity["index_code"])
        self._last_request_at: float | None = None
        self._state = self._load_state()

    def _load_state(self) -> dict[str, dict[str, object]]:
        if not self.state_path.exists():
            return {}
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != self.schema_version:
            raise OfficialSourceError("official retrieval schema mismatch")
        if payload.get("index_code") != self.index_code:
            raise OfficialSourceError("official retrieval index identity mismatch")
        return {item["source_url"]: item for item in payload.get("sources", [])}

    def _save_state(self) -> None:
        payload = {
            "schema_version": self.schema_version,
            "index_code": self.index_code,
            "sources": [self._state[url] for url in sorted(self._state)],
        }
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(_canonical_json(payload), encoding="utf-8")
        temporary.replace(self.state_path)

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in self.allowed_domains:
            raise OfficialSourceError(f"non-official URL rejected: {url}")

    def _throttle(self) -> None:
        if self._last_request_at is not None:
            remaining = self.interval - (time.monotonic() - self._last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at = time.monotonic()

    def _cached(self, url: str) -> tuple[bytes, SourceRecord] | None:
        cached = self._state.get(url)
        if not cached:
            return None
        path = self.raw_root / str(cached["stored_name"])
        if not path.is_file():
            raise OfficialSourceError(f"cached official source missing: {path.name}")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != cached["source_file_sha256"]:
            raise OfficialSourceError(f"cached source hash mismatch: {path.name}")
        record = SourceRecord(
            **{key: cached.get(key) for key in SourceRecord.__dataclass_fields__}
        )
        return content, record

    def fetch(
        self,
        url: str,
        *,
        purpose: str,
        parent_url: str | None = None,
        title: str | None = None,
    ) -> tuple[bytes, SourceRecord]:
        self._validate_url(url)
        cached = self._cached(url)
        if cached is not None:
            content, prior = cached
            expected = SourceRecord(
                **{
                    **asdict(prior),
                    "purpose": purpose,
                    "parent_url": parent_url,
                    "title": title,
                }
            )
            if expected != prior:
                self._state[url] = asdict(expected)
                self._save_state()
            return content, expected

        error: Exception | None = None
        for attempt in range(self.attempts):
            self._throttle()
            try:
                completed = subprocess.run(
                    [
                        "curl",
                        "--noproxy",
                        "*",
                        "--max-time",
                        "30",
                        "--silent",
                        "--show-error",
                        "--fail",
                        "--location",
                        "--max-filesize",
                        str(self.maximum_bytes),
                        "--write-out",
                        "\n__SHAIWEI_FETCH_METADATA__%{url_effective}\t%{content_type}",
                        url,
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                content, encoded_meta = completed.stdout.rsplit(self._MARKER, 1)
                final_url, media_type = encoded_meta.decode("utf-8").split("\t", 1)
                self._validate_url(final_url)
                if len(content) > self.maximum_bytes:
                    raise OfficialSourceError(f"official source exceeds byte limit: {url}")
                digest = hashlib.sha256(content).hexdigest()
                stored_name = f"{digest}{_suffix(final_url, media_type)}"
                path = self.raw_root / stored_name
                if path.exists() and path.read_bytes() != content:
                    raise OfficialSourceError(f"content-address collision: {stored_name}")
                if not path.exists():
                    temporary = path.with_suffix(path.suffix + ".tmp")
                    temporary.write_bytes(content)
                    temporary.replace(path)
                record = SourceRecord(
                    source_url=url,
                    final_url=final_url,
                    source_file_sha256=digest,
                    byte_count=len(content),
                    media_type=media_type,
                    retrieved_at=_utc_now(),
                    stored_name=stored_name,
                    purpose=purpose,
                    parent_url=parent_url,
                    title=title,
                )
                self._state[url] = asdict(record)
                self._save_state()
                return content, record
            except (OfficialSourceError, subprocess.CalledProcessError, ValueError) as exc:
                error = exc
                if attempt + 1 < self.attempts:
                    time.sleep(self.retry_base * (2**attempt))
        raise OfficialSourceError(f"official source failed after bounded retries: {url}") from error
