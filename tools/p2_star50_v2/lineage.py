"""Parse official Star50 sources and build the PIT membership lineage gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from bs4 import BeautifulSoup
import pandas as pd
from pypdf import PdfReader
import yaml

from shaiwei.config import PROJECT_ROOT
from shaiwei.ingest.catalog import load_latest_api
from tools.p2_star50.contract import sha256_file
from tools.p2_star50_v2.official_fetch import OfficialFetchError


PROTOCOL_PATH = PROJECT_ROOT / "config" / "p2_star50_v2.yaml"
PARSER_VERSION = "star50-membership-parser-v2"
INDEX_CODE = "000688"
SECURITY_RE = re.compile(r"(?<!\d)((?:688|689)\d{3})(?!\d)")
ANY_CODE_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")
DATE_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")


class LineageError(RuntimeError):
    """Raised when an official membership fact is incomplete or ambiguous."""


@dataclass(frozen=True)
class EffectiveDate:
    effective_date: str
    official_reference_date: str
    timing: str


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _canonical_sha256(payload: object) -> str:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _tool_snapshot_sha256() -> str:
    rows = [
        {"path": path.name, "sha256": sha256_file(path)}
        for path in sorted(Path(__file__).resolve().parent.glob("*.py"))
    ]
    return _canonical_sha256(rows)


def _code(value: object) -> str | None:
    if pd.isna(value):
        return None
    rendered = str(value).strip().split(".")[0].zfill(6)
    return rendered if re.fullmatch(r"(?:688|689)\d{3}", rendered) else None


def _index_code(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().split(".")[0].zfill(6)


def _source_path(raw_root: Path, source: dict[str, object]) -> Path:
    path = raw_root / str(source["stored_name"])
    if not path.is_file():
        raise LineageError(f"official source file missing: {path.name}")
    if sha256_file(path) != source["source_file_sha256"]:
        raise LineageError(f"official source hash mismatch: {path.name}")
    return path


def _html_text(path: Path) -> str:
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    return " ".join(soup.get_text(" ", strip=True).split())


def parse_initial_xlsx(path: Path) -> list[str]:
    book = pd.ExcelFile(path)
    if INDEX_CODE not in book.sheet_names:
        raise LineageError("initial official workbook lacks 000688 sheet")
    frame = pd.read_excel(path, sheet_name=INDEX_CODE)
    columns = [column for column in frame.columns if "证券代码" in str(column)]
    if len(columns) != 1:
        raise LineageError("initial official workbook has ambiguous security-code column")
    codes = [_code(value) for value in frame[columns[0]]]
    members = [code for code in codes if code is not None]
    if len(members) != 50 or len(set(members)) != 50:
        raise LineageError(f"initial official member count is not 50: {len(set(members))}")
    return members


def parse_adjustment_xlsx(path: Path) -> list[tuple[str, str]]:
    values: dict[str, list[str]] = {}
    for sheet in ("调出", "调入"):
        frame = pd.read_excel(path, sheet_name=sheet)
        index_columns = [column for column in frame.columns if "指数代码" in str(column)]
        security_columns = [column for column in frame.columns if "证券代码" in str(column)]
        if len(index_columns) != 1 or len(security_columns) != 1:
            raise LineageError(f"official workbook {sheet} schema is ambiguous")
        selected = frame.loc[frame[index_columns[0]].map(_index_code).eq(INDEX_CODE)]
        codes = [_code(value) for value in selected[security_columns[0]]]
        values[sheet] = [code for code in codes if code is not None]
    if len(values["调出"]) != len(values["调入"]):
        raise LineageError("official workbook in/out counts differ")
    return list(zip(values["调出"], values["调入"], strict=True))


def parse_adjustment_html(path: Path) -> list[tuple[str, str]]:
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    candidates: list[list[tuple[str, str]]] = []
    for table in soup.find_all("table"):
        pairs: list[tuple[str, str]] = []
        valid = True
        for row in table.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
            all_codes = [match.group(1) for cell in cells for match in ANY_CODE_RE.finditer(cell)]
            if not all_codes:
                continue
            if any(not re.fullmatch(r"(?:688|689)\d{3}", code) for code in all_codes):
                valid = False
                break
            codes = all_codes
            if len(codes) != 2:
                valid = False
                break
            pairs.append((codes[0], codes[1]))
        if valid and pairs and len(pairs) <= 5:
            candidates.append(pairs)
    unique = {tuple(candidate) for candidate in candidates}
    if not unique:
        return []
    if len(unique) != 1:
        raise LineageError("official HTML has ambiguous Star50 adjustment table")
    return list(next(iter(unique)))


def _pdf_text(path: Path) -> str:
    reader = PdfReader(path)
    if not reader.pages:
        raise LineageError("official PDF has no pages")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if not text.strip():
        raise LineageError("official PDF has no extractable text")
    return re.sub(r"科创\s*50", "科创50", text)


def parse_adjustment_pdf(path: Path) -> tuple[list[tuple[str, str]], bool]:
    text = _pdf_text(path)
    return _parse_adjustment_text(text)


def _parse_adjustment_text(text: str) -> tuple[list[tuple[str, str]], bool]:
    if "科创50指数样本无变动" in re.sub(r"\s+", "", text):
        return [], True
    headings = [match.start() for match in re.finditer(r"科创50\s*指数样本调整名单", text)]
    if not headings:
        return [], False
    segment = text[headings[-1] :]
    segment = re.split(r"科创50\s*指数备选名单", segment, maxsplit=1)[0]
    codes = SECURITY_RE.findall(segment)
    if not codes or len(codes) % 2:
        raise LineageError("official PDF Star50 adjustment code count is invalid")
    pairs = list(zip(codes[0::2], codes[1::2], strict=True))
    if len(pairs) > 5:
        raise LineageError("official PDF Star50 replacement count exceeds five")
    return pairs, False


def parse_adjustment_word(path: Path) -> tuple[list[tuple[str, str]], bool]:
    try:
        with ZipFile(path) as archive:
            document = archive.read("word/document.xml")
    except (BadZipFile, KeyError) as exc:
        raise LineageError("official WPS/DOCX attachment is not a valid Word document") from exc
    root = ElementTree.fromstring(document)
    text = " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
    if not text.strip():
        raise LineageError("official WPS/DOCX attachment has no extractable text")
    return _parse_adjustment_text(re.sub(r"科创\s*50", "科创50", text))


def _expected_count(text: str) -> int | None:
    compact = re.sub(r"\s+", "", text)
    if "科创50指数样本无变动" in compact:
        return 0
    patterns = (
        r"科创50(?:指数)?更换(\d+)只",
        r"科创50指数样本.*?指数更换(\d+)只证券",
        r"指数更换(\d+)只证券",
    )
    for pattern in patterns:
        match = re.search(pattern, compact)
        if match:
            return int(match.group(1))
    return None


def _next_open_date(reference: str, open_dates: list[str]) -> str:
    later = [day for day in open_dates if day > reference]
    if not later:
        raise LineageError(f"no trade date after official after-close date {reference}")
    return later[0]


def parse_effective_date(text: str, open_dates: list[str]) -> EffectiveDate:
    compact = re.sub(r"\s+", "", text)
    dated = [(match, "".join((match.group(1), match.group(2).zfill(2), match.group(3).zfill(2)))) for match in DATE_RE.finditer(compact)]
    candidates: list[tuple[str, str]] = []
    for match, day in dated:
        tail = compact[match.end() : match.end() + 16]
        head = compact[max(0, match.start() - 6) : match.start()]
        if re.match(r"收(?:市|盘)后生效", tail):
            candidates.append((day, "after_close"))
        elif re.match(r"(?:起|调整)", tail) or "将于" in head or "决定于" in head:
            if "调整" in tail or tail.startswith("起"):
                candidates.append((day, "start_of_day"))
    unique = sorted(set(candidates))
    if len(unique) != 1:
        raise LineageError(f"official effective date is missing or ambiguous: {unique}")
    reference, timing = unique[0]
    effective = _next_open_date(reference, open_dates) if timing == "after_close" else reference
    if effective not in open_dates:
        raise LineageError(f"normalized effective date is not an SSE trade date: {effective}")
    return EffectiveDate(effective, reference, timing)


def _parse_page_date(url: str) -> str:
    match = re.search(r"/c_(\d{8})_\d+\.shtml$", url)
    if not match:
        raise LineageError(f"official page URL lacks announcement date: {url}")
    return match.group(1)


def _frame_hash(frame: pd.DataFrame, columns: list[str]) -> str:
    rendered = frame.loc[:, columns].sort_values(columns, kind="stable").to_csv(
        index=False, lineterminator="\n"
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _write_parquet_immutable(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        prior = pd.read_parquet(path)
        if not prior.equals(frame):
            raise LineageError(f"immutable artifact differs: {path}")
        return
    frame.to_parquet(path, index=False)


def _write_json_immutable(path: Path, payload: object) -> None:
    rendered = _canonical_json(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise LineageError(f"immutable artifact differs: {path}")
        return
    path.write_text(rendered, encoding="utf-8")


def _validate_event_uniqueness(events: pd.DataFrame) -> None:
    for columns, label in (
        (["effective_date", "out_code", "in_code"], "replacement pair"),
        (["effective_date", "out_code"], "out code"),
        (["effective_date", "in_code"], "in code"),
    ):
        if events.duplicated(columns, keep=False).any():
            raise LineageError(f"duplicate official {label} in one effective batch")


def _membership_comparison(
    trade_date: str,
    official: set[str],
    secondary_rows: list[str],
) -> dict[str, object]:
    secondary = set(secondary_rows)
    duplicate_count = len(secondary_rows) - len(secondary)
    exact_match = (
        official == secondary
        and len(official) == 50
        and len(secondary) == 50
        and duplicate_count == 0
    )
    return {
        "trade_date": trade_date,
        "official_count": len(official),
        "tushare_count": len(secondary),
        "tushare_row_count": len(secondary_rows),
        "tushare_duplicate_count": duplicate_count,
        "official_only": sorted(official - secondary),
        "tushare_only": sorted(secondary - official),
        "exact_match": exact_match,
    }


def _source_public(source: dict[str, object]) -> dict[str, object]:
    return {
        key: source.get(key)
        for key in (
            "source_url",
            "final_url",
            "source_file_sha256",
            "byte_count",
            "media_type",
            "retrieved_at",
            "purpose",
            "parent_url",
            "title",
        )
    }


def build_lineage(protocol: dict[str, object], discovery_path: Path) -> dict[str, object]:
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    raw_root = PROJECT_ROOT / str(protocol["identity"]["raw_source_root"])
    sources = discovery["sources"]
    pages = [source for source in sources if source["purpose"] in {"initial_publication", "membership_announcement"}]
    attachments_by_parent: dict[str, list[dict[str, object]]] = {}
    for source in sources:
        if source["purpose"] == "official_attachment":
            attachments_by_parent.setdefault(str(source["parent_url"]), []).append(source)

    initial_url = str(protocol["source_policy"]["initial_publication_url"])
    initial_page = next((source for source in pages if source["source_url"] == initial_url), None)
    if initial_page is None:
        raise LineageError("official initial publication page is missing")
    initial_attachments = [
        source for source in attachments_by_parent.get(initial_url, []) if str(source["stored_name"]).endswith(".xlsx")
    ]
    if len(initial_attachments) != 1:
        raise LineageError("official initial member workbook is missing or ambiguous")
    initial_source = initial_attachments[0]
    members = parse_initial_xlsx(_source_path(raw_root, initial_source))
    initial_page_text = re.sub(r"\s+", "", _html_text(_source_path(raw_root, initial_page)))
    initial_publication_checks = {
        "historical_levels_after_2020_07_22_close": "2020年7月22日收盘后发布" in initial_page_text,
        "realtime_release_2020_07_23": "7月23日正式发布实时行情" in initial_page_text,
    }
    methodology_sources = [
        source for source in attachments_by_parent.get(initial_url, []) if str(source["stored_name"]).endswith(".pdf")
    ]
    if len(methodology_sources) != 1:
        raise LineageError("official initial methodology PDF is missing or ambiguous")
    methodology_source = methodology_sources[0]
    methodology_text = re.sub(r"\s+", "", _pdf_text(_source_path(raw_root, methodology_source)))
    methodology_checks = {
        "quarterly_adjustment": "样本每季度调整一次" in methodology_text,
        "regular_effective_next_trade_day": "第二个星期五的下一交易日" in methodology_text,
        "temporary_adjustment_mechanism": "临时调整" in methodology_text,
    }
    initial_page_date = _parse_page_date(initial_url)
    if initial_page_date > "20200722":
        raise LineageError("initial official member list was not published before launch")
    initial_frame = pd.DataFrame(
        [
            {
                "code": f"{code}.SH",
                "source_url": initial_source["source_url"],
                "source_file_sha256": initial_source["source_file_sha256"],
                "retrieved_at": initial_source["retrieved_at"],
                "parser_version": PARSER_VERSION,
            }
            for code in sorted(members)
        ]
    )

    calendar = load_latest_api("tushare.trade_cal")
    open_dates = sorted(
        set(
            calendar.loc[
                calendar["exchange"].astype(str).eq("SSE")
                & pd.to_numeric(calendar["is_open"], errors="coerce").eq(1),
                "cal_date",
            ].astype(str)
        )
    )
    event_rows: list[dict[str, object]] = []
    notice_checks: list[dict[str, object]] = []
    for page in sorted(
        (source for source in pages if source["purpose"] == "membership_announcement"),
        key=lambda source: source["source_url"],
    ):
        page_path = _source_path(raw_root, page)
        page_text = _html_text(page_path)
        effective = parse_effective_date(page_text, open_dates)
        announcement_date = _parse_page_date(str(page["source_url"]))
        html_pairs = parse_adjustment_html(page_path)
        parsed: list[tuple[str, str]] | None = html_pairs or None
        parsed_source = page
        attachment_results = []
        no_change = False
        for attachment in attachments_by_parent.get(str(page["source_url"]), []):
            path = _source_path(raw_root, attachment)
            if path.suffix == ".xlsx":
                pairs = parse_adjustment_xlsx(path)
                explicit_no_change = False
            elif path.suffix == ".pdf":
                pairs, explicit_no_change = parse_adjustment_pdf(path)
            elif path.suffix in {".docx", ".wps"}:
                pairs, explicit_no_change = parse_adjustment_word(path)
            else:
                continue
            if pairs or explicit_no_change:
                attachment_results.append((pairs, explicit_no_change, attachment))
        if len(attachment_results) > 1:
            distinct = {(tuple(pairs), flag) for pairs, flag, _ in attachment_results}
            if len(distinct) != 1:
                raise LineageError(f"official attachments disagree: {page['source_url']}")
        if attachment_results:
            attachment_pairs, no_change, parsed_source = attachment_results[0]
            if parsed is not None and parsed != attachment_pairs:
                raise LineageError(f"official HTML and attachment disagree: {page['source_url']}")
            parsed = attachment_pairs
        declared_count = _expected_count(page_text)
        if parsed is None:
            parsed = []
        expected = len(parsed) if declared_count is None else declared_count
        if expected != len(parsed):
            raise LineageError(
                f"official replacement count mismatch for {page['source_url']}: expected={expected}, parsed={len(parsed)}"
            )
        if expected == 0 and not (no_change or "样本无变动" in page_text):
            raise LineageError(f"zero-change official notice lacks explicit statement: {page['source_url']}")
        if announcement_date > effective.official_reference_date:
            raise LineageError(f"announcement follows official effective reference: {page['source_url']}")
        if any(code.endswith(".BJ") for pair in parsed for code in pair):
            raise LineageError(f"forbidden .BJ code in official event: {page['source_url']}")
        notice_checks.append(
            {
                "announcement_date": announcement_date,
                "effective_date": effective.effective_date,
                "official_reference_date": effective.official_reference_date,
                "effective_timing": effective.timing,
                "event_type": "temporary_adjustment" if "临时" in str(page["title"]) else "regular_adjustment",
                "replacement_count": len(parsed),
                "declared_replacement_count": declared_count,
                "explicit_no_change": expected == 0,
                "source_url": page["source_url"],
                "source_file_sha256": parsed_source["source_file_sha256"],
                "parser_crosscheck": "HTML_AND_ATTACHMENT" if html_pairs and attachment_results else "SINGLE_OFFICIAL_MATERIAL",
            }
        )
        for out_code, in_code in parsed:
            event_type = "temporary_adjustment" if "临时" in str(page["title"]) else "regular_adjustment"
            event_rows.append(
                {
                    "announcement_date": pd.Timestamp(announcement_date),
                    "effective_date": pd.Timestamp(effective.effective_date),
                    "official_reference_date": pd.Timestamp(effective.official_reference_date),
                    "effective_timing": effective.timing,
                    "event_type": event_type,
                    "out_code": f"{out_code}.SH",
                    "in_code": f"{in_code}.SH",
                    "source_url": parsed_source["source_url"],
                    "source_file_sha256": parsed_source["source_file_sha256"],
                    "retrieved_at": parsed_source["retrieved_at"],
                    "parser_version": PARSER_VERSION,
                }
            )

    events = pd.DataFrame(event_rows).sort_values(
        ["effective_date", "out_code", "in_code"], kind="stable"
    ).reset_index(drop=True)
    _validate_event_uniqueness(events)
    current = {f"{code}.SH" for code in members}
    event_member_counts = []
    for effective_date, group in events.groupby("effective_date", sort=True):
        outs = set(group["out_code"])
        ins = set(group["in_code"])
        if missing := outs - current:
            raise LineageError(f"official event removes absent members on {effective_date.date()}: {sorted(missing)}")
        if already := ins & current:
            raise LineageError(f"official event adds existing members on {effective_date.date()}: {sorted(already)}")
        current = (current - outs) | ins
        event_member_counts.append(
            {"effective_date": effective_date.strftime("%Y-%m-%d"), "member_count": len(current)}
        )
        if len(current) != 50:
            raise LineageError(f"official member count after event is {len(current)}, not 50")

    start = str(protocol["initial_set_contract"]["strategy_usable_date_if_complete"]).replace("-", "")
    end = str(protocol["source_policy"]["source_cutoff_date"]).replace("-", "")
    daily_rows = []
    current = set(initial_frame["code"])
    groups = {day.strftime("%Y%m%d"): group for day, group in events.groupby("effective_date", sort=True)}
    for day in [value for value in open_dates if start <= value <= end]:
        if day in groups:
            group = groups[day]
            current = (current - set(group["out_code"])) | set(group["in_code"])
        if len(current) != 50:
            raise LineageError(f"daily official member count is {len(current)} on {day}")
        daily_rows.extend({"trade_date": pd.Timestamp(day), "code": code} for code in sorted(current))
    daily = pd.DataFrame(daily_rows)

    weights = load_latest_api("tushare.index_weight")
    weights = weights.loc[weights["index_code"].astype(str).eq("000688.SH")].copy()
    weights["trade_date"] = weights["trade_date"].astype(str)
    snapshot_start = str(protocol["crosscheck_contract"]["completed_snapshot_start"]).replace("-", "")
    snapshot_end = str(protocol["crosscheck_contract"]["completed_snapshot_end"]).replace("-", "")
    weights = weights.loc[weights["trade_date"].between(snapshot_start, snapshot_end)]
    official_by_date = {
        day.strftime("%Y%m%d"): set(group["code"])
        for day, group in daily.groupby("trade_date", sort=True)
    }
    comparisons = []
    for trade_date, group in weights.groupby("trade_date", sort=True):
        secondary_rows = group["con_code"].dropna().astype(str).tolist()
        official = official_by_date.get(trade_date, set())
        comparisons.append(_membership_comparison(trade_date, official, secondary_rows))
    expected_snapshots = int(protocol["crosscheck_contract"]["expected_snapshot_count"])
    crosscheck_pass = len(comparisons) == expected_snapshots and all(item["exact_match"] for item in comparisons)
    bse_codes = sorted(
        {code for code in initial_frame["code"] if code.endswith(".BJ")}
        | {code for column in ("out_code", "in_code") for code in events[column] if code.endswith(".BJ")}
    )
    archive_boundaries = discovery.get("archive_boundaries", [])
    archive_scan_complete = bool(archive_boundaries) and bool(archive_boundaries[-1].get("newest_announcement_date")) and str(
        archive_boundaries[-1]["newest_announcement_date"]
    ) < "20200619"
    expected_notice_count = int(discovery["candidate_announcement_count"]) - 1
    official_lineage_complete = (
        len(initial_frame) == 50
        and all(initial_publication_checks.values())
        and all(methodology_checks.values())
        and archive_scan_complete
        and len(pages) == int(discovery["candidate_announcement_count"])
        and len(notice_checks) == expected_notice_count
        and sum(item["replacement_count"] for item in notice_checks) == len(events)
        and not bse_codes
        and all(item["member_count"] == 50 for item in event_member_counts)
    )
    pit_constructible = official_lineage_complete and not any(
        item["announcement_date"] > item["official_reference_date"] for item in notice_checks
    )
    verdict = "GO" if official_lineage_complete and crosscheck_pass and pit_constructible else "NO_GO"

    paths = {
        key: PROJECT_ROOT / str(protocol["identity"][key])
        for key in (
            "initial_set_artifact",
            "membership_events_artifact",
            "daily_membership_artifact",
            "quality_report",
        )
    }
    _write_parquet_immutable(paths["initial_set_artifact"], initial_frame)
    _write_parquet_immutable(paths["membership_events_artifact"], events)
    _write_parquet_immutable(paths["daily_membership_artifact"], daily)
    manifest = {
        "schema_version": "p2-star50-official-sources-manifest-v2",
        "protocol_sha256": sha256_file(PROTOCOL_PATH),
        "discovery_report_sha256": sha256_file(discovery_path),
        "parser_version": PARSER_VERSION,
        "tool_snapshot_sha256": _tool_snapshot_sha256(),
        "source_count": len(sources),
        "archive_boundaries": archive_boundaries,
        "archive_scan_complete": archive_scan_complete,
        "initial_publication_checks": initial_publication_checks,
        "methodology_checks": methodology_checks,
        "official_sources": [_source_public(source) for source in sources],
        "notice_checks": notice_checks,
    }
    manifest_path = PROJECT_ROOT / str(protocol["identity"]["source_manifest"])
    _write_json_immutable(manifest_path, manifest)
    report = {
        "schema_version": "p2-star50-official-lineage-quality-v2",
        "protocol_sha256": sha256_file(PROTOCOL_PATH),
        "manifest_sha256": sha256_file(manifest_path),
        "discovery_report_sha256": sha256_file(discovery_path),
        "parser_version": PARSER_VERSION,
        "tool_snapshot_sha256": _tool_snapshot_sha256(),
        "index_code": "000688.SH",
        "initial_set": {
            "member_count": len(initial_frame),
            "publication_date": datetime.strptime(initial_page_date, "%Y%m%d").date().isoformat(),
            "strategy_usable_date": protocol["initial_set_contract"]["strategy_usable_date_if_complete"],
            "source_url": initial_source["source_url"],
            "source_file_sha256": initial_source["source_file_sha256"],
            "publication_page_source_file_sha256": initial_page["source_file_sha256"],
            "publication_checks": initial_publication_checks,
            "methodology_source_url": methodology_source["source_url"],
            "methodology_source_file_sha256": methodology_source["source_file_sha256"],
            "methodology_checks": methodology_checks,
            "canonical_sha256": _frame_hash(initial_frame, list(initial_frame.columns)),
        },
        "official_lineage": {
            "announcement_count": len(notice_checks),
            "replacement_notice_count": len([item for item in notice_checks if item["replacement_count"]]),
            "explicit_no_change_notice_count": len([item for item in notice_checks if item["explicit_no_change"]]),
            "replacement_pair_count": len(events),
            "regular_adjustment_pair_count": int(events["event_type"].eq("regular_adjustment").sum()),
            "temporary_adjustment_pair_count": int(events["event_type"].eq("temporary_adjustment").sum()),
            "official_archive_page_count": len(archive_boundaries),
            "official_archive_scan_complete": archive_scan_complete,
            "official_archive_boundary": archive_boundaries[-1],
            "member_count_after_every_event": event_member_counts,
            "event_canonical_sha256": _frame_hash(events, list(events.columns)),
            "notice_checks": notice_checks,
        },
        "daily_membership": {
            "start_date": daily["trade_date"].min().strftime("%Y-%m-%d"),
            "end_date": daily["trade_date"].max().strftime("%Y-%m-%d"),
            "trade_date_count": int(daily["trade_date"].nunique()),
            "row_count": len(daily),
            "member_count_minimum": int(daily.groupby("trade_date")["code"].nunique().min()),
            "member_count_maximum": int(daily.groupby("trade_date")["code"].nunique().max()),
            "canonical_sha256": _frame_hash(daily, list(daily.columns)),
        },
        "tushare_crosscheck": {
            "role": "secondary_set_crosscheck_only",
            "weight_values_used": False,
            "trade_date_used_as_official_effective_date": False,
            "expected_snapshot_count": expected_snapshots,
            "observed_snapshot_count": len(comparisons),
            "mismatch_count": len([item for item in comparisons if not item["exact_match"]]),
            "comparisons": comparisons,
        },
        "bse_codes": bse_codes,
        "official_lineage_complete": official_lineage_complete,
        "tushare_crosscheck_pass": crosscheck_pass,
        "pit_constructible": pit_constructible,
        "engineering_complete": False,
        "strategy_results_inspected": False,
        "production_authorization": "none",
        "verdict": verdict,
        "verdict_scope": "official_membership_lineage_data_gate_only",
        "production_model_or_signal_changed": False,
    }
    _write_json_immutable(paths["quality_report"], report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    parser.add_argument("--discovery-report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol_path = args.protocol if args.protocol.is_absolute() else PROJECT_ROOT / args.protocol
    discovery_path = (
        args.discovery_report if args.discovery_report.is_absolute() else PROJECT_ROOT / args.discovery_report
    )
    protocol = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("schema_version") != "p2-star50-protocol-v2":
        raise SystemExit("lineage build requires frozen p2-star50-protocol-v2")
    try:
        report = build_lineage(protocol, discovery_path)
    except (LineageError, OfficialFetchError) as exc:
        raise SystemExit(str(exc)) from exc
    print(
        json.dumps(
            {
                "official_lineage_complete": report["official_lineage_complete"],
                "tushare_crosscheck_pass": report["tushare_crosscheck_pass"],
                "pit_constructible": report["pit_constructible"],
                "verdict": report["verdict"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["verdict"] == "GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
