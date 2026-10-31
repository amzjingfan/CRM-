"""原生订单卡片仅能发送已核验的当前买家订单。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.integrations.tiktok_read import TikTokOrder
from app.shared.exceptions.errors import AppError, ErrorCode
from app.workspace import service


def order_context(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    order = TikTokOrder.model_validate(
        {
            "id": "600001",
            "user_id": "900001",
            "status": "DELIVERED",
            "line_items": [{"sku_id": "200001", "product_name": "Walking pad"}],
        }
    )
    conversation = SimpleNamespace(platform="tiktok", store_id=uuid.uuid4(), status="active")
    monkeypatch.setattr(service, "_verified_sidebar_order", AsyncMock(return_value=(conversation, object(), order)))
    monkeypatch.setattr(service, "_connected_send_channel", AsyncMock(return_value=object()))
    monkeypatch.setattr(service, "_message_send_mode", lambda *_: "real")
    return SimpleNamespace(
        get=AsyncMock(return_value=SimpleNamespace(raw_payload={"delivery_mode": "real"})), commit=AsyncMock()
    )


@pytest.mark.asyncio
async def test_order_card_requires_confirmation_before_read_or_send(monkeypatch: pytest.MonkeyPatch) -> None:
    session = order_context(monkeypatch)
    send = AsyncMock()
    monkeypatch.setattr(service, "send_agent_message", send)
    with pytest.raises(AppError) as raised:
        await service.send_agent_order_card(session, SimpleNamespace(), uuid.uuid4(), "600001", "key", confirmed=False)
    assert raised.value.status_code == 422
    service._verified_sidebar_order.assert_not_awaited()  # type: ignore[attr-defined]
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_order_card_sends_native_type_and_persists_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    session = order_context(monkeypatch)
    send = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    monkeypatch.setattr(service, "send_agent_message", send)
    monkeypatch.setattr(service, "_message_view", lambda message: message.raw_payload)
    result = await service.send_agent_order_card(
        session, SimpleNamespace(), uuid.uuid4(), "600001", "key", confirmed=True
    )
    assert send.await_args.kwargs["message_type"] == "order_card"
    assert send.await_args.kwargs["card_order_id"] == "600001"
    assert result["card"]["kind"] == "order_card"
    assert result["card"]["order_id"] == "600001"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_order_card_rejects_unverified_order_without_send(monkeypatch: pytest.MonkeyPatch) -> None:
    session = order_context(monkeypatch)
    monkeypatch.setattr(
        service,
        "_verified_sidebar_order",
        AsyncMock(side_effect=AppError(ErrorCode.RESOURCE_NOT_FOUND, "订单不存在", 404)),
    )
    send = AsyncMock()
    monkeypatch.setattr(service, "send_agent_message", send)
    with pytest.raises(AppError) as raised:
        await service.send_agent_order_card(session, SimpleNamespace(), uuid.uuid4(), "600002", "key", confirmed=True)
    assert raised.value.status_code == 404
    send.assert_not_awaited()
