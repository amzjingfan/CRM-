"""清洗只删确定噪声，关键事实保留；任何问题阻断整版本入库。"""

import json
from pathlib import Path
from typing import Any

import pytest

from app.knowledge_base.document_cleaning import clean_document, clean_unit, version_requires_review
from app.knowledge_base.document_parser import ParsedUnit

SAMPLE_PATH = Path(__file__).resolve().parents[2] / "ai" / "datasets" / "rag-cleaning-v1.json"


def _unit(
    index: int,
    blocks: list[dict[str, Any]],
    *,
    ocr: bool = False,
    kind: str = "page",
) -> ParsedUnit:
    return ParsedUnit(
        index=index,
        kind=kind,
        locator={"page": index + 1},
        blocks=blocks,
        parse_mode="ocr" if ocr else "txt",
        ocr_derived=ocr,
        parser_version="4.0.12",
    )


def _text(content: str, *, bbox: list[float] | None = None) -> dict[str, Any]:
    block: dict[str, Any] = {"type": "text", "content": [{"type": "text", "content": content}]}
    if bbox is not None:
        block["bbox"] = bbox
    return block


@pytest.mark.parametrize("case_index", [0, 1])
def test_fixed_samples_keep_every_critical_field(case_index: int) -> None:
    dataset = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    case = dataset["cases"][case_index]
    block_type = "table" if case_index == 1 else "text"
    clean = clean_unit(_unit(0, [{"type": block_type, "content": case["source"]}]))
    assert all(value in clean.cleaned_text for value in case["must_keep"])
    assert not clean.needs_review


def test_repeated_margin_header_and_page_numbers_removed_without_changing_policy() -> None:
    units = [
        _unit(
            0,
            [
                _text("Company Memo", bbox=[0.1, 0.01, 0.5, 0.04]),
                _text("不支持退款。"),
                _text("Page 1", bbox=[0.4, 0.96, 0.6, 0.99]),
            ],
        ),
        _unit(
            1,
            [
                _text("Company Memo", bbox=[0.1, 0.01, 0.5, 0.04]),
                _text("金额 ¥20.00。"),
                _text("Page 2", bbox=[0.4, 0.96, 0.6, 0.99]),
            ],
        ),
    ]
    cleaned = clean_document(units)
    assert len(cleaned) == 2
    assert all("Company Memo" not in item.cleaned_text and "Page" not in item.cleaned_text for item in cleaned)
    assert "不支持退款" in cleaned[0].cleaned_text
    assert "¥20.00" in cleaned[1].cleaned_text


def test_repeated_negative_policy_at_margin_is_not_dropped() -> None:
    units = [
        _unit(0, [_text("No refunds", bbox=[0.1, 0.95, 0.5, 0.99])]),
        _unit(1, [_text("No refunds", bbox=[0.1, 0.95, 0.5, 0.99])]),
    ]
    assert all("No refunds" in item.cleaned_text for item in clean_document(units))


def test_ocr_derived_key_content_blocks_whole_version() -> None:
    cleaned = clean_document([_unit(0, [_text("原生文字")]), _unit(1, [_text("SKU-2 ¥90")], ocr=True)])
    assert cleaned[1].needs_review
    assert "OCR_REVIEW_REQUIRED" in cleaned[1].issue_codes
    assert version_requires_review(cleaned)
    assert not version_requires_review([cleaned[0]])


def test_mineru_office_paragraph_title_is_supported_content() -> None:
    unit = _unit(
        0,
        [
            {"type": "paragraph_title", "content": "Warehouse handling policy", "level": 1},
            {"type": "text", "content": "SKU-AX1 ships only after payment confirmation."},
        ],
        kind="document_unit",
    )
    cleaned = clean_unit(unit)
    assert not cleaned.needs_review
    assert "Warehouse handling policy" in cleaned.cleaned_text


@pytest.mark.parametrize(
    ("blocks", "expected_code"),
    [
        ([], "EMPTY_UNIT"),
        ([_text("退款�期限")], "TEXT_CORRUPTED"),
        ([{"type": "image", "content": []}], "NON_TEXT_CONTENT_UNRECOGNIZED"),
        ([_text("正文"), {"type": "text", "content": []}], "PARSED_CONTENT_INCOMPLETE"),
        ([_text("正文"), {"type": "unknown", "content": []}], "UNKNOWN_BLOCK_TYPE"),
        (
            [{"type": "table", "content": "<table><tr><th>SKU</th><th>金额</th></tr><tr><td>A-1</td></tr></table>"}],
            "TABLE_ROW_INCOMPLETE",
        ),
    ],
)
def test_unreliable_content_requires_review(blocks: list[dict[str, Any]], expected_code: str) -> None:
    clean = clean_unit(_unit(0, blocks))
    assert clean.needs_review
    assert expected_code in clean.issue_codes


def test_no_units_cannot_be_auto_approved() -> None:
    assert version_requires_review([])


def test_table_without_explicit_header_requires_review() -> None:
    html = "<table><tr><td>SKU</td><td>金额</td></tr><tr><td>A-1</td><td>¥20</td></tr></table>"
    clean = clean_unit(_unit(0, [{"type": "table", "content": html}]))
    assert clean.needs_review
    assert "TABLE_HEADER_UNVERIFIED" in clean.issue_codes
