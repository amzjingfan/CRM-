"""Agent 调试专用的已验证 TikTok 订单只读投影。"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.database.base import User
from app.tools.contracts import QueryLogisticsArguments, QueryOrderArguments, ToolInvocation
from app.tools.executor import SqlAlchemyToolExecutor, ToolDispatchError, ToolDispatchOutcome
from app.workspace.sidebar import SidebarOrder, SidebarOrderDetail, get_sidebar_order_detail


def _tracking_stage(description: str | None) -> str | None:
    """只从官方轨迹的明确开头识别阶段，不把订单状态当物流状态。"""
    if not description:
        return None
    value = description.strip().casefold()
    for prefixes, stage in (
        (("delivered", "signed for", "已签收", "已送达"), "delivered"),
        (("in transit", "arrived at", "departed", "运送中", "运输中"), "in_transit"),
        (("shipped", "dispatched", "已发货"), "shipped"),
    ):
        for prefix in prefixes:
            if value == prefix or (
                value.startswith(prefix) and value[len(prefix) : len(prefix) + 1] in {" ", ",", ".", ":"}
            ):
                return stage
    return None


class AgentDebugLiveOrderExecutor(SqlAlchemyToolExecutor):
    """复用工具权限、审计与超时，只替换本次已验证的实时订单查询。"""

    def __init__(
        self,
        session: AsyncSession,
        store_id: uuid.UUID,
        order: SidebarOrder,
        detail: SidebarOrderDetail | None = None,
        *,
        user: User | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> None:
        super().__init__(session)
        self.store_id = store_id
        self.order = order
        self.detail = detail
        self.user = user
        self.conversation_id = conversation_id

    def _matches(self, invocation: ToolInvocation, order_id: str) -> bool:
        return invocation.context.store_id == self.store_id and order_id == str(self.order.id)

    async def _query_order(self, invocation: ToolInvocation, arguments: QueryOrderArguments) -> ToolDispatchOutcome:
        if not self._matches(invocation, arguments.order_id):
            return await super()._query_order(invocation, arguments)
        if self.order.total_amount is None or not self.order.currency:
            raise ToolDispatchError("TOOL_OUTPUT_INVALID")
        return ToolDispatchOutcome(
            status="succeeded",
            data={
                "order_id": str(self.order.id),
                "external_order_id": self.order.external_order_id,
                "status": self.order.status,
                "payment_status": self.order.payment_status,
                "fulfillment_status": None,
                "currency": self.order.currency,
                "total_amount": str(self.order.total_amount),
                "ordered_at": self.order.ordered_at.isoformat() if self.order.ordered_at else None,
            },
            output_summary={"order_id": str(self.order.id), "status": self.order.status},
        )

    async def _query_logistics(
        self, invocation: ToolInvocation, arguments: QueryLogisticsArguments
    ) -> ToolDispatchOutcome:
        if not self._matches(invocation, arguments.order_id):
            return await super()._query_logistics(invocation, arguments)
        if self.detail is None and self.user is not None and self.conversation_id is not None:
            # 只有模型实际选择 query_logistics 后才向 TikTok 查询详情；
            # 订单归属和用户权限继续由 workspace 只读入口复核。
            self.detail = await get_sidebar_order_detail(
                self.session, self.user, self.conversation_id, self.order.external_order_id
            )
        description = self.detail.latest_tracking_description if self.detail else None
        status = _tracking_stage(description)
        return ToolDispatchOutcome(
            status="succeeded",
            data={
                "order_id": str(self.order.id),
                "external_order_id": self.order.external_order_id,
                "tracking_number": self.order.tracking_number,
                # 订单状态不等于物流轨迹；没有已验证轨迹时不得冒充实时物流状态。
                "tracking_status": status,
                "latest_tracking_description": description,
                "latest_tracking_at": self.detail.latest_tracking_at.isoformat()
                if self.detail and self.detail.latest_tracking_at
                else None,
                "shipped_at": None,
                "delivered_at": None,
            },
            output_summary={
                "order_id": str(self.order.id),
                "tracking_status": status,
                "has_tracking_event": bool(description),
            },
        )
