"""只提取 TikTok 客服消息展示所需字段，不保存完整平台载荷。"""

import json
from urllib.parse import urlsplit

from app.shared.exceptions.errors import AppError, ErrorCode

CARD_TYPES = {
    "PRODUCT_CARD": "商品卡片",
    "BUYER_ENTER_FROM_PRODUCT": "买家查看的商品",
    "ORDER_CARD": "订单卡片",
    "BUYER_ENTER_FROM_ORDER": "买家查看的订单",
    "RETURN_REFUND_CARD": "售后卡片",
    "COUPON_CARD": "优惠券卡片",
    "LOGISTICS_CARD": "物流卡片",
}


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _text(value: object, limit: int = 500) -> str | None:
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None


def _display_value(value: object) -> str | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return _text(str(value))
    return _text(value)


def _url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 4096:
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    return value if parts.scheme == "https" and parts.hostname and not parts.username and not parts.password else None


def parse_tiktok_message(
    message_type: str, raw_content: object, raw_data: object = None, plaintext: object = None
) -> tuple[str, dict[str, object]]:
    """保留客服可见原意；链接只允许 HTTPS，视频 URL 必须由平台提供。"""
    if not isinstance(raw_content, str):
        raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 消息内容无效", 422)
    content = _object(raw_content)
    if not content and raw_content.strip() != "{}":
        raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 消息内容无效", 422)
    data = _object(raw_data)
    kind = message_type.upper()
    text = _text(content.get("content"), 4000)
    if kind in {"IMAGE", "VIDEO", "EMOTICONS"}:
        media: dict[str, object] = {}
        for key in ("url", "cover"):
            safe_url = _url(content.get(key))
            if safe_url:
                media[key] = safe_url
        for key in ("width", "height"):
            try:
                number = int(str(content.get(key)))
                if 0 < number <= 20_000:
                    media[key] = number
            except (TypeError, ValueError):
                pass
        if kind == "VIDEO":
            for key in ("vid", "duration", "expire_time"):
                value = _text(content.get(key), 100)
                if value:
                    media[key] = value
        return ({"IMAGE": "图片", "VIDEO": "视频", "EMOTICONS": "表情"}[kind], {"media": media})
    if kind in CARD_TYPES:
        card: dict[str, object] = {"kind": kind.lower()}
        for key in ("product_id", "order_id", "sku_id", "coupon_id", "package_id"):
            value = _text(content.get(key), 200)
            if value:
                card[key] = value
        for source, target in (
            ("product_name", "title"),
            ("product_image", "image_url"),
            ("product_lowest_price", "price"),
            ("paid_price", "paid_price"),
            ("order_status", "status"),
            ("sold_quantity", "sold_quantity"),
            ("quantity", "quantity"),
        ):
            raw_value = data.get(source)
            value = _url(raw_value) if target == "image_url" else _display_value(raw_value)
            if value:
                card[target] = value
        for source, target in (("product_link", "url"), ("order_link", "url")):
            value = _url(data.get(source))
            if value:
                card[target] = value
        if kind == "LOGISTICS_CARD":
            packages = data.get("packages")
            package_views: list[dict[str, str]] = []
            for package in packages[:20] if isinstance(packages, list) else []:
                if not isinstance(package, dict):
                    continue
                package_view: dict[str, str] = {}
                for source, target in (
                    ("product_name", "title"),
                    ("product_image", "image_url"),
                    ("package_id", "package_id"),
                    ("paid_price", "paid_price"),
                    ("quantity", "quantity"),
                    ("tracking_number", "tracking_number"),
                    ("shipping_provider_name", "carrier_name"),
                ):
                    raw_value = package.get(source)
                    value = _url(raw_value) if target == "image_url" else _display_value(raw_value)
                    if value:
                        package_view[target] = value
                tracking = package.get("tracking")
                if isinstance(tracking, list) and tracking and isinstance(tracking[0], dict):
                    description = _text(tracking[0].get("description"), 500)
                    if description:
                        package_view["latest_description"] = description
                if package_view:
                    package_views.append(package_view)
            if package_views:
                card["packages"] = package_views
        return CARD_TYPES[kind], {"card": card}
    return text or _text(plaintext, 4000) or "TikTok 消息（请在 TikTok Shop 查看）", {}
