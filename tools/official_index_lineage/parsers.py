"""Pure parsers for official index member and methodology materials."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from bs4 import BeautifulSoup
import pandas as pd

from tools.official_index_lineage.contract import DataGateError, sha256_file

SECURITY_RE = re.compile(r"(?<!\d)((?:688|689)\d{3})(?!\d)")
ANY_CODE_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")
DATE_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")
PARSER_VERSION = "official-index-lineage-parser-v1"


@dataclass(frozen=True)
class EffectiveDate:
    effective_date: str
    official_reference_date: str
    timing: str


@dataclass(frozen=True)
class AdjustmentMaterial:
    pairs: tuple[tuple[str, str], ...]
    explicit_no_change: bool


def source_path(raw_root: Path, source: dict[str, object]) -> Path:
    path = raw_root / str(source["stored_name"])
    if not path.is_file():
        raise DataGateError(f"official source missing: {path.name}")
    if sha256_file(path) != source["source_file_sha256"]:
        raise DataGateError(f"official source hash mismatch: {path.name}")
    return path


def code(value: object) -> str | None:
    if pd.isna(value):
        return None
    rendered = str(value).strip().split(".")[0].zfill(6)
    return rendered if re.fullmatch(r"(?:688|689)\d{3}", rendered) else None


def index_code(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().split(".")[0].zfill(6)


def html_text(path: Path) -> str:
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    return " ".join(soup.get_text(" ", strip=True).split())


def pdf_text(path: Path) -> str:
    from pypdf import PdfReader  # Docker/runtime dependency; keep host pure tests importable.

    reader = PdfReader(path)
    if not reader.pages:
        raise DataGateError("official PDF has no pages")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if not text.strip():
        raise DataGateError("official PDF has no extractable text")
    return text


def word_text(path: Path) -> str:
    try:
        with ZipFile(path) as archive:
            document = archive.read("word/document.xml")
    except (BadZipFile, KeyError) as error:
        raise DataGateError("official Word/WPS file is not OOXML") from error
    root = ElementTree.fromstring(document)
    text = " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
    if not text.strip():
        raise DataGateError("official Word/WPS file has no extractable text")
    return text


def material_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".html", ".shtml"}:
        return html_text(path)
    if suffix == ".pdf":
        return pdf_text(path)
    if suffix in {".docx", ".wps"}:
        return word_text(path)
    if suffix in {".xls", ".xlsx"}:
        book = pd.ExcelFile(path)
        parts = []
        for sheet in book.sheet_names:
            frame = pd.read_excel(path, sheet_name=sheet, header=None)
            parts.append(sheet)
            parts.append(" ".join(frame.fillna("").astype(str).to_numpy().ravel()))
        return " ".join(parts)
    raise DataGateError(f"unsupported official material: {path.suffix}")


def parse_initial_xlsx(path: Path, provider_code: str, expected_count: int) -> list[str]:
    book = pd.ExcelFile(path)
    candidate_sheets = [
        sheet for sheet in book.sheet_names if index_code(sheet) == provider_code
    ]
    if not candidate_sheets and len(book.sheet_names) == 1:
        candidate_sheets = list(book.sheet_names)
    if len(candidate_sheets) != 1:
        raise DataGateError("initial official workbook has no unique target-index sheet")
    frame = pd.read_excel(path, sheet_name=candidate_sheets[0])
    columns = [column for column in frame.columns if "证券代码" in str(column)]
    if len(columns) != 1:
        raise DataGateError("initial workbook security-code column is ambiguous")
    members = [code(value) for value in frame[columns[0]]]
    clean = [item for item in members if item is not None]
    if len(clean) != expected_count or len(set(clean)) != expected_count:
        raise DataGateError(
            f"initial member count differs: rows={len(clean)}, unique={len(set(clean))}"
        )
    return clean


def _structured_adjustment_xlsx(path: Path, provider_code: str) -> AdjustmentMaterial | None:
    book = pd.ExcelFile(path)
    if not {"调出", "调入"}.issubset(book.sheet_names):
        return None
    values: dict[str, list[str]] = {}
    for sheet in ("调出", "调入"):
        frame = pd.read_excel(path, sheet_name=sheet)
        index_columns = [column for column in frame.columns if "指数代码" in str(column)]
        security_columns = [column for column in frame.columns if "证券代码" in str(column)]
        if len(index_columns) != 1 or len(security_columns) != 1:
            raise DataGateError(f"official {sheet} sheet schema is ambiguous")
        selected = frame.loc[frame[index_columns[0]].map(index_code).eq(provider_code)]
        values[sheet] = [
            item for item in (code(value) for value in selected[security_columns[0]]) if item
        ]
    if not values["调出"] and not values["调入"]:
        return None
    if len(values["调出"]) != len(values["调入"]):
        raise DataGateError("official adjustment in/out counts differ")
    return AdjustmentMaterial(
        tuple(zip(values["调出"], values["调入"], strict=True)),
        False,
    )


def _normalized_star200(text: str) -> str:
    return re.sub(r"科创(?:板)?\s*200", "科创200", text)


def _text_adjustment(text: str) -> AdjustmentMaterial | None:
    normalized = _normalized_star200(text)
    compact = re.sub(r"\s+", "", normalized)
    if "科创200指数样本无变动" in compact or "科创200样本无变动" in compact:
        return AdjustmentMaterial((), True)
    headings = [
        match.start()
        for pattern in (
            r"科创200\s*指数样本调整名单",
            r"上证科创板200\s*指数样本调整名单",
        )
        for match in re.finditer(pattern, normalized)
    ]
    if not headings:
        return None
    segment = normalized[max(headings) :]
    segment = re.split(
        r"(?:科创200\s*指数备选名单|上证科创板\d+\s*指数样本调整名单|\n\s*附件)",
        segment,
        maxsplit=1,
    )[0]
    codes = SECURITY_RE.findall(segment)
    if not codes or len(codes) % 2:
        raise DataGateError("official STAR200 adjustment code count is invalid")
    pairs = tuple(zip(codes[0::2], codes[1::2], strict=True))
    if len(pairs) > 30:
        raise DataGateError("official STAR200 replacement count exceeds frozen 15% cap")
    return AdjustmentMaterial(pairs, False)


def parse_adjustment_material(path: Path, provider_code: str) -> AdjustmentMaterial | None:
    if path.suffix.lower() in {".xls", ".xlsx"}:
        structured = _structured_adjustment_xlsx(path, provider_code)
        if structured is not None:
            return structured
    return _text_adjustment(material_text(path))


def parse_page_date(url: str) -> str:
    match = re.search(r"/c_(\d{8})_\d+\.shtml$", url)
    if not match:
        raise DataGateError(f"official page URL lacks announcement date: {url}")
    return match.group(1)


def next_open_date(reference: str, open_dates: list[str]) -> str:
    later = [day for day in open_dates if day > reference]
    if not later:
        raise DataGateError(f"no official trade date after {reference}")
    return later[0]


def parse_effective_date(text: str, open_dates: list[str]) -> EffectiveDate:
    compact = re.sub(r"\s+", "", text)
    candidates: list[tuple[str, str]] = []
    for match in DATE_RE.finditer(compact):
        day = f"{match.group(1)}{match.group(2).zfill(2)}{match.group(3).zfill(2)}"
        tail = compact[match.end() : match.end() + 18]
        head = compact[max(0, match.start() - 8) : match.start()]
        if re.match(r"收(?:市|盘)后生效", tail):
            candidates.append((day, "after_close"))
        elif ("将于" in head or "决定于" in head) and ("生效" in tail or "实施" in tail):
            candidates.append((day, "start_of_day"))
        elif tail.startswith("起") and ("实施" in tail or "调整" in tail):
            candidates.append((day, "start_of_day"))
    unique = sorted(set(candidates))
    if len(unique) != 1:
        raise DataGateError(f"official effective date is missing or ambiguous: {unique}")
    reference, timing = unique[0]
    effective = next_open_date(reference, open_dates) if timing == "after_close" else reference
    if effective not in open_dates:
        raise DataGateError(f"normalized effective date is not an SSE trade date: {effective}")
    return EffectiveDate(effective, reference, timing)


def methodology_checks(launch_text: str, revision_text: str, current_text: str) -> dict[str, bool]:
    launch = re.sub(r"\s+", "", _normalized_star200(launch_text))
    revision = re.sub(r"\s+", "", _normalized_star200(revision_text))
    current = re.sub(r"\s+", "", _normalized_star200(current_text))
    return {
        "launch_v1_0_identity": "版本号V1.0" in launch and "指数代码：000699" in launch,
        "launch_six_month_rule": "上市时间超过6个月" in launch,
        "launch_quarterly_rule": "样本每季度调整一次" in launch,
        "revision_names_star200": "科创200" in revision,
        "revision_effective_date": "2025年3月17日实施" in revision,
        "revision_grandfathering": "新老样本划断" in revision,
        "current_v1_1_identity": "版本号V1.1" in current and "指数代码：000699" in current,
        "current_twelve_month_rule": "上市时间超过12个月" in current,
    }
