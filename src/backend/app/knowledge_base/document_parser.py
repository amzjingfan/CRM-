"""仅解析进程调用的 MinerU 4.x 适配层；业务进程不导入模型依赖。"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from app.knowledge_base.document_service import MAX_DOCUMENT_BYTES, MEDIA_TYPES, TEXT_SUFFIXES

MINERU_VERSION = "4.0.12"
MAX_PDF_PAGES = 100
MAX_IMAGE_PIXELS = 25_000_000
MAX_RESULT_BLOCKS = 20_000


class DocumentParseError(ValueError):
    """解析失败只向调度层提供稳定错误码，不携带用户文档正文。"""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ParsedUnit:
    index: int
    kind: str
    locator: dict[str, int]
    blocks: list[dict[str, Any]]
    parse_mode: str
    ocr_derived: bool
    parser_version: str


def _contains_text(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_contains_text(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_text(item) for key, item in value.items() if key in {"content", "text", "html"})
    return False


def parse_middle_json(payload: dict[str, Any], suffix: str) -> list[ParsedUnit]:
    """校验 DocVortex MiddleJson 后保留原始页/块定位与空白页。"""
    if suffix not in MEDIA_TYPES:
        raise DocumentParseError("FILE_TYPE_UNSUPPORTED")
    if payload.get("schema") != "docvortex.middle" or payload.get("schema_version") != "2.0":
        raise DocumentParseError("PARSER_SCHEMA_UNSUPPORTED")
    if payload.get("is_full_document") is not True:
        raise DocumentParseError("PARSER_RESULT_INCOMPLETE")
    metadata = payload.get("metadata")
    producer = metadata.get("producer") if isinstance(metadata, dict) else None
    parser_version = producer.get("version") if isinstance(producer, dict) else None
    if not isinstance(producer, dict) or producer.get("name") != "mineru" or parser_version != MINERU_VERSION:
        raise DocumentParseError("PARSER_VERSION_MISMATCH")
    extensions = payload.get("extensions")
    mineru = extensions.get("mineru") if isinstance(extensions, dict) else None
    mode = mineru.get("parse_mode") if isinstance(mineru, dict) else None
    if not isinstance(mode, str) or not mode:
        raise DocumentParseError("PARSER_MODE_MISSING")
    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        raise DocumentParseError("PARSER_RESULT_EMPTY")
    if suffix == ".pdf" and len(pages) > MAX_PDF_PAGES:
        raise DocumentParseError("PAGE_LIMIT_EXCEEDED")

    units: list[ParsedUnit] = []
    total_blocks = 0
    for index, page in enumerate(pages):
        if not isinstance(page, dict) or not isinstance(page.get("page_idx"), int):
            raise DocumentParseError("PARSER_PAGE_INVALID")
        page_idx = page["page_idx"]
        if page_idx != index:
            raise DocumentParseError("PARSER_PAGE_INCOMPLETE")
        blocks = page.get("blocks")
        if not isinstance(blocks, list) or any(not isinstance(block, dict) for block in blocks):
            raise DocumentParseError("PARSER_BLOCK_INVALID")
        total_blocks += len(blocks)
        if total_blocks > MAX_RESULT_BLOCKS:
            raise DocumentParseError("PARSER_RESULT_TOO_LARGE")
        if suffix == ".pdf":
            kind, locator = "page", {"page": page_idx + 1}
        elif suffix in {".png", ".jpg", ".jpeg"}:
            kind, locator = "image", {"source_unit": page_idx}
        else:
            kind, locator = "document_unit", {"source_unit": page_idx}
        units.append(
            ParsedUnit(
                index=index,
                kind=kind,
                locator=locator,
                blocks=blocks,
                parse_mode=mode,
                ocr_derived=mode != "txt" and suffix in {".pdf", ".png", ".jpg", ".jpeg"},
                parser_version=parser_version,
            )
        )
    return units


def _parse_with_mineru(path: Path, *, tier: str, ocr_mode: str) -> dict[str, Any]:
    """SDK 仅在隔离 Worker 执行时导入，绝不使用官方远端服务。"""
    try:
        from mineru.parser import parse
    except ImportError as exc:
        raise DocumentParseError("PARSER_UNAVAILABLE") from exc
    try:
        if path.suffix.lower() == ".pdf":
            result = parse(str(path), tier=tier, ocr_mode=ocr_mode, page_range="all")
        elif path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            result = parse(str(path), tier=tier, ocr_mode=ocr_mode)
        else:
            result = parse(str(path), tier=tier)
        return cast(dict[str, Any], result.to_dict())
    except Exception as exc:
        raise DocumentParseError("PARSER_EXECUTION_FAILED") from exc


def _pdf_page_count(path: Path) -> int:
    """只读取 PDF 目录，超长文档在推理前终止。"""
    try:
        from pypdfium2 import PdfDocument
    except ImportError as exc:
        raise DocumentParseError("PARSER_UNAVAILABLE") from exc
    try:
        document = PdfDocument(str(path))
        try:
            return int(len(document))
        finally:
            document.close()
    except Exception as exc:
        raise DocumentParseError("SOURCE_FILE_INVALID") from exc


def _image_pixels(path: Path) -> int:
    """只读取图片头，不解码大图。"""
    try:
        from PIL import Image
    except ImportError as exc:
        raise DocumentParseError("PARSER_UNAVAILABLE") from exc
    try:
        with Image.open(path) as image:
            width, height = image.size
            return int(width) * int(height)
    except Exception as exc:
        raise DocumentParseError("SOURCE_FILE_INVALID") from exc


def parse_document(path: Path, suffix: str, mode: str) -> list[ParsedUnit]:
    """按冻结档位处理单个受控本地文件；PDF 自动模式只在必要时升到 Basic。"""
    if suffix not in MEDIA_TYPES or path.suffix.lower() != suffix:
        raise DocumentParseError("FILE_TYPE_UNSUPPORTED")
    if mode not in {"auto", "flash", "basic"}:
        raise DocumentParseError("PARSER_MODE_INVALID")
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg"} and mode == "basic":
        raise DocumentParseError("PARSER_TIER_UNSUPPORTED")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise DocumentParseError("SOURCE_FILE_UNAVAILABLE") from exc
    if size <= 0 or size > MAX_DOCUMENT_BYTES:
        raise DocumentParseError("FILE_SIZE_INVALID")
    if suffix in TEXT_SUFFIXES:
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise DocumentParseError("TEXT_ENCODING_INVALID") from exc
        return [
            ParsedUnit(
                index=0,
                kind="document_unit",
                locator={"source_unit": 0},
                blocks=[{"type": "text", "index": 0, "content": [{"type": "text", "content": content}]}],
                parse_mode="native_text",
                ocr_derived=False,
                parser_version="native-text-v1",
            )
        ]
    if suffix == ".pdf":
        page_count = _pdf_page_count(path)
        if page_count <= 0:
            raise DocumentParseError("PARSER_RESULT_EMPTY")
        if page_count > MAX_PDF_PAGES:
            raise DocumentParseError("PAGE_LIMIT_EXCEEDED")
        if mode == "basic":
            return parse_middle_json(_parse_with_mineru(path, tier="basic", ocr_mode="auto"), suffix)
        flash = parse_middle_json(_parse_with_mineru(path, tier="flash", ocr_mode="txt"), suffix)
        if mode == "auto" and any(not any(_contains_text(block) for block in unit.blocks) for unit in flash):
            return parse_middle_json(_parse_with_mineru(path, tier="basic", ocr_mode="auto"), suffix)
        return flash
    if suffix in {".png", ".jpg", ".jpeg"}:
        pixels = _image_pixels(path)
        if pixels <= 0 or pixels > MAX_IMAGE_PIXELS:
            raise DocumentParseError("IMAGE_PIXEL_LIMIT_EXCEEDED")
        tier = "flash" if mode == "flash" else "basic"
        return parse_middle_json(_parse_with_mineru(path, tier=tier, ocr_mode="ocr"), suffix)
    return parse_middle_json(_parse_with_mineru(path, tier="flash", ocr_mode="auto"), suffix)
