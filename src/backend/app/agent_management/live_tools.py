"""Agent 调试专用的已验证 TikTok 订单只读投影。"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.tools.contracts import QueryLogisticsArguments, QueryOrderArguments, ToolInvocation
from app.tools.executor import SqlAlchemyToolExecutor, ToolDispatchError, ToolDispatchOutcome
from app.workspace.sidebar import SidebarOrder


class AgentDebugLiveOrderExecutor(SqlAlchemyToolExecutor):
    """复用工具权限、审计与超时，只替换本次已验证的实时订单查询。"""

    def __init__(self, session: AsyncSession, store_id: uuid.UUID, order: SidebarOrder) -> None:
        super().__init__(session)
        self.store_id = store_id
        self.order = order

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
        return ToolDispatchOutcome(
            status="succeeded",
            data={
                "order_id": str(self.order.id),
                "external_order_id": self.order.external_order_id,
                "tracking_number": self.order.tracking_number,
                # 订单状态不等于物流轨迹；没有已验证轨迹时不得冒充实时物流状态。
                "tracking_status": self.order.tracking_status,
                "shipped_at": None,
                "delivered_at": None,
            },
            output_summary={"order_id": str(self.order.id), "tracking_status": self.order.tracking_status},
        )
