"""动态多 Agent 真实调试：只读工具和绑定文件，输出仅供人工复核。"""

import asyncio
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.factory import SharedAgentRuntime
from app.agents.management.config_service import get_config, require_knowledge_view_for_binding
from app.agents.management.repository import get_published_agent, list_enabled_agents
from app.agents.management.schemas import AgentDebugRequest, AgentDebugView
from app.agents.memory.service import MemoryFact, load_memory
from app.agents.orchestration.service import RunProgress
from app.agents.providers.factory import validate_tool_model
from app.agents.runtime.execution import execute_model_run, persist_dynamic_result
from app.agents.runtime.models import AgentRun
from app.agents.runtime.snapshot import freeze_debug_context
from app.audit.models import AuditLog
from app.chat.service import user_permissions
from app.conversations.models import Conversation
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.workspace.sidebar import SidebarOrder


async def run_agent_debug_v2(
    session: AsyncSession,
    user: User,
    config_id: uuid.UUID,
    payload: AgentDebugRequest,
    trace_id: str,
    runtime: SharedAgentRuntime | None,
    *,
    progress: RunProgress | None = None,
) -> AgentDebugView:
    """店铺级路由与单 Agent 调试共享同一新执行链路；绝不发送平台消息。"""
    settings = get_settings()
    if not settings.agent_debug_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "Agent 真实调试尚未启用", 503)
    config = await get_config(session, user, config_id, permission_code="agent.manage")
    if payload.mode == "store":
        agents = tuple(await list_enabled_agents(session, config.store_id))
    else:
        published = await get_published_agent(session, store_id=config.store_id, config_id=config.id)
        if published is None or not published.ready_for_v2:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "请先发布完整的 Agent 配置", 409)
        agents = (published,)
    bound_ids = [uuid.UUID(file_id) for agent in agents for file_id in agent.file_ids]
    require_knowledge_view_for_binding(user, bound_ids)
    if bound_ids and not settings.embedding_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "绑定文件检索尚未启用", 503)
    if not settings.llm_primary_model:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "路由模型尚未配置", 503)
    try:
        validate_tool_model(settings, settings.llm_primary_provider, settings.llm_primary_model)
    except ValueError as error:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "路由模型不支持原生工具调用", 503) from error
    permissions = user_permissions(user)
    conversation = None
    order_id: str | None = None
    live_order: SidebarOrder | None = None
    deadline = time.monotonic() + settings.agent_debug_timeout_seconds
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
    snapshot = await freeze_debug_context(
        session,
        store_id=config.store_id,
        conversation_id=payload.conversation_id,
        published_agents=agents,
    )
    memory_summary = ""
    memory_facts: tuple[MemoryFact, ...] = ()
    if conversation is not None:
        memory = await load_memory(session, snapshot)
        memory_summary = memory.summary
        memory_facts = memory.facts
    run = AgentRun(
        store_id=config.store_id,
        agent_config_id=config.id,
        conversation_id=payload.conversation_id,
        trigger_message_id=None,
        model_provider=settings.llm_primary_provider,
        model_name=settings.llm_primary_model,
        prompt_version="dynamic-v2",
        action="human_review",
        status="running",
        input_summary=f"mode=debug-v2;scope={payload.mode};candidate_count={len(agents)}",
        trace_id=trace_id,
        snapshot_hash=snapshot.snapshot_hash,
        snapshot_ref=snapshot.low_sensitive_reference(),
        phase="frozen",
        config_version=agents[0].config_version if payload.mode == "single" and agents else None,
    )
    session.add(run)
    session.add(
        AuditLog(
            store_id=config.store_id,
            actor_type="user",
            actor_id=user.id,
            action="agent.debug.run",
            resource_type="agent_config",
            resource_id=config.id,
            request_id=trace_id,
            after_data={"mode": payload.mode, "candidate_count": len(agents)},
            result="accepted",
        )
    )
    await session.commit()
    progress = progress if progress is not None else RunProgress()
    progress.primary_agent_id = config.id
    try:
        async with asyncio.timeout(max(0.0, deadline - time.monotonic())) as run_timeout:
            progress.run_timeout = run_timeout
            result = await execute_model_run(
                snapshot=snapshot,
                question=payload.message,
                agents=agents,
                run_id=run.id,
                permissions=permissions,
                trace_id=trace_id,
                deadline=deadline,
                settings=settings,
                runtime=runtime,
                order_id=order_id,
                live_order=live_order,
                memory_summary=memory_summary,
                memory_facts=memory_facts,
                user=user,
                progress=progress,
            )
    except (Exception, asyncio.CancelledError) as error:
        timed_out = isinstance(error, TimeoutError)
        cancelled = isinstance(error, asyncio.CancelledError)
        # 保留截止前工具轨迹；异常路径不携带答案、事实或记忆写入。
        await persist_dynamic_result(
            session,
            run=run,
            result=progress.failure("deadline_exceeded" if timed_out else "dynamic_run_failed"),
            snapshot=snapshot,
            agents=agents,
            mode="debug",
            elapsed_ms=int((time.monotonic() - (deadline - settings.agent_debug_timeout_seconds)) * 1000),
        )
        run.status = "timeout" if timed_out else "failed"
        run.phase = "timeout" if timed_out else "failed"
        run.error_code = (
            "DYNAMIC_RUN_CANCELLED" if cancelled else "DYNAMIC_RUN_TIMEOUT" if timed_out else "DYNAMIC_RUN_FAILED"
        )
        await session.commit()
        if cancelled:
            raise
        raise AppError(
            ErrorCode.THIRD_PARTY_ERROR,
            "Agent 调试已超时" if timed_out else "Agent 动态调试失败",
            504 if timed_out else 503,
        ) from error
    await persist_dynamic_result(
        session,
        run=run,
        result=result,
        snapshot=snapshot,
        agents=agents,
        mode="debug",
        elapsed_ms=int((time.monotonic() - (deadline - settings.agent_debug_timeout_seconds)) * 1000),
    )
    citations = list(
        {
            citation.chunk_id: citation for specialist in result.specialists for citation in specialist.citation_details
        }.values()
    )
    tool_events = [
        {"agent_id": str(specialist.agent_id), "tool_name": item.name, "status": item.status, "call_id": item.call_id}
        for specialist in result.specialists
        for item in specialist.tool_events
    ]
    return AgentDebugView(
        agent_run_id=run.id,
        content="\n\n".join(result.suggestion.reply_parts)
        if result.suggestion.reply_parts
        else result.suggestion.content,
        action="human_review",
        terminal_state=result.phase.value,
        citations=citations,
        tool_calls=[],
        trace_id=trace_id,
        routed_agents=[
            {"id": str(item.agent_id), "name": next(agent.name for agent in agents if agent.id == item.agent_id)}
            for item in result.route.selections
        ],
        tool_events=tool_events,
        reason_code=result.reason_code,
        customer_translation=result.suggestion.customer_translation,
        customer_translation_error_code=result.suggestion.customer_translation_error_code,
    )
