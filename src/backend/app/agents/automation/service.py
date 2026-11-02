"""入站任务、幂等账本和持久租约调度。"""

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, exists, func, literal, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from app.agents.automation.models import AutomationDelivery
from app.agents.automation.policy import policy_from_store
from app.agents.management.config_models import AgentTask
from app.agents.management.config_repository import find_enabled_config
from app.conversations.models import Conversation, Message
from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import Store


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def payload_hash(
    *,
    store_id: uuid.UUID,
    conversation_id: uuid.UUID,
    content: str,
    message_type: str,
    card_order_id: str | None,
    card_package_id: str | None,
) -> str:
    payload = [str(store_id), str(conversation_id), content, message_type, card_order_id, card_package_id]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


async def enqueue_delivery(
    session: AsyncSession,
    *,
    store_id: uuid.UUID,
    conversation_id: uuid.UUID,
    source_kind: str,
    source_key: str,
    content: str,
    authorized_by: uuid.UUID | None,
    policy_revision: int,
    mode: str,
    trigger_message_id: uuid.UUID | None = None,
    agent_run_id: uuid.UUID | None = None,
    part_index: int = 0,
    message_type: str = "text",
    card_order_id: str | None = None,
    card_package_id: str | None = None,
    not_before: datetime | None = None,
    authorization_json: dict[str, object] | None = None,
) -> AutomationDelivery:
    from app.tools.contracts import SendPlatformMessageArguments

    SendPlatformMessageArguments.model_validate(
        {
            "conversation_id": conversation_id,
            "content": content,
            "message_type": message_type,
            "card_order_id": card_order_id,
            "card_package_id": card_package_id,
        }
    )
    if (
        source_kind not in {"agent", "welcome", "timeout"}
        or mode not in {"preview", "auto"}
        or not source_key
        or len(source_key) > 200
        or part_index < 0
        or policy_revision < 0
    ):
        raise AppError(ErrorCode.VALIDATION_ERROR, "自动投递来源无效", 422)
    digest = payload_hash(
        store_id=store_id,
        conversation_id=conversation_id,
        content=content,
        message_type=message_type,
        card_order_id=card_order_id,
        card_package_id=card_package_id,
    )
    # 同店入账串行化，唯一约束作为最终防线；由调用方一起提交来源状态和队列。
    await session.scalar(select(Store.id).where(Store.id == store_id).with_for_update())
    existing = await session.scalar(
        select(AutomationDelivery).where(
            AutomationDelivery.store_id == store_id,
            AutomationDelivery.conversation_id == conversation_id,
            AutomationDelivery.source_kind == source_kind,
            AutomationDelivery.source_key == source_key,
            AutomationDelivery.part_index == part_index,
        )
    )
    if existing is not None:
        if (
            existing.payload_hash,
            existing.authorized_by,
            existing.policy_revision,
            existing.mode,
            existing.agent_run_id,
            existing.trigger_message_id,
        ) != (digest, authorized_by, policy_revision, mode, agent_run_id, trigger_message_id):
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "自动投递幂等键内容不一致", 409)
        return existing
    row = AutomationDelivery(
        id=uuid.uuid4(),
        store_id=store_id,
        conversation_id=conversation_id,
        trigger_message_id=trigger_message_id,
        source_kind=source_kind,
        source_key=source_key,
        part_index=part_index,
        content=content,
        message_type=message_type,
        card_order_id=card_order_id,
        card_package_id=card_package_id,
        agent_run_id=agent_run_id,
        authorized_by=authorized_by,
        policy_revision=policy_revision,
        payload_hash=digest,
        mode=mode,
        status="pending",
        not_before=not_before,
        authorization_json=dict(authorization_json or {}),
        attempt_count=0,
    )
    session.add(row)
    await session.flush()
    return row


async def on_agent_inbound(
    session: AsyncSession, conversation: Conversation, trigger: Message, settings: Settings
) -> bool:
    store = await session.scalar(
        select(Store).where(Store.id == conversation.store_id, Store.status == "active", Store.deleted_at.is_(None))
    )
    raw = (store.metadata_json or {}).get("agent_automation") if store is not None else None
    if raw is None:
        return False
    # 显式 off/损坏策略也阻断旧 legacy 路径，不能回退到更宽松的全局开关。
    if store is None:
        return True
    try:
        policy = policy_from_store(store)
    except ValueError:
        return True
    if policy.mode == "off" or (conversation.metadata_json or {}).get("automation_paused") is True:
        return True
    if (
        conversation.platform != "tiktok"
        or conversation.status != "active"
        or trigger.direction != "inbound"
        or trigger.store_id != conversation.store_id
        or trigger.conversation_id != conversation.id
        or trigger.role != "user"
    ):
        return True
    if (
        policy.enabled_at is None
        or utc(trigger.created_at) <= policy.enabled_at
        or (policy.mode == "auto" and not settings.tiktok_automation_effective_enabled)
    ):
        return True
    config = await find_enabled_config(session, conversation.store_id)
    if config is None:
        return True
    existing = await session.scalar(select(AgentTask.id).where(AgentTask.trigger_message_id == trigger.id))
    if existing is None:
        session.add(
            AgentTask(
                store_id=conversation.store_id,
                conversation_id=conversation.id,
                trigger_message_id=trigger.id,
                agent_config_id=config.id,
                mode="automation",
                trace_id=f"automation:{policy.revision}:{uuid.uuid4()}",
                status="pending",
            )
        )
    return True


async def recover_expired_deliveries(session: AsyncSession) -> None:
    now = datetime.now(UTC)
    rows = (
        await session.scalars(
            select(AutomationDelivery)
            .where(AutomationDelivery.status.in_(("claimed", "dispatching")), AutomationDelivery.claimed_until <= now)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for row in rows:
        if row.status == "dispatching":
            row.status = "unknown"
            row.error_code = "AUTOMATION_RECEIPT_UNKNOWN"
            row.processed_at = now
        else:
            row.status = "pending"
        row.claim_token = None
        row.claimed_until = None


def task_has_predecessor(settings: Settings) -> ColumnElement[bool]:
    earlier = aliased(AgentTask)
    receipts = exists(
        select(AutomationDelivery.id).where(
            AutomationDelivery.store_id == earlier.store_id,
            AutomationDelivery.conversation_id == earlier.conversation_id,
            AutomationDelivery.trigger_message_id == earlier.trigger_message_id,
        )
    )
    unsettled = exists(
        select(AutomationDelivery.id).where(
            AutomationDelivery.store_id == earlier.store_id,
            AutomationDelivery.conversation_id == earlier.conversation_id,
            AutomationDelivery.trigger_message_id == earlier.trigger_message_id,
            AutomationDelivery.status.in_(("pending", "claimed", "dispatching", "unknown")),
        )
    )
    retryable = earlier.attempt_count < settings.auto_reply_max_attempts
    active = or_(
        earlier.status == "pending",
        and_(
            earlier.status == "processing",
            or_(retryable, earlier.updated_at > datetime.now(UTC) - timedelta(minutes=5)),
        ),
        and_(earlier.status == "failed", retryable),
        and_(earlier.status == "queued", or_(~receipts, unsettled)),
    )
    return exists(
        select(earlier.id).where(
            earlier.store_id == AgentTask.store_id,
            earlier.conversation_id == AgentTask.conversation_id,
            tuple_(earlier.created_at, earlier.id) < tuple_(AgentTask.created_at, AgentTask.id),
            active,
        )
    )


async def delivery_predecessor(session: AsyncSession, row: AutomationDelivery) -> str | None:
    earlier = aliased(AutomationDelivery)
    trigger = await session.get(Message, row.trigger_message_id) if row.trigger_message_id else None
    task = (
        await session.scalar(select(AgentTask).where(AgentTask.trigger_message_id == row.trigger_message_id))
        if row.trigger_message_id
        else None
    )
    current_time = task.created_at if task else trigger.created_at if trigger else row.created_at
    current_trigger = task.id if task else trigger.id if trigger else row.id
    priority = {"welcome": 0, "agent": 1, "timeout": 2}
    same_group = and_(earlier.source_kind == row.source_kind, earlier.source_key == row.source_key)
    earlier_priority = case((earlier.source_kind == "welcome", 0), (earlier.source_kind == "agent", 1), else_=2)
    earlier_key = tuple_(
        func.coalesce(AgentTask.created_at, Message.created_at, earlier.created_at),
        earlier_priority,
        func.coalesce(AgentTask.id, Message.id, earlier.id),
        earlier.source_key,
    )
    current_key = tuple_(
        literal(current_time), literal(priority[row.source_kind]), literal(current_trigger), literal(row.source_key)
    )
    status = await session.scalar(
        select(earlier.status)
        .outerjoin(Message, Message.id == earlier.trigger_message_id)
        .outerjoin(AgentTask, AgentTask.trigger_message_id == earlier.trigger_message_id)
        .where(
            earlier.store_id == row.store_id,
            earlier.conversation_id == row.conversation_id,
            or_(earlier.not_before.is_(None), earlier.not_before <= datetime.now(UTC)),
            or_(
                and_(
                    same_group, earlier.part_index < row.part_index, earlier.status.notin_(("succeeded", "previewed"))
                ),
                and_(
                    ~same_group,
                    earlier_key < current_key,
                    earlier.status.in_(("pending", "claimed", "dispatching", "unknown")),
                ),
            ),
        )
        .order_by(earlier.created_at, earlier.part_index, earlier.id)
        .limit(1)
    )

    return status if isinstance(status, str) else None


async def claim_delivery(session: AsyncSession, settings: Settings) -> AutomationDelivery | None:
    await recover_expired_deliveries(session)
    now = datetime.now(UTC)
    source_priority = case(
        (AutomationDelivery.source_kind == "welcome", 0), (AutomationDelivery.source_kind == "agent", 1), else_=2
    )
    row = await session.scalar(
        select(AutomationDelivery)
        .outerjoin(Message, Message.id == AutomationDelivery.trigger_message_id)
        .outerjoin(AgentTask, AgentTask.trigger_message_id == AutomationDelivery.trigger_message_id)
        .where(
            AutomationDelivery.status == "pending",
            or_(AutomationDelivery.not_before.is_(None), AutomationDelivery.not_before <= now),
        )
        .order_by(
            func.coalesce(AgentTask.created_at, Message.created_at, AutomationDelivery.created_at),
            source_priority,
            func.coalesce(AgentTask.id, Message.id, AutomationDelivery.id),
            AutomationDelivery.part_index,
            AutomationDelivery.created_at,
            AutomationDelivery.id,
        )
        .with_for_update(of=AutomationDelivery, skip_locked=True)
        .limit(1)
    )
    if row is not None:
        earlier = await delivery_predecessor(session, row)
        if earlier is None and row.source_kind == "agent":
            blocked_task = await session.scalar(
                select(AgentTask.id)
                .where(AgentTask.trigger_message_id == row.trigger_message_id, task_has_predecessor(settings))
                .limit(1)
            )
            if blocked_task is not None:
                earlier = "processing"
        if earlier is not None:
            if earlier in {"failed", "cancelled", "unknown"}:
                row.status = "cancelled"
                row.error_code = "AUTOMATION_PREVIOUS_PART_UNDELIVERED"
                row.processed_at = now
            row = None
        else:
            row.status = "claimed"
            row.claim_token = uuid.uuid4()
            row.claimed_until = now + timedelta(minutes=5)
            row.attempt_count += 1
    await session.commit()
    return row


async def process_delivery(session: AsyncSession, row: AutomationDelivery, settings: Settings) -> None:
    from app.agents.automation.authorization import authorize_delivery
    from app.tools.contracts import ToolExecutionContext, ToolInvocation
    from app.tools.executor import SqlAlchemyToolExecutor

    row_id = row.id
    token = row.claim_token
    await session.refresh(row, with_for_update=True)
    if row.status != "claimed" or row.claim_token != token:
        return
    if not await authorize_delivery(session, row, settings, require_external=row.mode == "auto"):
        row.status, row.error_code = "cancelled", "AUTOMATION_AUTHORIZATION_CHANGED"
    elif row.mode == "preview":
        row.status = "previewed"
    else:
        # 任何平台调用前落库；退出后只进入 unknown，不重新执行。
        row.status = "dispatching"
        await session.commit()
        result = await SqlAlchemyToolExecutor(session).execute(
            ToolInvocation(
                tool_name="send_platform_message",
                idempotency_key=f"automation:{row.id}",
                arguments={
                    "conversation_id": str(row.conversation_id),
                    "content": row.content,
                    "message_type": row.message_type,
                    "card_order_id": row.card_order_id,
                    "card_package_id": row.card_package_id,
                },
                context=ToolExecutionContext(
                    store_id=row.store_id,
                    actor_type="agent" if row.source_kind == "agent" else "job",
                    actor_id=row.authorized_by,
                    permissions={"workspace.reply"},
                    agent_run_id=row.agent_run_id,
                    automation_delivery_id=row.id,
                    automation_claim_token=token,
                ),
            )
        )
        refreshed = await session.get(AutomationDelivery, row_id, populate_existing=True)
        assert refreshed is not None
        row = refreshed
        row.status = (
            "succeeded"
            if result.status == "succeeded" and not result.mocked
            else "unknown"
            if result.status == "unknown"
            else "failed"
        )
        row.error_code = result.error_code or ("AUTOMATION_MOCK_BLOCKED" if result.mocked else None)
        message = await session.scalar(
            select(Message).where(Message.store_id == row.store_id, Message.idempotency_key == f"automation:{row.id}")
        )
        row.remote_message_id = message.external_message_id if message and message.status == "sent" else None
    row.processed_at = datetime.now(UTC)
    row.claim_token = None
    row.claimed_until = None
    await session.commit()
