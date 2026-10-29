"""用 @tool 发布语义目录，并将模型选择约束到可信执行上下文。"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, cast

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, ConfigDict, Field

from app.agents.safety.tool_projection import project_tool_result
from app.agents.tools.logistics_updates import (
    BoundLogisticsEvent,
    LogisticsUpdateService,
    build_notify_logistics_update_tool,
)
from app.agents.tools.metadata import TOOL_METADATA
from app.tools.contracts import (
    TOOL_DEFINITIONS,
    WRITE_TOOL_NAMES,
    StrictToolArguments,
    ToolExecutionContext,
    ToolInvocation,
    ToolName,
    ToolResult,
)


class NoModelArguments(StrictToolArguments):
    """订单、客户等可信资源 ID 不接受模型自由传入。"""

    model_config = ConfigDict(extra="forbid")


class KnowledgeSearchArguments(StrictToolArguments):
    """模型只可提交查询文本；店铺及文件范围由闭包中的可信服务固定。"""

    query: str = Field(min_length=1, max_length=4000)


class ToolExecutionPort(Protocol):
    async def execute(self, invocation: ToolInvocation) -> ToolResult: ...


class BusinessToolPort(Protocol):
    async def invoke(self, name: str, arguments: dict[str, object]) -> dict[str, object]: ...

    async def permits(self, permission: str) -> bool: ...


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
    metadata = TOOL_METADATA.get(name)
    if metadata is None:
        raise ValueError(f"未知 Agent 工具: {name}")

    @tool(name, args_schema=NoModelArguments, description=metadata.description)
    async def invoke() -> dict[str, object]:
        """服务端重新检查权限并绑定可信对象，写工具只提出人工确认。"""
        if name in WRITE_TOOL_NAMES:
            return {"status": "human_confirmation_required", "tool_name": name}
        if name not in TOOL_DEFINITIONS:
            return {"status": "context_unavailable", "tool_name": name}
        definition = TOOL_DEFINITIONS[name]
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
    business_executor: BusinessToolPort | None = None,
    logistics_service: LogisticsUpdateService | None = None,
    logistics_context: BoundLogisticsEvent | None = None,
) -> tuple[BaseTool, ...]:
    """不按数量或预设意图裁剪配置；未知工具显式拒绝发布/运行。"""
    if len(set(configured_names)) != len(configured_names):
        raise ValueError("Agent 工具配置包含重复名称")
    catalog: list[BaseTool] = []
    for name in configured_names:
        if name not in TOOL_METADATA:
            raise ValueError(f"未知 Agent 工具: {name}")
        if name == "search_knowledge":
            continue
        if name == "notify_logistics_update":
            catalog.append(build_notify_logistics_update_tool(logistics_service, context=logistics_context))
            continue
        if business_executor is not None and name not in WRITE_TOOL_NAMES:
            catalog.append(_build_business_tool(name, business_executor))
        else:
            catalog.append(_build_one(name, context, executor))
    if knowledge_search is not None or "search_knowledge" in configured_names:

        @tool(
            "search_knowledge",
            args_schema=KnowledgeSearchArguments,
            description=TOOL_METADATA["search_knowledge"].description,
        )
        async def search_knowledge(query: str) -> dict[str, object]:
            """知识范围和版本由可信回调冻结，模型不能指定文件或店铺 ID。"""
            if knowledge_search is None:
                return {"status": "no_knowledge_bound", "hits": []}
            return await knowledge_search(query)

        catalog.append(search_knowledge)
    return tuple(catalog)


def _build_business_tool(name: str, executor: BusinessToolPort) -> BaseTool:
    metadata = TOOL_METADATA[name]

    @tool(name, args_schema=metadata.arguments, description=metadata.description)
    async def invoke(**arguments: object) -> dict[str, object]:
        """具体业务服务在每次调用前重新核验授权与冻结上下文。"""
        return await executor.invoke(name, arguments)

    return invoke


async def invoke_selected_tool(selected: BaseTool, raw_arguments: dict[str, object]) -> object:
    """在 LangChain 调用前显式拒绝额外模型参数，防止其宽松解析丢弃字段。"""
    schema = selected.args_schema
    if not isinstance(schema, type) or not issubclass(schema, BaseModel):
        raise ValueError("工具参数 Schema 无效")
    parsed = schema.model_validate(raw_arguments)
    return await selected.ainvoke(parsed.model_dump(mode="json"))
