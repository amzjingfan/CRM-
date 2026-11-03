"""可信入站接待调度；授权与回复取消在投递前重新检查。"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.reply_policy import AgentReplyProfile, detect_customer_language, resolve_reply_language
from app.conversations.models import Conversation, Message
from app.reception.models import ReceptionConversationState, ReceptionPolicy, ReceptionPolicyStore
from app.reception.schemas import PolicySchedule
from app.reception.service import _permission_store_ids
from app.shared.config.settings import Settings
from app.shared.database.base import User
from app.stores.models import Store

if TYPE_CHECKING:
    from app.agents.automation.models import AutomationDelivery

APPROVED_COPY = {
    "welcome": (
        "您好，欢迎咨询！请问有什么可以帮您？",
        "Hi! Welcome to our store. How can we help you today?",
    ),
    "timeout": (
        "我们已收到您的消息，客服正在处理中。感谢您的耐心等待。",
        "We've received your message. Our support team is working on your question. Thank you for your patience.",
    ),
}


def advance_inbound(state: ReceptionConversationState, trigger: Message, *, idle_hours: int) -> bool:
    """重放和乱序消息不能倒退咨询段或延后最早未答时间。"""
    at = trigger.sent_at or trigger.created_at
    if state.last_activity_at is not None and at <= state.last_activity_at:
        if (
            state.unanswered_since is not None
            and state.unanswered_message_id != trigger.id
            and at < state.unanswered_since
        ):
            state.unanswered_since = at
            state.unanswered_message_id = trigger.id
        return False
    new_segment = state.last_activity_at is None or at - state.last_activity_at >= timedelta(hours=idle_hours)
    if new_segment:
        state.segment_id = trigger.id
    state.last_activity_at = at
    if state.unanswered_since is None:
        state.unanswered_since = at
        state.unanswered_message_id = trigger.id
    return new_segment


def policy_active(policy: ReceptionPolicy, timezone: str, now: datetime) -> bool:
    if not policy.enabled or policy.delivery_mode == "off":
        return False
    if policy.valid_from is not None and now < policy.valid_from:
        return False
    if policy.valid_to is not None and now >= policy.valid_to:
        return False
    if policy.schedule is None:
        return True
    try:
        schedule = PolicySchedule.model_validate(policy.schedule)
        local = now.astimezone(ZoneInfo(timezone))
    except (ValueError, ZoneInfoNotFoundError):
        return False
    if schedule.mode == "long_term":
        return True
    if schedule.start_date is None or schedule.end_date is None:
        return False
    if not schedule.start_date <= local.date() <= schedule.end_date:
        return False
    if schedule.mode == "fixed_hours":
        return (
            schedule.daily_start_time is not None
            and schedule.daily_end_time is not None
            and schedule.daily_start_time <= local.time().replace(tzinfo=None) < schedule.daily_end_time
        )
    return True


def reception_content(policy: ReceptionPolicy, trigger: Message) -> str | None:
    language = resolve_reply_language(AgentReplyProfile(), detect_customer_language(trigger.content), trigger.language)
    if language == "zh-CN":
        return policy.content
    if policy.content_en and policy.content_en.strip():
        return policy.content_en
    # 自定义中文没有批准的英文版本时停止，不能凭空翻译店铺承诺。
    approved = APPROVED_COPY.get(policy.kind)
    if approved and policy.content == approved[0]:
        return approved[1]
    if detect_customer_language(policy.content).value == "en":
        return policy.content
    return None


async def _locked_conversation(
    session: AsyncSession, conversation_id: uuid.UUID, store_id: uuid.UUID
) -> Conversation | None:
    result: Conversation | None = await session.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.store_id == store_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result


async def _policy_authorized(session: AsyncSession, policy: ReceptionPolicy, store_id: uuid.UUID) -> bool:
    actor_id = policy.authorized_by or policy.created_by
    actor = await session.get(User, actor_id, populate_existing=True)
    if actor is None or actor.status != "active":
        return False
    for permission in ("marketing.manage", "marketing.view", "workspace.reply"):
        if store_id not in await _permission_store_ids(session, actor, permission):
            return False
    return True


async def _successful_reply_since(
    session: AsyncSession, state: ReceptionConversationState, since: datetime | None = None
) -> bool:
    since = since or state.unanswered_since
    if since is None:
        return False
    messages = (
        await session.scalars(
            select(Message).where(
                Message.store_id == state.store_id,
                Message.conversation_id == state.conversation_id,
                Message.direction == "outbound",
                Message.status.in_(("sent", "delivered")),
                Message.sent_at >= since,
            )
        )
    ).all()
    return any((message.raw_payload or {}).get("automation_source_kind") != "welcome" for message in messages)


async def _advance_delayed_timeout(
    session: AsyncSession, state: ReceptionConversationState, trigger: Message, policy: ReceptionPolicy | None
) -> list["AutomationDelivery"]:
    """只提前尚未领取的同一任务；已答或已开始投递的周期不得重建。"""
    from app.agents.automation.models import AutomationDelivery
    from app.agents.automation.service import payload_hash

    at = trigger.sent_at or trigger.created_at
    if (
        policy is None
        or state.unanswered_since is None
        or state.unanswered_message_id == trigger.id
        or at >= state.unanswered_since
        or state.timeout_policy_id != policy.id
        or state.timeout_policy_revision != policy.revision
        or await _successful_reply_since(session, state, at)
    ):
        return []
    row = await session.scalar(
        select(AutomationDelivery)
        .where(
            AutomationDelivery.store_id == state.store_id,
            AutomationDelivery.conversation_id == state.conversation_id,
            AutomationDelivery.source_kind == "timeout",
            AutomationDelivery.source_key == str(state.unanswered_message_id),
            AutomationDelivery.policy_revision == policy.revision,
            AutomationDelivery.mode == policy.delivery_mode,
            AutomationDelivery.status == "pending",
        )
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )
    if row is None or row.authorization_json.get("policy_id") != str(policy.id):
        return []
    content = reception_content(policy, trigger)
    if content is None:
        return []
    advance_inbound(state, trigger, idle_hours=policy.welcome_idle_hours)
    row.source_key = str(trigger.id)
    row.trigger_message_id = trigger.id
    row.not_before = at + timedelta(minutes=policy.timeout_minutes or 60)
    row.content = content
    row.payload_hash = payload_hash(
        store_id=row.store_id,
        conversation_id=row.conversation_id,
        content=row.content,
        message_type=row.message_type,
        card_order_id=row.card_order_id,
        card_package_id=row.card_package_id,
    )
    await session.flush()
    return [row]


async def on_reception_inbound(
    session: AsyncSession, conversation: Conversation, trigger: Message, settings: Settings
) -> list["AutomationDelivery"]:
    """调用方只传已验证并持久化的入站；与消息接收同事务，不提交。"""
    from app.agents.automation.service import enqueue_delivery

    if trigger.message_type not in {"text", "plain_text"}:
        # 展示占位不表达买家的语言或问题，等待真实文字后再建立接待计时器。
        return []
    locked = await _locked_conversation(session, conversation.id, conversation.store_id)
    if locked is None or locked.platform != "tiktok" or locked.status != "active":
        return []
    persisted = await session.scalar(
        select(Message).where(
            Message.id == trigger.id,
            Message.store_id == locked.store_id,
            Message.conversation_id == locked.id,
            Message.direction == "inbound",
            Message.role == "user",
            Message.status.in_(("received", "delivered")),
        )
    )
    if persisted is None:
        return []
    store = await session.get(Store, locked.store_id)
    if store is None or store.status != "active" or store.deleted_at is not None:
        return []
    state = await session.get(ReceptionConversationState, locked.id)
    if state is None:
        state = ReceptionConversationState(conversation_id=locked.id, store_id=locked.store_id)
        session.add(state)
    if await _successful_reply_since(session, state):
        state.unanswered_since = None
        state.unanswered_message_id = None
    policies = (
        await session.scalars(
            select(ReceptionPolicy)
            .join(ReceptionPolicyStore)
            .where(
                ReceptionPolicyStore.store_id == locked.store_id,
                ReceptionPolicy.enabled.is_(True),
                ReceptionPolicy.delivery_mode != "off",
            )
            .order_by(ReceptionPolicy.sort_order, ReceptionPolicy.id)
        )
    ).all()
    at = persisted.sent_at or persisted.created_at
    active = [
        policy
        for policy in policies
        if policy_active(policy, store.timezone, at)
        and (policy.delivery_mode != "auto" or settings.tiktok_automation_effective_enabled)
        and persisted.created_at > policy.updated_at
        and await _policy_authorized(session, policy, locked.store_id)
        and reception_content(policy, persisted) is not None
    ]
    timeout_policy = next((policy for policy in active if policy.kind == "timeout"), None)
    if state.last_activity_at is not None and at <= state.last_activity_at:
        return await _advance_delayed_timeout(session, state, persisted, timeout_policy)
    if not active:
        state.unanswered_since = None
        state.unanswered_message_id = None
        state.timeout_policy_id = None
        state.timeout_policy_revision = None
        return []
    # 关闭或改版后的旧计时器不重放；下一条可信入站从当前策略重新计时。
    if (
        timeout_policy is None
        or state.timeout_policy_id != timeout_policy.id
        or state.timeout_policy_revision != timeout_policy.revision
    ):
        state.unanswered_since = None
        state.unanswered_message_id = None
    idle = next((policy.welcome_idle_hours for policy in active if policy.kind == "welcome"), 24)
    new_segment = advance_inbound(state, persisted, idle_hours=idle)
    rows: list[AutomationDelivery] = []
    selected: set[str] = set()
    for policy in active:
        if policy.kind in selected or (policy.kind == "welcome" and not new_segment):
            continue
        if policy.kind == "timeout" and state.unanswered_message_id != persisted.id:
            continue
        content = reception_content(policy, persisted)
        if content is None:
            continue
        selected.add(policy.kind)
        source = state.segment_id if policy.kind == "welcome" else state.unanswered_message_id
        if source is None:
            continue
        not_before = (
            at
            if policy.kind == "welcome"
            else (
                state.unanswered_since + timedelta(minutes=policy.timeout_minutes or 60)
                if state.unanswered_since is not None
                else at
            )
        )
        rows.append(
            await enqueue_delivery(
                session,
                store_id=locked.store_id,
                conversation_id=locked.id,
                source_kind=policy.kind,
                source_key=str(source),
                content=content,
                authorized_by=policy.authorized_by or policy.created_by,
                policy_revision=policy.revision,
                mode=policy.delivery_mode,
                trigger_message_id=persisted.id,
                not_before=not_before,
                authorization_json={"policy_id": str(policy.id)},
            )
        )
        if policy.kind == "timeout":
            state.timeout_policy_id = policy.id
            state.timeout_policy_revision = policy.revision
    if timeout_policy is None:
        state.unanswered_since = None
        state.unanswered_message_id = None
        state.timeout_policy_id = None
        state.timeout_policy_revision = None
    await session.flush()
    return rows


async def on_reception_outbound(
    session: AsyncSession, conversation: Conversation, message: Message, *, source_kind: str | None = None
) -> None:
    """仅平台成功回复取消计时，欢迎语、已读、草稿或未知回执不取消。"""
    locked = await _locked_conversation(session, conversation.id, conversation.store_id)
    if (
        locked is None
        or message.store_id != locked.store_id
        or message.conversation_id != locked.id
        or message.direction != "outbound"
        or message.status not in {"sent", "delivered"}
    ):
        return
    state = await session.get(ReceptionConversationState, locked.id)
    if state is None:
        return
    at = message.sent_at or message.created_at
    if state.last_activity_at is None or at > state.last_activity_at:
        state.last_activity_at = at
    if (source_kind or (message.raw_payload or {}).get("automation_source_kind")) == "welcome":
        return
    if state.unanswered_since is not None and at >= state.unanswered_since:
        state.unanswered_since = None
        state.unanswered_message_id = None


async def authorize_reception_delivery(session: AsyncSession, row: "AutomationDelivery", settings: Settings) -> bool:
    """投递双开关与接待来源、当前权限均须保持有效；预演独立可用。"""
    if row.mode == "auto" and not settings.tiktok_automation_effective_enabled:
        return False
    if row.source_kind not in {"welcome", "timeout"}:
        return False
    locked = await _locked_conversation(session, row.conversation_id, row.store_id)
    if locked is None or locked.status != "active" or locked.platform != "tiktok":
        return False
    try:
        policy_id = uuid.UUID(str(row.authorization_json.get("policy_id")))
    except (ValueError, AttributeError):
        return False
    policy = await session.scalar(
        select(ReceptionPolicy)
        .join(ReceptionPolicyStore)
        .where(
            ReceptionPolicy.id == policy_id,
            ReceptionPolicyStore.store_id == row.store_id,
        )
        .with_for_update(of=ReceptionPolicy)
        .execution_options(populate_existing=True)
    )
    store = await session.get(Store, row.store_id, populate_existing=True)
    now = datetime.now(UTC)
    if (
        policy is None
        or store is None
        or store.status != "active"
        or store.deleted_at is not None
        or policy.kind != row.source_kind
        or policy.revision != row.policy_revision
        or policy.delivery_mode != row.mode
        or policy.delivery_mode not in {"preview", "auto"}
        or (policy.authorized_by or policy.created_by) != row.authorized_by
        or not policy_active(policy, store.timezone, now)
        or not await _policy_authorized(session, policy, row.store_id)
    ):
        return False
    state = await session.get(ReceptionConversationState, locked.id, populate_existing=True)
    trigger = await session.scalar(
        select(Message).where(
            Message.id == row.trigger_message_id,
            Message.store_id == row.store_id,
            Message.conversation_id == row.conversation_id,
            Message.direction == "inbound",
            Message.role == "user",
        )
    )
    if (
        state is None
        or state.store_id != row.store_id
        or trigger is None
        or str(trigger.id) != row.source_key
        or trigger.created_at <= policy.updated_at
        or reception_content(policy, trigger) != row.content
    ):
        return False
    if row.source_kind == "welcome":
        return str(state.segment_id) == row.source_key and not await _successful_reply_since(
            session, state, trigger.sent_at or trigger.created_at
        )
    if (
        state.unanswered_since is None
        or str(state.unanswered_message_id) != row.source_key
        or now < state.unanswered_since + timedelta(minutes=policy.timeout_minutes or 60)
    ):
        return False
    if await _successful_reply_since(session, state):
        state.unanswered_since = None
        state.unanswered_message_id = None
        return False
    return True


async def collect_due_reception_deliveries(
    session: AsyncSession, settings: Settings, now: datetime | None = None
) -> list["AutomationDelivery"]:
    """计时器在入站时入账，扫描仅返回已到期任务，绝不补发历史消息。"""
    from app.agents.automation.models import AutomationDelivery

    return list(
        (
            await session.scalars(
                select(AutomationDelivery)
                .where(
                    AutomationDelivery.source_kind.in_(("welcome", "timeout")),
                    AutomationDelivery.status == "pending",
                    AutomationDelivery.not_before <= (now or datetime.now(UTC)),
                )
                .order_by(AutomationDelivery.not_before, AutomationDelivery.id)
                .limit(100)
            )
        ).all()
    )
