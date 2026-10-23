"""九种通用文档策略必须真的按选择和大小产生可追溯块。"""

from dataclasses import replace
from typing import Any

import pytest

from app.knowledge_base.document_chunking import DocumentChunkError, _token_windows, chunk_document
from app.knowledge_base.document_cleaning import CleanedUnit
from app.knowledge_base.document_schemas import DocumentIndexConfig


class CharacterTokenizer:
    def encode(self, text: str) -> list[int]:
        return [ord(char) for char in text]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(token) for token in tokens)


TOKENIZER = CharacterTokenizer()


def test_token_window_rechecks_actual_decoded_token_count() -> None:
    class BoundaryExpandingTokenizer(CharacterTokenizer):
        def decode(self, tokens: list[int]) -> str:
            text = super().decode(tokens)
            return text + (" " if text.startswith("D") else "")

    tokenizer = BoundaryExpandingTokenizer()
    windows = _token_windows("ABCDEFGHIJKL", 4, 1, tokenizer)
    assert len(windows) > 1
    assert all(len(tokenizer.encode(window)) <= 4 for window in windows)
    assert all(char in "".join(windows) for char in "ABCDEFGHIJKL")


def _clean(
    index: int,
    content: str,
    *,
    kind: str = "page",
    blocks: list[dict[str, Any]] | None = None,
    ocr: bool = False,
) -> CleanedUnit:
    return CleanedUnit(
        index=index,
        kind=kind,
        locator={"page": index + 1} if kind == "page" else {"source_unit": index},
        raw_text=content,
        cleaned_text=content,
        blocks=blocks or [{"type": "text", "content": [{"type": "text", "content": content}]}],
        issue_codes=[],
        needs_review=False,
        parse_mode="ocr" if ocr else "txt",
        ocr_derived=ocr,
        parser_version="4.0.12",
    )


@pytest.mark.parametrize(
    ("strategy", "suffix", "content"),
    [
        ("recursive", ".pdf", "# 退款规则\n无凭证不得退款。\n申请期限为七天。"),
        ("heading_paragraph", ".md", "# 退款规则\n无凭证不得退款。\n申请期限为七天。"),
        ("sentence", ".txt", "无凭证不得退款。申请期限为七天。"),
        ("fixed_token", ".docx", "Alpha beta gamma delta epsilon zeta eta theta."),
        ("fixed_char", ".txt", "Alpha beta gamma delta epsilon zeta eta theta."),
        ("page_slide", ".pdf", "第一页内容。第二句内容。"),
        ("ocr_layout", ".png", "图片中的商品编号 SKU-123。"),
    ],
)
def test_non_table_strategies_make_scoped_chunks(strategy: str, suffix: str, content: str) -> None:
    unit = _clean(0, content, ocr=strategy == "ocr_layout")
    chunks = chunk_document(
        [unit], DocumentIndexConfig(strategy=strategy, chunk_size=32, overlap=4), TOKENIZER, suffix=suffix
    )
    assert chunks
    assert all(
        chunk.strategy == strategy and chunk.locator == unit.locator and chunk.unit_index == 0 for chunk in chunks
    )
    assert all(chunk.token_count <= 32 and chunk.content for chunk in chunks)


def test_selected_size_and_overlap_change_fixed_token_boundaries() -> None:
    source = "ABCDEFGHIJ" * 12
    small = chunk_document(
        [_clean(0, source)],
        DocumentIndexConfig(strategy="fixed_token", chunk_size=32, overlap=0),
        TOKENIZER,
        suffix=".txt",
    )
    large = chunk_document(
        [_clean(0, source)],
        DocumentIndexConfig(strategy="fixed_token", chunk_size=64, overlap=0),
        TOKENIZER,
        suffix=".txt",
    )
    overlapped = chunk_document(
        [_clean(0, source)],
        DocumentIndexConfig(strategy="fixed_token", chunk_size=32, overlap=5),
        TOKENIZER,
        suffix=".txt",
    )
    assert len(small) > len(large)
    assert small[0].content != large[0].content
    assert overlapped[1].content.startswith(overlapped[0].content[-5:])


def test_fixed_character_window_uses_unicode_characters_and_actual_token_count() -> None:
    source = "中文SKU-A金额¥20.00" * 8
    chunks = chunk_document(
        [_clean(0, source)],
        DocumentIndexConfig(strategy="fixed_char", chunk_size=32, overlap=4),
        TOKENIZER,
        suffix=".txt",
    )
    assert len(chunks) > 1
    assert all(len(chunk.content) <= 32 and chunk.token_count == len(chunk.content) for chunk in chunks)
    assert chunks[1].content.startswith(chunks[0].content[-4:])


def test_page_strategy_never_crosses_source_pages() -> None:
    units = [_clean(0, "第一页。"), _clean(1, "第二页。")]
    chunks = chunk_document(
        units, DocumentIndexConfig(strategy="page_slide", chunk_size=32, overlap=4), TOKENIZER, suffix=".pdf"
    )
    assert [(chunk.unit_index, chunk.locator["page"]) for chunk in chunks] == [(0, 1), (1, 2)]
    assert chunks[0].content.startswith("第 1 页\n")
    assert chunks[1].content.startswith("第 2 页\n")
    assert "第二页" not in chunks[0].content


def test_heading_strategy_keeps_heading_path() -> None:
    unit = _clean(0, "# 售后政策\n## 退款\n无凭证不得退款。", kind="document_unit")
    chunks = chunk_document(
        [unit], DocumentIndexConfig(strategy="heading_paragraph", chunk_size=32, overlap=0), TOKENIZER, suffix=".md"
    )
    assert any(chunk.heading_path == ["售后政策", "退款"] for chunk in chunks)


def test_heading_strategy_uses_mineru_office_title_blocks() -> None:
    unit = _clean(
        0,
        "Warehouse handling policy\nSKU-AX1 ships only after payment confirmation.",
        kind="document_unit",
        blocks=[
            {"type": "paragraph_title", "content": "Warehouse handling policy", "level": 1},
            {"type": "text", "content": "SKU-AX1 ships only after payment confirmation."},
        ],
    )
    chunks = chunk_document(
        [unit],
        DocumentIndexConfig(strategy="heading_paragraph", chunk_size=80, overlap=0),
        TOKENIZER,
        suffix=".docx",
    )
    assert len(chunks) == 1
    assert chunks[0].heading_path == ["Warehouse handling policy"]
    assert "SKU-AX1 ships" in chunks[0].content


def test_semantic_strategy_uses_supplied_sentence_vectors_for_boundary() -> None:
    unit = _clean(0, "退款期限为七天。无凭证不得退款。物流单号可在订单页查看。")
    config = DocumentIndexConfig(strategy="semantic_similarity", chunk_size=64, overlap=0)
    with pytest.raises(DocumentChunkError) as missing:
        chunk_document([unit], config, TOKENIZER, suffix=".txt")
    assert missing.value.code == "SEMANTIC_VECTORS_REQUIRED"
    chunks = chunk_document(
        [unit],
        config,
        TOKENIZER,
        suffix=".txt",
        semantic_vectors={0: [[1.0, 0.0], [0.99, 0.01], [0.0, 1.0]]},
    )
    assert len(chunks) == 2
    assert "物流" not in chunks[0].content and "物流" in chunks[1].content


def test_table_rows_repeat_header_and_reject_oversized_row() -> None:
    html = (
        "<table><tr><th>SKU</th><th>金额</th></tr>"
        + "".join(f"<tr><td>A-{index}</td><td>¥{index}.00</td></tr>" for index in range(6))
        + "</table>"
    )
    unit = _clean(0, html, kind="document_unit", blocks=[{"type": "table", "content": html}])
    config = DocumentIndexConfig(strategy="table_rows", chunk_size=32, overlap=0)
    chunks = chunk_document([unit], config, TOKENIZER, suffix=".xlsx")
    assert len(chunks) > 1
    assert all("SKU" in chunk.content and "金额" in chunk.content for chunk in chunks)
    assert all(chunk.token_count <= 32 for chunk in chunks)
    huge = "<table><tr><th>SKU</th></tr><tr><td>" + "X" * 100 + "</td></tr></table>"
    with pytest.raises(DocumentChunkError) as oversized:
        chunk_document(
            [_clean(0, huge, blocks=[{"type": "table", "content": huge}])], config, TOKENIZER, suffix=".xlsx"
        )
    assert oversized.value.code == "ROW_TOO_LARGE_REVIEW_REQUIRED"


def test_table_strategy_defaults_to_zero_overlap_and_rejects_nonzero_overlap() -> None:
    assert DocumentIndexConfig(strategy="table_rows").overlap == 0
    with pytest.raises(DocumentChunkError) as error:
        chunk_document(
            [_clean(0, "SKU | 金额")],
            DocumentIndexConfig(strategy="table_rows", overlap=10),
            TOKENIZER,
            suffix=".xlsx",
        )
    assert error.value.code == "TABLE_OVERLAP_UNSUPPORTED"


@pytest.mark.parametrize(
    ("strategy", "suffix"),
    [("page_slide", ".txt"), ("ocr_layout", ".docx"), ("table_rows", ".txt")],
)
def test_incompatible_format_strategy_is_rejected(strategy: str, suffix: str) -> None:
    with pytest.raises(DocumentChunkError) as error:
        chunk_document([_clean(0, "正文")], DocumentIndexConfig(strategy=strategy), TOKENIZER, suffix=suffix)
    assert error.value.code == "STRATEGY_FORMAT_UNSUPPORTED"


def test_unknown_suffix_is_rejected_even_for_general_strategy() -> None:
    with pytest.raises(DocumentChunkError) as error:
        chunk_document([_clean(0, "正文")], DocumentIndexConfig(), TOKENIZER, suffix=".exe")
    assert error.value.code == "FILE_TYPE_UNSUPPORTED"


def test_unreviewed_unit_and_chunk_limit_fail_closed() -> None:
    pending = _clean(0, "待复核")
    pending = replace(pending, needs_review=True)
    with pytest.raises(DocumentChunkError) as error:
        chunk_document([pending], DocumentIndexConfig(), TOKENIZER, suffix=".txt")
    assert error.value.code == "VERSION_REVIEW_REQUIRED"
    with pytest.raises(DocumentChunkError) as limit:
        chunk_document(
            [_clean(0, "A" * 65_000)],
            DocumentIndexConfig(strategy="fixed_token", chunk_size=32, overlap=0),
            TOKENIZER,
            suffix=".txt",
        )
    assert limit.value.code == "CHUNK_LIMIT_EXCEEDED"
