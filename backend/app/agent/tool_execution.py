"""把 Agent 工具需求转换为受控、可审计的全栈工具调用。"""

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from app.agent.schemas import AgentWorkflowCommand, ApprovedToolAction, RequiredToolName
from app.tools.contracts import (
    TOOL_DEFINITIONS,
    ToolExecutionContext,
    ToolInvocation,
    ToolName,
    ToolResult,
    validate_tool_arguments,
)


class ToolExecutionPort(Protocol):
    """全栈工具执行层提供给 Agent 的唯一副作用端口。"""

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        """执行白名单工具并返回已持久化的低敏结果。"""
        ...


@dataclass(frozen=True, slots=True)
class ExecutedAgentTool:
    """关联工具名称、执行来源店铺和结果，供工作流解释与追踪。

    ``source_store_id`` 在受控调用创建时即固定，后续证据构建不能再用当前
    工作流店铺覆盖它。字段保留可空只为兼容不参与证据授权的旧测试替身；
    缺少来源的执行结果不会被提升为可信工具证据。
    """

    tool_name: ToolName
    result: ToolResult
    source_store_id: uuid.UUID | None = None


@dataclass(slots=True)
class AgentToolBatchResult:
    """一次工作流节点的工具执行汇总。"""

    results: list[ExecutedAgentTool] = field(default_factory=list)
    unresolved_tools: list[RequiredToolName] = field(default_factory=list)


class AgentToolService:
    """执行确定性工具计划，不让模型决定权限、资源 ID 或写入参数。"""

    def __init__(self, executor: ToolExecutionPort) -> None:
        """绑定由全栈模块实现的白名单执行端口。"""
        self.executor = executor

    async def execute_required(
        self,
        command: AgentWorkflowCommand,
        *,
        agent_run_id: uuid.UUID,
        required_tools: list[RequiredToolName],
    ) -> AgentToolBatchResult:
        """按声明顺序执行可授权工具，其余工具明确保留为未解析。

        查询参数来自可信 `tool_context`；地址、优惠券和平台发送必须存在
        `ApprovedToolAction`。转人工属于安全接管动作，只要求可信上下文显式
        开放工具并提供权限，不依赖模型或客户确认。
        """
        batch = AgentToolBatchResult()
        tool_context = command.tool_context
        if tool_context is None:
            batch.unresolved_tools.extend(self._unique(required_tools))
            return batch

        for tool_name in self._unique(required_tools):
            if tool_name not in tool_context.available_tools:
                batch.unresolved_tools.append(tool_name)
                continue
            invocation = self._build_invocation(command, agent_run_id, tool_name)
            if invocation is None:
                batch.unresolved_tools.append(tool_name)
                continue
            result = await self.executor.execute(invocation)
            batch.results.append(
                ExecutedAgentTool(
                    tool_name=tool_name,
                    result=result,
                    source_store_id=invocation.context.store_id,
                )
            )
        return batch

    def _build_invocation(
        self,
        command: AgentWorkflowCommand,
        agent_run_id: uuid.UUID,
        tool_name: RequiredToolName,
    ) -> ToolInvocation | None:
        """从可信上下文组装参数；缺少业务 ID 或写批准时拒绝猜测。"""
        tool_context = command.tool_context
        if tool_context is None:
            return None
        arguments: dict[str, object] | None = None
        idempotency_key = f"agent:{agent_run_id}:{tool_name}"

        if tool_name in {"query_order", "query_logistics"}:
            if tool_context.order_id is not None:
                arguments = {"order_id": tool_context.order_id}
        elif tool_name == "query_customer_profile":
            if tool_context.customer_id is not None:
                arguments = {"customer_id": str(tool_context.customer_id)}
        elif tool_name == "transfer_to_human":
            approval = self._find_approval(command, tool_name)
            if approval is not None:
                arguments = approval.arguments
                idempotency_key = approval.idempotency_key
            else:
                arguments = {
                    "conversation_id": str(command.conversation_id),
                    "reason": "agent_safety_handoff",
                    "assign_to": None,
                }
        else:
            approval = self._find_approval(command, tool_name)
            if approval is not None:
                arguments = approval.arguments
                idempotency_key = approval.idempotency_key

        if arguments is None:
            return None
        normalized_arguments = validate_tool_arguments(tool_name, arguments)
        return ToolInvocation(
            tool_name=tool_name,
            idempotency_key=idempotency_key,
            arguments=normalized_arguments,
            context=ToolExecutionContext(
                store_id=command.store_id,
                actor_type="agent",
                actor_id=None,
                permissions=tool_context.permissions,
                agent_run_id=agent_run_id,
                trace_id=command.trace_id,
            ),
        )

    @staticmethod
    def _find_approval(command: AgentWorkflowCommand, tool_name: str) -> ApprovedToolAction | None:
        """返回可信层批准的唯一写操作；Schema 已拒绝重复批准。"""
        if command.tool_context is None:
            return None
        return next(
            (item for item in command.tool_context.approved_actions if item.tool_name == tool_name),
            None,
        )

    @staticmethod
    def _unique(required_tools: list[RequiredToolName]) -> list[RequiredToolName]:
        """保持选择顺序并去重，避免同一节点重复产生业务副作用。"""
        return list(dict.fromkeys(required_tools))


def required_permission(tool_name: ToolName) -> str:
    """返回工具固定权限，供调用方展示和契约测试。"""
    return TOOL_DEFINITIONS[tool_name].permission
