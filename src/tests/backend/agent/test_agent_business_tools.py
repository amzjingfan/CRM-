"""业务工具使用可信会话和本轮候选引用，不按正则选工具。"""

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.workspace.schemas import PageMeta
from app.workspace.sidebar import SidebarOrder, SidebarOrders


def order(name: str) -> SidebarOrder:
    return SidebarOrder(
        id=uuid.uuid4(),
        external_order_id=name,
        status="IN_TRANSIT",
        payment_status="paid",
        currency="USD",
        total_amount=Decimal("29.00"),
        payment_breakdown={},
        ordered_at=None,
        tracking_number=None,
        tracking_status=None,
        items=[],
    )


def executor(monkeypatch, items=None):
    from app.agents.tools import business

    snapshot = SimpleNamespace(
        store_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        debug_without_conversation=False,
        message_ids=(),
    )
    service = business.AgentBusinessExecutor(
        SimpleNamespace(add=Mock(), commit=AsyncMock(), rollback=AsyncMock()),
        SimpleNamespace(id=uuid.uuid4()),
        snapshot,
        uuid.uuid4(),
        frozenset({"orders.view", "workspace.view", "workspace.reply"}),
        "trace",
    )
    monkeypatch.setattr(
        service,
        "authorize",
        AsyncMock(
            return_value=SimpleNamespace(
                id=snapshot.conversation_id,
                store_id=snapshot.store_id,
                customer_id=snapshot.customer_id,
                platform="tiktok",
            )
        ),
    )
    search = AsyncMock(
        return_value=SidebarOrders(items=items or [], pagination=PageMeta(page=1, page_size=20, total=len(items or [])))
    )
    monkeypatch.setattr(business, "search_sidebar_orders", search)
    monkeypatch.setattr(business, "get_settings", lambda: SimpleNamespace(real_tiktok_read_enabled=False))
    return service, search


@pytest.mark.asyncio
async def test_multiple_orders_require_explicit_selection_and_do_not_choose_latest(monkeypatch):
    service, search = executor(monkeypatch, [order("111"), order("222")])
    result = await service.invoke("query_order", {})
    assert result["status"] == "selection_required"
    assert result["facts"]["selection_required"] is True
    assert result["source"] and result["observed_at"] and result["fact_scope"]
    refs = [item["order_ref"] for item in result["facts"]["candidates"]]
    assert len(set(refs)) == 2 and all(ref.startswith("o") for ref in refs)
    selected = await service.invoke("query_order", {"order_ref": refs[1]})
    assert selected["status"] == "succeeded"
    assert selected["facts"]["order_ref"] == refs[1]
    assert "external_order_id" not in selected["facts"] and "order_id" not in selected["facts"]
    assert search.await_count == 1


@pytest.mark.asyncio
async def test_candidate_reference_is_local_and_unissued_reference_is_rejected(monkeypatch):
    service, search = executor(monkeypatch, [order("111")])
    result = await service.invoke("query_order", {"order_ref": "o99"})
    assert result["status"] == "invalid_selection"
    search.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_orders_are_verified_no_data_not_tool_failure(monkeypatch):
    service, _ = executor(monkeypatch)
    result = await service.invoke("search_customer_orders", {})
    assert result["status"] == "succeeded"
    assert result["facts"]["total"] == 0
    assert result["source"] == "crm_local_snapshot"
    assert result["observed_at"]


@pytest.mark.asyncio
async def test_order_time_filter_is_applied_before_paging_without_refetching_every_page(monkeypatch):
    service, search = executor(monkeypatch, [order("111")])
    search.return_value.pagination.total = 100
    result = await service.invoke("search_customer_orders", {"created_after": "2026-10-01T00:00:00Z", "page": 2})
    assert search.await_count == 1
    assert search.await_args.args[-1].created_after is not None
    assert result["facts"]["total"] == 100 and result["facts"]["next_page"] == 3


@pytest.mark.asyncio
async def test_tool_arguments_cannot_inject_foreign_customer(monkeypatch):
    from pydantic import ValidationError

    service, search = executor(monkeypatch)
    with pytest.raises(ValidationError):
        await service.invoke("search_customer_orders", {"customer_id": str(uuid.uuid4())})
    search.assert_not_awaited()


@pytest.mark.asyncio
async def test_permission_failure_has_no_data_and_never_queries(monkeypatch):
    from app.shared.exceptions.errors import AppError, ErrorCode

    service, search = executor(monkeypatch)
    monkeypatch.setattr(service, "authorize", AsyncMock(side_effect=AppError(ErrorCode.PERMISSION_DENIED, "拒绝", 403)))
    result = await service.invoke("query_order", {})
    assert result["status"] == "permission_denied"
    assert not result.get("facts")
    search.assert_not_awaited()


@pytest.mark.asyncio
async def test_product_candidates_and_paging_are_bound_to_current_search(monkeypatch):
    from app.agents.tools import business
    from app.workspace.sidebar import SidebarProduct, SidebarProducts

    service, _ = executor(monkeypatch)
    product = SidebarProduct(id="trusted-product", title="Training band", status="ACTIVATE", image_url=None, skus=[])
    monkeypatch.setattr(
        business,
        "search_store_products",
        AsyncMock(
            return_value=SidebarProducts(
                items=[product], next_page_token="opaque-token", total_count=1, partial_search=True
            )
        ),
    )
    detail = AsyncMock(return_value=product)
    monkeypatch.setattr(business, "get_store_product", detail)
    result = await service.invoke("search_products", {"query": "band"})
    facts = result["facts"]
    product_ref = facts["products"][0]["product_ref"]
    assert product_ref.startswith("p")
    assert "trusted-product" not in str(result) and "opaque-token" not in str(result)
    with pytest.raises(ValueError):
        await service.invoke("search_products", {"query": "different", "page_ref": facts["next_page_ref"]})
    detail_result = await service.invoke("query_product", {"product_ref": product_ref})
    assert detail_result["facts"]["title"] == "Training band"
    assert detail.await_args.args[-1] == "trusted-product"


@pytest.mark.asyncio
async def test_store_product_queries_do_not_require_a_customer_conversation(monkeypatch):
    from app.agents.tools import business
    from app.workspace.sidebar import SidebarProducts

    service, _ = executor(monkeypatch)
    monkeypatch.undo()
    service.snapshot.debug_without_conversation = True
    monkeypatch.setattr(business, "current_permissions", AsyncMock(return_value={"workspace.view"}))
    read = AsyncMock(return_value=SidebarProducts(items=[], next_page_token=None, total_count=0))
    monkeypatch.setattr(business, "search_store_products", read, raising=False)
    result = await service.invoke("search_products", {})
    assert result["status"] == "succeeded"
    assert read.await_args.args[1] == service.snapshot.store_id


@pytest.mark.asyncio
async def test_complete_logistics_keeps_all_parcels_and_pages_events(monkeypatch):
    from datetime import UTC, datetime, timedelta

    from app.agents.tools import business
    from app.workspace.sidebar import (
        SidebarOrderDetail,
        SidebarTrackingEvent,
        SidebarTrackingPackage,
        SidebarTrackingTimeline,
    )

    service, _ = executor(monkeypatch, [order("111")])
    monkeypatch.setattr(business, "get_settings", lambda: SimpleNamespace(real_tiktok_read_enabled=True))
    monkeypatch.setattr(
        business,
        "get_sidebar_order_detail",
        AsyncMock(
            return_value=SidebarOrderDetail(
                payment_method_name="card",
                shipping_provider="carrier",
                latest_tracking_description=None,
                latest_tracking_at=None,
                enhanced_tracking_available=True,
            )
        ),
    )
    now = datetime.now(UTC)
    packages = [
        SidebarTrackingPackage(
            package_id=f"pkg-{i}",
            tracking_number=f"track-{i}",
            carrier_name="Carrier",
            events=[
                SidebarTrackingEvent(
                    description="In transit",
                    occurred_at=now - timedelta(hours=j),
                    action_code=100,
                    tracking_number=f"old-{i}",
                )
                for j in range(7)
            ],
        )
        for i in range(2)
    ]
    monkeypatch.setattr(
        business, "get_sidebar_enhanced_tracking", AsyncMock(return_value=SidebarTrackingTimeline(packages=packages))
    )
    result = await service.invoke("query_logistics", {"enhanced": True})
    assert len(result["facts"]["packages"]) == 2
    assert len(result["facts"]["events"]) == 10
    assert result["facts"]["events"][0]["occurred_at"] == now.isoformat()
    assert {event["tracking_number"] for event in result["facts"]["events"]} == {"old-0", "old-1"}
    assert result["facts"]["next_event_offset"] == 10
    result = await service.invoke(
        "query_logistics", {"order_ref": result["facts"]["order_ref"], "enhanced": True, "event_offset": 10}
    )
    assert len(result["facts"]["events"]) == 4 and result["facts"]["next_event_offset"] is None
    import json

    many = [
        SidebarTrackingPackage(package_id=f"many-{i}", tracking_number="T" * 200, carrier_name="C" * 200, events=[])
        for i in range(80)
    ]
    monkeypatch.setattr(
        business, "get_sidebar_enhanced_tracking", AsyncMock(return_value=SidebarTrackingTimeline(packages=many))
    )
    for large in (
        many,
        [
            SidebarTrackingPackage(
                package_id=f"combined-{i}",
                tracking_number="T" * 200,
                carrier_name="C" * 200,
                events=[
                    SidebarTrackingEvent(
                        description="In transit " + '"' * 980,
                        action_code=100,
                        occurred_at=now,
                        tracking_number="H" * 200,
                    )
                ],
            )
            for i in range(10)
        ],
    ):
        monkeypatch.setattr(
            business, "get_sidebar_enhanced_tracking", AsyncMock(return_value=SidebarTrackingTimeline(packages=large))
        )
        package_offset = event_offset = 0
        seen_packages, seen_events = [], 0
        while True:
            page = await service.invoke(
                "query_logistics", {"enhanced": True, "package_offset": package_offset, "event_offset": event_offset}
            )
            assert len(json.dumps(page, ensure_ascii=False, default=str, separators=(",", ":"))) < 16000
            assert page["facts"]["package_count"] == len(large)
            if package_offset is not None:
                seen_packages.extend(item["package"] for item in page["facts"]["packages"])
            if event_offset is not None:
                seen_events += len(page["facts"]["events"])
            next_package = page["facts"]["next_package_offset"]
            next_event = page["facts"]["next_event_offset"]
            if next_package is None and next_event is None:
                break
            # 已读完的另一数组以总长度作为结束位置，避免重复读取。
            package_offset = next_package if next_package is not None else len(large)
            event_offset = next_event if next_event is not None else sum(len(item.events) for item in large)
        assert seen_packages == list(range(1, len(large) + 1))
        assert seen_events == sum(len(item.events) for item in large)


@pytest.mark.asyncio
async def test_standard_tracking_does_not_hide_known_parcels_or_assign_order_events_to_one_parcel(monkeypatch):
    from app.agents.tools import business
    from app.workspace.sidebar import (
        SidebarOrderDetail,
        SidebarOrderItem,
        SidebarStandardTracking,
        SidebarTrackingPackage,
    )

    current = order("111")
    current.items = [
        SidebarOrderItem(
            name="Band",
            product_id=None,
            sku=None,
            sku_id=None,
            sku_name=None,
            image_url=None,
            quantity=1,
            unit_price=None,
            total_amount=None,
            package_id=f"parcel-{i}",
            tracking_number=f"tracking-{i}",
        )
        for i in range(2)
    ]
    service, _ = executor(monkeypatch, [current])
    monkeypatch.setattr(business, "get_settings", lambda: SimpleNamespace(real_tiktok_read_enabled=True))
    monkeypatch.setattr(
        business,
        "get_sidebar_order_detail",
        AsyncMock(
            return_value=SidebarOrderDetail(
                payment_method_name=None,
                shipping_provider="Carrier",
                latest_tracking_description=None,
                latest_tracking_at=None,
            )
        ),
    )
    monkeypatch.setattr(
        business,
        "get_sidebar_standard_tracking",
        AsyncMock(
            return_value=SidebarStandardTracking(
                packages=[SidebarTrackingPackage(tracking_number=None, carrier_name="Carrier", events=[])]
            )
        ),
    )
    result = await service.invoke("query_logistics", {})
    assert len(result["facts"]["packages"]) == 2
    assert result["facts"]["event_scope"] == "order"


@pytest.mark.asyncio
async def test_aftersales_requires_case_selection_before_reading_processing_records(monkeypatch):
    from app.agents.tools import business
    from app.integrations.tiktok_read import TikTokReturn, TikTokReturnRecord

    service, _ = executor(monkeypatch, [order("111")])
    rows = [
        TikTokReturn(order_id="111", return_id=value, return_type="REFUND", return_status="PENDING")
        for value in ["456", "457"]
    ]
    client = SimpleNamespace(
        search_returns=AsyncMock(return_value=(rows, None)),
        get_return_records=AsyncMock(
            return_value=[
                TikTokReturnRecord(event="ORDER_RETURN", create_time=1690532213, description="Buyer submitted request")
            ]
        ),
    )
    monkeypatch.setattr(business, "_verified_sidebar_order", AsyncMock(return_value=(None, client, None)))
    result = await service.invoke("query_aftersales", {"include_records": True})
    assert result["facts"]["records_selection_required"]
    client.get_return_records.assert_not_awaited()
    chosen = result["facts"]["returns"][0]["return_ref"]
    assert chosen.startswith("r") and "return_id" not in result["facts"]["returns"][0]
    detail = await service.invoke(
        "query_aftersales", {"order_ref": result["facts"]["order_ref"], "return_ref": chosen, "include_records": True}
    )
    assert detail["facts"]["returns"][0]["records"][0]["description"] == "Buyer submitted request"
    assert client.get_return_records.await_args.args[0] == "456"
    with pytest.raises(ValueError):
        await service.invoke(
            "query_aftersales",
            {"order_ref": result["facts"]["order_ref"], "return_ref": "r99", "include_records": True},
        )
    assert client.get_return_records.await_count == 1
