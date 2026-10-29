"""原生物流卡片只引用当前买家订单中已核对的包裹。"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.integrations.tiktok_read import TikTokOrder, TikTokStandardTrackingEntry
from app.shared.exceptions.errors import AppError, ErrorCode
from app.workspace import service, sidebar
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
        get_standard_tracking=AsyncMock(return_value=([], "request")),
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


def tracking_event(description: str, day: int) -> SidebarTrackingEvent:
    return SidebarTrackingEvent(description=description, occurred_at=datetime(2026, 10, day, tzinfo=UTC), action_code=1)


def replace_order(monkeypatch: pytest.MonkeyPatch, client: SimpleNamespace, line_items: list[dict]) -> None:
    order = TikTokOrder.model_validate(
        {
            "id": "600001",
            "user_id": "900001",
            "status": "IN_TRANSIT",
            "shipping_provider": "Carrier",
            "line_items": line_items,
        }
    )
    conversation = SimpleNamespace(platform="tiktok", store_id=uuid.uuid4(), status="active")
    monkeypatch.setattr(service, "_verified_sidebar_order", AsyncMock(return_value=(conversation, client, order)))


@pytest.mark.asyncio
async def test_logistics_card_preview_reads_in_disabled_send_mode_without_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, client = card_context(monkeypatch, "123456")
    send_mode = AsyncMock(side_effect=AssertionError("preview must not inspect sending"))
    send = AsyncMock(side_effect=AssertionError("preview must not send"))
    monkeypatch.setattr(service, "_connected_send_channel", send_mode)
    monkeypatch.setattr(service, "_message_send_mode", lambda *_: "disabled")
    monkeypatch.setattr(service, "send_agent_message", send)

    previews = await service.get_logistics_card_preview(session, SimpleNamespace(), uuid.uuid4(), "600001")

    assert len(previews) == 1
    assert previews[0].card.package_id == "123456"
    assert previews[0].card.latest_description == "Picked up"
    assert previews[0].card.product_name == "Walking pad"
    assert previews[0].packages[previews[0].selected].package_id == "123456"
    assert previews[0].enhanced_available is True
    send_mode.assert_not_awaited()
    send.assert_not_awaited()
    session.commit.assert_not_awaited()
    client.get_standard_tracking.assert_not_awaited()


@pytest.mark.asyncio
async def test_standard_preview_uses_verified_single_package_and_latest_timestamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, client = card_context(monkeypatch, "123456")
    client.channel.metadata_json = {"seller_type": "LOCAL"}
    replace_order(
        monkeypatch,
        client,
        [{"package_id": "123456", "tracking_number": "TRACK-1", "sku_id": "200001", "product_name": "Walking pad"}],
    )
    client.get_standard_tracking.return_value = (
        [
            TikTokStandardTrackingEntry(description="Old", update_time_millis=1000, action_code=1),
            TikTokStandardTrackingEntry(description="Latest", update_time_millis=3000, action_code=3),
            TikTokStandardTrackingEntry(description="Middle", update_time_millis=2000, action_code=2),
        ],
        "request",
    )

    previews = await service.get_logistics_card_preview(session, SimpleNamespace(), uuid.uuid4(), "600001")

    assert len(previews) == 1
    assert previews[0].card.package_id == "123456"
    assert previews[0].card.latest_description == "Latest"
    assert previews[0].card.latest_at == datetime.fromtimestamp(3, UTC)
    assert [event.description for event in previews[0].packages[0].events] == ["Latest", "Middle", "Old"]
    assert previews[0].enhanced_available is False
    service.get_sidebar_enhanced_tracking.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_enhanced_preview_preserves_verified_multiple_packages_and_sorted_latest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, client = card_context(monkeypatch, "123456")
    replace_order(
        monkeypatch,
        client,
        [
            {"package_id": "123456", "tracking_number": "TRACK-1", "sku_id": "200001", "product_name": "First"},
            {"package_id": "654321", "tracking_number": "TRACK-2", "sku_id": "200002", "product_name": "Second"},
        ],
    )
    service.get_sidebar_enhanced_tracking.return_value = SidebarTrackingTimeline(
        packages=[
            SidebarTrackingPackage(
                package_id="123456",
                tracking_number="TRACK-1",
                carrier_name="Carrier",
                events=[tracking_event("Old", 20), tracking_event("Latest", 24)],
            ),
            SidebarTrackingPackage(
                package_id="654321",
                tracking_number="TRACK-2",
                carrier_name="Carrier",
                events=[tracking_event("Other package", 23)],
            ),
        ]
    )

    previews = await service.get_logistics_card_preview(session, SimpleNamespace(), uuid.uuid4(), "600001")

    assert [
        (item.card.package_id, item.card.product_name, item.card.latest_description, item.selected) for item in previews
    ] == [("123456", "First", "Latest", 0), ("654321", "Second", "Other package", 1)]
    assert all(len(item.packages) == 2 for item in previews)
    assert [event.description for event in previews[0].packages[0].events] == ["Latest", "Old"]
    client.get_standard_tracking.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_enhanced_preview_rejects_multiple_packages_without_verified_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    session, client = card_context(monkeypatch, "123456")
    service.get_sidebar_enhanced_tracking.return_value = SidebarTrackingTimeline(
        packages=[
            SidebarTrackingPackage(tracking_number="TRACK-1", carrier_name="Carrier", events=[]),
            SidebarTrackingPackage(tracking_number="TRACK-2", carrier_name="Carrier", events=[]),
        ]
    )

    with pytest.raises(AppError) as raised:
        await service.get_logistics_card_preview(session, SimpleNamespace(), uuid.uuid4(), "600001")

    assert raised.value.status_code == 422
    client.get_standard_tracking.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_standard_preview_does_not_assign_order_timeline_to_multiple_packages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, client = card_context(monkeypatch, "123456")
    client.channel.metadata_json = {"seller_type": "LOCAL"}
    replace_order(
        monkeypatch,
        client,
        [
            {"package_id": "123456", "tracking_number": "TRACK-1", "product_name": "First"},
            {"package_id": "654321", "tracking_number": "TRACK-2", "product_name": "Second"},
        ],
    )

    previews = await service.get_logistics_card_preview(session, SimpleNamespace(), uuid.uuid4(), "600001")

    assert [item.card.package_id for item in previews] == ["123456", "654321"]
    assert all(item.card.latest_description is None and not item.packages[item.selected].events for item in previews)
    client.get_standard_tracking.assert_not_awaited()


@pytest.mark.asyncio
async def test_standard_preview_refuses_ambiguous_tracking_numbers_without_package_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, client = card_context(monkeypatch, "123456")
    client.channel.metadata_json = {"seller_type": "LOCAL"}
    replace_order(monkeypatch, client, [{"tracking_number": "TRACK-1"}, {"tracking_number": "TRACK-2"}])

    with pytest.raises(AppError) as raised:
        await service.get_logistics_card_preview(session, SimpleNamespace(), uuid.uuid4(), "600001")

    assert raised.value.status_code == 422
    client.get_standard_tracking.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_rejects_store_outside_user_access_before_platform_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sidebar, "_conversation", AsyncMock(side_effect=AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404))
    )
    client = AsyncMock()
    monkeypatch.setattr(sidebar, "_tiktok_client", client)
    enhanced = AsyncMock()
    monkeypatch.setattr(service, "get_sidebar_enhanced_tracking", enhanced)

    with pytest.raises(AppError) as raised:
        await service.get_logistics_card_preview(SimpleNamespace(), SimpleNamespace(), uuid.uuid4(), "600001")

    assert raised.value.status_code == 404
    client.assert_not_awaited()
    enhanced.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_rejects_other_buyer_order_before_any_tracking(monkeypatch: pytest.MonkeyPatch) -> None:
    conversation = SimpleNamespace(platform="tiktok", store_id=uuid.uuid4())
    wrong_order = TikTokOrder(id="600001", user_id="900002", status="IN_TRANSIT")
    client = SimpleNamespace(
        get_order_details=AsyncMock(return_value=([wrong_order], "request")), get_standard_tracking=AsyncMock()
    )
    monkeypatch.setattr(sidebar, "_conversation", AsyncMock(return_value=conversation))
    monkeypatch.setattr(sidebar, "_tiktok_client", AsyncMock(return_value=client))
    monkeypatch.setattr(sidebar, "_local_verified_customer", AsyncMock(return_value=object()))
    monkeypatch.setattr(sidebar, "_verified_buyer_user_id", AsyncMock(return_value="900001"))
    monkeypatch.setattr(sidebar, "get_settings", lambda: SimpleNamespace(real_tiktok_read_enabled=True))
    enhanced = AsyncMock()
    monkeypatch.setattr(service, "get_sidebar_enhanced_tracking", enhanced)

    with pytest.raises(AppError) as raised:
        await service.get_logistics_card_preview(SimpleNamespace(), SimpleNamespace(), uuid.uuid4(), "600001")

    assert raised.value.status_code == 404
    client.get_standard_tracking.assert_not_awaited()
    enhanced.assert_not_awaited()


@pytest.mark.asyncio
async def test_sent_card_snapshot_selects_latest_enhanced_node_by_time(monkeypatch: pytest.MonkeyPatch) -> None:
    session, _ = card_context(monkeypatch, "123456")
    service.get_sidebar_enhanced_tracking.return_value.packages[0].events = [
        tracking_event("Old", 20),
        tracking_event("Latest", 24),
        tracking_event("Middle", 22),
    ]
    session.get.return_value = SimpleNamespace(raw_payload={})
    monkeypatch.setattr(service, "send_agent_message", AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())))
    monkeypatch.setattr(service, "_message_view", lambda value: value.raw_payload)

    result = await service.send_agent_logistics_card(
        session, SimpleNamespace(), uuid.uuid4(), "600001", "123456", "request-1", confirmed=True
    )

    assert result["logistics_card"]["latest_description"] == "Latest"
    assert result["logistics_card"]["latest_at"] == "2026-10-24T00:00:00Z"


@pytest.mark.asyncio
async def test_sent_card_still_requires_explicit_confirmation_and_send_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    session, _ = card_context(monkeypatch, "123456")
    send = AsyncMock()
    monkeypatch.setattr(service, "send_agent_message", send)
    with pytest.raises(AppError) as raised:
        await service.send_agent_logistics_card(
            session, SimpleNamespace(), uuid.uuid4(), "600001", "123456", "request-1", confirmed=False
        )
    assert raised.value.status_code == 422
    service._verified_sidebar_order.assert_not_awaited()
    monkeypatch.setattr(service, "_message_send_mode", lambda *_: "disabled")
    with pytest.raises(AppError) as raised:
        await service.send_agent_logistics_card(
            session, SimpleNamespace(), uuid.uuid4(), "600001", "123456", "request-1", confirmed=True
        )
    assert raised.value.status_code == 403
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_does_not_fallback_after_enhanced_order_reverification_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, client = card_context(monkeypatch, "123456")
    service.get_sidebar_enhanced_tracking.side_effect = AppError(ErrorCode.RESOURCE_NOT_FOUND, "订单不存在", 404)
    with pytest.raises(AppError) as raised:
        await service.get_logistics_card_preview(session, SimpleNamespace(), uuid.uuid4(), "600001")
    assert raised.value.status_code == 404
    client.get_standard_tracking.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_enhanced_cooldown_keeps_verified_standard_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    session, client = card_context(monkeypatch, "123456")
    service.get_sidebar_enhanced_tracking.side_effect = AppError(ErrorCode.THIRD_PARTY_ERROR, "增强物流冷却中", 503)
    client.get_standard_tracking.return_value = (
        [TikTokStandardTrackingEntry(description="Standard latest", update_time_millis=3000, action_code=1)],
        "request",
    )
    previews = await service.get_logistics_card_preview(session, SimpleNamespace(), uuid.uuid4(), "600001")
    assert previews[0].card.latest_description == "Standard latest"
    assert previews[0].card.package_id is None
    assert previews[0].enhanced_available is True
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_does_not_guess_product_when_enhanced_packages_share_tracking_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _ = card_context(monkeypatch, "123456")
    service.get_sidebar_enhanced_tracking.return_value = SidebarTrackingTimeline(
        packages=[
            SidebarTrackingPackage(package_id="123456", tracking_number="TRACK-1", carrier_name="Carrier", events=[]),
            SidebarTrackingPackage(package_id="654321", tracking_number="TRACK-1", carrier_name="Carrier", events=[]),
        ]
    )
    previews = await service.get_logistics_card_preview(session, SimpleNamespace(), uuid.uuid4(), "600001")
    assert [item.card.package_id for item in previews] == ["123456", "654321"]
    assert all(item.card.product_name is None and item.card.quantity is None for item in previews)


@pytest.mark.asyncio
async def test_standard_preview_rejects_additional_unidentified_package(monkeypatch: pytest.MonkeyPatch) -> None:
    session, client = card_context(monkeypatch, "123456")
    client.channel.metadata_json = {"seller_type": "LOCAL"}
    replace_order(
        monkeypatch,
        client,
        [
            {"package_id": "123456", "tracking_number": "TRACK-1"},
            {"tracking_number": "TRACK-2"},
        ],
    )
    with pytest.raises(AppError) as raised:
        await service.get_logistics_card_preview(session, SimpleNamespace(), uuid.uuid4(), "600001")
    assert raised.value.status_code == 422
    client.get_standard_tracking.assert_not_awaited()


@pytest.mark.asyncio
async def test_preview_rejects_duplicate_official_package_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    session, _ = card_context(monkeypatch, "123456")
    package = SidebarTrackingPackage(package_id="123456", tracking_number="TRACK-1", carrier_name="Carrier", events=[])
    service.get_sidebar_enhanced_tracking.return_value = SidebarTrackingTimeline(
        packages=[package, package.model_copy()]
    )
    with pytest.raises(AppError) as raised:
        await service.get_logistics_card_preview(session, SimpleNamespace(), uuid.uuid4(), "600001")
    assert raised.value.status_code == 422


@pytest.mark.asyncio
async def test_single_enhanced_package_without_events_uses_standard_nodes_and_keeps_package_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, client = card_context(monkeypatch, "123456")
    service.get_sidebar_enhanced_tracking.return_value.packages[0].events = []
    client.get_standard_tracking.return_value = (
        [TikTokStandardTrackingEntry(description="Standard latest", update_time_millis=3000, action_code=1)],
        "request",
    )

    previews = await service.get_logistics_card_preview(session, SimpleNamespace(), uuid.uuid4(), "600001")

    assert previews[0].card.package_id == "123456"
    assert previews[0].card.tracking_number == "TRACK-1"
    assert previews[0].card.carrier_name == "Carrier"
    assert previews[0].card.latest_description == "Standard latest"
    assert previews[0].packages[0].events[0].description == "Standard latest"
