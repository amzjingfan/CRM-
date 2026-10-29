"""通知策略与真实发送的二次授权；布尔命令不能代替持久事实。"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.config_models import AgentConfig
from app.agents.management.repository import PublishedAgent, get_published_agent
from app.agents.prompts.compiler import verify_published_prompt
from app.agents.tools.access import current_permissions
from app.conversations.models import Conversation
from app.customers.models import Customer
from app.integrations.tiktok_read import TikTokReadClient
from app.orders.models import Order
from app.shared.config.settings import Settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError
from app.stores.models import ChannelAccount, Store
from app.tools.contracts import SendPlatformMessageArguments, ToolInvocation

from .contracts import AuthorizationSnapshot, BoundLogisticsEvent
from .models import LogisticsNotification, LogisticsNotificationPolicy

NOTIFICATION_TOOL = "notify_logistics_update"
NOTIFICATION_PERMISSIONS = {"workspace.reply", "orders.view"}
NOTIFICATION_SCOPES = {"seller.order.info", "seller.customer_service", "seller.logistics"}


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def bound_agent(session: AsyncSession, store_id: uuid.UUID, agent_id: uuid.UUID | None) -> PublishedAgent | None:
    if agent_id is None:
        return None
    active = await session.scalar(
        select(AgentConfig.id).where(
            AgentConfig.id == agent_id,
            AgentConfig.store_id == store_id,
            AgentConfig.status == "enabled",
            AgentConfig.deleted_at.is_(None),
        )
    )
    if active is None:
        return None
    agent = await get_published_agent(session, store_id=store_id, config_id=agent_id)
    if agent is None or not agent.ready_for_v2 or NOTIFICATION_TOOL not in agent.tool_names or not agent.prompt_hash:
        return None
    verify_published_prompt(agent.prompt_sections, agent.prompt_hash)
    return agent


async def policy_authorizer(session: AsyncSession, policy: LogisticsNotificationPolicy) -> User | None:
    if policy.authorized_by is None:
        return None
    user = await session.get(User, policy.authorized_by)
    if user is None or user.status != "active":
        return None
    try:
        permissions = await current_permissions(session, user, policy.store_id)
    except AppError:
        return None
    return user if NOTIFICATION_PERMISSIONS.issubset(permissions) else None


async def verified_remote_window(
    session: AsyncSession,
    settings: Settings,
    conversation: Conversation,
) -> tuple[bool, bool, bool]:
    """官方 can_send_message 是窗口依据；未提供或身份不匹配一律关闭。"""
    customer = await session.scalar(
        select(Customer).where(
            Customer.id == conversation.customer_id,
            Customer.store_id == conversation.store_id,
            Customer.platform == "tiktok",
        )
    )
    channel = await session.scalar(
        select(ChannelAccount)
        .join(Store, Store.id == ChannelAccount.store_id)
        .where(
            ChannelAccount.store_id == conversation.store_id,
            ChannelAccount.platform == "tiktok",
            ChannelAccount.status == "connected",
            Store.status == "active",
            Store.deleted_at.is_(None),
        )
    )
    if customer is None or channel is None or not customer.external_customer_id:
        return False, False, False
    now = datetime.now(UTC)
    if channel.token_expires_at is None or utc(channel.token_expires_at) <= now:
        return False, False, False
    if channel.authorization_status in {"revoked", "deauthorized", "reauthorization_required"}:
        return False, False, False
    if channel.authorization_expires_at and utc(channel.authorization_expires_at) <= now:
        return False, False, False
    if channel.seller_authorization is not None and channel.seller_authorization.status != "connected":
        return False, False, False
    if not NOTIFICATION_SCOPES.issubset(set(channel.scopes)):
        return True, False, False
    remote = await TikTokReadClient(settings, channel).get_conversation(conversation.external_conversation_id)
    buyers = [item for item in remote.participants if item.role == "BUYER"]
    identity = (
        remote.id == conversation.external_conversation_id
        and len(buyers) == 1
        and buyers[0].im_user_id == customer.external_customer_id
        and bool(buyers[0].user_id)
    )
    return True, identity, bool(identity and remote.can_send_message)


async def authorize_event(
    session: AsyncSession,
    settings: Settings,
    context: BoundLogisticsEvent,
    *,
    expected_revision: int | None = None,
    require_external: bool = False,
) -> AuthorizationSnapshot:
    policy = await session.scalar(
        select(LogisticsNotificationPolicy)
        .where(
            LogisticsNotificationPolicy.store_id == context.scope.store_id,
        )
        .execution_options(populate_existing=True)
    )
    global_enabled = settings.logistics_notifications_enabled
    if require_external:
        global_enabled = global_enabled and settings.real_tiktok_logistics_notifications_enabled
    if not global_enabled or policy is None or not policy.enabled:
        return AuthorizationSnapshot(global_enabled=global_enabled)
    if expected_revision is not None and policy.revision != expected_revision:
        return AuthorizationSnapshot(global_enabled=True, store_enabled=False)
    if require_external and policy.mode != "external":
        return AuthorizationSnapshot(global_enabled=True, store_enabled=False)
    agent = await bound_agent(session, policy.store_id, policy.agent_id)
    user = await policy_authorizer(session, policy)
    order = await session.scalar(
        select(Order.id).where(
            Order.id == context.scope.order_id,
            Order.store_id == context.scope.store_id,
            Order.customer_id == context.scope.customer_id,
            Order.platform == "tiktok",
        )
    )
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == context.scope.conversation_id,
            Conversation.store_id == context.scope.store_id,
            Conversation.customer_id == context.scope.customer_id,
            Conversation.platform == "tiktok",
            Conversation.status != "closed",
        )
    )
    event_after_cutoff = policy.enabled_at is not None and utc(
        policy.enabled_at
    ) < context.event.occurred_at <= datetime.now(UTC)
    basic = {
        "global_enabled": True,
        "store_enabled": True,
        "tool_bound": agent is not None,
        "grant_active": user is not None,
        "identity_verified": order is not None and event_after_cutoff,
        "conversation_valid": conversation is not None,
    }
    if agent is None or user is None or order is None or conversation is None or not event_after_cutoff:
        return AuthorizationSnapshot(**basic)
    grant, identity, window = await verified_remote_window(session, settings, conversation)
    return AuthorizationSnapshot(
        **{**basic, "grant_active": grant, "identity_verified": identity},
        send_window_valid=window,
        scope_available=grant and identity,
    )


async def authorize_persisted_send(
    session: AsyncSession,
    settings: Settings,
    invocation: ToolInvocation,
    arguments: SendPlatformMessageArguments,
) -> bool:
    """仅服务端通知键可选此路；每次都从数据库核对正文、目标和现权。"""
    key = invocation.context.logistics_notification_key
    if (
        not key
        or invocation.context.actor_type not in {"job", "agent"}
        or invocation.context.human_confirmed
        or arguments.message_type != "text"
        or arguments.card_order_id
        or arguments.card_package_id
        or arguments.media_token
        or key != invocation.idempotency_key
    ):
        return False
    row = await session.scalar(
        select(LogisticsNotification)
        .where(
            LogisticsNotification.idempotency_key == key,
            LogisticsNotification.store_id == invocation.context.store_id,
        )
        .with_for_update()
    )
    if row is None or row.mode != "external" or row.state != "unknown" or row.reviewed_text != arguments.content:
        return False
    context = BoundLogisticsEvent.model_validate(row.context_json)
    if (
        context.idempotency_key != key
        or context.scope.store_id != invocation.context.store_id
        or context.scope.conversation_id != arguments.conversation_id
        or row.customer_id != context.scope.customer_id
        or row.order_id != context.scope.order_id
        or row.conversation_id != context.scope.conversation_id
    ):
        return False
    policy = await session.get(LogisticsNotificationPolicy, invocation.context.store_id)
    if policy is None or policy.authorized_by != invocation.context.actor_id:
        return False
    decision = await authorize_event(session, settings, context, require_external=True)
    return decision.blocking_reason is None
