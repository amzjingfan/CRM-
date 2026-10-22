"""原生物流卡片只引用当前买家订单中已核对的包裹。"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.integrations.tiktok_read import TikTokOrder
from app.shared.exceptions.errors import AppError
from app.workspace import service
from app.workspace.sidebar import SidebarTrackingEvent, SidebarTrackingPackage, SidebarTrackingTimeline


def card_context(monkeypatch: pytest.MonkeyPatch, package_id: str) -> tuple[SimpleNamespace, SimpleNamespace]:
    order = TikTokOrder.model_validate(
        {
            "id": "600001",
            "user_id": "900001",
            "status": "IN_TRANSIT",
            "line_items": [{"sku_id": "200001", "product_name": "Walking pad", "tracking_number": "TRACK-1"}],
        }
    )
    conversation = SimpleNamespace(platform="tiktok", store_id=uuid.uuid4(), status="active")
    client = SimpleNamespace(
        channel=SimpleNamespace(metadata_json={"seller_type": "CROSS_BORDER"}),
        get_standard_tracking=AsyncMock(),
    )
    monkeypatch.setattr(service, "_verified_sidebar_order", AsyncMock(return_value=(conversation, client, order)))
    monkeypatch.setattr(service, "_connected_send_channel", AsyncMock(return_value=object()))
    monkeypatch.setattr(service, "_message_send_mode", lambda *_: "real")
    monkeypatch.setattr(
        service,
        "get_sidebar_enhanced_tracking",
        AsyncMock(
            return_value=SidebarTrackingTimeline(
                packages=[
                    SidebarTrackingPackage(
                        package_id=package_id,
                        tracking_number="TRACK-1",
                        carrier_name="Carrier",
                        events=[
                            SidebarTrackingEvent(
                                description="Picked up",
                                occurred_at=datetime(2026, 10, 22, tzinfo=UTC),
                                action_code=1,
                            )
                        ],
                    )
                ]
            )
        ),
    )
    session = SimpleNamespace(get=AsyncMock(), commit=AsyncMock())
    return session, client


@pytest.mark.asyncio
async def test_logistics_card_rejects_unverified_package_before_send(monkeypatch: pytest.MonkeyPatch) -> None:
    session, client = card_context(monkeypatch, "123456")
    send = AsyncMock()
    monkeypatch.setattr(service, "send_agent_message", send)

    with pytest.raises(AppError) as raised:
        await service.send_agent_logistics_card(
            session, SimpleNamespace(), uuid.uuid4(), "600001", "999999", "request-1", confirmed=True
        )

    assert raised.value.status_code == 404
    send.assert_not_awaited()
    client.get_standard_tracking.assert_not_awaited()


@pytest.mark.asyncio
async def test_logistics_card_accepts_verified_enhanced_package_and_keeps_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, client = card_context(monkeypatch, "123456")
    message = SimpleNamespace(raw_payload={"delivery_mode": "real"})
    session.get.return_value = message
    send = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    monkeypatch.setattr(service, "send_agent_message", send)
    monkeypatch.setattr(service, "_message_view", lambda value: value.raw_payload)

    result = await service.send_agent_logistics_card(
        session, SimpleNamespace(), uuid.uuid4(), "600001", "123456", "request-1", confirmed=True
    )

    assert result["logistics_card"]["package_id"] == "123456"
    assert result["logistics_card"]["latest_description"] == "Picked up"
    assert result["logistics_card"]["tracking_number"] == "TRACK-1"
    assert send.await_args.kwargs["message_type"] == "logistics_card"
    assert send.await_args.kwargs["card_package_id"] == "123456"
    client.get_standard_tracking.assert_not_awaited()
    session.commit.assert_awaited_once()
