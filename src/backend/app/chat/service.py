"""会话人工建议入口；动态 Agent 使用冻结快照和已发布配置。"""

import logging
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.factory import SharedAgentRuntime
from app.agents.core.schemas import (
    AgentAction,
    AgentRunStatus,
    AgentWorkflowResult,
)
from app.agents.core.security import SYNTHETIC_DEMO_PROMPT_VERSION
from app.agents.core.synthetic_demo import generate_synthetic_demo, resolve_synthetic_demo_scenario
from app.agents.management.config_models import AgentConfig
from app.agents.management.config_repository import find_enabled_config
from app.agents.runtime.models import AgentRun
from app.auth.store_access import allowed_store_ids
from app.chat.schemas import SuggestionCitation, SuggestionTranslation, SuggestionView
from app.conversations.models import Conversation, Message
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.database.session import session_factory
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import Store

logger = logging.getLogger(__name__)


def _log_g5_context_phase(event: str, trace_id: str, started_at: int) -> None:
    """仅输出固定阶段和耗时，不记录店铺、用户或消息内容。"""
    logger.info(
        event,
        extra={
            "event": event,
            "trace_id": trace_id,
            "latency_ms": max(0, (time.perf_counter_ns() - started_at) // 1_000_000),
        },
    )


def user_permissions(user: User) -> set[str]:
    """从已加载角色构建权限集合；admin 仍只开放配置允许的建议工具。"""
    return {permission.code for role in user.roles for permission in role.permissions}


async def _conversation_and_trigger(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    trigger_message_id: uuid.UUID | None,
    store_ids: set[uuid.UUID],
) -> tuple[Conversation, Message]:
    conversation = await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.store_id.in_(store_ids))
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    conditions = [Message.conversation_id == conversation.id, Message.role == "user"]
    if trigger_message_id is not None:
        conditions.append(Message.id == trigger_message_id)
    trigger = await session.scalar(
        select(Message).where(*conditions).order_by(Message.created_at.desc(), Message.id.desc()).limit(1)
    )
    if trigger is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "未找到可处理的客户消息", 404)
    return conversation, trigger


async def run_agent_for_message(
    session: AsyncSession,
    config: AgentConfig,
    conversation: Conversation,
    trigger: Message,
    trace_id: str,
    permissions: set[str],
    allow_transfer: bool = False,
    runtime: SharedAgentRuntime | None = None,
    user: User | None = None,
) -> AgentWorkflowResult:
    """正式建议只调用动态 Agent；关闭开关时安全失败，不回落旧 FAQ。"""
    settings = get_settings()
    if not settings.agent_v2_formal_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "动态 Agent 正式建议尚未启用", 503)
    from app.agents.runtime.formal import run_formal_suggestion

    return await run_formal_suggestion(
        session,
        conversation=conversation,
        trigger=trigger,
        trace_id=trace_id,
        permissions=permissions,
        runtime=runtime,
        user=user,
    )


async def record_first_output_latency(
    session: AsyncSession,
    agent_run_id: uuid.UUID,
    latency_ms: int,
) -> None:
    """仅首次写入从工作流开始到首个可公开结果的耗时。"""
    run = await session.get(AgentRun, agent_run_id)
    if run is not None and run.first_output_latency_ms is None:
        run.first_output_latency_ms = max(0, latency_ms)
        await session.commit()


async def mark_suggestion_delivery_interrupted(
    session: AsyncSession,
    agent_run_id: uuid.UUID,
    error_code: str = "SSE_DELIVERY_INTERRUPTED",
) -> None:
    """结果交付前中断时补写失败终态，同时保留已完成计算的低敏摘要。"""
    run = await session.get(AgentRun, agent_run_id)
    if run is None or run.status != "succeeded":
        return
    run.status = "failed"
    run.error_code = error_code
    computation_summary = run.output_summary or "none"
    run.output_summary = (
        f"{computation_summary};computation_status=succeeded;delivery_status=interrupted;delivery_error={error_code}"
    )
    await session.commit()


async def reconcile_cancelled_sse_agent_run(
    user: User,
    conversation_id: uuid.UUID,
    trace_id: str,
    stream_started_at: datetime,
) -> bool:
    """请求会话被取消后，仅收敛本次授权范围内尚在运行的 Agent 审计记录。"""
    async with session_factory() as audit_session:
        store_ids = await allowed_store_ids(audit_session, user)
        if not store_ids:
            return False
        candidates = (
            await audit_session.scalars(
                select(AgentRun.id)
                .where(
                    AgentRun.trace_id == trace_id,
                    AgentRun.conversation_id == conversation_id,
                    AgentRun.store_id.in_(store_ids),
                    AgentRun.created_at >= stream_started_at - timedelta(seconds=5),
                    AgentRun.status == AgentRunStatus.RUNNING.value,
                )
                .limit(2)
            )
        ).all()
        if not candidates:
            return False
        if len(candidates) != 1:
            raise RuntimeError("SSE 取消审计匹配多个运行记录")
        updated = (
            await audit_session.scalars(
                update(AgentRun)
                .where(AgentRun.id == candidates[0], AgentRun.status == AgentRunStatus.RUNNING.value)
                .values(
                    status=AgentRunStatus.FAILED.value,
                    action=AgentAction.FAILED.value,
                    error_code="AGENT_CANCELLED",
                    output_summary="error_code=AGENT_CANCELLED",
                )
                .returning(AgentRun.id)
            )
        ).one_or_none()
        if updated is None:
            return False
        await audit_session.commit()
        return True


def suggestion_view(result: AgentWorkflowResult) -> SuggestionView:
    translation = result.customer_translation
    return SuggestionView(
        agent_run_id=result.agent_run_id,
        content=result.draft_reply,
        intent=result.intent.value if result.intent is not None else None,
        confidence=result.final_confidence,
        action=result.action.value,
        terminal_state=result.terminal_state.value,
        requires_human=result.requires_human,
        transfer_performed=result.transfer_performed,
        citations=[
            SuggestionCitation(
                document_id=item.document_id,
                chunk_id=item.chunk_id,
                score=item.score,
                source_label=item.source_label,
            )
            for item in result.citations
        ],
        translation=(
            SuggestionTranslation(
                trigger_message_id=translation.trigger_message_id,
                source_text_sha256=translation.source_text_sha256,
                source_language=translation.source_language.value,
                target_language=translation.target_language,
                message_translation=translation.message_translation,
                draft_translation=translation.draft_translation,
                prompt_version=translation.prompt_version,
            )
            if translation is not None
            else None
        ),
        trace_id=result.trace_id,
    )


async def synthetic_demo_suggestion_view(
    session: AsyncSession,
    config: AgentConfig,
    conversation: Conversation,
    trigger: Message,
    trace_id: str,
    scenario_id: str,
) -> SuggestionView:
    """调用真实模型处理固定合成数据，并将低敏运行摘要写入 Agent 追踪表。"""
    result = await generate_synthetic_demo(get_settings(), scenario_id, trace_id)
    run = AgentRun(
        agent_config_id=config.id,
        store_id=conversation.store_id,
        conversation_id=conversation.id,
        trigger_message_id=trigger.id,
        model_provider=result.provider,
        model_name=result.model,
        prompt_version=SYNTHETIC_DEMO_PROMPT_VERSION,
        intent=result.output.intent,
        intent_confidence=Decimal(str(round(result.output.confidence, 4))),
        retrieval_score=None,
        final_confidence=Decimal(str(round(result.output.confidence, 4))),
        # 合成演示永远只生成供员工查看的草稿，即使模型给出高置信度也不自动发送。
        action="human_review",
        status="succeeded",
        input_summary=f"synthetic_demo:{scenario_id}",
        output_summary=f"synthetic_demo:{result.output.reason_code}",
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        trace_id=trace_id,
    )
    session.add(run)
    await session.commit()
    return SuggestionView(
        agent_run_id=run.id,
        content=result.output.content,
        intent=result.output.intent,
        confidence=result.output.confidence,
        action="human_review",
        terminal_state="HUMAN_REVIEW",
        requires_human=result.output.requires_human,
        transfer_performed=False,
        citations=[],
        trace_id=trace_id,
        demo_mode=True,
        demo_scenario=scenario_id,
    )


async def suggest_for_user(
    session: AsyncSession,
    user: User,
    conversation_id: uuid.UUID,
    trigger_message_id: uuid.UUID | None,
    trace_id: str,
    runtime: SharedAgentRuntime | None = None,
) -> SuggestionView:
    settings = get_settings()
    g5_timing_enabled = settings.sse_load_test_enabled
    started_at = time.perf_counter_ns()
    store_ids = await allowed_store_ids(session, user)
    if g5_timing_enabled:
        _log_g5_context_phase("g5_chat_context_store_timing", trace_id, started_at)
    started_at = time.perf_counter_ns()
    conversation, trigger = await _conversation_and_trigger(
        session,
        conversation_id,
        trigger_message_id,
        store_ids,
    )
    if g5_timing_enabled:
        _log_g5_context_phase("g5_chat_context_conversation_timing", trace_id, started_at)
    started_at = time.perf_counter_ns()
    config = await find_enabled_config(session, conversation.store_id)
    if g5_timing_enabled:
        _log_g5_context_phase("g5_chat_context_config_timing", trace_id, started_at)
    if config is None:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "该店铺未启用 Agent", 409)
    if settings.ai_synthetic_demo_enabled:
        store = await session.scalar(select(Store).where(Store.id == conversation.store_id))
        if store is not None and store.code == "ai-demo-store" and store.metadata_json.get("synthetic_demo") is True:
            scenario_id = resolve_synthetic_demo_scenario(conversation.external_conversation_id, trigger.content)
            if scenario_id is None:
                raise AppError(ErrorCode.RESOURCE_CONFLICT, "AI 演示会话已被修改，请重新生成演示数据", 409)
            return await synthetic_demo_suggestion_view(
                session,
                config,
                conversation,
                trigger,
                trace_id,
                scenario_id,
            )
    result = await run_agent_for_message(
        session,
        config,
        conversation,
        trigger,
        trace_id,
        user_permissions(user),
        runtime=runtime,
        user=user,
    )
    return suggestion_view(result)


async def load_automation_context(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    trigger_message_id: uuid.UUID,
) -> tuple[Conversation, Message]:
    """Agent Worker 使用已落库任务反查可信上下文。"""
    return await _conversation_and_trigger(
        session,
        conversation_id,
        trigger_message_id,
        set((await session.scalars(select(Conversation.store_id).where(Conversation.id == conversation_id))).all()),
    )
