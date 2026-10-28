"""用 @tool 发布语义目录，并将模型选择约束到可信执行上下文。"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, cast

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, ConfigDict, Field

from app.agents.safety.tool_projection import project_tool_result
from app.tools.contracts import (
    TOOL_DEFINITIONS,
    WRITE_TOOL_NAMES,
    StrictToolArguments,
    ToolExecutionContext,
    ToolInvocation,
    ToolName,
    ToolResult,
)

READ_TOOL_DESCRIPTIONS = {
    "query_order": "只读查询当前授权会话对应的订单状态、金额和履约事实。订单标识由服务端绑定。",
    "query_logistics": "只读查询当前授权订单的物流轨迹、最新状态和时间。订单标识由服务端绑定。",
    "query_customer_profile": "只读查询当前授权会话客户的最小画像信息。客户标识由服务端绑定。",
}
WRITE_TOOL_DESCRIPTIONS = {
    "update_shipping_address": "提出修改收件地址的人工确认请求；本工具不会执行地址变更。",
    "send_coupon": "提出发放优惠券的人工确认请求；本工具不会发放优惠券。",
    "transfer_to_human": "提出转人工请求；本工具不会修改会话状态。",
    "send_platform_message": "提出平台消息发送的人工确认请求；本工具不会发送消息。",
}


class NoModelArguments(StrictToolArguments):
    """订单、客户等可信资源 ID 不接受模型自由传入。"""

    model_config = ConfigDict(extra="forbid")


class KnowledgeSearchArguments(StrictToolArguments):
    """模型只可提交查询文本；店铺及文件范围由闭包中的可信服务固定。"""

    query: str = Field(min_length=1, max_length=4000)


class ToolExecutionPort(Protocol):
    async def execute(self, invocation: ToolInvocation) -> ToolResult: ...


@dataclass(frozen=True, slots=True)
class AgentToolContext:
    store_id: uuid.UUID
    agent_run_id: uuid.UUID
    order_id: str | None
    customer_id: uuid.UUID | None
    permissions: frozenset[str]
    trace_id: str


def _tool_arguments(name: str, context: AgentToolContext) -> dict[str, object] | None:
    if name in {"query_order", "query_logistics"}:
        return {"order_id": context.order_id} if context.order_id else None
    if name == "query_customer_profile":
        return {"customer_id": str(context.customer_id)} if context.customer_id else None
    return None


def _build_one(name: str, context: AgentToolContext, executor: ToolExecutionPort) -> BaseTool:
    description = READ_TOOL_DESCRIPTIONS.get(name) or WRITE_TOOL_DESCRIPTIONS.get(name)
    if description is None:
        raise ValueError(f"未知 Agent 工具: {name}")

    @tool(name, args_schema=NoModelArguments, description=description)
    async def invoke() -> dict[str, object]:
        """服务端重新检查权限并绑定可信对象，写工具只提出人工确认。"""
        definition = TOOL_DEFINITIONS[name]
        if name in WRITE_TOOL_NAMES:
            return {"status": "human_confirmation_required", "tool_name": name}
        if definition.permission not in context.permissions:
            return {"status": "permission_denied", "tool_name": name}
        arguments = _tool_arguments(name, context)
        if arguments is None:
            return {"status": "context_unavailable", "tool_name": name}
        result = await executor.execute(
            ToolInvocation(
                tool_name=cast(ToolName, name),
                idempotency_key=f"agent:{context.agent_run_id}:{name}:{uuid.uuid4()}",
                arguments=arguments,
                context=ToolExecutionContext(
                    store_id=context.store_id,
                    actor_type="agent",
                    permissions=set(context.permissions),
                    agent_run_id=context.agent_run_id,
                    trace_id=context.trace_id,
                    human_confirmed=False,
                ),
            )
        )
        return project_tool_result(name, result)

    return invoke


def build_agent_tools(
    configured_names: tuple[str, ...],
    *,
    context: AgentToolContext,
    executor: ToolExecutionPort,
    knowledge_search: Callable[[str], Awaitable[dict[str, object]]] | None = None,
) -> tuple[BaseTool, ...]:
    """不按数量或预设意图裁剪配置；未知工具显式拒绝发布/运行。"""
    if len(set(configured_names)) != len(configured_names):
        raise ValueError("Agent 工具配置包含重复名称")
    catalog = [_build_one(name, context, executor) for name in configured_names]
    if knowledge_search is not None:

        @tool(
            "search_knowledge",
            args_schema=KnowledgeSearchArguments,
            description="检索当前 Agent 显式绑定且仍获内部审批的知识文件；只返回有来源的片段。",
        )
        async def search_knowledge(query: str) -> dict[str, object]:
            """知识范围和版本由可信回调冻结，模型不能指定文件或店铺 ID。"""
            return await knowledge_search(query)

        catalog.append(search_knowledge)
    return tuple(catalog)


async def invoke_selected_tool(selected: BaseTool, raw_arguments: dict[str, object]) -> object:
    """在 LangChain 调用前显式拒绝额外模型参数，防止其宽松解析丢弃字段。"""
    schema = selected.args_schema
    if not isinstance(schema, type) or not issubclass(schema, BaseModel):
        raise ValueError("工具参数 Schema 无效")
    parsed = schema.model_validate(raw_arguments)
    return await selected.ainvoke(parsed.model_dump(mode="json"))
