"""MinerU 4.x 本地结果适配，不下载模型。"""

from pathlib import Path
from typing import Any

import pytest

from app.knowledge_base import document_parser


def _middle(pages: list[dict[str, Any]], *, mode: str = "txt") -> dict[str, Any]:
    return {
        "schema": "docvortex.middle",
        "schema_version": "2.0",
        "metadata": {"file_suffix": "pdf", "producer": {"name": "mineru", "version": "4.0.12"}},
        "extensions": {"mineru": {"tier": "flash", "parse_mode": mode}},
        "pages": pages,
        "is_full_document": True,
    }


def _page(index: int, text: str) -> dict[str, Any]:
    return {
        "page_idx": index,
        "blocks": [{"type": "text", "index": 0, "content": [{"type": "text", "content": text}]}] if text else [],
    }


def test_middle_json_keeps_pdf_source_page_and_blocks() -> None:
    units = document_parser.parse_middle_json(_middle([_page(0, "第 1 页"), _page(1, "第 2 页")]), ".pdf")
    assert [(unit.index, unit.kind, unit.locator["page"], unit.blocks[0]["type"]) for unit in units] == [
        (0, "page", 1, "text"),
        (1, "page", 2, "text"),
    ]
    assert all(not unit.ocr_derived for unit in units)


def test_image_ocr_is_marked_for_review_downstream() -> None:
    units = document_parser.parse_middle_json(_middle([_page(0, "图片里的 SKU-2")], mode="ocr"), ".png")
    assert len(units) == 1
    assert units[0].kind == "image"
    assert units[0].ocr_derived
    assert "page" not in units[0].locator


def test_office_has_source_unit_not_invented_pdf_page() -> None:
    units = document_parser.parse_middle_json(_middle([_page(0, "表格"), _page(1, "续表")]), ".xlsx")
    assert [unit.locator for unit in units] == [{"source_unit": 0}, {"source_unit": 1}]
    assert all(unit.kind == "document_unit" for unit in units)


@pytest.mark.parametrize(
    "payload",
    [
        {**_middle([_page(0, "ok")]), "schema": "docvortex.model"},
        {**_middle([_page(0, "ok")]), "schema_version": "1.0"},
        _middle([]),
        _middle([_page(0, "ok"), _page(0, "duplicate")]),
        {**_middle([_page(0, "ok")]), "is_full_document": False},
    ],
)
def test_malformed_or_incomplete_result_fails_closed(payload: dict[str, Any]) -> None:
    with pytest.raises(document_parser.DocumentParseError):
        document_parser.parse_middle_json(payload, ".pdf")


def test_blank_pdf_page_is_preserved_for_whole_version_review() -> None:
    units = document_parser.parse_middle_json(_middle([_page(0, "正文"), _page(1, "")]), ".pdf")
    assert len(units) == 2
    assert units[1].blocks == []


def test_plain_text_is_read_without_mineru(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "policy.md"
    path.write_text("# 退换货\n不支持无凭证退款。", encoding="utf-8")
    monkeypatch.setattr(document_parser, "_parse_with_mineru", lambda *_args, **_kwargs: pytest.fail("called MinerU"))
    units = document_parser.parse_document(path, ".md", "auto")
    assert len(units) == 1
    assert units[0].blocks[0]["content"][0]["content"].startswith("# 退换货")


def test_auto_pdf_tries_flash_then_basic_for_blank_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "mixed.pdf"
    path.write_bytes(b"%PDF-1.7\n")
    monkeypatch.setattr(document_parser, "_pdf_page_count", lambda _path: 2)
    calls: list[tuple[str, str]] = []

    def fake_parse(_path: Path, *, tier: str, ocr_mode: str) -> dict[str, Any]:
        calls.append((tier, ocr_mode))
        if tier == "flash":
            return _middle([_page(0, "原生文本"), _page(1, "")])
        return _middle([_page(0, "原生文本"), _page(1, "扫描页")], mode="ocr")

    monkeypatch.setattr(document_parser, "_parse_with_mineru", fake_parse)
    units = document_parser.parse_document(path, ".pdf", "auto")
    assert calls == [("flash", "txt"), ("basic", "auto")]
    assert len(units) == 2
    assert units[1].ocr_derived


def test_explicit_flash_keeps_unreadable_page_for_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"%PDF-1.7\n")
    monkeypatch.setattr(document_parser, "_pdf_page_count", lambda _path: 1)
    calls: list[str] = []

    def fake_parse(_path: Path, *, tier: str, ocr_mode: str) -> dict[str, Any]:
        calls.append(tier)
        return _middle([_page(0, "")])

    monkeypatch.setattr(document_parser, "_parse_with_mineru", fake_parse)
    units = document_parser.parse_document(path, ".pdf", "flash")
    assert calls == ["flash"]
    assert units[0].blocks == []


def test_non_pdf_office_always_uses_flash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "report.docx"
    path.write_bytes(b"test")
    calls: list[tuple[str, str]] = []

    def fake_parse(_path: Path, *, tier: str, ocr_mode: str) -> dict[str, Any]:
        calls.append((tier, ocr_mode))
        return _middle([_page(0, "正文")])

    monkeypatch.setattr(document_parser, "_parse_with_mineru", fake_parse)
    assert len(document_parser.parse_document(path, ".docx", "auto")) == 1
    assert calls == [("flash", "auto")]


def test_pdf_over_100_pages_is_rejected() -> None:
    with pytest.raises(document_parser.DocumentParseError) as exc:
        document_parser.parse_middle_json(_middle([_page(i, "正文") for i in range(101)]), ".pdf")
    assert exc.value.code == "PAGE_LIMIT_EXCEEDED"


def test_pdf_page_count_is_checked_before_mineru(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "oversized.pdf"
    path.write_bytes(b"%PDF-1.7\n")
    monkeypatch.setattr(document_parser, "_pdf_page_count", lambda _path: 101)
    monkeypatch.setattr(document_parser, "_parse_with_mineru", lambda *_args, **_kwargs: pytest.fail("called MinerU"))
    with pytest.raises(document_parser.DocumentParseError) as exc:
        document_parser.parse_document(path, ".pdf", "auto")
    assert exc.value.code == "PAGE_LIMIT_EXCEEDED"


def test_image_pixels_are_checked_before_mineru(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "oversized.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(document_parser, "_image_pixels", lambda _path: 25_000_001)
    monkeypatch.setattr(document_parser, "_parse_with_mineru", lambda *_args, **_kwargs: pytest.fail("called MinerU"))
    with pytest.raises(document_parser.DocumentParseError) as exc:
        document_parser.parse_document(path, ".png", "auto")
    assert exc.value.code == "IMAGE_PIXEL_LIMIT_EXCEEDED"
