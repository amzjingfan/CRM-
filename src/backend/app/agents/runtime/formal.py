"""正式人工建议使用同一动态路由与函数工具链路，结果只供坐席复核。"""

import asyncio
import time
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.factory import SharedAgentRuntime
from app.agents.core.reply_policy import CustomerLanguage, detect_customer_language
from app.agents.core.schemas import (
    AgentAction,
    AgentWorkflowResult,
    ClassificationState,
    WorkflowTerminalState,
)
from app.agents.management.repository import list_enabled_agents
from app.agents.memory.models import AgentSessionMemory
from app.agents.memory.service import load_memory, remember_session_question
from app.agents.orchestration.service import RunProgress
from app.agents.providers.factory import validate_tool_model
from app.agents.runtime.execution import execute_model_run, persist_dynamic_result
from app.agents.runtime.models import AgentRun
from app.agents.runtime.snapshot import freeze_run_context
from app.agents.safety.grounding import GROUNDING_PROMPT_VERSION
from app.conversations.models import Conversation, Message
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.workspace.sidebar import SidebarOrder


async def run_formal_suggestion(
    session: AsyncSession,
    *,
    conversation: Conversation,
    trigger: Message,
    trace_id: str,
    permissions: set[str],
    runtime: SharedAgentRuntime | None,
    user: User | None = None,
) -> AgentWorkflowResult:
    """所有候选从同店已启用配置读取；旧 FAQ 路径不参与本次运行。"""
    settings = get_settings()
    if not settings.agent_v2_formal_enabled or not settings.llm_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "动态 Agent 正式建议尚未启用", 503)
    agents = tuple(await list_enabled_agents(session, conversation.store_id))
    if not agents:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "该店铺未启用 Agent", 409)
    if not settings.llm_primary_model:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "路由模型尚未配置", 503)
    try:
        validate_tool_model(settings, settings.llm_primary_provider, settings.llm_primary_model)
    except ValueError as error:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "路由模型不支持原生工具调用", 503) from error
    if any(agent.file_ids for agent in agents) and not settings.embedding_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "绑定文件检索尚未启用", 503)

    deadline = time.monotonic() + settings.agent_debug_timeout_seconds
    memory_revision = (
        await session.scalar(
            select(AgentSessionMemory.revision).where(
                AgentSessionMemory.store_id == conversation.store_id,
                AgentSessionMemory.conversation_id == conversation.id,
                AgentSessionMemory.customer_id == conversation.customer_id,
            )
        )
        or 0
    )
    snapshot = await freeze_run_context(
        session,
        store_id=conversation.store_id,
        conversation_id=conversation.id,
        trigger_message_id=trigger.id,
        published_agents=agents,
        memory_revision=memory_revision,
    )
    memory = await load_memory(session, snapshot)
    order_id: str | None = None
    live_order: SidebarOrder | None = None

    run = AgentRun(
        store_id=conversation.store_id,
        agent_config_id=agents[0].id,
        conversation_id=conversation.id,
        trigger_message_id=trigger.id,
        model_provider=settings.llm_primary_provider,
        model_name=settings.llm_primary_model,
        prompt_version="dynamic-v2",
        action="human_review",
        status="running",
        input_summary=f"mode=formal-v2;candidate_count={len(agents)}",
        trace_id=trace_id,
        snapshot_hash=snapshot.snapshot_hash,
        snapshot_ref=snapshot.low_sensitive_reference(),
        phase="frozen",
    )
    session.add(run)
    await session.commit()
    progress = RunProgress()
    try:
        async with asyncio.timeout(max(0.0, deadline - time.monotonic())):
            result = await execute_model_run(
                snapshot=snapshot,
                question=trigger.content,
                agents=agents,
                run_id=run.id,
                permissions=permissions,
                trace_id=trace_id,
                deadline=deadline,
                settings=settings,
                runtime=runtime,
                order_id=order_id,
                live_order=live_order,
                memory_summary=memory.summary,
                memory_facts=memory.facts,
                user=user,
                progress=progress,
            )
    except Exception as error:
        timed_out = isinstance(error, TimeoutError)
        # 保留截止前工具轨迹；异常路径不携带答案、事实或记忆写入。
        await persist_dynamic_result(
            session,
            run=run,
            result=progress.failure("deadline_exceeded" if timed_out else "dynamic_run_failed"),
            snapshot=snapshot,
            agents=agents,
            mode="formal",
            elapsed_ms=int((time.monotonic() - (deadline - settings.agent_debug_timeout_seconds)) * 1000),
        )
        run.status = "timeout" if timed_out else "failed"
        run.phase = "timeout" if timed_out else "failed"
        run.error_code = "DYNAMIC_RUN_TIMEOUT" if timed_out else "DYNAMIC_RUN_FAILED"
        await session.commit()
        raise AppError(
            ErrorCode.THIRD_PARTY_ERROR,
            "Agent 建议已超时" if timed_out else "Agent 动态建议失败",
            504 if timed_out else 503,
        ) from error
    await persist_dynamic_result(
        session,
        run=run,
        result=result,
        snapshot=snapshot,
        agents=agents,
        mode="formal",
        elapsed_ms=int((time.monotonic() - (deadline - settings.agent_debug_timeout_seconds)) * 1000),
    )
    try:
        observations = tuple(
            (specialist.agent_id, observation)
            for specialist in result.specialists
            for observation in specialist.observations
        )
        await remember_session_question(session, snapshot, memory, trigger.content, observations)
    except AppError:
        # 关闭、身份变化或并发版本冲突只影响派生记忆，不能改写已完成的人工建议。
        await session.rollback()
    language = detect_customer_language(trigger.content)
    reply_language: Literal["zh-CN", "en"] = "en" if language == CustomerLanguage.EN else "zh-CN"
    citations = list(
        {item.chunk_id: item for specialist in result.specialists for item in specialist.citation_details}.values()
    )
    return AgentWorkflowResult(
        agent_run_id=run.id,
        terminal_state=WorkflowTerminalState.HUMAN_REVIEW,
        intent=None,
        classification_state=ClassificationState.UNKNOWN,
        citations=citations,
        draft_reply=result.suggestion.content,
        required_tools=[],
        intent_confidence=0,
        retrieval_score=0,
        grounding_confidence=0,
        final_confidence=0,
        action=AgentAction.HUMAN_REVIEW,
        requires_human=True,
        detected_language=language,
        reply_language=reply_language,
        provider=settings.llm_primary_provider,
        model=settings.llm_primary_model,
        prompt_versions={"dynamic_router": "v2", "evidence_review": GROUNDING_PROMPT_VERSION},
        input_tokens=run.input_tokens or 0,
        output_tokens=run.output_tokens or 0,
        latency_ms=run.latency_ms or 0,
        trace_id=trace_id,
        safety_reason_codes=[result.reason_code] if result.reason_code else [],
    )
