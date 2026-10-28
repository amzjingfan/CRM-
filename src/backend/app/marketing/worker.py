"""弃单挽回和中差评跟进的可靠调度器。"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.errors import LLMProviderError
from app.agents.core.factory import build_marketing_copy_service
from app.agents.core.marketing_generation import MarketingActionType, MarketingCopyCommand
from app.agents.core.reply_policy import (
    AgentReplyProfile,
    CustomerLanguage,
    ReplyTone,
    detect_customer_language,
    resolve_reply_language,
    resolve_store_reply_profile,
)
from app.agents.core.repository import (
    AgentRunStart,
    MarketingAgentRunCompletion,
    SqlAlchemyAgentRunRecorder,
)
from app.agents.core.schemas import AgentAction, AgentRunStatus
from app.agents.management.config_models import AgentConfig
from app.conversations.models import Conversation, Message
from app.integrations.adapters import get_platform_adapter
from app.integrations.schemas import SendMessageCommand
from app.marketing.models import CustomerReview, MarketingCampaign, MarketingEvent
from app.orders.models import Order
from app.shared.config.settings import Settings, get_settings
from app.stores.models import ChannelAccount
from app.tools.models import CouponIssuance
from app.tools.repository import begin_tool_call, finish_tool_call

RETRY_DELAYS_SECONDS = (30, 120, 300)
NON_RETRYABLE_ERRORS = {"PLATFORM_RESULT_UNKNOWN", "AI_MARKETING_REVIEW_REQUIRED"}
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GeneratedMarketingContent:
    """把安全文案和对应运行 ID 一起交给受控副作用层。"""

    content: str | None
    agent_run_id: uuid.UUID | None


def build_ai_marketing_command(
    *,
    campaign: MarketingCampaign,
    event: MarketingEvent,
    source: Order | CustomerReview,
    profile: AgentReplyProfile,
    detected_language: CustomerLanguage,
    trace_id: str,
) -> MarketingCopyCommand:
    """把业务实体压缩成不含客户标识和平台订单号的 AI 命令。

    订单只提供支付状态、币种和金额；评价只提供星级和经模型服务再次
    脱敏的正文。模型不需要客户 ID、外部订单号或店铺凭证来生成文案。
    """
    language = resolve_reply_language(profile, detected_language)
    if event.source_type == "order":
        order = cast(Order, source)
        return MarketingCopyCommand(
            store_id=campaign.store_id,
            campaign_id=campaign.id,
            event_id=event.id,
            trigger_type="cart_abandoned",
            action_type=cast(MarketingActionType, campaign.action_type),
            language=language,
            tone=profile.tone,
            order_payment_status=order.payment_status,
            order_currency=order.currency,
            order_total=str(order.total_amount),
            trace_id=trace_id,
        )
    review = cast(CustomerReview, source)
    return MarketingCopyCommand(
        store_id=campaign.store_id,
        campaign_id=campaign.id,
        event_id=event.id,
        trigger_type="bad_review",
        action_type=cast(MarketingActionType, campaign.action_type),
        language=language,
        tone=profile.tone,
        review_rating=review.rating,
        review_content=review.content,
        trace_id=trace_id,
    )


async def _frequency_allowed(
    session: AsyncSession, campaign: MarketingCampaign, customer_id: uuid.UUID | None, now: datetime
) -> bool:
    """执行活动级冷却和 30 天频控；无客户归属的数据不触达。"""
    if customer_id is None:
        return False
    contact_at = func.coalesce(MarketingEvent.completed_at, MarketingEvent.triggered_at)
    recent = await session.scalar(
        select(MarketingEvent)
        .where(
            MarketingEvent.campaign_id == campaign.id,
            MarketingEvent.customer_id == customer_id,
            MarketingEvent.status.not_in(["cancelled"]),
            contact_at > now - timedelta(hours=campaign.cooldown_hours),
        )
        .order_by(contact_at.desc())
        .limit(1)
    )
    if recent:
        return False
    count_30d = await session.scalar(
        select(func.count())
        .select_from(MarketingEvent)
        .where(
            MarketingEvent.campaign_id == campaign.id,
            MarketingEvent.customer_id == customer_id,
            MarketingEvent.status.not_in(["cancelled"]),
            contact_at >= now - timedelta(days=30),
        )
    )
    return int(count_30d or 0) < campaign.max_contacts_30d


async def _discover_events(session: AsyncSession, now: datetime) -> bool:
    """为满足规则的订单和评价创建唯一事件。"""
    campaigns = list(
        (await session.scalars(select(MarketingCampaign).where(MarketingCampaign.status == "active"))).all()
    )
    created = False
    for campaign in campaigns:
        cutoff = now - timedelta(minutes=campaign.trigger_delay_minutes)
        sources: list[Order | CustomerReview]
        if campaign.trigger_type == "cart_abandoned":
            sources = list(
                (
                    await session.scalars(
                        select(Order).where(
                            Order.store_id == campaign.store_id,
                            Order.customer_id.is_not(None),
                            or_(Order.payment_status.in_(["pending", "unpaid"]), Order.status == "pending"),
                            func.coalesce(Order.ordered_at, Order.created_at) <= cutoff,
                        )
                    )
                ).all()
            )
        else:
            sources = list(
                (
                    await session.scalars(
                        select(CustomerReview).where(
                            CustomerReview.store_id == campaign.store_id,
                            CustomerReview.customer_id.is_not(None),
                            CustomerReview.rating <= 3,
                            CustomerReview.reviewed_at <= cutoff,
                        )
                    )
                ).all()
            )
        for source in sources:
            if not await _frequency_allowed(session, campaign, source.customer_id, now):
                continue
            event = MarketingEvent(
                store_id=campaign.store_id,
                campaign_id=campaign.id,
                customer_id=source.customer_id,
                source_type="order" if isinstance(source, Order) else "review",
                source_id=source.id,
                status="waiting_ai" if campaign.content_mode == "ai" else "pending",
                next_attempt_at=now,
                triggered_at=now,
            )
            try:
                async with session.begin_nested():
                    session.add(event)
                    await session.flush()
                created = True
            except IntegrityError:
                # 活动与来源唯一约束是最终幂等防线，并发扫描不会重复触达。
                continue
    await session.commit()
    return created


async def _mark_conversions(session: AsyncSession, now: datetime) -> bool:
    """订单支付或评价改善后标记转化。"""
    events = list(
        (
            await session.scalars(
                select(MarketingEvent).where(
                    MarketingEvent.status.in_(["succeeded", "waiting_ai", "waiting_review", "approved"]),
                    MarketingEvent.converted_at.is_(None),
                )
            )
        ).all()
    )
    changed = False
    for event in events:
        converted = False
        if event.source_type == "order":
            order = await session.get(Order, event.source_id)
            converted = bool(order and (order.payment_status == "paid" or order.paid_at is not None))
        elif event.source_type == "review":
            review = await session.get(CustomerReview, event.source_id)
            converted = bool(review and review.rating >= 4)
        if converted:
            event.status = "converted"
            event.converted_at = now
            changed = True
    if changed:
        await session.commit()
    return changed


async def _load_marketing_profile(
    session: AsyncSession,
    event: MarketingEvent,
) -> tuple[AgentReplyProfile, uuid.UUID | None]:
    """读取当前店铺启用 Agent 的受限回复配置，不扩大知识或工具范围。"""
    config = await session.scalar(
        select(AgentConfig).where(
            AgentConfig.store_id == event.store_id,
            AgentConfig.status == "enabled",
            AgentConfig.deleted_at.is_(None),
        )
    )
    if config is not None:
        try:
            return resolve_store_reply_profile(config.knowledge_scope), config.id
        except ValueError as error:
            raise RuntimeError("AI_REPLY_PROFILE_INVALID") from error
    default_tone = ReplyTone.EMPATHETIC if event.source_type == "review" else ReplyTone.FRIENDLY
    return AgentReplyProfile(tone=default_tone), None


async def _detect_event_language(
    session: AsyncSession,
    event: MarketingEvent,
    source: Order | CustomerReview,
) -> CustomerLanguage:
    """优先使用评价正文，其次使用客户最近一条入站消息判断语言。"""
    if isinstance(source, CustomerReview) and source.content:
        detected = detect_customer_language(source.content)
        if detected != CustomerLanguage.UNKNOWN:
            return detected
    if event.customer_id is None:
        return CustomerLanguage.UNKNOWN
    latest_message = await session.scalar(
        select(Message)
        .where(
            Message.store_id == event.store_id,
            Message.customer_id == event.customer_id,
            Message.direction == "inbound",
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
    )
    if latest_message is None:
        return CustomerLanguage.UNKNOWN
    detected = detect_customer_language(latest_message.content)
    if detected == CustomerLanguage.UNKNOWN and latest_message.language in {"zh-CN", "en"}:
        return CustomerLanguage(latest_message.language)
    return detected


async def _generate_ai_content(
    session: AsyncSession,
    event: MarketingEvent,
    campaign: MarketingCampaign,
    settings: Settings,
) -> GeneratedMarketingContent:
    """生成安全营销草稿；该函数不发送、不发券，也不写业务实体。"""
    if "message" not in campaign.action_type:
        return GeneratedMarketingContent(content=None, agent_run_id=None)
    if not settings.ai_marketing_enabled or not settings.llm_enabled:
        raise RuntimeError("AI_MARKETING_DISABLED")
    source: Order | CustomerReview | None
    if event.source_type == "order":
        source = await session.get(Order, event.source_id)
    else:
        source = await session.get(CustomerReview, event.source_id)
    if source is None or source.store_id != event.store_id:
        raise RuntimeError("MARKETING_SOURCE_NOT_FOUND")
    conversation = await session.scalar(
        select(Conversation)
        .where(
            Conversation.store_id == event.store_id,
            Conversation.customer_id == event.customer_id,
        )
        .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.id.desc())
        .limit(1)
    )
    if conversation is None:
        raise RuntimeError("CONVERSATION_NOT_FOUND")
    profile, agent_config_id = await _load_marketing_profile(session, event)
    command = build_ai_marketing_command(
        campaign=campaign,
        event=event,
        source=source,
        profile=profile,
        detected_language=await _detect_event_language(session, event, source),
        trace_id=str(event.id),
    )
    recorder = SqlAlchemyAgentRunRecorder(session)
    run_id = await recorder.start(
        AgentRunStart(
            store_id=event.store_id,
            conversation_id=conversation.id,
            trigger_message_id=None,
            provider_name=settings.llm_primary_provider,
            model_name=settings.llm_primary_model or "unconfigured",
            prompt_version="marketing-copy-v1.0.0",
            input_summary=(
                f"run_type=marketing;event_id={event.id};campaign_id={campaign.id};"
                f"trigger_type={campaign.trigger_type};action_type={campaign.action_type}"
            ),
            trace_id=command.trace_id,
            agent_config_id=agent_config_id,
        )
    )
    try:
        result = await build_marketing_copy_service(settings).generate(command)
    except LLMProviderError as error:
        await recorder.fail(
            run_id,
            AgentRunStatus.TIMEOUT if error.code.value == "LLM_TIMEOUT" else AgentRunStatus.FAILED,
            AgentAction.HUMAN_REVIEW,
            error.code.value,
            settings.llm_primary_provider,
            settings.llm_primary_model or "unconfigured",
            0,
        )
        raise
    except Exception:
        await recorder.fail(
            run_id,
            AgentRunStatus.FAILED,
            AgentAction.HUMAN_REVIEW,
            "AI_MARKETING_GENERATION_FAILED",
            settings.llm_primary_provider,
            settings.llm_primary_model or "unconfigured",
            0,
        )
        raise
    await recorder.complete_marketing(
        run_id,
        MarketingAgentRunCompletion(
            event_id=event.id,
            provider_name=result.provider,
            model_name=result.model,
            prompt_version=result.prompt_version,
            is_safe=result.is_safe,
            requires_human=result.requires_human,
            safety_reason_codes=result.safety_reason_codes,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
        ),
    )
    logger.info(
        "ai_marketing_copy_completed",
        extra={
            "event": "ai_marketing_copy_completed",
            "trace_id": command.trace_id,
            "marketing_event_id": str(event.id),
            "campaign_id": str(campaign.id),
            "trigger_type": campaign.trigger_type,
            "is_safe": result.is_safe,
            "requires_human": result.requires_human,
            "safety_reason_codes": result.safety_reason_codes,
            "prompt_version": result.prompt_version,
            "provider": result.provider,
            "model": result.model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_ms": result.latency_ms,
        },
    )
    if not result.is_safe or result.content is None:
        raise RuntimeError("AI_MARKETING_REVIEW_REQUIRED")
    return GeneratedMarketingContent(content=result.content, agent_run_id=run_id)


async def _send_coupon(
    session: AsyncSession,
    event: MarketingEvent,
    campaign: MarketingCampaign,
    *,
    agent_run_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """以 job 身份执行 Mock 发券工具。"""
    assert event.customer_id is not None and campaign.coupon_code is not None
    key = f"marketing:{event.id}:coupon"
    call, replayed, started = await begin_tool_call(
        session,
        event.store_id,
        "job",
        None,
        "send_coupon",
        key,
        {"customer_id": str(event.customer_id), "coupon_code": campaign.coupon_code},
        {"customer_id": str(event.customer_id), "coupon_code": campaign.coupon_code},
        agent_run_id=agent_run_id,
        trace_id=str(event.id),
    )
    issuance = await session.scalar(select(CouponIssuance).where(CouponIssuance.tool_call_id == call.id))
    if issuance is None:
        issuance = CouponIssuance(
            store_id=event.store_id,
            customer_id=event.customer_id,
            tool_call_id=call.id,
            coupon_code=campaign.coupon_code,
            description=f"营销活动：{campaign.name}",
            mocked=True,
        )
        session.add(issuance)
        await session.flush()
        await finish_tool_call(session, call, started, "succeeded", {"issuance_id": str(issuance.id)}, True)
    elif not replayed:
        await finish_tool_call(session, call, started, "succeeded", {"issuance_id": str(issuance.id)}, True)
    return call.id


async def _send_message(
    session: AsyncSession,
    event: MarketingEvent,
    campaign: MarketingCampaign,
    content: str,
    *,
    agent_run_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """通过受控平台工具发送已审核内容；无渠道或会话时明确失败。"""
    assert event.customer_id is not None
    conversation = await session.scalar(
        select(Conversation)
        .where(Conversation.store_id == event.store_id, Conversation.customer_id == event.customer_id)
        .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.id.desc())
        .limit(1)
    )
    if conversation is None:
        raise RuntimeError("CONVERSATION_NOT_FOUND")
    channel = await session.scalar(
        select(ChannelAccount).where(
            ChannelAccount.store_id == event.store_id,
            ChannelAccount.platform == conversation.platform,
            ChannelAccount.status == "connected",
        )
    )
    if channel is None:
        raise RuntimeError("CHANNEL_NOT_AVAILABLE")
    key = f"marketing:{event.id}:message"
    call, replayed, started = await begin_tool_call(
        session,
        event.store_id,
        "job",
        None,
        "send_platform_message",
        key,
        {"conversation_id": str(conversation.id), "content": content},
        {"conversation_id": str(conversation.id), "content_length": len(content)},
        agent_run_id=agent_run_id,
        trace_id=str(event.id),
    )
    if replayed:
        if call.status == "unknown":
            raise RuntimeError("PLATFORM_RESULT_UNKNOWN")
        if call.status != "succeeded":
            raise RuntimeError(call.error_code or "PLATFORM_SEND_FAILED")
        return call.id
    message = Message(
        store_id=event.store_id,
        conversation_id=conversation.id,
        customer_id=event.customer_id,
        platform=conversation.platform,
        external_message_id=f"pending-{uuid.uuid4()}",
        idempotency_key=key,
        role="system",
        direction="outbound",
        content=content,
        status="processing",
        raw_payload={"marketing_event_id": str(event.id)},
    )
    session.add(message)
    await session.commit()
    try:
        result = await get_platform_adapter(conversation.platform).send_message(
            channel,
            SendMessageCommand(
                external_conversation_id=conversation.external_conversation_id,
                content=content,
                idempotency_key=key,
            ),
        )
    except Exception:
        message.status = "failed"
        message.error_code = "PLATFORM_RESULT_UNKNOWN"
        await finish_tool_call(session, call, started, "unknown", None, False, "PLATFORM_RESULT_UNKNOWN")
        raise
    if result.external_message_id is not None:
        message.external_message_id = result.external_message_id
    message.status = result.status
    message.error_code = result.error_code
    await finish_tool_call(
        session,
        call,
        started,
        "succeeded" if result.status == "sent" else "failed",
        {"message_id": str(message.id), "status": result.status},
        result.mock,
        result.error_code,
    )
    if result.status != "sent":
        raise RuntimeError(result.error_code or "PLATFORM_SEND_FAILED")
    return call.id


async def _execute_due_event(session: AsyncSession, now: datetime, settings: Settings) -> bool:
    """使用行锁认领一个到期事件并执行最多三次的显式重试。"""
    due_statuses = ["pending", "failed"]
    if settings.ai_marketing_enabled:
        due_statuses.append("waiting_ai")
    event = await session.scalar(
        select(MarketingEvent)
        .where(
            MarketingEvent.status.in_(due_statuses),
            MarketingEvent.attempt_count < 3,
            MarketingEvent.next_attempt_at <= now,
        )
        .order_by(MarketingEvent.next_attempt_at, MarketingEvent.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if event is None:
        return False
    campaign = await session.get(MarketingCampaign, event.campaign_id)
    if campaign is None or campaign.status != "active":
        event.status = "failed"
        event.error_code = "CAMPAIGN_NOT_ACTIVE"
        event.completed_at = now
        await session.commit()
        return True
    event.status = "processing"
    event.attempt_count += 1
    await session.commit()
    try:
        calls: list[uuid.UUID] = []
        message_content = campaign.template_content
        agent_run_id: uuid.UUID | None = None
        if campaign.content_mode == "ai":
            # AI 只生成待审核草稿。即使安全检查通过，也必须先持久化并
            # 停在 waiting_review，绝不在同一次 Worker 执行中产生副作用。
            generated = await _generate_ai_content(session, event, campaign, settings)
            if generated.content is None:
                raise RuntimeError("MARKETING_CONTENT_MISSING")
            event.ai_draft_content = generated.content
            event.ai_draft_agent_run_id = generated.agent_run_id
            event.ai_review_status = "pending"
            event.ai_reviewed_by = None
            event.ai_reviewed_at = None
            event.status = "waiting_review"
            event.error_code = None
            event.next_attempt_at = None
            event.completed_at = None
            event.tool_call_ids = []
            await session.commit()
            return True
        if campaign.action_type in {"send_coupon", "send_coupon_and_message"}:
            calls.append(await _send_coupon(session, event, campaign, agent_run_id=agent_run_id))
        if campaign.action_type in {"send_message", "send_coupon_and_message"}:
            if message_content is None:
                raise RuntimeError("MARKETING_CONTENT_MISSING")
            calls.append(
                await _send_message(
                    session,
                    event,
                    campaign,
                    message_content,
                    agent_run_id=agent_run_id,
                )
            )
        event.tool_call_ids = [str(item) for item in calls]
        event.status = "succeeded"
        event.error_code = None
        event.completed_at = now
    except Exception as exc:
        if isinstance(exc, LLMProviderError):
            event.error_code = exc.code.value
            is_retryable = exc.retriable
        else:
            event.error_code = str(exc)[:100] or "MARKETING_ACTION_FAILED"
            is_retryable = event.error_code not in NON_RETRYABLE_ERRORS
        if not is_retryable or event.attempt_count >= 3:
            event.status = "failed"
            event.completed_at = now
            event.next_attempt_at = None
        else:
            event.status = "failed"
            event.next_attempt_at = now + timedelta(seconds=RETRY_DELAYS_SECONDS[event.attempt_count - 1])
    await session.commit()
    return True


async def process_marketing_cycle(session: AsyncSession, settings: Settings | None = None) -> bool:
    """执行一次发现、转化和到期任务循环，保证 Webhook 主链路不被阻塞。"""
    runtime_settings = settings or get_settings()
    now = datetime.now(UTC)
    discovered = await _discover_events(session, now)
    converted = await _mark_conversions(session, now)
    executed = await _execute_due_event(session, now, runtime_settings)
    return discovered or converted or executed
