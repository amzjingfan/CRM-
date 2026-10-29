"""复用官方买家核验、原生模型和统一工具执行器的通知接线。"""

import asyncio
import json
import time
import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.errors import LLMProviderError
from app.agents.management.repository import PublishedAgent
from app.agents.prompts.compiler import verify_published_prompt
from app.agents.providers.factory import tool_provider
from app.agents.runtime.output import plain_text_answer
from app.agents.safety.grounding import review_final_answer
from app.agents.safety.input import prepare_untrusted_text
from app.audit.models import AuditLog
from app.conversations.models import Conversation, Message
from app.orders.models import Order
from app.shared.config.settings import Settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.tools.contracts import ToolExecutionContext, ToolInvocation
from app.tools.executor import SqlAlchemyToolExecutor
from app.tools.models import ToolCall
from app.workspace.sidebar import (
    _read_standard_tracking,
    _tracking_from_order,
    _verified_sidebar_order,
    get_sidebar_enhanced_tracking,
)

from .authorization import (
    NOTIFICATION_PERMISSIONS,
    authorize_event,
    bound_agent,
    verified_remote_window,
)
from .contracts import (
    AuthorizationSnapshot,
    BoundLogisticsEvent,
    DeliveryReceipt,
    LogisticsObservation,
    LogisticsScope,
    PreparedLogisticsNotification,
    ReviewDecision,
    TrackingEvent,
)
from .models import LogisticsNotificationPolicy
from .policy import require_policy_access
from .repository import SqlAlchemyLogisticsRepository
from .service import LogisticsUpdateService

Sessions = Callable[[], AbstractAsyncContextManager[AsyncSession]]
NOTIFICATION_OUTPUT_POLICY = (
    "本次只通知买家最新物流节点及其实际发生时间，一条简洁纯文本。遵从买家原始消息语言。"
    "不要列完整轨迹，不增加买家没有要求的政策、建议、促销、承诺、预计送达或操作结果。"
)


@dataclass(frozen=True)
class VerifiedLogisticsSource:
    observations: tuple[LogisticsObservation, ...]
    buyer_text: str


async def read_verified_observations(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    conversation_id: uuid.UUID,
    order_id: uuid.UUID,
    cutoff: datetime | None,
) -> VerifiedLogisticsSource:
    permissions = await require_policy_access(session, user, store_id)
    if not NOTIFICATION_PERMISSIONS.issubset(permissions):
        raise AppError(ErrorCode.PERMISSION_DENIED, "物流预演需要当前店铺订单权限", 403)
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.store_id == store_id,
            Conversation.platform == "tiktok",
            Conversation.status != "closed",
        )
    )
    order = await session.scalar(
        select(Order).where(
            Order.id == order_id,
            Order.store_id == store_id,
            Order.platform == "tiktok",
        )
    )
    if conversation is None or order is None or order.customer_id != conversation.customer_id:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "授权会话或买家订单不存在", 404)
    buyer = await session.scalar(
        select(Message)
        .where(
            Message.store_id == store_id,
            Message.conversation_id == conversation_id,
            Message.customer_id == conversation.customer_id,
            Message.direction == "inbound",
            Message.role == "user",
            Message.message_type == "text",
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
    )
    if buyer is None or not buyer.content.strip():
        raise AppError(ErrorCode.VALIDATION_ERROR, "没有可核验的买家语言上下文", 422)
    buyer_text = prepare_untrusted_text(buyer.content, source="user_message").text
    # 订单和会话 BUYER 在既有官方入口中逐项核验，不用本地首次同步时间推断新订单。
    _, client, remote_order = await _verified_sidebar_order(session, user, conversation_id, order.external_order_id)
    tracking = await _read_standard_tracking(client, order.external_order_id, _tracking_from_order(remote_order))
    official_order_at = datetime.fromtimestamp(remote_order.create_time, UTC) if remote_order.create_time else None
    from .worker import first_observation_mode

    packages = tracking.packages
    if (
        not any(package.package_id for package in packages)
        and client.channel.metadata_json.get("seller_type") == "CROSS_BORDER"
    ):
        # 多包裹通用轨迹无法精确归属时复用既有增强入口；其 Redis 八小时门禁保持生效。
        packages = (
            await get_sidebar_enhanced_tracking(session, user, conversation_id, order.external_order_id)
        ).packages
    observations = []
    for package in packages:
        events = tuple(
            TrackingEvent(
                occurred_at=event.occurred_at,
                status=str(event.action_code) if event.action_code is not None else "tracking_update",
                description=event.description,
            )
            for event in package.events
            if event.occurred_at is not None and event.description and event.description.strip()
        )
        # 缺包裹标识或可靠节点时不能编造一个包裹或当前状态。
        if not package.package_id or not events:
            continue
        latest_at = max(event.occurred_at for event in events)
        observations.append(
            LogisticsObservation(
                scope=LogisticsScope(
                    store_id=store_id,
                    customer_id=conversation.customer_id,
                    conversation_id=conversation_id,
                    order_id=order.id,
                    package_id=package.package_id,
                ),
                buyer_language=buyer.language or "match_buyer_message",
                events=events,
                first_observation=first_observation_mode(cutoff, official_order_at, latest_at),
            )
        )
    return VerifiedLogisticsSource(tuple(observations), buyer_text)


class NativeNotificationModel:
    """生成与独立复核分别使用新上下文，共用绝对 deadline 和真实用量。"""

    def __init__(self, settings: Settings, agent: PublishedAgent, buyer_text: str) -> None:
        if not settings.llm_enabled or not agent.model_provider or not agent.model_name or not agent.prompt_hash:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "物流通知模型未启用", 503)
        self.settings, self.agent, self.buyer_text = settings, agent, buyer_text
        self.prompt = verify_published_prompt(agent.prompt_sections, agent.prompt_hash)
        self.deadline = time.monotonic() + settings.chat_stream_timeout_seconds
        self.input_tokens = self.output_tokens = 0

    @staticmethod
    def evidence(context: BoundLogisticsEvent) -> dict[str, object]:
        return {
            "latest_logistics_event": {
                "description": prepare_untrusted_text(context.event.description, source="tool_result").text,
                "status": prepare_untrusted_text(context.event.status, source="tool_result").text,
                "occurred_at": context.event.occurred_at.isoformat(),
            }
        }

    def usage(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    async def generate(self, context: BoundLogisticsEvent) -> str:
        assert self.agent.model_provider is not None and self.agent.model_name is not None
        try:
            async with (
                tool_provider(
                    self.settings,
                    self.agent.model_provider,
                    self.agent.model_name,
                    deadline=self.deadline,
                ) as provider,
                asyncio.timeout(max(0.0, self.deadline - time.monotonic())),
            ):
                turn = await provider.complete(
                    messages=(
                        {"role": "system", "content": self.prompt.text + "\n" + NOTIFICATION_OUTPUT_POLICY},
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "untrusted_buyer_message": self.buyer_text,
                                    "buyer_language": context.buyer_language,
                                    "verified_evidence": self.evidence(context),
                                },
                                ensure_ascii=False,
                            ),
                        },
                    ),
                    tools=(),
                    max_output_tokens=self.settings.llm_max_output_tokens,
                )
        except LLMProviderError as error:
            self.usage(error.input_tokens, error.output_tokens)
            raise
        self.usage(turn.input_tokens, turn.output_tokens)
        if turn.calls or not turn.content:
            raise ValueError("notification_generation_invalid")
        return plain_text_answer(turn.content)

    async def review(self, context: BoundLogisticsEvent, candidate: str) -> ReviewDecision:
        assert self.agent.model_provider is not None and self.agent.model_name is not None
        candidate = prepare_untrusted_text(candidate, source="agent_draft").text
        async with tool_provider(
            self.settings,
            self.agent.model_provider,
            self.agent.model_name,
            deadline=self.deadline,
        ) as provider:
            decision = await review_final_answer(
                question=self.buyer_text,
                answer=candidate,
                evidence=self.evidence(context),
                provider=provider,
                deadline=self.deadline,
                max_output_tokens=self.settings.llm_max_output_tokens,
                privacy_policies=(self.prompt.sections["compliance"],),
                output_policies=(self.prompt.sections["language_format"], NOTIFICATION_OUTPUT_POLICY),
                max_answer_characters=2000,
                on_usage=self.usage,
            )
        return (
            ReviewDecision(status="approved", text=decision.answer)
            if decision.supported and decision.answer
            else (ReviewDecision(status="rejected", reason="notification_review_rejected"))
        )


class SqlNotificationDelivery:
    def __init__(self, sessions: Sessions, settings: Settings) -> None:
        self.sessions, self.settings = sessions, settings

    async def preview(self, notification: PreparedLogisticsNotification) -> DeliveryReceipt:
        # 正文已由 prepare 持久化；审阅 API 读取该台账，不创建任何出站消息。
        return DeliveryReceipt(status="succeeded", reference=notification.idempotency_key)

    async def deliver(self, notification: PreparedLogisticsNotification) -> DeliveryReceipt:
        if not (
            self.settings.logistics_notifications_enabled and self.settings.real_tiktok_logistics_notifications_enabled
        ):
            return DeliveryReceipt(status="failed")
        async with self.sessions() as session:
            policy = await session.get(LogisticsNotificationPolicy, notification.scope.store_id)
            if policy is None or policy.authorized_by is None:
                return DeliveryReceipt(status="failed")
            result = await SqlAlchemyToolExecutor(session).execute(
                ToolInvocation(
                    tool_name="send_platform_message",
                    idempotency_key=notification.idempotency_key,
                    arguments={
                        "conversation_id": str(notification.scope.conversation_id),
                        "content": notification.text,
                    },
                    context=ToolExecutionContext(
                        store_id=notification.scope.store_id,
                        actor_type="job",
                        actor_id=policy.authorized_by,
                        permissions={"workspace.reply"},
                        human_confirmed=False,
                        logistics_notification_key=notification.idempotency_key,
                    ),
                )
            )
        status: Literal["succeeded", "failed", "unknown"] = (
            "succeeded" if result.status == "succeeded" else "failed" if result.status == "failed" else "unknown"
        )
        return DeliveryReceipt(status="failed" if result.mocked else status, reference=str(result.tool_call_id))

    async def reconcile(self, notification: PreparedLogisticsNotification) -> DeliveryReceipt:
        async with self.sessions() as session:
            call = await session.scalar(
                select(ToolCall).where(
                    ToolCall.store_id == notification.scope.store_id,
                    ToolCall.idempotency_key == notification.idempotency_key,
                    ToolCall.tool_name == "send_platform_message",
                )
            )
            if call is None or call.mocked:
                return DeliveryReceipt(status="unknown")
            # 复用工作台已核对平台事实后的持久终态；unknown 不以“未找到消息”推断失败。
            status: Literal["succeeded", "failed", "unknown"] = (
                "succeeded" if call.status == "succeeded" else "failed" if call.status == "failed" else "unknown"
            )
            return DeliveryReceipt(status=status, reference=str(call.id))


def build_notification_service(
    sessions: Sessions,
    settings: Settings,
    policy: LogisticsNotificationPolicy,
    model: NativeNotificationModel,
) -> LogisticsUpdateService:
    async def authorize(context: BoundLogisticsEvent) -> AuthorizationSnapshot:
        async with sessions() as session:
            return await authorize_event(
                session,
                settings,
                context,
                expected_revision=policy.revision,
                require_external=policy.mode == "external",
            )

    return LogisticsUpdateService(
        repository=SqlAlchemyLogisticsRepository(sessions),
        authorize=authorize,
        generate=model.generate,
        review=model.review,
        delivery=SqlNotificationDelivery(sessions, settings),
        mode="external" if policy.mode == "external" else "preview",
    )


class ManualLogisticsPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    store_id: uuid.UUID
    conversation_id: uuid.UUID
    order_id: uuid.UUID
    package_id: str | None = Field(default=None, min_length=1, max_length=200)


class ManualLogisticsPreview(BaseModel):
    status: str
    reason: str | None = None
    preview_text: str | None = None
    event_at: datetime | None = None
    buyer_language: str | None = None


async def manual_preview(
    session: AsyncSession,
    user: User,
    payload: ManualLogisticsPreviewRequest,
    settings: Settings,
) -> ManualLogisticsPreview:
    """人工只读预演不要求后台开关，不改变后台开关、基线或发送台账。"""
    await require_policy_access(session, user, payload.store_id)
    policy = await session.get(LogisticsNotificationPolicy, payload.store_id)
    policy_revision = policy.revision if policy else None
    agent = await bound_agent(session, payload.store_id, policy.agent_id if policy else None)
    if agent is None or not settings.llm_enabled or not settings.real_tiktok_read_enabled:
        return ManualLogisticsPreview(status="blocked", reason="preview_configuration_unavailable")
    source = await read_verified_observations(
        session,
        user,
        payload.store_id,
        payload.conversation_id,
        payload.order_id,
        None,
    )
    candidates = [
        item
        for item in source.observations
        if payload.package_id is None or item.scope.package_id == payload.package_id
    ]
    if not candidates:
        return ManualLogisticsPreview(status="blocked", reason="verified_event_unavailable")
    observation = max(candidates, key=lambda item: (item.latest.occurred_at, item.latest.fingerprint))
    conversation = await session.get(Conversation, payload.conversation_id)
    if conversation is None:
        return ManualLogisticsPreview(status="blocked", reason="conversation_unavailable")
    grant, identity, window = await verified_remote_window(session, settings, conversation)
    if not (grant and identity and window):
        return ManualLogisticsPreview(status="blocked", reason="conversation_window_unavailable")
    context = BoundLogisticsEvent(
        scope=observation.scope,
        event=observation.latest,
        buyer_language=observation.buyer_language,
    )
    model = NativeNotificationModel(settings, agent, source.buyer_text)
    model_failed = False
    try:
        candidate = await model.generate(context)
        decision = await model.review(context, candidate)
    except asyncio.CancelledError:
        raise
    except Exception:
        model_failed = True
        decision = ReviewDecision(status="rejected", reason="preview_model_unavailable")
    # 模型等待期间撤权、Agent 停用或会话关闭均使预览失效。
    permissions = await require_policy_access(session, user, payload.store_id)
    if policy is not None:
        await session.refresh(policy)
    still_bound = await bound_agent(session, payload.store_id, policy.agent_id if policy else None)
    await session.refresh(conversation)
    if (
        not NOTIFICATION_PERMISSIONS.issubset(permissions)
        or still_bound != agent
        or conversation.status == "closed"
        or policy is None
        or policy.revision != policy_revision
    ):
        return ManualLogisticsPreview(status="blocked", reason="preview_authorization_changed")
    grant, identity, window = await verified_remote_window(session, settings, conversation)
    if not (grant and identity and window):
        return ManualLogisticsPreview(status="blocked", reason="conversation_window_unavailable")
    session.add(
        AuditLog(
            store_id=payload.store_id,
            actor_type="user",
            actor_id=user.id,
            action="logistics.notification.manual_preview",
            resource_type="order",
            resource_id=payload.order_id,
            after_data={
                "review_status": decision.status,
                "input_tokens": model.input_tokens,
                "output_tokens": model.output_tokens,
            },
            result="succeeded" if decision.status == "approved" else "failed",
        )
    )
    await session.commit()
    return ManualLogisticsPreview(
        status="blocked" if model_failed else "previewed" if decision.status == "approved" else "rejected",
        reason=None if decision.status == "approved" else decision.reason,
        preview_text=decision.text if decision.status == "approved" else None,
        event_at=context.event.occurred_at,
        buyer_language=context.buyer_language,
    )
