"""Agent 管理页的受控真实调试，不创建客户消息也不触发平台发送。"""

import asyncio
import uuid
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.factory import SharedAgentRuntime, build_agent_workflow
from app.agent.models import AgentRun
from app.agent.reply_policy import resolve_store_reply_profile
from app.agent.schemas import AgentToolRuntimeContext, AgentWorkflowCommand, IntentName
from app.agent.tool_routing import detect_required_tools
from app.agent.workflow import AgentWorkflowExecutionError
from app.agent_management.live_tools import AgentDebugLiveOrderExecutor
from app.agent_management.schemas import AgentDebugRequest, AgentDebugView
from app.agent_management.service import get_config, require_knowledge_view_for_binding, validate_knowledge_file_ids
from app.audit.models import AuditLog
from app.chat.service import SAFE_SUGGESTION_TOOLS, user_permissions
from app.conversations.models import Conversation
from app.orders.models import Order
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.tools.contracts import ToolName
from app.workspace.sidebar import SidebarOrder, SidebarOrderDetail, get_sidebar_order_detail, latest_verified_live_order


async def run_agent_debug(
    session: AsyncSession,
    user: User,
    config_id: uuid.UUID,
    payload: AgentDebugRequest,
    trace_id: str,
    runtime: SharedAgentRuntime | None,
) -> AgentDebugView:
    """停用 Agent 也可调试已保存配置；业务工具仅接受授权会话派生的 ID。"""
    settings = get_settings()
    if not settings.agent_debug_enabled or not settings.embedding_enabled or runtime is None:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "Agent 真实调试尚未启用", 503)
    config = await get_config(session, user, config_id)
    if config.knowledge_scope.get("agent_type", "service") != "service":
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "经营类 Agent 暂不支持客服调试", 409)

    raw_file_ids = config.knowledge_scope.get("file_ids", [])
    if not isinstance(raw_file_ids, list):
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "Agent 知识绑定配置无效", 409)
    try:
        file_ids = [uuid.UUID(str(item)) for item in raw_file_ids]
    except (TypeError, ValueError, AttributeError) as error:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "Agent 知识绑定配置无效", 409) from error
    require_knowledge_view_for_binding(user, file_ids)
    if file_ids:
        await validate_knowledge_file_ids(session, config.store_id, file_ids)

    permissions = user_permissions(user)
    available_tools: set[ToolName] = set()
    order_id: str | None = None
    customer_id: uuid.UUID | None = None
    live_order: SidebarOrder | None = None
    live_detail: SidebarOrderDetail | None = None
    deadline: float | None = None
    if payload.conversation_id is not None:
        if "admin" not in {role.code for role in user.roles} and "workspace.view" not in permissions:
            raise AppError(ErrorCode.PERMISSION_DENIED, "没有读取会话上下文的权限", 403)
        conversation = await session.scalar(
            select(Conversation).where(
                Conversation.id == payload.conversation_id,
                Conversation.store_id == config.store_id,
            )
        )
        if conversation is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "当前店铺会话不存在", 404)
        customer_id = conversation.customer_id
        recent_order = await session.scalar(
            select(Order)
            .where(
                Order.store_id == config.store_id,
                Order.customer_id == customer_id,
            )
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        order_id = str(recent_order.id) if recent_order is not None else None
        available_tools = cast(set[ToolName], set(config.enabled_tools) & SAFE_SUGGESTION_TOOLS)
        wants_order_tool = any(
            set(detect_required_tools(payload.message, intent)) & {"query_order", "query_logistics"}
            for intent in IntentName
        )
        wants_logistics_tool = any(
            "query_logistics" in detect_required_tools(payload.message, intent) for intent in IntentName
        )
        if (
            conversation.platform == "tiktok"
            and getattr(settings, "real_tiktok_read_enabled", False)
            and available_tools & {"query_order", "query_logistics"}
            and wants_order_tool
        ):
            deadline = asyncio.get_running_loop().time() + settings.agent_debug_timeout_seconds
            try:
                async with asyncio.timeout_at(deadline):
                    live_order = await latest_verified_live_order(session, conversation)
                    if live_order is not None and wants_logistics_tool:
                        live_detail = await get_sidebar_order_detail(
                            session, user, conversation.id, live_order.external_order_id
                        )
            except TimeoutError as error:
                raise AppError(ErrorCode.THIRD_PARTY_ERROR, "Agent 调试已超时，请稍后重试", 504) from error
            order_id = str(live_order.id) if live_order is not None else None

    command = AgentWorkflowCommand(
        store_id=config.store_id,
        conversation_id=payload.conversation_id or uuid.uuid4(),
        trigger_message_id=uuid.uuid4(),
        message=payload.message,
        history=[],
        language=None,
        trace_id=trace_id,
        tool_context=AgentToolRuntimeContext(
            order_id=order_id,
            customer_id=customer_id,
            available_tools=available_tools,
            permissions=permissions,
        ),
        reply_profile=resolve_store_reply_profile(config.knowledge_scope),
        knowledge_file_ids=file_ids,
        debug_mode=True,
        agent_config_id=config.id,
    )
    session.add(
        AuditLog(
            store_id=config.store_id,
            actor_type="user",
            actor_id=user.id,
            action="agent.debug.run",
            resource_type="agent_config",
            resource_id=config.id,
            request_id=trace_id,
            after_data={"has_conversation": payload.conversation_id is not None, "bound_file_count": len(file_ids)},
            result="accepted",
        )
    )
    await session.commit()
    try:
        executor = (
            AgentDebugLiveOrderExecutor(session, config.store_id, live_order, live_detail)
            if live_order is not None
            else None
        )
        deadline = deadline or asyncio.get_running_loop().time() + settings.agent_debug_timeout_seconds
        async with asyncio.timeout_at(deadline):
            result = await build_agent_workflow(session, settings, runtime=runtime, tool_executor=executor).run(
                session, command
            )
    except TimeoutError as error:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "Agent 调试已超时，请稍后重试", 504) from error
    except AgentWorkflowExecutionError as error:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, f"Agent 调试失败（{error.error_code}）", 503) from error
    run = await session.get(AgentRun, result.agent_run_id)
    if run is not None and run.agent_config_id is None:
        run.agent_config_id = config.id
        await session.commit()
    return AgentDebugView(
        agent_run_id=result.agent_run_id,
        content=result.draft_reply,
        action=result.action.value,
        terminal_state=result.terminal_state.value,
        citations=result.citations,
        tool_calls=result.tool_calls,
        trace_id=result.trace_id,
    )
