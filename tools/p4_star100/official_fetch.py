"""Discover and immutably retrieve official Star100 lineage materials."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import yaml

from shaiwei.config import PROJECT_ROOT
from tools.p4_star100.contract import PROTOCOL_PATH, sha256_file, tool_snapshot_sha256

ARCHIVE_URL = "https://www.sse.com.cn/market/sseindex/diclosure/"


class OfficialFetchError(RuntimeError):
    """Raised when official evidence cannot be retrieved without weakening policy."""


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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _suffix(url: str, media_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".html", ".shtml", ".pdf", ".xls", ".xlsx", ".doc", ".docx", ".wps"}:
        return suffix
    if "html" in media_type:
        return ".html"
    if "pdf" in media_type:
        return ".pdf"
    return ".bin"


class CurlFetcher:
    """Serial content-addressed official-source fetcher for the frozen P4 policy."""

    _MARKER = b"\n__SHAIWEI_FETCH_METADATA__"

    def __init__(self, protocol: dict[str, object]) -> None:
        policy = protocol["official_source_policy"]
        self.allowed_domains = set(policy["primary_domains"])
        self.interval = float(policy["minimum_request_interval_seconds"])
        self.attempts = int(policy["maximum_attempts"])
        self.retry_base = float(policy["retry_base_seconds"])
        self.maximum_bytes = int(policy["maximum_file_bytes"])
        self.raw_root = PROJECT_ROOT / str(protocol["identity"]["raw_source_root"])
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.raw_root / "retrieval_index.json"
        self._last_request_at: float | None = None
        self._state = self._load_state()

    def _load_state(self) -> dict[str, dict[str, object]]:
        if not self.state_path.exists():
            return {}
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "p4-star100-official-retrieval-v1":
            raise OfficialFetchError("unexpected official retrieval state schema")
        return {item["source_url"]: item for item in payload.get("sources", [])}

    def _save_state(self) -> None:
        payload = {
            "schema_version": "p4-star100-official-retrieval-v1",
            "sources": [self._state[url] for url in sorted(self._state)],
        }
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(_canonical_json(payload), encoding="utf-8")
        temporary.replace(self.state_path)

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in self.allowed_domains:
            raise OfficialFetchError(f"non-official URL rejected: {url}")

    def _throttle(self) -> None:
        if self._last_request_at is not None:
            remaining = self.interval - (time.monotonic() - self._last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at = time.monotonic()

    def _read_cached(self, url: str) -> tuple[bytes, SourceRecord] | None:
        cached = self._state.get(url)
        if not cached:
            return None
        path = self.raw_root / str(cached["stored_name"])
        if not path.is_file():
            raise OfficialFetchError(f"cached official source missing: {path.name}")
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != cached["source_file_sha256"]:
            raise OfficialFetchError(f"cached official source hash mismatch: {path.name}")
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
        cached = self._read_cached(url)
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
                    raise OfficialFetchError(f"official source exceeds byte limit: {url}")
                digest = hashlib.sha256(content).hexdigest()
                stored_name = f"{digest}{_suffix(final_url, media_type)}"
                path = self.raw_root / stored_name
                if path.exists() and path.read_bytes() != content:
                    raise OfficialFetchError(f"content-address collision: {stored_name}")
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
            except (OfficialFetchError, subprocess.CalledProcessError, ValueError) as exc:
                error = exc
                if attempt + 1 < self.attempts:
                    time.sleep(self.retry_base * (2**attempt))
        raise OfficialFetchError(
            f"official source failed after {self.attempts} attempts: {url}"
        ) from error


def _archive_page_url(page_number: int) -> str:
    if page_number == 1:
        return ARCHIVE_URL + "s_list.shtml"
    return ARCHIVE_URL + f"s_list_{page_number}.shtml"


def _announcement_rows(content: bytes) -> list[dict[str, str]]:
    soup = BeautifulSoup(content, "html.parser")
    rows: dict[str, dict[str, str]] = {}
    for anchor in soup.select('a[href*="/market/sseindex/diclosure/c/c_"]'):
        href = urljoin(ARCHIVE_URL, anchor.get("href", ""))
        name = Path(urlparse(href).path).name
        parts = name.split("_")
        if len(parts) < 3 or len(parts[1]) != 8 or not parts[1].isdigit():
            continue
        rows[href] = {
            "announcement_date": parts[1],
            "source_url": href,
            "title": html.unescape(anchor.get("title") or anchor.get_text(" ", strip=True)),
        }
    return [rows[url] for url in sorted(rows)]


def _is_candidate(row: dict[str, str], protocol: dict[str, object]) -> bool:
    url = row["source_url"]
    title = row["title"]
    explicit_urls = {
        str(protocol["official_source_policy"]["launch_announcement_url"]),
        str(protocol["official_source_policy"]["methodology_revision_url"]),
    }
    if url in explicit_urls:
        return True
    adjustment = "调整" in title and ("样本" in title or "定期调整结果" in title)
    temporary = "临时调整" in title
    return title.startswith("关于") and (adjustment or temporary)


def _attachment_urls(content: bytes, parent_url: str) -> list[str]:
    soup = BeautifulSoup(content, "html.parser")
    suffixes = (".pdf", ".xlsx", ".xls", ".docx", ".wps")
    urls = set()
    for anchor in soup.select("a[href]"):
        href = urljoin(parent_url, anchor.get("href", ""))
        if urlparse(href).path.lower().endswith(suffixes):
            urls.add(href)
    return sorted(urls)


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def discover(fetcher: CurlFetcher, protocol: dict[str, object]) -> dict[str, object]:
    start = str(protocol["official_source_policy"]["discovery_start_date"]).replace("-", "")
    end = str(protocol["official_source_policy"]["discovery_end_date"]).replace("-", "")
    archive_records = []
    archive_boundaries: list[dict[str, object]] = []
    candidate_rows: dict[str, dict[str, str]] = {}
    crossed_start = False
    for page_number in range(1, 100):
        url = _archive_page_url(page_number)
        content, record = fetcher.fetch(url, purpose="official_archive_listing")
        archive_records.append(record)
        rows = _announcement_rows(content)
        dates = [row["announcement_date"] for row in rows]
        archive_boundaries.append(
            {
                "page_number": page_number,
                "source_url": url,
                "source_file_sha256": record.source_file_sha256,
                "entry_count": len(rows),
                "newest_announcement_date": max(dates) if dates else None,
                "oldest_announcement_date": min(dates) if dates else None,
            }
        )
        for row in rows:
            if start <= row["announcement_date"] <= end and _is_candidate(row, protocol):
                candidate_rows[row["source_url"]] = row
        if dates and max(dates) < start:
            crossed_start = True
            break
    else:
        raise OfficialFetchError("official archive discovery exceeded bounded page limit")
    if not crossed_start:
        raise OfficialFetchError("official archive scan did not cross the launch boundary")

    explicit = (
        ("launch_announcement_url", "launch_publication"),
        ("methodology_revision_url", "methodology_revision"),
    )
    for key, purpose in explicit:
        url = str(protocol["official_source_policy"][key])
        candidate_rows.setdefault(
            url,
            {
                "announcement_date": "20230721" if purpose == "launch_publication" else "20250226",
                "source_url": url,
                "title": purpose,
            },
        )

    page_records = []
    attachment_records = []
    classified_pages = []
    launch_url = str(protocol["official_source_policy"]["launch_announcement_url"])
    revision_url = str(protocol["official_source_policy"]["methodology_revision_url"])
    for url, row in sorted(candidate_rows.items(), key=lambda item: (item[1]["announcement_date"], item[0])):
        purpose = (
            "launch_publication"
            if url == launch_url
            else "methodology_revision"
            if url == revision_url
            else "adjustment_candidate"
        )
        content, record = fetcher.fetch(url, purpose=purpose, title=row["title"])
        page_records.append(record)
        attachments = _attachment_urls(content, url)
        classified_pages.append(
            {
                "announcement_date": row["announcement_date"],
                "source_url": url,
                "title": row["title"],
                "purpose": purpose,
                "attachment_count": len(attachments),
            }
        )
        for attachment_url in attachments:
            _, attachment = fetcher.fetch(
                attachment_url,
                purpose="official_attachment",
                parent_url=url,
                title=row["title"],
            )
            attachment_records.append(attachment)

    current_methodology_url = str(protocol["official_source_policy"]["current_methodology_url"])
    if current_methodology_url not in {record.source_url for record in attachment_records}:
        _, record = fetcher.fetch(
            current_methodology_url,
            purpose="official_attachment",
            parent_url=revision_url,
            title="current_methodology_v1_1",
        )
        attachment_records.append(record)

    payload = {
        "schema_version": "p4-star100-official-discovery-v1",
        "protocol_sha256": sha256_file(PROTOCOL_PATH),
        "tool_snapshot_sha256": tool_snapshot_sha256(),
        "source_cutoff_date": protocol["identity"]["source_cutoff_date"],
        "archive_scan_crossed_launch_boundary": crossed_start,
        "archive_page_count": len(archive_records),
        "candidate_page_count": len(page_records),
        "attachment_count": len(attachment_records),
        "archive_boundaries": archive_boundaries,
        "classified_pages": classified_pages,
        "sources": [asdict(record) for record in [*archive_records, *page_records, *attachment_records]],
    }
    rendered = _canonical_json(payload)
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    report_path = fetcher.raw_root.parent / f"official-discovery-{digest[:12]}.json"
    if report_path.exists() and report_path.read_text(encoding="utf-8") != rendered:
        raise OfficialFetchError("immutable discovery report differs")
    report_path.write_text(rendered, encoding="utf-8")
    return {**payload, "discovery_report": str(report_path.relative_to(PROJECT_ROOT))}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol_path = args.protocol if args.protocol.is_absolute() else PROJECT_ROOT / args.protocol
    protocol = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    fetcher = CurlFetcher(protocol)
    payload = discover(fetcher, protocol)
    print(
        json.dumps(
            {
                "status": "OFFICIAL_DISCOVERY_CAPTURED",
                "archive_page_count": payload["archive_page_count"],
                "candidate_page_count": payload["candidate_page_count"],
                "attachment_count": payload["attachment_count"],
                "discovery_report": payload["discovery_report"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
