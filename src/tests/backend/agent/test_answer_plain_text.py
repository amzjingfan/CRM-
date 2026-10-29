"""买家草稿使用纯文本排版；保留业务值中的星号与原文。"""

import pytest

from app.agents.runtime.output import plain_text_answer


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "**Order delivered**\n\nPlease check the *tracking history*.",
            "Order delivered\n\nPlease check the tracking history.",
        ),
        ("## Details\n\n- **Item:** Walking pad\n- Quantity: 1", "Details\n\n• Item: Walking pad\n• Quantity: 1"),
        ("1. Ordered\n2. Delivered", "1. Ordered\n2. Delivered"),
        ("SKU `AB*12` costs $19.99; 2 * 3 = 6.", "SKU AB*12 costs $19.99; 2 * 3 = 6."),
        ("See [tracking](https://example.invalid/track).", "See tracking (https://example.invalid/track)."),
        ("```text\nSKU AB*12\n```", "SKU AB*12"),
    ],
)
def test_markdown_is_presented_as_readable_plain_text(source, expected):
    assert plain_text_answer(source) == expected


def test_table_preserves_headers_and_business_values():
    text = plain_text_answer("| Item | Quantity |\n| --- | --- |\n| AB*12 | 1 |")
    assert text == "Item | Quantity\nAB*12 | 1"


def test_existing_plain_text_and_literal_asterisks_are_not_rewritten():
    text = "Order AB*12: 1 item, $19.99.\nLatest status: delivered."
    assert plain_text_answer(text) == text


def test_verified_business_literals_are_preserved_even_when_they_look_like_markup():
    assert (
        plain_text_answer("**Item:** AB*12*XY and A_B_C", literal_values=("AB*12*XY", "A_B_C"))
        == "Item: AB*12*XY and A_B_C"
    )
