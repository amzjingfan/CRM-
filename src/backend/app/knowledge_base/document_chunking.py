"""按冻结配置实施九种通用文档分块；FAQ 仍使用既有独立流程。"""

import math
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol

from app.knowledge_base.document_cleaning import CleanedUnit
from app.knowledge_base.document_schemas import DocumentIndexConfig
from app.knowledge_base.document_service import MEDIA_TYPES

MAX_CHUNKS = 2000
PAGE_FORMATS = {".pdf", ".ppt", ".pptx"}
OCR_FORMATS = {".pdf", ".png", ".jpg", ".jpeg"}
TABLE_FORMATS = {".xls", ".xlsx", ".csv", ".tsv", ".pdf", ".doc", ".docx", ".ppt", ".pptx"}
HEADING_FORMATS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".md"}
SENTENCE_FORMATS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".md", ".png", ".jpg", ".jpeg"}


class DocumentChunkError(ValueError):
    def __init__(self, code: str, *, unit_index: int | None = None) -> None:
        self.code = code
        self.unit_index = unit_index
        super().__init__(code)


class DocumentTokenizer(Protocol):
    def encode(self, text: str) -> list[int]: ...

    def decode(self, tokens: list[int]) -> str: ...


class BgeM3Tokenizer:
    """仅在 Worker 中从与 BGE-M3 revision 对应的本地 tokenizer.json 加载。"""

    def __init__(self, tokenizer_path: Path) -> None:
        try:
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise DocumentChunkError("TOKENIZER_UNAVAILABLE") from exc
        if not tokenizer_path.is_file():
            raise DocumentChunkError("TOKENIZER_UNAVAILABLE")
        self._tokenizer = Tokenizer.from_file(str(tokenizer_path))

    def encode(self, text: str) -> list[int]:
        return list(self._tokenizer.encode(text, add_special_tokens=False).ids)

    def decode(self, tokens: list[int]) -> str:
        return str(self._tokenizer.decode(tokens, skip_special_tokens=False))


@dataclass(frozen=True, slots=True)
class DocumentChunkDraft:
    index: int
    unit_index: int
    content: str
    token_count: int
    heading_path: list[str]
    locator: dict[str, int]
    strategy: str


def _validate_strategy(config: DocumentIndexConfig, suffix: str, units: list[CleanedUnit]) -> None:
    if suffix not in MEDIA_TYPES:
        raise DocumentChunkError("FILE_TYPE_UNSUPPORTED")
    strategy = config.strategy
    if strategy == "page_slide" and suffix not in PAGE_FORMATS:
        raise DocumentChunkError("STRATEGY_FORMAT_UNSUPPORTED")
    if strategy == "ocr_layout" and (suffix not in OCR_FORMATS or not all(unit.ocr_derived for unit in units)):
        raise DocumentChunkError("STRATEGY_FORMAT_UNSUPPORTED")
    if strategy == "table_rows" and suffix not in TABLE_FORMATS:
        raise DocumentChunkError("STRATEGY_FORMAT_UNSUPPORTED")
    if strategy == "table_rows" and config.overlap != 0:
        raise DocumentChunkError("TABLE_OVERLAP_UNSUPPORTED")
    if strategy == "heading_paragraph" and suffix not in HEADING_FORMATS:
        raise DocumentChunkError("STRATEGY_FORMAT_UNSUPPORTED")
    if strategy in {"sentence", "semantic_similarity"} and suffix not in SENTENCE_FORMATS:
        raise DocumentChunkError("STRATEGY_FORMAT_UNSUPPORTED")


def _block_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(filter(None, (_block_text(item) for item in value)))
    if isinstance(value, dict):
        return _block_text(value.get("content", value.get("text", "")))
    return ""


def _token_windows(text: str, size: int, overlap: int, tokenizer: DocumentTokenizer) -> list[str]:
    tokens = tokenizer.encode(text)
    windows: list[str] = []
    offset = 0
    while offset < len(tokens):
        end = min(offset + size, len(tokens))
        window = tokenizer.decode(tokens[offset:end])
        # BGE 的子词边界解码后重新编码可能增加 token；写库前以实际文本计数。
        while end > offset and len(tokenizer.encode(window)) > size:
            end -= 1
            window = tokenizer.decode(tokens[offset:end])
        if end == offset:
            raise DocumentChunkError("CHUNK_SIZE_EXCEEDED")
        if window.strip():
            windows.append(window)
        if end >= len(tokens):
            break
        offset = max(offset + 1, end - overlap)
    return windows


def _char_windows(text: str, size: int, overlap: int) -> list[str]:
    windows: list[str] = []
    offset = 0
    while offset < len(text):
        window = text[offset : offset + size]
        if window.strip():
            windows.append(window)
        if offset + size >= len(text):
            break
        offset += size - overlap
    return windows


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?])\s*|(?<=\.)\s+|\n+", text)
    return [part.strip() for part in parts if part.strip()]


def _pack(parts: list[str], size: int, overlap: int, tokenizer: DocumentTokenizer) -> list[str]:
    """优先保留部件边界，过长部件再退到 Token 窗口。"""
    result: list[str] = []
    current = ""
    for part in parts:
        if not part.strip():
            continue
        if len(tokenizer.encode(part)) > size:
            if current:
                result.append(current)
                current = ""
            result.extend(_token_windows(part, size, overlap, tokenizer))
            continue
        candidate = f"{current}\n{part}" if current else part
        if len(tokenizer.encode(candidate)) <= size:
            current = candidate
            continue
        result.append(current)
        tail = tokenizer.decode(tokenizer.encode(current)[-overlap:]) if overlap else ""
        next_candidate = f"{tail}\n{part}" if tail else part
        current = next_candidate if len(tokenizer.encode(next_candidate)) <= size else part
    if current:
        result.append(current)
    return result


def _heading_sections(unit: CleanedUnit) -> list[tuple[list[str], str]]:
    headings: list[str] = []
    sections: list[tuple[list[str], str]] = []
    current_lines: list[str] = []

    def flush() -> None:
        if current_lines:
            sections.append((headings.copy(), "\n".join(current_lines)))
            current_lines.clear()

    if any(block.get("type") in {"paragraph_title", "heading", "title"} for block in unit.blocks):
        for block in unit.blocks:
            content = _block_text(block.get("content")).strip()
            if not content:
                continue
            if block.get("type") in {"paragraph_title", "heading", "title"}:
                flush()
                raw_level = block.get("level")
                level = raw_level if isinstance(raw_level, int) and 1 <= raw_level <= 6 else 1
                headings[:] = headings[: level - 1] + [content]
            else:
                current_lines.append(content)
        flush()
        return sections or [([], unit.cleaned_text)]

    for line in unit.cleaned_text.splitlines():
        marker = re.match(r"^(#{1,6})\s+(.+)$", line)
        if marker:
            flush()
            level = len(marker.group(1))
            headings[:] = headings[: level - 1] + [marker.group(2).strip()]
        elif line.strip():
            current_lines.append(line.strip())
    flush()
    return sections or [([], unit.cleaned_text)]


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise DocumentChunkError("SEMANTIC_VECTOR_INVALID")
    if any(not math.isfinite(value) for value in left + right):
        raise DocumentChunkError("SEMANTIC_VECTOR_INVALID")
    norm_left = math.sqrt(sum(value * value for value in left))
    norm_right = math.sqrt(sum(value * value for value in right))
    if norm_left == 0 or norm_right == 0:
        raise DocumentChunkError("SEMANTIC_VECTOR_INVALID")
    return sum(a * b for a, b in zip(left, right, strict=True)) / (norm_left * norm_right)


def _semantic_groups(sentences: list[str], vectors: list[list[float]] | None) -> list[str]:
    if len(sentences) <= 1:
        return sentences
    if vectors is None:
        raise DocumentChunkError("SEMANTIC_VECTORS_REQUIRED")
    if len(vectors) != len(sentences):
        raise DocumentChunkError("SEMANTIC_VECTOR_INVALID")
    groups: list[str] = []
    current: list[str] = [sentences[0]]
    for index in range(1, len(sentences)):
        if _cosine(vectors[index - 1], vectors[index]) < 0.65:
            groups.append("".join(current))
            current = []
        current.append(sentences[index])
    groups.append("".join(current))
    return groups


class _HtmlTable(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self._row is not None and self._cell is not None:
            self._row.append(" ".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def _table_groups(unit: CleanedUnit, config: DocumentIndexConfig, tokenizer: DocumentTokenizer) -> list[str]:
    groups: list[str] = []
    found = False
    for block in unit.blocks:
        if block.get("type") != "table":
            continue
        found = True
        table = _HtmlTable()
        table.feed(_block_text(block.get("content")))
        if len(table.rows) < 2 or any(len(row) != len(table.rows[0]) for row in table.rows):
            raise DocumentChunkError("TABLE_STRUCTURE_REQUIRED", unit_index=unit.index)
        header = " | ".join(table.rows[0])
        current = header
        for row in table.rows[1:]:
            row_line = " | ".join(row)
            if len(tokenizer.encode(f"{header}\n{row_line}")) > config.chunk_size:
                raise DocumentChunkError("ROW_TOO_LARGE_REVIEW_REQUIRED", unit_index=unit.index)
            candidate = f"{current}\n{row_line}"
            if len(tokenizer.encode(candidate)) > config.chunk_size:
                groups.append(current)
                current = f"{header}\n{row_line}"
            else:
                current = candidate
        groups.append(current)
    if not found:
        raise DocumentChunkError("TABLE_STRUCTURE_REQUIRED", unit_index=unit.index)
    return groups


def chunk_document(
    units: list[CleanedUnit],
    config: DocumentIndexConfig,
    tokenizer: DocumentTokenizer,
    *,
    suffix: str,
    semantic_vectors: dict[int, list[list[float]]] | None = None,
) -> list[DocumentChunkDraft]:
    """任何来源单元待复核即失败；一个块永远不跨来源单元。"""
    if not units or any(unit.needs_review for unit in units):
        raise DocumentChunkError("VERSION_REVIEW_REQUIRED")
    _validate_strategy(config, suffix, units)
    chunks: list[DocumentChunkDraft] = []
    for unit in units:
        if not unit.cleaned_text.strip():
            raise DocumentChunkError("VERSION_REVIEW_REQUIRED")
        sections: list[tuple[list[str], list[str]]]
        if config.strategy == "fixed_token":
            sections = [([], _token_windows(unit.cleaned_text, config.chunk_size, config.overlap, tokenizer))]
        elif config.strategy == "fixed_char":
            sections = [([], _char_windows(unit.cleaned_text, config.chunk_size, config.overlap))]
        elif config.strategy == "table_rows":
            sections = [([], _table_groups(unit, config, tokenizer))]
        elif config.strategy == "page_slide":
            number = unit.locator.get("page", unit.locator.get("source_unit", 0) + 1)
            prefix = f"第 {number} 页\n" if suffix == ".pdf" else f"幻灯片 {number}\n"
            budget = config.chunk_size - len(tokenizer.encode(prefix))
            if budget <= config.overlap:
                raise DocumentChunkError("CHUNK_SIZE_EXCEEDED")
            sections = [
                (
                    [],
                    [
                        prefix + window
                        for window in _token_windows(unit.cleaned_text, budget, config.overlap, tokenizer)
                    ],
                )
            ]
        elif config.strategy == "ocr_layout":
            sections = [
                ([], _pack([_block_text(block.get("content"))], config.chunk_size, config.overlap, tokenizer))
                for block in unit.blocks
                if _block_text(block.get("content")).strip()
            ]
        elif config.strategy == "heading_paragraph":
            sections = [
                (path, _pack(body.splitlines(), config.chunk_size, config.overlap, tokenizer))
                for path, body in _heading_sections(unit)
            ]
        elif config.strategy == "recursive":
            sections = [
                (path, _pack(_sentences(body), config.chunk_size, config.overlap, tokenizer))
                for path, body in _heading_sections(unit)
            ]
        elif config.strategy == "semantic_similarity":
            sentences = _sentences(unit.cleaned_text)
            groups = _semantic_groups(sentences, (semantic_vectors or {}).get(unit.index))
            sections = [([], _pack([group], config.chunk_size, config.overlap, tokenizer)) for group in groups]
        else:
            sections = [([], _pack(_sentences(unit.cleaned_text), config.chunk_size, config.overlap, tokenizer))]

        for heading_path, contents in sections:
            for content in contents:
                if not content.strip():
                    continue
                count = len(tokenizer.encode(content))
                if config.strategy != "fixed_char" and count > config.chunk_size:
                    raise DocumentChunkError("CHUNK_SIZE_EXCEEDED")
                chunks.append(
                    DocumentChunkDraft(
                        index=len(chunks),
                        unit_index=unit.index,
                        content=content,
                        token_count=count,
                        heading_path=heading_path,
                        locator=unit.locator.copy(),
                        strategy=config.strategy,
                    )
                )
                if len(chunks) > MAX_CHUNKS:
                    raise DocumentChunkError("CHUNK_LIMIT_EXCEEDED")
    if not chunks:
        raise DocumentChunkError("VERSION_REVIEW_REQUIRED")
    return chunks
