"""工作台会话、人工发送和状态流转服务。"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.draft_translation import DraftTargetLanguage, DraftTranslationService
from app.agents.core.errors import LLMProviderError
from app.agents.core.generation import StructuredGenerationService
from app.agents.core.providers.factory import build_provider
from app.agents.core.security import sanitize_prompt_text
from app.agents.core.translation import TranslationBundleResult, TranslationService
from app.audit.models import AuditLog
from app.auth.store_access import (
    allowed_store_ids,
    ensure_conversation_access,
    ensure_store_access,
    supervised_store_ids,
)
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.integrations.tiktok_write import TIKTOK_TEXT_MAX_LENGTH, is_tiktok_send_target_allowed
from app.orders.models import Order
from app.reception_assignment.models import ReceptionStoreConfig
from app.shared.config.settings import get_settings
from app.shared.database.base import Permission, User, role_permissions, user_roles
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount, Store
from app.tools.contracts import ToolExecutionContext, ToolInvocation
from app.tools.executor import SqlAlchemyToolExecutor
from app.tools.models import ToolCall
from app.tools.repository import begin_tool_call, finish_tool_call
from app.users.models import department_members
from app.workspace.delivery_errors import DeliveryNotStarted
from app.workspace.logistics_preview import (
    LogisticsCardPreview,
    logistics_card_snapshot,
    standard_tracking_package,
)
from app.workspace.repository import (
    find_conversation,
    find_order,
    list_conversations,
    list_messages,
    recent_orders,
    unread_message_total,
)
from app.workspace.schemas import (
    AssigneeView,
    AssignmentEventView,
    CustomerSummary,
    DraftTranslationView,
    LogisticsCardView,
    MediaMessageView,
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
from app.workspace.sidebar import (
    SidebarTrackingEventTranslation,
    SidebarTrackingPackage,
    SidebarTrackingTimelineTranslation,
    SidebarTrackingTranslation,
    _verified_sidebar_order,
    get_sidebar_enhanced_tracking,
    get_sidebar_order_detail,
)


def _customer_view(customer: Customer) -> CustomerSummary:
    data = CustomerSummary.model_validate(customer, from_attributes=True)
    override = (customer.metadata_json or {}).get("buyer_stage_override")
    return data.model_copy(
        update={"buyer_stage_override": override if override in ("pre", "during", "after") else None}
    )


async def _assert_conversation_visibility(session: AsyncSession, actor: User, conversation: Conversation) -> None:
    await ensure_conversation_access(session, actor, conversation)


async def _assert_conversation_owner(session: AsyncSession, actor: User, conversation: Conversation) -> None:
    await ensure_conversation_access(session, actor, conversation, owner_required=True)


async def set_buyer_stage_override(
    session: AsyncSession, actor: User, session_id: uuid.UUID, stage: Literal["pre", "during", "after"] | None
) -> CustomerSummary:
    """会话鉴权后更新同店买家画像，只记录阶段，不保存订单内容。"""
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, actor, "workspace.reply")
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    await _assert_conversation_owner(session, actor, conversation)
    customer = await session.scalar(
        select(Customer)
        .where(Customer.id == conversation.customer_id, Customer.store_id == conversation.store_id)
        .with_for_update()
    )
    if customer is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "客户不存在", 404)
    before = (customer.metadata_json or {}).get("buyer_stage_override")
    metadata = dict(customer.metadata_json or {})
    if stage is None:
        metadata.pop("buyer_stage_override", None)
    else:
        metadata["buyer_stage_override"] = stage
    if before != stage:
        customer.metadata_json = metadata
        session.add(
            AuditLog(
                store_id=conversation.store_id,
                actor_type="user",
                actor_id=actor.id,
                action="customer.buyer_stage_override",
                resource_type="customer",
                resource_id=customer.id,
                after_data={"stage": stage},
                result="succeeded",
            )
        )
        await session.commit()
    return _customer_view(customer)


def _session_view(
    conversation: Conversation,
    customer: Customer,
    last: Message | None,
    *,
    can_manage: bool = False,
    can_claim: bool = False,
    needs_takeover: bool = False,
) -> SessionSummary:
    return SessionSummary(
        id=conversation.id,
        store_id=conversation.store_id,
        platform=conversation.platform,
        status=conversation.status,
        is_starred=conversation.is_starred,
        closed_at=conversation.closed_at,
        unread_count=conversation.unread_count,
        assigned_user_id=conversation.assigned_user_id,
        can_manage=can_manage,
        can_claim=can_claim,
        needs_takeover=needs_takeover,
        last_message_at=conversation.last_message_at,
        last_message=last.content if last else None,
        customer=_customer_view(customer),
    )


def _assignment_event_view(item: AuditLog) -> AssignmentEventView:
    """仅将审计中的低敏派单字段投影到主管可见记录。"""
    data = item.after_data or {}
    raw_user_id = data.get("assigned_user_id")
    try:
        assigned_user_id = uuid.UUID(raw_user_id) if isinstance(raw_user_id, str) else None
    except ValueError:
        assigned_user_id = None
    reason = data.get("reason")
    return AssignmentEventView(
        action=item.action,
        actor_type=item.actor_type,
        assigned_user_id=assigned_user_id,
        reason=reason if isinstance(reason, str) else None,
        created_at=item.created_at,
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
    card_data = message.raw_payload.get("logistics_card")
    card = (
        LogisticsCardView.model_validate(card_data)
        if message.message_type == "logistics_card" and isinstance(card_data, dict)
        else None
    )
    media_data = message.raw_payload.get("media")
    media = (
        MediaMessageView.model_validate(media_data)
        if message.message_type in {"image", "video"} and isinstance(media_data, dict)
        else None
    )
    return MessageView(
        id=message.id,
        role=message.role,
        content=message.content,
        status=message.status,
        created_at=message.created_at,
        error_code=message.error_code,
        delivery_mode=delivery_mode,
        message_type=message.message_type or "text",
        logistics_card=card,
        media=media,
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
    search_scope: Literal["all", "buyer", "order", "tracking", "product"] = "all",
    search: str | None = None,
    terms: list[str] | None = None,
) -> SessionListData:
    """查询租户隔离的会话列表。"""
    if search_scope not in {"all", "buyer", "order", "tracking", "product"}:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不支持的搜索范围", 422)
    if search is not None and terms:
        raise AppError(ErrorCode.VALIDATION_ERROR, "单项搜索和批量搜索不能同时使用", 422)
    raw_terms = terms if terms else ([search] if search is not None else [])
    if len(raw_terms) > 20 or any(not item.strip() or len(item.strip()) > 120 for item in raw_terms):
        raise AppError(ErrorCode.VALIDATION_ERROR, "搜索最多 20 项且每项为 1～120 个字符", 422)
    search_terms = tuple(dict.fromkeys(item.strip() for item in raw_terms))
    store_ids = await allowed_store_ids(session, user, "workspace.view")
    supervisors = await supervised_store_ids(session, user)
    transfer_stores = await allowed_store_ids(session, user, "workspace.transfer")
    reply_stores = await allowed_store_ids(session, user, "workspace.reply")
    if store_id and store_id not in store_ids:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    rows, total = await list_conversations(
        session,
        store_ids,
        user.id,
        filter_name,
        platform,
        store_id,
        status,
        page,
        page_size,
        search_scope,
        search_terms,
        supervised_store_ids=supervisors,
    )
    return SessionListData(
        items=[
            _session_view(
                conversation,
                customer,
                message,
                can_manage=conversation.store_id in transfer_stores
                and (conversation.assigned_user_id == user.id or conversation.store_id in supervisors),
                can_claim=conversation.store_id in transfer_stores
                and conversation.store_id in reply_stores
                and conversation.assigned_user_id is None
                and conversation.status != "closed",
            )
            for conversation, customer, message in rows
        ],
        pagination=PageMeta(page=page, page_size=page_size, total=total),
        unread_messages_total=await unread_message_total(
            session, store_ids, user_id=user.id, supervised_store_ids=supervisors
        ),
    )


async def get_session_messages(
    session: AsyncSession, user: User, session_id: uuid.UUID, page: int, page_size: int
) -> SessionMessagesData:
    """查询会话详情，GET 不隐式修改未读数。"""
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, user, "workspace.view")
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    await _assert_conversation_visibility(session, user, conversation)
    customer = await session.get(Customer, conversation.customer_id)
    if customer is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "客户不存在", 404)
    messages, total = await list_messages(session, conversation.id, page, page_size)
    orders = await recent_orders(session, customer.id)
    last = await session.get(Message, conversation.last_message_id) if conversation.last_message_id else None
    supervisors = await supervised_store_ids(session, user)
    reply_stores = await allowed_store_ids(session, user, "workspace.reply")
    transfer_stores = await allowed_store_ids(session, user, "workspace.transfer")
    may_reply = conversation.store_id in reply_stores and (
        conversation.assigned_user_id == user.id or conversation.store_id in supervisors
    )
    may_manage = conversation.store_id in transfer_stores and (
        conversation.assigned_user_id == user.id or conversation.store_id in supervisors
    )
    needs_takeover = False
    assignment_events: list[AssignmentEventView] = []
    if conversation.store_id in supervisors:
        if conversation.assignment_source == "manual" and conversation.assigned_user_id is not None:
            needs_takeover = not await _assignee_can_reply(
                session, conversation.store_id, conversation.assigned_user_id
            )
            config = await session.get(ReceptionStoreConfig, conversation.store_id)
            if not needs_takeover and config is not None:
                member = await session.scalar(
                    select(department_members.c.user_id).where(
                        department_members.c.department_id == config.department_id,
                        department_members.c.user_id == conversation.assigned_user_id,
                    )
                )
                needs_takeover = member is None
        records = (
            await session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.store_id == conversation.store_id,
                    AuditLog.resource_type == "conversation",
                    AuditLog.resource_id == conversation.id,
                    AuditLog.action.in_(
                        [
                            "conversation.assign.auto",
                            "conversation.assign.auto_requeue",
                            "conversation.assign",
                            "conversation.transfer",
                        ]
                    ),
                )
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .limit(20)
            )
        ).all()
        assignment_events = [_assignment_event_view(item) for item in records]
    send_mode = (
        _message_send_mode(conversation, await _connected_send_channel(session, conversation))
        if may_reply
        else "disabled"
    )
    return SessionMessagesData(
        session=_session_view(
            conversation,
            customer,
            last,
            can_manage=may_manage,
            can_claim=conversation.store_id in transfer_stores
            and conversation.store_id in reply_stores
            and conversation.assigned_user_id is None
            and conversation.status != "closed",
            needs_takeover=needs_takeover,
        ),
        messages=[_message_view(item) for item in messages],
        customer=_customer_view(customer),
        recent_orders=[_order_view(item) for item in orders],
        assignment_events=assignment_events,
        pagination=PageMeta(page=page, page_size=page_size, total=total),
        send_mode=send_mode,
        translation_enabled=(
            conversation.platform == "tiktok" and get_settings().workspace_message_translation_enabled
        ),
        draft_translation_enabled=(
            conversation.platform == "tiktok"
            and send_mode != "disabled"
            and get_settings().workspace_message_translation_enabled
        ),
    )


async def translate_draft(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID,
    source_text: str,
    target_language: DraftTargetLanguage,
    trace_id: str,
) -> DraftTranslationView:
    """仅预览已授权会话的低敏草稿译文，不改变草稿或发送平台消息。"""
    settings = get_settings()
    if not settings.workspace_message_translation_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "草稿翻译未启用", 503)
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, user, "workspace.reply")
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    await _assert_conversation_owner(session, user, conversation)
    if conversation.platform != "tiktok" or conversation.status == "closed":
        raise AppError(ErrorCode.VALIDATION_ERROR, "该会话不能预览回复译文", 422)
    if _message_send_mode(conversation, await _connected_send_channel(session, conversation)) == "disabled":
        raise AppError(ErrorCode.PERMISSION_DENIED, "当前会话不在消息发送范围内", 403)
    if not source_text.strip() or len(source_text) > TIKTOK_TEXT_MAX_LENGTH:
        raise AppError(ErrorCode.VALIDATION_ERROR, "草稿必须为 1～2000 字符", 422)
    if sanitize_prompt_text(source_text) != source_text:
        raise AppError(ErrorCode.VALIDATION_ERROR, "草稿含需脱敏内容，请先修改后再翻译", 422)
    try:
        provider = build_provider("deepseek", settings.llm_primary_model, settings)
        translator = DraftTranslationService(StructuredGenerationService(provider, None, max_attempts=1))
        result = await translator.translate(source_text=source_text, target_language=target_language, trace_id=trace_id)
        if sanitize_prompt_text(result.translated_text) != result.translated_text:
            raise ValueError("译文包含需脱敏内容")
    except (LLMProviderError, ValueError) as error:
        session.add(
            AuditLog(
                store_id=conversation.store_id,
                actor_type="user",
                actor_id=user.id,
                action="draft.translate",
                resource_type="conversation",
                resource_id=conversation.id,
                request_id=trace_id,
                after_data={"target_language": target_language},
                result="failed",
            )
        )
        await session.commit()
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "草稿翻译暂不可用，请人工核对后重试", 503) from error
    session.add(
        AuditLog(
            store_id=conversation.store_id,
            actor_type="user",
            actor_id=user.id,
            action="draft.translate",
            resource_type="conversation",
            resource_id=conversation.id,
            request_id=trace_id,
            after_data={
                "target_language": target_language,
                "provider": result.provider,
                "model": result.model,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
            result="succeeded",
        )
    )
    await session.commit()
    return DraftTranslationView(
        source_text_sha256=result.source_text_sha256,
        target_language=result.target_language,
        translated_text=result.translated_text,
    )


async def translate_message(
    session: AsyncSession, user: User, session_id: uuid.UUID, message_id: uuid.UUID, trace_id: str
) -> MessageTranslationView:
    """按店铺和会话定位原文，只把脱敏后的单条文本送入现有翻译节点。"""
    settings = get_settings()
    if not settings.workspace_message_translation_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "消息翻译未启用", 503)
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, user, "workspace.view")
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    await _assert_conversation_visibility(session, user, conversation)
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


async def translate_sidebar_tracking(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID,
    order_id: str,
    trace_id: str,
    event_description: str | None = None,
    event_at: datetime | None = None,
    event_tracking_number: str | None = None,
    enhanced: bool = False,
) -> SidebarTrackingTranslation:
    """只翻译经会话买家核对的物流节点原文，不写入订单或发送消息。"""
    settings = get_settings()
    if not settings.workspace_message_translation_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "物流描述翻译未启用", 503)
    detail = await get_sidebar_order_detail(session, user, session_id, order_id)
    source = detail.latest_tracking_description
    if event_description is not None:
        if event_at is None:
            raise AppError(ErrorCode.VALIDATION_ERROR, "物流节点时间缺失", 422)
        packages = (
            (await get_sidebar_enhanced_tracking(session, user, session_id, order_id)).packages
            if enhanced
            else detail.tracking_packages
        )
        if not any(
            event.description == event_description
            and event.occurred_at == event_at
            and event.tracking_number == event_tracking_number
            for package in packages
            for event in package.events
        ):
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "物流节点不存在", 404)
        source = event_description
    if not source or not source.strip() or len(source) > 4000:
        raise AppError(ErrorCode.VALIDATION_ERROR, "暂无可翻译的物流描述", 422)
    if sanitize_prompt_text(source) != source:
        raise AppError(ErrorCode.VALIDATION_ERROR, "物流描述含需脱敏内容，无法翻译", 422)
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, user, "workspace.view")
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    await _assert_conversation_visibility(session, user, conversation)
    try:
        provider = build_provider("deepseek", settings.llm_primary_model, settings)
        translator = TranslationService(StructuredGenerationService(provider, None, max_attempts=1))
        result = await translator.translate_bundle(
            trigger_message_id=uuid.uuid5(uuid.NAMESPACE_URL, f"tiktok:tracking:{order_id}"),
            message=source,
            draft_reply=None,
            target_language="zh-CN",
            trace_id=trace_id,
        )
        translated = result.message_translation if result else source
        if sanitize_prompt_text(translated) != translated:
            raise ValueError("译文包含需脱敏内容")
    except (LLMProviderError, ValueError) as error:
        session.add(
            AuditLog(
                store_id=conversation.store_id,
                actor_type="user",
                actor_id=user.id,
                action="sidebar.tracking.translate",
                resource_type="conversation",
                resource_id=conversation.id,
                request_id=trace_id,
                after_data={"target_language": "zh-CN"},
                result="failed",
            )
        )
        await session.commit()
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "物流描述翻译暂不可用，请稍后重试", 503) from error
    session.add(
        AuditLog(
            store_id=conversation.store_id,
            actor_type="user",
            actor_id=user.id,
            action="sidebar.tracking.translate",
            resource_type="conversation",
            resource_id=conversation.id,
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
    return SidebarTrackingTranslation(source_description=source, translated_text=translated)


async def translate_sidebar_tracking_timeline(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID,
    order_id: str,
    trace_id: str,
    *,
    enhanced: bool = False,
) -> SidebarTrackingTimelineTranslation:
    """一次坐席操作翻译核对后的全部物流节点；模型并发有界且结果不持久化。"""
    settings = get_settings()
    if not settings.workspace_message_translation_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "物流描述翻译未启用", 503)
    packages = (
        (await get_sidebar_enhanced_tracking(session, user, session_id, order_id)).packages
        if enhanced
        else (await get_sidebar_order_detail(session, user, session_id, order_id)).tracking_packages
    )
    events = [event for package in packages for event in package.events]
    if not events or len(events) > 40:
        raise AppError(ErrorCode.VALIDATION_ERROR, "暂无可批量翻译的物流节点或节点超过 40 条", 422)
    # 全量检查通过后才调用模型，避免把第三方物流文本中的敏感片段送出边界。
    if any(
        not event.description.strip()
        or len(event.description) > 1000
        or sanitize_prompt_text(event.description) != event.description
        for event in events
    ):
        raise AppError(ErrorCode.VALIDATION_ERROR, "物流描述含需脱敏内容，无法翻译", 422)
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, user, "workspace.view")
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    await _assert_conversation_visibility(session, user, conversation)
    provider = build_provider("deepseek", settings.llm_primary_model, settings)
    translator = TranslationService(StructuredGenerationService(provider, None, max_attempts=1))
    semaphore = asyncio.Semaphore(3)

    async def translate(source: str) -> TranslationBundleResult | None:
        async with semaphore:
            return await translator.translate_bundle(
                trigger_message_id=uuid.uuid5(uuid.NAMESPACE_URL, f"tiktok:tracking:{order_id}"),
                message=source,
                draft_reply=None,
                target_language="zh-CN",
                trace_id=trace_id,
            )

    try:
        gathered = await asyncio.gather(*(translate(event.description) for event in events), return_exceptions=True)
        results: list[TranslationBundleResult | None] = []
        for result in gathered:
            if isinstance(result, BaseException):
                raise ValueError("物流节点翻译失败") from result
            results.append(result)
        translations = [
            result.message_translation if result else event.description
            for event, result in zip(events, results, strict=True)
        ]
        if any(not value.strip() or sanitize_prompt_text(value) != value for value in translations):
            raise ValueError("译文包含需脱敏内容")
    except (LLMProviderError, ValueError) as error:
        session.add(
            AuditLog(
                store_id=conversation.store_id,
                actor_type="user",
                actor_id=user.id,
                action="sidebar.tracking.translate_all",
                resource_type="conversation",
                resource_id=conversation.id,
                request_id=trace_id,
                after_data={"target_language": "zh-CN", "event_count": len(events)},
                result="failed",
            )
        )
        await session.commit()
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "物流轨迹翻译暂不可用，请稍后重试", 503) from error
    session.add(
        AuditLog(
            store_id=conversation.store_id,
            actor_type="user",
            actor_id=user.id,
            action="sidebar.tracking.translate_all",
            resource_type="conversation",
            resource_id=conversation.id,
            request_id=trace_id,
            after_data={
                "target_language": "zh-CN",
                "event_count": len(events),
                "input_tokens": sum(result.input_tokens for result in results if result),
                "output_tokens": sum(result.output_tokens for result in results if result),
            },
            result="succeeded",
        )
    )
    await session.commit()
    return SidebarTrackingTimelineTranslation(
        events=[
            SidebarTrackingEventTranslation(
                source_description=event.description,
                translated_text=translated,
                occurred_at=event.occurred_at,
                tracking_number=event.tracking_number,
            )
            for event, translated in zip(events, translations, strict=True)
        ]
    )


async def send_agent_message(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID,
    content: str,
    idempotency_key: str,
    *,
    confirmed: bool,
    message_type: Literal["text", "logistics_card", "image", "video"] = "text",
    card_order_id: str | None = None,
    card_package_id: str | None = None,
    media_token: str | None = None,
) -> MessageView:
    """把已人工确认的消息交给统一工具执行层并返回持久化终态。"""
    if not confirmed:
        raise DeliveryNotStarted(ErrorCode.VALIDATION_ERROR, "发送前必须完成人工二次确认", 422)
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, user, "workspace.reply")
    )
    if conversation is None:
        raise DeliveryNotStarted(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    try:
        await _assert_conversation_owner(session, user, conversation)
    except AppError as error:
        raise DeliveryNotStarted(error.code, error.message, error.status_code) from error
    if conversation.status == "closed":
        raise DeliveryNotStarted(ErrorCode.RESOURCE_CONFLICT, "会话已关闭，请先重新打开", 409)
    send_mode = _message_send_mode(conversation, await _connected_send_channel(session, conversation))
    if conversation.platform == "tiktok" and get_settings().real_tiktok_message_write_enabled and send_mode != "real":
        raise DeliveryNotStarted(ErrorCode.PERMISSION_DENIED, "当前会话不在真实消息发送范围内", 403)
    if send_mode == "real" and message_type == "text" and len(content) > TIKTOK_TEXT_MAX_LENGTH:
        raise DeliveryNotStarted(ErrorCode.VALIDATION_ERROR, "TikTok 普通文本不能超过 2000 字符", 422)
    if message_type in {"image", "video"}:
        if send_mode != "real" or not media_token:
            raise AppError(ErrorCode.PERMISSION_DENIED, "当前会话未开放真实媒体发送", 403)
    arguments: dict[str, object] = {"conversation_id": str(conversation.id), "content": content}
    if message_type == "logistics_card":
        arguments.update(
            {"message_type": message_type, "card_order_id": card_order_id, "card_package_id": card_package_id}
        )
    elif message_type in {"image", "video"}:
        arguments.update({"message_type": message_type, "media_token": media_token})
    result = await SqlAlchemyToolExecutor(session).execute(
        ToolInvocation(
            tool_name="send_platform_message",
            idempotency_key=idempotency_key,
            arguments=arguments,
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
        raise DeliveryNotStarted(ErrorCode.RESOURCE_CONFLICT, "当前店铺存在发送结果未知的消息，请先完成人工对账", 409)
    if result.error_code == "TOOL_MEDIA_PROOF_INVALID":
        raise AppError(ErrorCode.VALIDATION_ERROR, "媒体上传凭据无效、过期或不属于当前会话", 422)
    if result.error_code == "TOOL_OWNER_MISMATCH":
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
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
        raise DeliveryNotStarted(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    if result.status == "failed":
        # 平台写入前必先提交Message；确定失败且没有记录才可证明尚未写入。
        raise DeliveryNotStarted(ErrorCode.THIRD_PARTY_ERROR, "发送未开始，请检查授权或发送条件后重试", 503)
    raise AppError(ErrorCode.THIRD_PARTY_ERROR, "消息发送未创建可追踪记录", 503)


async def send_agent_logistics_card(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID,
    order_id: str,
    package_id: str | None,
    idempotency_key: str,
    *,
    confirmed: bool,
) -> MessageView:
    """核对买家和包裹后，经原人工确认工具链发送 TikTok 原生卡片。"""
    if not confirmed:
        raise DeliveryNotStarted(ErrorCode.VALIDATION_ERROR, "发送前必须完成人工二次确认", 422)
    try:
        conversation, client, order = await _verified_sidebar_order(session, user, session_id, order_id)
        known_package_ids = {item.package_id for item in order.line_items if item.package_id}
        enhanced_package = None
        enhanced_packages: list[SidebarTrackingPackage] = []
        if package_id and client.channel.metadata_json.get("seller_type") == "CROSS_BORDER":
            # 当前包裹的节点和 ID 都从已核对订单的官方增强轨迹读取。
            try:
                enhanced = await get_sidebar_enhanced_tracking(session, user, session_id, order_id)
                enhanced_packages = enhanced.packages
                enhanced_package = next((item for item in enhanced.packages if item.package_id == package_id), None)
            except AppError:
                if package_id not in known_package_ids:
                    raise
        if package_id and package_id not in known_package_ids and enhanced_package is None:
            raise DeliveryNotStarted(ErrorCode.RESOURCE_NOT_FOUND, "包裹不属于当前订单", 404)
        if len(known_package_ids) > 1 and not package_id:
            raise DeliveryNotStarted(ErrorCode.VALIDATION_ERROR, "多包裹订单需明确选择包裹", 422)
        if _message_send_mode(conversation, await _connected_send_channel(session, conversation)) == "disabled":
            raise DeliveryNotStarted(ErrorCode.PERMISSION_DENIED, "当前会话不能发送消息", 403)
        snapshot_package = enhanced_package
        if not (snapshot_package and snapshot_package.events) and len(known_package_ids) <= 1:
            events, _ = await client.get_standard_tracking(order_id)
            standard_package = standard_tracking_package(package_id, events)
            snapshot_package = (
                snapshot_package.model_copy(update={"events": standard_package.events})
                if snapshot_package is not None
                else standard_package
            )
        snapshot_package = snapshot_package or standard_tracking_package(package_id, ())
        card = logistics_card_snapshot(order, snapshot_package, packages=enhanced_packages or [snapshot_package])
    except AppError as error:
        raise DeliveryNotStarted(error.code, error.message, error.status_code) from error
    result = await send_agent_message(
        session,
        user,
        session_id,
        f"物流卡片 · 订单 {order_id}",
        idempotency_key,
        confirmed=True,
        message_type="logistics_card",
        card_order_id=order_id,
        card_package_id=package_id,
    )
    message = await session.get(Message, result.id)
    if message is None:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "物流卡片发送记录丢失", 503)
    message.raw_payload = {**message.raw_payload, "logistics_card": card.model_dump(mode="json")}
    await session.commit()
    return _message_view(message)


async def get_logistics_card_preview(
    session: AsyncSession, user: User, session_id: uuid.UUID, order_id: str
) -> list[LogisticsCardPreview]:
    """只读核验当前店铺买家订单；预览不依赖写入开关，也不产生消息记录。"""
    _conversation_view, client, order = await _verified_sidebar_order(session, user, session_id, order_id)
    enhanced_available = client.channel.metadata_json.get("seller_type") == "CROSS_BORDER"
    known_ids = list(dict.fromkeys(item.package_id for item in order.line_items if item.package_id))
    packages: list[SidebarTrackingPackage] = []
    if enhanced_available:
        try:
            packages = (await get_sidebar_enhanced_tracking(session, user, session_id, order_id)).packages
        except AppError as error:
            if error.status_code not in {429, 502, 503, 504}:
                raise
            # 增强读取仍遵循原八小时缓存/冷却；不可用时只展示可证明的通用信息。
            packages = []
    if packages:
        if (len(packages) > 1 or len(known_ids) > 1) and any(not item.package_id for item in packages):
            raise AppError(ErrorCode.VALIDATION_ERROR, "多包裹物流缺少可核验的包裹 ID", 422)
        if len(packages) == 1 and packages[0].package_id is None and len(known_ids) == 1:
            packages = [packages[0].model_copy(update={"package_id": known_ids[0]})]
        package_ids = [item.package_id for item in packages if item.package_id]
        if len(set(package_ids)) != len(package_ids):
            raise AppError(ErrorCode.VALIDATION_ERROR, "物流包裹映射不唯一", 422)
        packages = [*packages, *(standard_tracking_package(item, ()) for item in known_ids if item not in package_ids)]
        if len(packages) == 1 and not packages[0].events:
            events, _ = await client.get_standard_tracking(order_id)
            standard_package = standard_tracking_package(packages[0].package_id, events)
            packages = [packages[0].model_copy(update={"events": standard_package.events})]
    else:
        item_numbers = {item.tracking_number for item in order.line_items if item.tracking_number}
        identified_numbers = {
            item.tracking_number for item in order.line_items if item.package_id and item.tracking_number
        }
        if len(item_numbers) > 1 and any(
            not item.package_id and item.tracking_number and item.tracking_number not in identified_numbers
            for item in order.line_items
        ):
            raise AppError(ErrorCode.VALIDATION_ERROR, "多包裹物流缺少可核验的包裹 ID", 422)
        if len(known_ids) > 1:
            # 通用接口没有包裹分组证据，不能把同一份订单轨迹复制到每个包裹。
            packages = [standard_tracking_package(item, ()) for item in known_ids]
        else:
            events, _ = await client.get_standard_tracking(order_id)
            packages = [standard_tracking_package(known_ids[0] if known_ids else None, events)]
    packages = [
        package.model_copy(update={"events": sorted(package.events, key=lambda event: event.occurred_at, reverse=True)})
        for package in packages
    ]
    cards = [logistics_card_snapshot(order, package, packages=packages) for package in packages]
    packages = [
        package.model_copy(update={"tracking_number": card.tracking_number, "carrier_name": card.carrier_name})
        for package, card in zip(packages, cards, strict=True)
    ]
    return [
        LogisticsCardPreview(card=card, packages=packages, enhanced_available=enhanced_available, selected=index)
        for index, card in enumerate(cards)
    ]


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
    message.raw_payload = {**message.raw_payload, "delivery_mode": "real", "reconciled": True}
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
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, user, "workspace.view")
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    await _assert_conversation_owner(session, user, conversation)
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
        session, session_id, await allowed_store_ids(session, actor, "workspace.transfer"), for_update=True
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    await _assert_conversation_owner(session, actor, conversation)
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
        session, session_id, await allowed_store_ids(session, actor, "workspace.transfer"), for_update=True
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    await _assert_conversation_owner(session, actor, conversation)
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
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, actor, "workspace.transfer")
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    await _assert_conversation_visibility(session, actor, conversation)
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
        session, session_id, await allowed_store_ids(session, actor, "workspace.transfer"), for_update=True
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    if conversation.store_id not in await supervised_store_ids(session, actor):
        if conversation.assigned_user_id is not None and conversation.assigned_user_id != actor.id:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
        if conversation.assigned_user_id is not None or assignee_id != actor.id:
            raise AppError(ErrorCode.PERMISSION_DENIED, "客服只能领取待分配会话；转交请使用转交操作", 403)
    if conversation.status == "closed":
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "会话已关闭，请先重新打开", 409)
    if not await _assignee_can_reply(session, conversation.store_id, assignee_id):
        raise AppError(ErrorCode.VALIDATION_ERROR, "目标客服没有当前店铺回复权限", 422)
    conversation.assigned_user_id = assignee_id
    conversation.assignment_source = "manual"
    conversation.assignment_wait_reason = None
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
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, actor, "workspace.transfer")
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    await _assert_conversation_owner(session, actor, conversation)
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
    try:
        await _assert_conversation_owner(session, actor, conversation)
    except AppError:
        await finish_tool_call(session, tool_call, started, "failed", None, False, "TOOL_OWNER_MISMATCH")
        raise
    if conversation.status == "closed":
        await finish_tool_call(session, tool_call, started, "failed", None, False, "CONVERSATION_CLOSED")
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "会话已关闭，请先重新打开", 409)
    conversation.status = "transferred"
    conversation.transfer_reason = reason
    conversation.assigned_user_id = assign_to
    conversation.assignment_source = "manual" if assign_to else None
    conversation.assignment_wait_reason = None
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
    order = await find_order(session, order_id, await allowed_store_ids(session, user, "workspace.view"))
    if order is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "订单不存在", 404)
    await ensure_store_access(session, user, order.store_id)
    return _order_view(order)
