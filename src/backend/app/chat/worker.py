"""独立 Agent Worker：处理自动决策，但对 Mock 平台始终失败关闭。"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.schemas import AgentAction
from app.agents.management.auto_reply_preview import policy_from_store
from app.agents.management.config_models import AgentConfig, AgentTask
from app.agents.management.config_repository import find_enabled_config
from app.agents.tools.access import current_permissions
from app.chat.service import load_automation_context, run_agent_for_message
from app.integrations.adapters import get_platform_adapter
from app.shared.config.settings import Settings, get_settings
from app.shared.database.base import User
from app.shared.database.session import session_factory
from app.shared.exceptions.errors import AppError
from app.shared.health import collect_readiness
from app.shared.logging.setup import configure_logging
from app.stores.models import Store
from app.tools.contracts import ToolExecutionContext, ToolInvocation
from app.tools.executor import SqlAlchemyToolExecutor

logger = logging.getLogger(__name__)
AUTOMATION_PERMISSIONS = {"workspace.view", "workspace.reply", "workspace.transfer", "orders.view"}
PREVIEW_READ_PERMISSIONS = frozenset({"workspace.view", "orders.view", "knowledge.view"})


async def claim_task(session: AsyncSession, settings: Settings) -> AgentTask | None:
    """使用 SKIP LOCKED 原子认领，避免多个 Worker 重复处理同一消息。"""
    now = datetime.now(UTC)
    stale_before = now - timedelta(minutes=5)
    statement = select(AgentTask)
    if not settings.auto_reply_enabled:
        statement = statement.where(AgentTask.mode == "preview")
    task = await session.scalar(
        statement.where(
            or_(
                and_(
                    AgentTask.status.in_(["pending", "failed"]),
                    or_(AgentTask.next_attempt_at.is_(None), AgentTask.next_attempt_at <= now),
                ),
                and_(AgentTask.status == "processing", AgentTask.updated_at <= stale_before),
            ),
            AgentTask.attempt_count < settings.auto_reply_max_attempts,
        )
        .order_by(AgentTask.created_at, AgentTask.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if task is None:
        return None
    task.status = "processing"
    task.attempt_count += 1
    await session.commit()
    return task


async def process_task(session: AsyncSession, task: AgentTask, settings: Settings) -> None:
    """完成一次 Agent 决策；平台发送未知时绝不自动重复。"""
    if task.mode == "preview":
        await process_preview_task(session, task)
        return
    config = await session.get(AgentConfig, task.agent_config_id)
    if config is None or config.deleted_at is not None or config.status != "enabled":
        task.status = "failed"
        task.error_code = "AGENT_CONFIG_DISABLED"
        task.processed_at = datetime.now(UTC)
        await session.commit()
        return
    conversation, trigger = await load_automation_context(session, task.conversation_id, task.trigger_message_id)
    result = await run_agent_for_message(
        session,
        config,
        conversation,
        trigger,
        task.trace_id,
        AUTOMATION_PERMISSIONS,
        allow_transfer=True,
    )
    refreshed_task = await session.get(AgentTask, task.id)
    assert refreshed_task is not None
    task = refreshed_task
    task.agent_run_id = result.agent_run_id
    task.result_action = result.action.value
    task.processed_at = datetime.now(UTC)
    if result.action == AgentAction.HUMAN_REVIEW:
        task.status = "human_review"
    elif result.action == AgentAction.TRANSFER_HUMAN:
        task.status = "transferred" if result.transfer_performed else "human_review"
    elif result.action == AgentAction.AUTO_REPLY:
        adapter = get_platform_adapter(conversation.platform)
        if not adapter.real_writes:
            task.status = "blocked_mock"
            task.error_code = "MOCK_AUTO_SEND_BLOCKED"
        elif "send_platform_message" not in config.enabled_tools or not result.draft_reply:
            task.status = "human_review"
            task.error_code = "AUTO_SEND_NOT_APPROVED"
        else:
            invocation = ToolInvocation(
                tool_name="send_platform_message",
                idempotency_key=f"agent:{result.agent_run_id}:send",
                arguments={"conversation_id": str(conversation.id), "content": result.draft_reply},
                context=ToolExecutionContext(
                    store_id=conversation.store_id,
                    actor_type="agent",
                    permissions=AUTOMATION_PERMISSIONS,
                    agent_run_id=result.agent_run_id,
                    trace_id=task.trace_id,
                ),
            )
            dispatch = await SqlAlchemyToolExecutor(session).execute(invocation)
            if dispatch.status == "succeeded" and not dispatch.mocked:
                task.status = "succeeded"
            elif dispatch.status == "unknown":
                task.status = "failed"
                task.error_code = "TOOL_RESULT_UNKNOWN"
            else:
                task.status = "human_review"
                task.error_code = dispatch.error_code or "AUTO_SEND_FAILED"
    else:
        task.status = "failed"
        task.error_code = "AGENT_FAILED"
    await session.commit()


async def process_preview_task(session: AsyncSession, task: AgentTask) -> None:
    """使用启用时的真实操作者权限运行多 Agent；草稿只存任务，不调用平台发送。"""

    async def cancel(code: str) -> None:
        task.status = "preview_cancelled"
        task.error_code = code
        task.preview_content = None
        task.processed_at = datetime.now(UTC)
        await session.commit()

    store = await session.scalar(
        select(Store).where(Store.id == task.store_id, Store.status == "active", Store.deleted_at.is_(None))
    )
    try:
        policy = policy_from_store(store) if store is not None else None
    except AppError:
        policy = None
    if policy is None or not policy.enabled or policy.actor_id is None:
        await cancel("PREVIEW_POLICY_DISABLED")
        return
    actor = await session.get(User, policy.actor_id)
    if actor is None or actor.status != "active":
        await cancel("PREVIEW_ACTOR_UNAVAILABLE")
        return
    try:
        permissions = await current_permissions(session, actor, task.store_id)
    except AppError:
        permissions = set()
    if not {"agent.manage", "workspace.view"}.issubset(permissions):
        await cancel("PREVIEW_ACTOR_REVOKED")
        return
    config = await find_enabled_config(session, task.store_id)
    if config is None:
        await cancel("PREVIEW_AGENT_DISABLED")
        return
    conversation, trigger = await load_automation_context(session, task.conversation_id, task.trigger_message_id)
    if conversation.store_id != task.store_id or trigger.id != task.trigger_message_id:
        await cancel("PREVIEW_CONTEXT_CHANGED")
        return
    result = await run_agent_for_message(
        session,
        config,
        conversation,
        trigger,
        task.trace_id,
        permissions & PREVIEW_READ_PERMISSIONS,
        user=actor,
        allow_transfer=False,
    )
    refreshed = await session.get(AgentTask, task.id)
    assert refreshed is not None
    task = refreshed
    latest_store = await session.scalar(
        select(Store)
        .where(Store.id == task.store_id, Store.status == "active", Store.deleted_at.is_(None))
        .execution_options(populate_existing=True)
    )
    try:
        latest_policy = policy_from_store(latest_store) if latest_store is not None else None
        latest_permissions = await current_permissions(session, actor, task.store_id)
    except AppError:
        latest_policy = None
        latest_permissions = set()
    current_config = await find_enabled_config(session, task.store_id)
    if (
        latest_policy is None
        or not latest_policy.enabled
        or latest_policy.actor_id != actor.id
        or not {"agent.manage", "workspace.view"}.issubset(latest_permissions)
        or current_config is None
    ):
        await cancel("PREVIEW_POLICY_CHANGED")
        return
    task.agent_run_id = result.agent_run_id
    task.result_action = result.action.value
    task.preview_content = result.draft_reply
    task.status = "human_review" if result.draft_reply else "no_suggestion"
    task.processed_at = datetime.now(UTC)
    await session.commit()


async def process_one(settings: Settings) -> bool:
    async with session_factory() as session:
        task = await claim_task(session, settings)
        if task is None:
            return False
        task_id = task.id
        try:
            await process_task(session, task, settings)
        except Exception as exc:
            error_code = type(exc).__name__[:100]
            await session.rollback()
            failed = await session.get(AgentTask, task_id, with_for_update=True)
            if failed is not None:
                failed.status = "failed"
                failed.error_code = error_code
                if failed.attempt_count < settings.auto_reply_max_attempts:
                    failed.next_attempt_at = datetime.now(UTC) + timedelta(seconds=30)
                else:
                    failed.processed_at = datetime.now(UTC)
                await session.commit()
            logger.exception(
                "Agent 自动任务失败",
                extra={"trace_id": task.trace_id, "event": "agent_task_failed", "error_code": error_code},
            )
        return True


async def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    readiness = await collect_readiness(settings)
    if readiness.status != "ready":
        raise RuntimeError("Agent Worker 依赖尚未就绪")
    async with session_factory() as session:
        enabled_count = await session.scalar(
            select(func.count())
            .select_from(AgentConfig)
            .where(
                AgentConfig.status == "enabled",
                AgentConfig.deleted_at.is_(None),
            )
        )
    worker_trace_id = str(uuid.uuid4())
    logger.info(
        "Agent Worker 启动门禁通过 enabled_configs=%s",
        int(enabled_count or 0),
        extra={"trace_id": worker_trace_id, "event": "agent_worker_ready"},
    )
    if not settings.auto_reply_enabled:
        logger.info(
            "平台自动回复开关关闭，Worker 仅认领店铺预演任务",
            extra={"trace_id": worker_trace_id, "event": "agent_worker_disabled"},
        )
    while True:
        processed = await process_one(settings)
        if not processed:
            await asyncio.sleep(settings.auto_reply_poll_seconds)


if __name__ == "__main__":
    asyncio.run(run_worker())
