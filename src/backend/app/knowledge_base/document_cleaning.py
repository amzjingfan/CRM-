"""可追溯的文档清洗与整版本质量门禁（clean-v1）。"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from app.knowledge_base.document_parser import ParsedUnit

CLEANING_VERSION = "clean-v1"
PAGE_NUMBER = re.compile(r"(?:page\s+\d+|第\s*\d+\s*页)", re.IGNORECASE)
CRITICAL_MARGIN = re.compile(r"\d|[¥$€]|不|无|禁止|不得|\b(?:no|not|never|refunds?|sku|price|amount)\b", re.IGNORECASE)
KNOWN_BLOCK_TYPES = {
    "text",
    "title",
    "paragraph_title",
    "heading",
    "list",
    "code",
    "table",
    "image",
    "chart",
    "formula",
    "equation",
    "caption",
    "reference",
}


@dataclass(frozen=True, slots=True)
class CleanedUnit:
    index: int
    kind: str
    locator: dict[str, int]
    raw_text: str
    cleaned_text: str
    blocks: list[dict[str, Any]]
    issue_codes: list[str]
    needs_review: bool
    parse_mode: str
    ocr_derived: bool
    parser_version: str


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _content_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(filter(None, (_content_text(item) for item in value)))
    if isinstance(value, dict):
        return _content_text(value.get("content", value.get("text", "")))
    return ""


def _margin(block: dict[str, Any]) -> bool:
    bbox = block.get("bbox")
    return (
        isinstance(bbox, list)
        and len(bbox) == 4
        and all(isinstance(coordinate, (int, float)) for coordinate in bbox)
        and (bbox[1] <= 0.08 or bbox[3] >= 0.92)
    )


def _page_number(block: dict[str, Any]) -> bool:
    return _margin(block) and bool(PAGE_NUMBER.fullmatch(_normalize(_content_text(block.get("content")))))


class _TableRows(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.counts: list[int] = []
        self._current: int | None = None
        self.has_header = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._current = 0
        elif tag in {"td", "th"} and self._current is not None:
            self._current += 1
            if tag == "th":
                self.has_header = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self._current is not None:
            self.counts.append(self._current)
            self._current = None


def _table_quality(text: str) -> tuple[bool, bool]:
    parser = _TableRows()
    parser.feed(text)
    complete = bool(parser.counts) and all(count == parser.counts[0] and count > 0 for count in parser.counts)
    return complete, parser.has_header


def _issue(codes: list[str], code: str) -> None:
    if code not in codes:
        codes.append(code)


def clean_unit(unit: ParsedUnit, *, repeated_margins: frozenset[str] = frozenset()) -> CleanedUnit:
    """只删除可定位的页码/重复边缘文本；不推断或改写业务事实。"""
    raw_parts = [_content_text(block.get("content")) for block in unit.blocks]
    raw_text = "\n".join(filter(None, raw_parts))
    cleaned_parts: list[str] = []
    kept_blocks: list[dict[str, Any]] = []
    issues: list[str] = []
    for block, raw_part in zip(unit.blocks, raw_parts, strict=True):
        normalized = _normalize(raw_part)
        if _page_number(block) or (_margin(block) and normalized in repeated_margins):
            continue
        kept_blocks.append(block)
        if normalized:
            cleaned_parts.append(normalized)
        block_type = block.get("type")
        if block_type not in KNOWN_BLOCK_TYPES:
            _issue(issues, "UNKNOWN_BLOCK_TYPE")
        if block_type == "table":
            complete, has_header = _table_quality(normalized)
            if not complete:
                _issue(issues, "TABLE_ROW_INCOMPLETE")
            if not has_header:
                _issue(issues, "TABLE_HEADER_UNVERIFIED")
        if block_type in {"image", "chart"} or (block_type in {"formula", "equation"} and not normalized):
            _issue(issues, "NON_TEXT_CONTENT_UNRECOGNIZED")
        if (
            block_type in {"text", "title", "paragraph_title", "heading", "list", "code", "caption", "reference"}
            and not normalized
        ):
            _issue(issues, "PARSED_CONTENT_INCOMPLETE")
        if block.get("truncated") or block.get("error"):
            _issue(issues, "PARSED_CONTENT_INCOMPLETE")

    cleaned_text = _normalize("\n".join(cleaned_parts))
    if not cleaned_text:
        _issue(issues, "EMPTY_UNIT")
    if "\ufffd" in raw_text or any(ord(char) < 32 and char not in "\n\r\t" for char in raw_text):
        _issue(issues, "TEXT_CORRUPTED")
    if unit.ocr_derived:
        _issue(issues, "OCR_REVIEW_REQUIRED")
    return CleanedUnit(
        index=unit.index,
        kind=unit.kind,
        locator=unit.locator,
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        blocks=kept_blocks,
        issue_codes=issues,
        needs_review=bool(issues),
        parse_mode=unit.parse_mode,
        ocr_derived=unit.ocr_derived,
        parser_version=unit.parser_version,
    )


def clean_document(units: list[ParsedUnit]) -> list[CleanedUnit]:
    """跨页识别短且完全重复的页边缘文字，不丢失金额、SKU 或否定内容。"""
    margins: Counter[str] = Counter()
    for unit in units:
        seen = {
            _normalize(_content_text(block.get("content")))
            for block in unit.blocks
            if _margin(block) and block.get("type") == "text" and not _page_number(block)
        }
        margins.update(text for text in seen if text and len(text) <= 120 and not CRITICAL_MARGIN.search(text))
    repeated = frozenset(text for text, count in margins.items() if count >= 2)
    return [clean_unit(unit, repeated_margins=repeated) for unit in units]


def version_requires_review(units: list[CleanedUnit]) -> bool:
    """任一单元关键内容不可靠，整个新版本停在待复核。"""
    return not units or any(unit.needs_review for unit in units)
