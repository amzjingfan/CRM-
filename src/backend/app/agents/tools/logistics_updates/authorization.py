"""通知策略与真实发送的二次授权；布尔命令不能代替持久事实。"""

import uuid
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.config_models import AgentConfig
from app.agents.management.models import AgentConfigVersion
from app.agents.management.repository import PublishedAgent, get_published_agent
from app.agents.prompts.compiler import verify_published_prompt
from app.agents.tools.access import current_permissions
from app.conversations.models import Conversation
from app.customers.models import Customer
from app.integrations.tiktok_read import TikTokReadClient
from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileVersion
from app.orders.models import Order
from app.shared.config.settings import Settings
from app.shared.database.base import Permission, Role, User, role_permissions, user_roles
from app.shared.exceptions.errors import AppError
from app.stores.models import ChannelAccount, Store, TikTokSellerAuthorization
from app.tools.contracts import SendPlatformMessageArguments, ToolInvocation
from app.users.models import department_members, department_stores

from .contracts import AuthorizationSnapshot, BoundLogisticsEvent
from .models import LogisticsNotification, LogisticsNotificationPolicy
from .proof import NotificationAuthorization, text_sha256

NOTIFICATION_TOOL = "notify_logistics_update"
NOTIFICATION_PERMISSIONS = {"workspace.reply", "orders.view"}
NOTIFICATION_SCOPES = {"seller.order.info", "seller.customer_service", "seller.logistics"}


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def bound_agent(session: AsyncSession, store_id: uuid.UUID, agent_id: uuid.UUID | None) -> PublishedAgent | None:
    if agent_id is None:
        return None
    active = await session.scalar(
        select(AgentConfig)
        .where(
            AgentConfig.id == agent_id,
            AgentConfig.store_id == store_id,
            AgentConfig.status == "enabled",
            AgentConfig.deleted_at.is_(None),
        )
        .execution_options(populate_existing=True)
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
    user = await session.get(User, policy.authorized_by, populate_existing=True)
    if user is None or user.status != "active":
        return None
    try:
        permissions = await current_permissions(session, user, policy.store_id)
    except AppError:
        return None
    return user if NOTIFICATION_PERMISSIONS.issubset(permissions) else None


async def _window_source(session: AsyncSession, conversation: Conversation) -> tuple[Customer, ChannelAccount] | None:
    customer = await session.scalar(
        select(Customer)
        .where(
            Customer.id == conversation.customer_id,
            Customer.store_id == conversation.store_id,
            Customer.platform == "tiktok",
        )
        .execution_options(populate_existing=True)
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
        .execution_options(populate_existing=True)
    )
    if customer is None or channel is None or not customer.external_customer_id:
        return None
    now = datetime.now(UTC)
    if channel.token_expires_at is None or utc(channel.token_expires_at) <= now:
        return None
    if channel.authorization_status in {"revoked", "deauthorized", "reauthorization_required"}:
        return None
    if channel.authorization_expires_at and utc(channel.authorization_expires_at) <= now:
        return None
    if channel.seller_authorization is not None and channel.seller_authorization.status != "connected":
        return None
    if not NOTIFICATION_SCOPES.issubset(set(channel.scopes)):
        return None
    return customer, channel


async def verified_remote_window(
    session: AsyncSession,
    settings: Settings,
    conversation: Conversation,
) -> tuple[bool, bool, bool]:
    """官方 can_send_message 是窗口依据；未提供或身份不匹配一律关闭。"""
    source = await _window_source(session, conversation)
    if source is None:
        return False, False, False
    customer, channel = source
    remote = await TikTokReadClient(settings, channel).get_conversation(conversation.external_conversation_id)
    buyers = [item for item in remote.participants if item.role == "BUYER"]
    identity = (
        remote.id == conversation.external_conversation_id
        and len(buyers) == 1
        and buyers[0].im_user_id == customer.external_customer_id
        and bool(buyers[0].user_id)
    )
    return True, identity, bool(identity and remote.can_send_message)


async def _target_identity(session: AsyncSession, context: BoundLogisticsEvent) -> tuple[object, ...] | None:
    row = (
        await session.execute(
            select(
                Conversation.external_conversation_id,
                Customer.external_customer_id,
                ChannelAccount.id,
                ChannelAccount.external_store_id,
                ChannelAccount.seller_authorization_id,
            )
            .join(Customer, Customer.id == Conversation.customer_id)
            .join(ChannelAccount, ChannelAccount.store_id == Conversation.store_id)
            .where(
                Conversation.id == context.scope.conversation_id,
                Conversation.store_id == context.scope.store_id,
                Customer.id == context.scope.customer_id,
                Customer.store_id == context.scope.store_id,
                ChannelAccount.platform == "tiktok",
                ChannelAccount.status == "connected",
            )
        )
    ).first()
    return tuple(row) if row else None


async def authorize_event(
    session: AsyncSession,
    settings: Settings,
    context: BoundLogisticsEvent,
    *,
    expected_revision: int | None = None,
    require_external: bool = False,
    verify_remote: bool = True,
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
        global_enabled = (
            global_enabled
            and settings.real_tiktok_logistics_notifications_enabled
            and settings.tiktok_automation_effective_enabled
        )
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
        select(Conversation)
        .where(
            Conversation.id == context.scope.conversation_id,
            Conversation.store_id == context.scope.store_id,
            Conversation.customer_id == context.scope.customer_id,
            Conversation.platform == "tiktok",
            Conversation.status != "closed",
        )
        .execution_options(populate_existing=True)
    )
    conversation_valid = conversation is not None and not (
        require_external and bool((conversation.metadata_json or {}).get("automation_paused"))
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
        "conversation_valid": conversation_valid,
    }
    if agent is None or user is None or order is None or not conversation_valid or not event_after_cutoff:
        return AuthorizationSnapshot(**basic)
    assert conversation is not None
    if not verify_remote:
        return AuthorizationSnapshot(**basic, send_window_valid=True, scope_available=True)
    original_revision, original_actor = policy.revision, policy.authorized_by
    original_target = await _target_identity(session, context)
    grant, identity, window = await verified_remote_window(session, settings, conversation)
    # 远端等待后不能复用等待前的 ORM/授权快照；最后发送边界还会持锁核对完整复核证明。
    current = await authorize_event(
        session,
        settings,
        context,
        expected_revision=original_revision,
        require_external=require_external,
        verify_remote=False,
    )
    if (
        current.blocking_reason is not None
        or not (grant and identity and window)
        or policy.authorized_by != original_actor
        or await bound_agent(session, context.scope.store_id, policy.agent_id) != agent
        or original_target is None
        or await _target_identity(session, context) != original_target
    ):
        return current.model_copy(update={"scope_available": False})
    return current


async def _lock_authority(
    session: AsyncSession, context: BoundLogisticsEvent, proof: NotificationAuthorization
) -> None:
    """同一事务持有所有正向授权依据，DELETE/UPDATE 撤权需等适配器结果提交。"""
    await session.execute(select(Store).where(Store.id == context.scope.store_id).with_for_update())
    await session.execute(
        select(Conversation).where(Conversation.id == context.scope.conversation_id).with_for_update()
    )
    await session.execute(select(Customer).where(Customer.id == context.scope.customer_id).with_for_update())
    await session.execute(select(Order).where(Order.id == context.scope.order_id).with_for_update())
    await session.execute(
        select(LogisticsNotificationPolicy)
        .where(LogisticsNotificationPolicy.store_id == context.scope.store_id)
        .with_for_update()
    )
    await session.get(User, proof.authorized_by, populate_existing=True, with_for_update=True)
    roles = select(user_roles.c.role_id).where(user_roles.c.user_id == proof.authorized_by)
    await session.execute(
        select(user_roles)
        .where(user_roles.c.user_id == proof.authorized_by)
        .order_by(user_roles.c.id)
        .with_for_update()
    )
    await session.execute(select(Role.id).where(Role.id.in_(roles)).order_by(Role.id).with_for_update())
    await session.execute(
        select(role_permissions)
        .where(role_permissions.c.role_id.in_(roles))
        .order_by(role_permissions.c.role_id, role_permissions.c.permission_id)
        .with_for_update()
    )
    await session.execute(
        select(Permission.id)
        .where(Permission.id.in_(select(role_permissions.c.permission_id).where(role_permissions.c.role_id.in_(roles))))
        .order_by(Permission.id)
        .with_for_update()
    )
    departments = select(department_members.c.department_id).where(department_members.c.user_id == proof.authorized_by)
    await session.execute(
        select(department_members)
        .where(department_members.c.user_id == proof.authorized_by)
        .order_by(department_members.c.department_id)
        .with_for_update()
    )
    await session.execute(
        select(department_stores)
        .where(department_stores.c.department_id.in_(departments))
        .order_by(department_stores.c.department_id, department_stores.c.store_id)
        .with_for_update()
    )
    await session.execute(select(AgentConfig).where(AgentConfig.id == proof.agent_id).with_for_update())
    await session.execute(
        select(AgentConfigVersion)
        .where(AgentConfigVersion.agent_config_id == proof.agent_id, AgentConfigVersion.version == proof.agent_version)
        .with_for_update()
    )
    await session.execute(
        select(ChannelAccount)
        .where(ChannelAccount.store_id == context.scope.store_id, ChannelAccount.platform == "tiktok")
        .with_for_update()
    )
    await session.execute(
        select(TikTokSellerAuthorization)
        .where(
            TikTokSellerAuthorization.id.in_(
                select(ChannelAccount.seller_authorization_id).where(
                    ChannelAccount.store_id == context.scope.store_id, ChannelAccount.platform == "tiktok"
                )
            )
        )
        .with_for_update()
    )
    for reference in sorted(proof.file_versions, key=lambda item: str(item.file_id)):
        await session.execute(select(KnowledgeFile).where(KnowledgeFile.id == reference.file_id).with_for_update())
        await session.execute(
            select(KnowledgeFileVersion).where(KnowledgeFileVersion.id == reference.version_id).with_for_update()
        )


async def _current_proof(session: AsyncSession, context: BoundLogisticsEvent, proof: NotificationAuthorization) -> bool:
    policy = await session.get(LogisticsNotificationPolicy, context.scope.store_id, populate_existing=True)
    if (
        policy is None
        or policy.revision != proof.policy_revision
        or policy.authorized_by != proof.authorized_by
        or policy.agent_id != proof.agent_id
    ):
        return False
    agent = await bound_agent(session, context.scope.store_id, proof.agent_id)
    if agent is None or agent.config_version != proof.agent_version or agent.prompt_hash != proof.prompt_hash:
        return False
    try:
        permissions = await current_permissions(session, User(id=proof.authorized_by), context.scope.store_id)
    except AppError:
        return False
    if not NOTIFICATION_PERMISSIONS <= proof.required_permissions <= permissions:
        return False
    for reference in proof.file_versions:
        if str(reference.file_id) not in agent.file_ids:
            return False
        valid = await session.scalar(
            select(KnowledgeFileVersion.id)
            .join(KnowledgeFile, KnowledgeFile.id == KnowledgeFileVersion.file_id)
            .where(
                KnowledgeFile.id == reference.file_id,
                KnowledgeFile.store_id == context.scope.store_id,
                KnowledgeFile.active_version_number == reference.version_number,
                KnowledgeFile.archived_at.is_(None),
                KnowledgeFile.deleted_at.is_(None),
                KnowledgeFileVersion.id == reference.version_id,
                KnowledgeFileVersion.store_id == context.scope.store_id,
                KnowledgeFileVersion.version_number == reference.version_number,
                KnowledgeFileVersion.status == "ready",
                KnowledgeFileVersion.publication_approval == "approved_for_public_reply",
                KnowledgeFileVersion.approved_by.is_not(None),
                KnowledgeFileVersion.approved_at.is_not(None),
            )
        )
        if valid is None:
            return False
    return True


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
        .execution_options(populate_existing=True)
    )
    if row is None or row.mode != "external" or row.state != "unknown" or row.reviewed_text != arguments.content:
        return False
    try:
        proof = NotificationAuthorization.model_validate(row.authorization_json)
    except ValidationError:
        return False
    if (
        proof.event_key != key
        or proof.text_sha256 != text_sha256(arguments.content)
        or proof.authorized_by != invocation.context.actor_id
    ):
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
    target = await _target_identity(session, context)
    decision = await authorize_event(
        session, settings, context, expected_revision=proof.policy_revision, require_external=True
    )
    if decision.blocking_reason is not None:
        return False
    await _lock_authority(session, context, proof)
    current = await authorize_event(
        session, settings, context, expected_revision=proof.policy_revision, require_external=True, verify_remote=False
    )
    conversation = await session.get(Conversation, context.scope.conversation_id, populate_existing=True)
    return (
        current.blocking_reason is None
        and conversation is not None
        and target is not None
        and await _target_identity(session, context) == target
        and await _window_source(session, conversation) is not None
        and await _current_proof(session, context, proof)
    )
