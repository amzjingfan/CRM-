"""TikTok 富消息必须穿过通知和历史同步的展示契约。"""

import uuid
from datetime import UTC, datetime

from app.conversations.models import Message
from app.integrations.adapters import TikTokAdapter
from app.integrations.tiktok_message import parse_tiktok_message
from app.workspace.service import _message_view


def _event(kind: str, content: str, data: str | None = None):
    return TikTokAdapter._resolve_message_event(
        "event-1",
        "shop-1",
        {
            "sender": {"role": "BUYER", "im_user_id": "101"},
            "conversation_id": "501",
            "message_id": "701",
            "type": kind,
            "content": content,
            "data": data,
            "create_time": 1_700_000_001,
        },
    )


def test_image_and_video_events_preserve_platform_media() -> None:
    image = _event("IMAGE", '{"url":"https://cdn.example/image.jpg","width":"304","height":"290"}')
    video = _event(
        "VIDEO",
        '{"url":"https://cdn.example/video.mp4","cover":"https://cdn.example/cover.jpg","vid":"v1","expire_time":"1999999999"}',
    )
    assert image is not None and image.message_type == "image"
    assert image.display_data["media"]["url"] == "https://cdn.example/image.jpg"
    assert video is not None and video.message_type == "video"
    assert video.display_data["media"]["cover"] == "https://cdn.example/cover.jpg"


def test_product_and_order_cards_preserve_structured_details() -> None:
    product = _event(
        "PRODUCT_CARD",
        '{"product_id":"123"}',
        '{"product_id":"123","product_name":"Hat","product_image":"https://cdn.example/hat.jpg","product_lowest_price":"$9"}',
    )
    order = _event(
        "ORDER_CARD",
        '{"order_id":"456"}',
        '{"order_id":"456","order_status":"SHIPPED","product_name":"Hat"}',
    )
    assert product is not None and product.message_type == "product_card"
    assert product.display_data["card"]["title"] == "Hat"
    assert order is not None and order.display_data["card"]["order_id"] == "456"
    assert order.display_data["card"]["status"] == "SHIPPED"


def test_other_tiktok_rich_types_do_not_fall_back_to_type_placeholders() -> None:
    cases = [
        ("EMOTICONS", '{"url":"https://cdn.example/sticker.webp"}', None, "media"),
        ("BUYER_ENTER_FROM_PRODUCT", '{"product_id":"123"}', None, "card"),
        ("BUYER_ENTER_FROM_ORDER", '{"order_id":"456"}', None, "card"),
        ("RETURN_REFUND_CARD", '{"order_id":"456","sku_id":"7"}', None, "card"),
        ("COUPON_CARD", '{"coupon_id":"8"}', None, "card"),
        (
            "LOGISTICS_CARD",
            '{"order_id":"456","package_id":"9"}',
            '{"packages":[{"product_name":"Hat","tracking_number":"T1"}]}',
            "card",
        ),
    ]
    for kind, content, data, expected_field in cases:
        label, display = parse_tiktok_message(kind, content, data)
        assert not label.startswith("[TikTok ")
        assert expected_field in display


def test_logistics_card_keeps_each_platform_package() -> None:
    _, display = parse_tiktok_message(
        "LOGISTICS_CARD",
        '{"order_id":"456"}',
        '{"packages":[{"package_id":"1","product_name":"Hat","tracking_number":"T1"},{"package_id":"2","product_name":"Scarf","tracking_number":"T2"}]}',
    )
    assert [item["tracking_number"] for item in display["card"]["packages"]] == ["T1", "T2"]


def test_media_url_must_be_https_and_message_view_exposes_rich_card() -> None:
    _, display = parse_tiktok_message("IMAGE", '{"url":"javascript:alert(1)"}')
    assert display == {"media": {}}
    card = {"kind": "product_card", "title": "Hat", "product_id": "123"}
    message = Message(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        platform="tiktok",
        external_message_id="701",
        role="user",
        direction="inbound",
        content="商品卡片",
        message_type="product_card",
        status="received",
        raw_payload={"card": card},
        created_at=datetime.now(UTC),
    )
    assert _message_view(message).rich_card is not None
    assert _message_view(message).rich_card.title == "Hat"
    message.raw_payload = {"card": {"kind": "logistics_card", "packages": [{"tracking_number": "T2"}]}}
    assert _message_view(message).rich_card.packages[0].tracking_number == "T2"
