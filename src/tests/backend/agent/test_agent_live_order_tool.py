"""动态 Agent 的真实只读订单工具只返回当前店铺核验字段。"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.agents.tools.live_order import AgentDebugLiveOrderExecutor, _tracking_stage
from app.tools.contracts import (
    QueryLogisticsArguments,
    QueryOrderArguments,
    ToolExecutionContext,
    ToolInvocation,
    validate_tool_output,
)
from app.workspace.sidebar import SidebarOrder, SidebarOrderDetail


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Delivered to service counter.", "delivered"),
        ("Arrived at sorting center.", "in_transit"),
        ("Deliveredness is a marketing term.", None),
        ("Delivery attempted.", None),
        (None, None),
    ],
)
def test_tracking_stage_requires_explicit_trajectory(description: str | None, expected: str | None) -> None:
    assert _tracking_stage(description) == expected


@pytest.mark.asyncio
async def test_live_order_tool_projects_minimal_fields_without_logging_tracking_data() -> None:
    store_id = uuid.uuid4()
    order = SidebarOrder(
        id=uuid.uuid4(),
        external_order_id="123456789",
        status="SHIPPED",
        payment_status=None,
        currency="USD",
        total_amount=Decimal("12.00"),
        payment_breakdown={},
        ordered_at=None,
        tracking_number="synthetic-tracking",
        tracking_status=None,
        items=[],
        live_detail_available=True,
    )
    detail = SidebarOrderDetail(
        payment_method_name=None,
        shipping_provider="Synthetic Carrier",
        latest_tracking_description="Delivered to service counter.",
        latest_tracking_at=None,
    )
    executor = AgentDebugLiveOrderExecutor(AsyncMock(), store_id, order, detail)
    invocation = ToolInvocation(
        tool_name="query_order",
        idempotency_key="test-only",
        arguments={"order_id": str(order.id)},
        context=ToolExecutionContext(store_id=store_id, actor_type="agent", permissions={"orders.view"}),
    )

    order_result = await executor._query_order(invocation, QueryOrderArguments(order_id=str(order.id)))
    logistics_result = await executor._query_logistics(invocation, QueryLogisticsArguments(order_id=str(order.id)))

    assert validate_tool_output("query_order", order_result.data or {})["status"] == "SHIPPED"
    assert (
        validate_tool_output("query_logistics", logistics_result.data or {})["tracking_number"] == "synthetic-tracking"
    )
    assert logistics_result.data["tracking_status"] == "delivered"
    assert logistics_result.data["latest_tracking_description"] == detail.latest_tracking_description
    assert "service counter" not in str(logistics_result.output_summary)
    assert "synthetic-tracking" not in str(logistics_result.output_summary)
