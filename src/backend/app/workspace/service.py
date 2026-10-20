"""工作台会话、人工发送和状态流转服务。"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.errors import LLMProviderError
from app.agent.generation import StructuredGenerationService
from app.agent.providers.factory import build_provider
from app.agent.translation import TranslationService
from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids, ensure_store_access
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.integrations.tiktok_write import TIKTOK_TEXT_MAX_LENGTH, is_tiktok_send_target_allowed
from app.orders.models import Order
from app.shared.config.settings import get_settings
from app.shared.database.base import Permission, User, role_permissions, user_roles
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount, Store
from app.tools.contracts import ToolExecutionContext, ToolInvocation
from app.tools.executor import SqlAlchemyToolExecutor
from app.tools.models import ToolCall
from app.tools.repository import begin_tool_call, finish_tool_call
from app.workspace.repository import (
    find_conversation,
    find_order,
    list_conversations,
    list_messages,
    recent_orders,
)
from app.workspace.schemas import (
    AssigneeView,
    CustomerSummary,
    MessageTranslationView,
    MessageView,
    OrderSummary,
    PageMeta,
    SessionActionResult,
    SessionListData,
    SessionMessagesData,
    SessionSummary,
    TransferResult,
)


def _customer_view(customer: Customer) -> CustomerSummary:
    return CustomerSummary.model_validate(customer, from_attributes=True)


def _session_view(conversation: Conversation, customer: Customer, last: Message | None) -> SessionSummary:
    return SessionSummary(
        id=conversation.id,
        store_id=conversation.store_id,
        platform=conversation.platform,
        status=conversation.status,
        is_starred=conversation.is_starred,
        closed_at=conversation.closed_at,
        unread_count=conversation.unread_count,
        assigned_user_id=conversation.assigned_user_id,
        last_message_at=conversation.last_message_at,
        last_message=last.content if last else None,
        customer=_customer_view(customer),
    )


def _order_view(order: Order) -> OrderSummary:
    return OrderSummary.model_validate(order, from_attributes=True)


def _message_view(message: Message) -> MessageView:
    """转换消息并从低敏运行元数据中提取交付模式。"""
    delivery_mode: Literal["inbound", "mock", "real", "unknown"]
    if message.direction == "inbound":
        delivery_mode = "inbound"
    else:
        raw_mode = message.raw_payload.get("delivery_mode")
        if raw_mode == "mock":
            delivery_mode = "mock"
        elif raw_mode == "real":
            delivery_mode = "real"
        else:
            delivery_mode = "unknown"
    return MessageView(
        id=message.id,
        role=message.role,
        content=message.content,
        status=message.status,
        created_at=message.created_at,
        error_code=message.error_code,
        delivery_mode=delivery_mode,
    )


def _message_send_mode(
    conversation: Conversation, channel: ChannelAccount | None = None
) -> Literal["disabled", "mock", "real"]:
    """返回当前进程对指定平台的人工消息运行模式。"""
    settings = get_settings()
    if conversation.status == "closed":
        return "disabled"
    if conversation.platform == "tiktok" and settings.real_tiktok_message_write_enabled:
        if (
            channel is not None
            and channel.store_id == conversation.store_id
            and channel.status == "connected"
            and "seller.customer_service" in (channel.scopes or [])
            and isinstance((channel.metadata_json or {}).get("shop_cipher"), str)
            and bool((channel.metadata_json or {}).get("shop_cipher"))
            and (channel.token_expires_at is None or channel.token_expires_at > datetime.now(UTC))
            and is_tiktok_send_target_allowed(settings, conversation.store_id, conversation.external_conversation_id)
        ):
            return "real"
        return "disabled"
    if settings.allow_mock_platform_adapters:
        return "mock"
    return "disabled"


async def _connected_send_channel(session: AsyncSession, conversation: Conversation) -> ChannelAccount | None:
    """只使用活动店铺的匹配 TikTok 授权判断工作台与发送入口。"""
    if conversation.platform != "tiktok" or not get_settings().real_tiktok_message_write_enabled:
        return None
    channel: ChannelAccount | None = await session.scalar(
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
    return channel


async def get_session_list(
    session: AsyncSession,
    user: User,
    filter_name: str,
    platform: str | None,
    store_id: uuid.UUID | None,
    status: str | None,
    page: int,
    page_size: int,
) -> SessionListData:
    """查询租户隔离的会话列表。"""
    store_ids = await allowed_store_ids(session, user)
    if store_id and store_id not in store_ids:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    rows, total = await list_conversations(
        session, store_ids, user.id, filter_name, platform, store_id, status, page, page_size
    )
    return SessionListData(
        items=[_session_view(conversation, customer, message) for conversation, customer, message in rows],
        pagination=PageMeta(page=page, page_size=page_size, total=total),
    )


async def get_session_messages(
    session: AsyncSession, user: User, session_id: uuid.UUID, page: int, page_size: int
) -> SessionMessagesData:
    """查询会话详情，GET 不隐式修改未读数。"""
    conversation = await find_conversation(session, session_id, await allowed_store_ids(session, user))
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    customer = await session.get(Customer, conversation.customer_id)
    if customer is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "客户不存在", 404)
    messages, total = await list_messages(session, conversation.id, page, page_size)
    orders = await recent_orders(session, customer.id)
    last = await session.get(Message, conversation.last_message_id) if conversation.last_message_id else None
    return SessionMessagesData(
        session=_session_view(conversation, customer, last),
        messages=[_message_view(item) for item in messages],
        customer=_customer_view(customer),
        recent_orders=[_order_view(item) for item in orders],
        pagination=PageMeta(page=page, page_size=page_size, total=total),
        send_mode=_message_send_mode(conversation, await _connected_send_channel(session, conversation)),
        translation_enabled=(
            conversation.platform == "tiktok" and get_settings().workspace_message_translation_enabled
        ),
    )


async def translate_message(
    session: AsyncSession, user: User, session_id: uuid.UUID, message_id: uuid.UUID, trace_id: str
) -> MessageTranslationView:
    """按店铺和会话定位原文，只把脱敏后的单条文本送入现有翻译节点。"""
    settings = get_settings()
    if not settings.workspace_message_translation_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "消息翻译未启用", 503)
    conversation = await find_conversation(session, session_id, await allowed_store_ids(session, user))
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    if conversation.platform != "tiktok":
        raise AppError(ErrorCode.VALIDATION_ERROR, "仅支持 TikTok 消息翻译", 422)
    message = await session.scalar(
        select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conversation.id,
            Message.store_id == conversation.store_id,
        )
    )
    if message is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "消息不存在", 404)
    if message.message_type != "text" or not message.content.strip() or len(message.content) > 4000:
        raise AppError(ErrorCode.VALIDATION_ERROR, "仅支持翻译不超过 4000 字的文本消息", 422)
    try:
        provider = build_provider("deepseek", settings.llm_primary_model, settings)
        translator = TranslationService(StructuredGenerationService(provider, None, max_attempts=1))
        result = await translator.translate_bundle(
            trigger_message_id=message.id,
            message=message.content,
            draft_reply=None,
            target_language="zh-CN",
            trace_id=trace_id,
        )
    except (LLMProviderError, ValueError) as error:
        session.add(
            AuditLog(
                store_id=conversation.store_id,
                actor_type="user",
                actor_id=user.id,
                action="message.translate",
                resource_type="message",
                resource_id=message.id,
                request_id=trace_id,
                after_data={"target_language": "zh-CN"},
                result="failed",
            )
        )
        await session.commit()
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "翻译暂不可用，请稍后重试", 503) from error
    session.add(
        AuditLog(
            store_id=conversation.store_id,
            actor_type="user",
            actor_id=user.id,
            action="message.translate",
            resource_type="message",
            resource_id=message.id,
            request_id=trace_id,
            after_data={
                "target_language": "zh-CN",
                "provider": result.provider if result else "none",
                "model": result.model if result else "none",
                "input_tokens": result.input_tokens if result else 0,
                "output_tokens": result.output_tokens if result else 0,
            },
            result="succeeded" if result else "skipped",
        )
    )
    await session.commit()
    return MessageTranslationView(
        message_id=message.id,
        translated_text=result.message_translation if result else message.content,
    )


async def send_agent_message(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID,
    content: str,
    idempotency_key: str,
    *,
    confirmed: bool,
) -> MessageView:
    """把已人工确认的消息交给统一工具执行层并返回持久化终态。"""
    if not confirmed:
        raise AppError(ErrorCode.VALIDATION_ERROR, "发送前必须完成人工二次确认", 422)
    conversation = await find_conversation(session, session_id, await allowed_store_ids(session, user))
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    if conversation.status == "closed":
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "会话已关闭，请先重新打开", 409)
    send_mode = _message_send_mode(conversation, await _connected_send_channel(session, conversation))
    if conversation.platform == "tiktok" and get_settings().real_tiktok_message_write_enabled and send_mode != "real":
        raise AppError(ErrorCode.PERMISSION_DENIED, "当前会话不在真实消息发送范围内", 403)
    if send_mode == "real" and len(content) > TIKTOK_TEXT_MAX_LENGTH:
        raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 普通文本不能超过 2000 字符", 422)
    result = await SqlAlchemyToolExecutor(session).execute(
        ToolInvocation(
            tool_name="send_platform_message",
            idempotency_key=idempotency_key,
            arguments={"conversation_id": str(conversation.id), "content": content},
            context=ToolExecutionContext(
                store_id=conversation.store_id,
                actor_type="user",
                actor_id=user.id,
                permissions={"workspace.reply"},
                human_confirmed=True,
            ),
        )
    )
    if result.error_code == "TOOL_IDEMPOTENCY_CONFLICT":
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于不同请求或仍在执行", 409)
    if result.error_code == "TOOL_RECONCILIATION_REQUIRED":
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "当前店铺存在发送结果未知的消息，请先完成人工对账", 409)
    existing = await session.scalar(
        select(Message).where(
            Message.store_id == conversation.store_id,
            Message.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.content != content:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于不同消息", 409)
        return _message_view(existing)
    if result.error_code == "TOOL_RESOURCE_NOT_FOUND":
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    raise AppError(ErrorCode.THIRD_PARTY_ERROR, "消息发送未创建可追踪记录", 503)


async def reconcile_unknown_message(
    session: AsyncSession,
    user: User,
    message_id: uuid.UUID,
    resolution: Literal["sent", "failed"],
    external_message_id: str | None,
) -> MessageView:
    """按管理员已核对的平台事实关闭 unknown，并解除店铺发送熔断。"""
    store_ids = await allowed_store_ids(session, user)
    message = await session.scalar(
        select(Message).where(
            Message.id == message_id,
            Message.store_id.in_(store_ids),
            Message.direction == "outbound",
        )
    )
    if message is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "消息不存在", 404)
    if message.status != "unknown" or not message.idempotency_key:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "消息不处于待人工对账状态", 409)
    tool_call = await session.scalar(
        select(ToolCall).where(
            ToolCall.store_id == message.store_id,
            ToolCall.idempotency_key == message.idempotency_key,
            ToolCall.tool_name == "send_platform_message",
            ToolCall.status == "unknown",
        )
    )
    if tool_call is None:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "消息缺少待对账工具记录", 409)
    if external_message_id is not None:
        duplicate = await session.scalar(
            select(Message.id).where(
                Message.platform == message.platform,
                Message.external_message_id == external_message_id,
                Message.id != message.id,
            )
        )
        if duplicate is not None:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "平台消息 ID 已被其他消息使用", 409)

    previous_error = message.error_code
    message.status = resolution
    message.error_code = None if resolution == "sent" else "MANUALLY_CONFIRMED_FAILED"
    message.sent_at = datetime.now(UTC) if resolution == "sent" else None
    message.raw_payload = {"delivery_mode": "real", "reconciled": True}
    if external_message_id is not None:
        message.external_message_id = external_message_id
    tool_call.status = "succeeded" if resolution == "sent" else "failed"
    tool_call.error_code = message.error_code
    tool_call.output_summary = {
        "message_id": str(message.id),
        "status": resolution,
        "mocked": False,
    }
    session.add(
        AuditLog(
            store_id=message.store_id,
            actor_type="user",
            actor_id=user.id,
            action="message.reconcile",
            resource_type="message",
            resource_id=message.id,
            before_data={"status": "unknown", "error_code": previous_error},
            after_data={"status": resolution, "platform": message.platform},
            result="succeeded",
        )
    )
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "平台消息 ID 已被其他消息使用", 409) from error
    await session.refresh(message)
    return _message_view(message)


async def mark_read(session: AsyncSession, user: User, session_id: uuid.UUID) -> int:
    """显式清零会话未读数。"""
    conversation = await find_conversation(session, session_id, await allowed_store_ids(session, user))
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    conversation.unread_count = 0
    await session.commit()
    return 0


def _action_result(conversation: Conversation) -> SessionActionResult:
    return SessionActionResult(
        status=conversation.status,
        is_starred=conversation.is_starred,
        closed_at=conversation.closed_at,
    )


async def set_conversation_star(
    session: AsyncSession, actor: User, session_id: uuid.UUID, starred: bool
) -> SessionActionResult:
    """CRM 内部差评风险标记；重复设置同一状态不产生新审计。"""
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, actor), for_update=True
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    if conversation.is_starred != starred:
        conversation.is_starred = starred
        session.add(
            AuditLog(
                store_id=conversation.store_id,
                actor_type="user",
                actor_id=actor.id,
                action="conversation.star",
                resource_type="conversation",
                resource_id=conversation.id,
                after_data={"is_starred": starred},
                result="succeeded",
            )
        )
        await session.commit()
    return _action_result(conversation)


async def set_conversation_closed(
    session: AsyncSession, actor: User, session_id: uuid.UUID, closed: bool
) -> SessionActionResult:
    """本地关闭/重开；未结清出站消息时拒绝关闭。"""
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, actor), for_update=True
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    if closed and conversation.status != "closed":
        unresolved = await session.scalar(
            select(Message.id)
            .where(
                Message.store_id == conversation.store_id,
                Message.conversation_id == conversation.id,
                Message.direction == "outbound",
                Message.status.in_(("processing", "unknown")),
            )
            .limit(1)
        )
        if unresolved is not None:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "会话仍有待对账消息，暂不能关闭", 409)
        conversation.status = "closed"
        conversation.closed_at = datetime.now(UTC)
    elif not closed and conversation.status == "closed":
        conversation.status = "active"
        conversation.closed_at = None
    else:
        return _action_result(conversation)
    session.add(
        AuditLog(
            store_id=conversation.store_id,
            actor_type="user",
            actor_id=actor.id,
            action="conversation.close" if closed else "conversation.reopen",
            resource_type="conversation",
            resource_id=conversation.id,
            after_data={"status": conversation.status},
            result="succeeded",
        )
    )
    await session.commit()
    return _action_result(conversation)


async def list_session_assignees(session: AsyncSession, actor: User, session_id: uuid.UUID) -> list[AssigneeView]:
    """只展示当前会话所属店铺的可用坐席。"""
    conversation = await find_conversation(session, session_id, await allowed_store_ids(session, actor))
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    rows = (
        await session.execute(
            select(User.id, User.name)
            .join(user_roles, user_roles.c.user_id == User.id)
            .join(role_permissions, role_permissions.c.role_id == user_roles.c.role_id)
            .join(Permission, Permission.id == role_permissions.c.permission_id)
            .where(
                user_roles.c.store_id == conversation.store_id,
                User.status == "active",
                Permission.code == "workspace.reply",
            )
            .distinct()
            .order_by(User.name, User.id)
        )
    ).all()
    return [AssigneeView(id=user_id, name=name) for user_id, name in rows]


async def _assignee_can_reply(session: AsyncSession, store_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """转交目标必须在职、属于同店并有人工回复权限。"""
    assignment = await session.scalar(
        select(user_roles.c.id)
        .join(User, User.id == user_roles.c.user_id)
        .join(role_permissions, role_permissions.c.role_id == user_roles.c.role_id)
        .join(Permission, Permission.id == role_permissions.c.permission_id)
        .where(
            user_roles.c.user_id == user_id,
            user_roles.c.store_id == store_id,
            User.status == "active",
            Permission.code == "workspace.reply",
        )
        .limit(1)
    )
    return assignment is not None


async def assign_session(
    session: AsyncSession, actor: User, session_id: uuid.UUID, assignee_id: uuid.UUID
) -> Conversation:
    """分配前验证目标客服确实拥有该店铺角色。"""
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, actor), for_update=True
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    if conversation.status == "closed":
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "会话已关闭，请先重新打开", 409)
    if not await _assignee_can_reply(session, conversation.store_id, assignee_id):
        raise AppError(ErrorCode.VALIDATION_ERROR, "目标客服没有当前店铺回复权限", 422)
    conversation.assigned_user_id = assignee_id
    session.add(
        AuditLog(
            store_id=conversation.store_id,
            actor_type="user",
            actor_id=actor.id,
            action="conversation.assign",
            resource_type="conversation",
            resource_id=conversation.id,
            after_data={"assigned_user_id": str(assignee_id)},
            result="succeeded",
        )
    )
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def transfer_session(
    session: AsyncSession,
    actor: User,
    session_id: uuid.UUID,
    reason: str,
    assign_to: uuid.UUID | None,
    idempotency_key: str,
) -> TransferResult:
    """集中执行转人工状态流转并以审计 ID 作为 transfer_id。"""
    conversation = await find_conversation(session, session_id, await allowed_store_ids(session, actor))
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    if conversation.status == "closed":
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "会话已关闭，请先重新打开", 409)
    if assign_to and not await _assignee_can_reply(session, conversation.store_id, assign_to):
        raise AppError(ErrorCode.VALIDATION_ERROR, "目标客服没有当前店铺回复权限", 422)
    tool_call, replayed, started = await begin_tool_call(
        session,
        conversation.store_id,
        "user",
        actor.id,
        "transfer_to_human",
        idempotency_key,
        {"conversation_id": str(conversation.id), "reason": reason, "assign_to": str(assign_to) if assign_to else None},
        {"conversation_id": str(conversation.id), "has_assignee": assign_to is not None},
    )
    if replayed:
        transfer_id = (tool_call.output_summary or {}).get("transfer_id")
        if isinstance(transfer_id, str):
            return TransferResult(transfer_id=uuid.UUID(transfer_id), status="transferred")
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "转人工历史结果不可重放", 409)
    # begin_tool_call 会提交事务；重新加锁确认未被另一坐席同时关闭。
    await session.refresh(conversation, with_for_update=True)
    if conversation.status == "closed":
        await finish_tool_call(session, tool_call, started, "failed", None, False, "CONVERSATION_CLOSED")
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "会话已关闭，请先重新打开", 409)
    conversation.status = "transferred"
    conversation.transfer_reason = reason
    conversation.assigned_user_id = assign_to
    audit = AuditLog(
        store_id=conversation.store_id,
        actor_type="user",
        actor_id=actor.id,
        action="conversation.transfer",
        resource_type="conversation",
        resource_id=conversation.id,
        after_data={"assigned_user_id": str(assign_to) if assign_to else None},
        result="succeeded",
    )
    session.add(audit)
    await session.flush()
    await finish_tool_call(
        session,
        tool_call,
        started,
        "succeeded",
        {"transfer_id": str(audit.id), "status": "transferred"},
        False,
    )
    return TransferResult(transfer_id=audit.id, status="transferred")


async def get_order(session: AsyncSession, user: User, order_id: str) -> OrderSummary:
    """按内部或平台订单号查询租户内订单。"""
    order = await find_order(session, order_id, await allowed_store_ids(session, user))
    if order is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "订单不存在", 404)
    await ensure_store_access(session, user, order.store_id)
    return _order_view(order)
