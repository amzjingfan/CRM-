"""客户侧栏按官方会话身份只读关联订单的行为测试。"""

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.integrations.tiktok_read import TikTokConversation, TikTokCoupon, TikTokOrder, TikTokStandardTrackingEntry
from app.shared.exceptions.errors import AppError, ErrorCode
from app.workspace import sidebar
from app.workspace.sidebar import SidebarSearch


def conversation() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        platform="tiktok",
        external_conversation_id="700001",
    )


def remote_conversation(im_user_id: str = "800001", user_id: str | None = "900001") -> TikTokConversation:
    return TikTokConversation.model_validate(
        {
            "id": "700001",
            "create_time": 1,
            "participants": [{"role": "BUYER", "im_user_id": im_user_id, "user_id": user_id}],
        }
    )


def live_order(user_id: str = "900001") -> TikTokOrder:
    return TikTokOrder.model_validate(
        {
            "id": "600001",
            "user_id": user_id,
            "status": "IN_TRANSIT",
            "create_time": 1_700_000_000,
            "tracking_number": "TRACK-1",
            "payment": {"currency": "USD", "total_amount": "97.90", "seller_discount": "5.00"},
            "line_items": [
                {
                    "id": "400001",
                    "product_id": "300001",
                    "sku_id": "200001",
                    "seller_sku": "PAD-1",
                    "product_name": "Walking pad",
                    "sku_name": "Black",
                    "sale_price": "97.90",
                }
            ],
        }
    )


@pytest.mark.asyncio
async def test_live_orders_show_official_buyer_order_and_search(monkeypatch: pytest.MonkeyPatch) -> None:
    selected = conversation()
    session = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(store_id=selected.store_id, platform="tiktok", external_customer_id="800001")
        )
    )
    client = SimpleNamespace(
        get_conversation=AsyncMock(return_value=remote_conversation()),
        search_orders=AsyncMock(return_value=([live_order()], None, None)),
    )
    monkeypatch.setattr(sidebar, "_tiktok_client", AsyncMock(return_value=client))

    result = await sidebar._search_live_orders(
        session, selected, SidebarSearch(section="orders", field="sellerSku", query="PAD-1")
    )

    assert result.pagination.total == 1
    assert result.items[0].external_order_id == "600001"
    assert result.items[0].total_amount == Decimal("97.90")
    assert result.items[0].items[0].sku_id == "200001"
    assert result.items[0].tracking_number == "TRACK-1"
    assert result.items[0].live_detail_available is True
    client.search_orders.assert_awaited_once_with(page_size=100, page_token=None, buyer_user_id="900001")


@pytest.mark.asyncio
async def test_live_orders_reject_mismatched_im_identity_before_order_request(monkeypatch: pytest.MonkeyPatch) -> None:
    selected = conversation()
    session = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(store_id=selected.store_id, platform="tiktok", external_customer_id="800001")
        )
    )
    client = SimpleNamespace(
        get_conversation=AsyncMock(return_value=remote_conversation(im_user_id="800002")),
        search_orders=AsyncMock(),
    )
    monkeypatch.setattr(sidebar, "_tiktok_client", AsyncMock(return_value=client))

    with pytest.raises(AppError) as raised:
        await sidebar._search_live_orders(session, selected, SidebarSearch(section="orders", field="order"))
    assert raised.value.status_code == 502
    client.search_orders.assert_not_awaited()


@pytest.mark.asyncio
async def test_live_orders_reject_cross_buyer_response(monkeypatch: pytest.MonkeyPatch) -> None:
    selected = conversation()
    session = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(store_id=selected.store_id, platform="tiktok", external_customer_id="800001")
        )
    )
    client = SimpleNamespace(
        get_conversation=AsyncMock(return_value=remote_conversation()),
        search_orders=AsyncMock(return_value=([live_order(user_id="900002")], None, None)),
    )
    monkeypatch.setattr(sidebar, "_tiktok_client", AsyncMock(return_value=client))

    with pytest.raises(AppError) as raised:
        await sidebar._search_live_orders(session, selected, SidebarSearch(section="orders", field="order"))
    assert raised.value.status_code == 502


def test_live_order_invalid_amount_fails_closed() -> None:
    order = live_order()
    assert order.payment is not None
    order.payment.total_amount = "invalid"
    with pytest.raises(AppError) as raised:
        sidebar._live_order_view(order)
    assert raised.value.status_code == 502


def test_live_order_keeps_actual_paid_time_without_inventing_payment_state() -> None:
    order = live_order()
    order.paid_time = 1_700_000_100
    result = sidebar._live_order_view(order)
    assert result.paid_at is not None
    assert result.paid_at.isoformat() == "2023-11-14T22:15:00+00:00"
    assert result.payment_status is None


def test_coupon_money_discount_is_formatted_without_python_mapping_text() -> None:
    coupon = TikTokCoupon.model_validate(
        {
            "id": "123",
            "title": "Shop coupon",
            "status": "EXPIRED",
            "display_type": "REGULAR",
            "discount": {"type": "AMOUNT_OFF", "reduction_amount": {"amount": "10", "currency": "$"}},
        }
    )
    result = sidebar._coupon_view(coupon)
    assert result.discount_type == "AMOUNT_OFF"
    assert result.discount_value == "$10.00"


def test_coupon_unknown_discount_shape_has_no_fabricated_value() -> None:
    coupon = TikTokCoupon.model_validate(
        {"id": "123", "title": "Shop coupon", "discount": {"type": "AMOUNT_OFF", "reduction_amount": {"wrong": "10"}}}
    )
    assert sidebar._coupon_view(coupon).discount_value is None


@pytest.mark.asyncio
async def test_order_detail_shows_official_fields_and_newest_tracking(monkeypatch: pytest.MonkeyPatch) -> None:
    selected = conversation()
    monkeypatch.setattr(sidebar, "get_settings", lambda: SimpleNamespace(real_tiktok_read_enabled=True))
    order = live_order()
    order.shipping_provider = "Carrier A"
    order.payment_method_name = "Card"
    client = SimpleNamespace(
        get_conversation=AsyncMock(return_value=remote_conversation()),
        get_order_details=AsyncMock(return_value=([order], None)),
        get_standard_tracking=AsyncMock(
            return_value=(
                [
                    TikTokStandardTrackingEntry(
                        description="Delivered", update_time_millis=1700000002000, action_code=2
                    ),
                    TikTokStandardTrackingEntry(
                        description="Dispatched", update_time_millis=1700000001000, action_code=1
                    ),
                ],
                None,
            )
        ),
    )
    monkeypatch.setattr(sidebar, "_conversation", AsyncMock(return_value=selected))
    monkeypatch.setattr(sidebar, "_tiktok_client", AsyncMock(return_value=client))
    session = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(store_id=selected.store_id, platform="tiktok", external_customer_id="800001")
        )
    )

    result = await sidebar.get_sidebar_order_detail(session, SimpleNamespace(), selected.id, "600001")

    assert result.payment_method_name == "Card"
    assert result.shipping_provider == "Carrier A"
    assert result.latest_tracking_description == "Delivered"
    assert result.latest_tracking_at.isoformat() == "2023-11-14T22:13:22+00:00"
    client.get_order_details.assert_awaited_once_with(["600001"])
    client.get_standard_tracking.assert_awaited_once_with("600001")


@pytest.mark.asyncio
async def test_order_detail_rejects_other_conversation_buyer_before_order_read(monkeypatch: pytest.MonkeyPatch) -> None:
    selected = conversation()
    monkeypatch.setattr(sidebar, "get_settings", lambda: SimpleNamespace(real_tiktok_read_enabled=True))
    client = SimpleNamespace(
        get_conversation=AsyncMock(return_value=remote_conversation(im_user_id="800002")),
        get_order_details=AsyncMock(),
        get_standard_tracking=AsyncMock(),
    )
    monkeypatch.setattr(sidebar, "_conversation", AsyncMock(return_value=selected))
    monkeypatch.setattr(sidebar, "_tiktok_client", AsyncMock(return_value=client))
    session = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(store_id=selected.store_id, platform="tiktok", external_customer_id="800001")
        )
    )

    with pytest.raises(AppError) as raised:
        await sidebar.get_sidebar_order_detail(session, SimpleNamespace(), selected.id, "600001")
    assert raised.value.status_code == 502
    client.get_order_details.assert_not_awaited()
    client.get_standard_tracking.assert_not_awaited()


@pytest.mark.asyncio
async def test_order_detail_rejects_cross_buyer_order_before_tracking(monkeypatch: pytest.MonkeyPatch) -> None:
    selected = conversation()
    monkeypatch.setattr(sidebar, "get_settings", lambda: SimpleNamespace(real_tiktok_read_enabled=True))
    client = SimpleNamespace(
        get_conversation=AsyncMock(return_value=remote_conversation()),
        get_order_details=AsyncMock(return_value=([live_order(user_id="900002")], None)),
        get_standard_tracking=AsyncMock(),
    )
    monkeypatch.setattr(sidebar, "_conversation", AsyncMock(return_value=selected))
    monkeypatch.setattr(sidebar, "_tiktok_client", AsyncMock(return_value=client))
    session = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(store_id=selected.store_id, platform="tiktok", external_customer_id="800001")
        )
    )

    with pytest.raises(AppError) as raised:
        await sidebar.get_sidebar_order_detail(session, SimpleNamespace(), selected.id, "600001")
    assert raised.value.status_code == 404
    client.get_standard_tracking.assert_not_awaited()


@pytest.mark.asyncio
async def test_order_detail_requires_real_read_mode_before_platform_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    selected = conversation()
    monkeypatch.setattr(sidebar, "_conversation", AsyncMock(return_value=selected))
    monkeypatch.setattr(sidebar, "_tiktok_client", AsyncMock())
    monkeypatch.setattr(sidebar, "get_settings", lambda: SimpleNamespace(real_tiktok_read_enabled=False))

    with pytest.raises(AppError) as raised:
        await sidebar.get_sidebar_order_detail(SimpleNamespace(), SimpleNamespace(), selected.id, "600001")
    assert raised.value.status_code == 404
    sidebar._tiktok_client.assert_not_awaited()


@pytest.mark.asyncio
async def test_order_detail_rejects_non_ascii_order_id_before_platform_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    selected = conversation()
    monkeypatch.setattr(sidebar, "_conversation", AsyncMock(return_value=selected))
    monkeypatch.setattr(sidebar, "_tiktok_client", AsyncMock())
    monkeypatch.setattr(sidebar, "get_settings", lambda: SimpleNamespace(real_tiktok_read_enabled=True))

    with pytest.raises(AppError) as raised:
        await sidebar.get_sidebar_order_detail(SimpleNamespace(), SimpleNamespace(), selected.id, "٦٠٠٠٠١")
    assert raised.value.status_code == 422
    sidebar._tiktok_client.assert_not_awaited()


@pytest.mark.asyncio
async def test_order_detail_does_not_return_partial_fields_when_tracking_scope_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = conversation()
    monkeypatch.setattr(sidebar, "get_settings", lambda: SimpleNamespace(real_tiktok_read_enabled=True))
    client = SimpleNamespace(
        get_conversation=AsyncMock(return_value=remote_conversation()),
        get_order_details=AsyncMock(return_value=([live_order()], None)),
        get_standard_tracking=AsyncMock(side_effect=AppError(ErrorCode.PERMISSION_DENIED, "缺少物流授权", 403)),
    )
    monkeypatch.setattr(sidebar, "_conversation", AsyncMock(return_value=selected))
    monkeypatch.setattr(sidebar, "_tiktok_client", AsyncMock(return_value=client))
    session = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(store_id=selected.store_id, platform="tiktok", external_customer_id="800001")
        )
    )

    with pytest.raises(AppError) as raised:
        await sidebar.get_sidebar_order_detail(session, SimpleNamespace(), selected.id, "600001")
    assert raised.value.status_code == 403
