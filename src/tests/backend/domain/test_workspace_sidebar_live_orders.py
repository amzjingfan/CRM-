"""客户侧栏按官方会话身份只读关联订单的行为测试。"""

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.integrations.tiktok_read import TikTokConversation, TikTokOrder
from app.shared.exceptions.errors import AppError
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
