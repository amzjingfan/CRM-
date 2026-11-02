"""现有 jobs 的低频补偿扫描；每订单持久占位后才读取官方物流。"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import case, exists, literal, or_, select
from sqlalchemy.dialects.postgresql import insert

from app.agents.safety.input import prepare_untrusted_text
from app.audit.models import AuditLog
from app.conversations.models import Conversation, Message
from app.orders.models import Order
from app.shared.config.settings import Settings

from .authorization import bound_agent, policy_authorizer, utc
from .contracts import BoundLogisticsEvent, PreparedLogisticsNotification
from .discovery import discover_eligible_orders
from .integration import (
    NativeNotificationModel,
    Sessions,
    SqlNotificationDelivery,
    build_notification_service,
    read_verified_observations,
)
from .models import LogisticsNotification, LogisticsNotificationPolicy, LogisticsOrderScan
from .repository import SqlAlchemyLogisticsRepository

logger = logging.getLogger(__name__)


def first_observation_mode(
    cutoff: datetime | None,
    official_order_at: datetime | None,
    event_at: datetime | None,
) -> Literal["baseline", "notify"]:
    if (
        cutoff is not None
        and official_order_at is not None
        and event_at is not None
        and utc(official_order_at) > utc(cutoff)
        and utc(event_at) > utc(cutoff)
    ):
        return "notify"
    return "baseline"


@dataclass(frozen=True)
class LogisticsScanClaim:
    store_id: uuid.UUID
    order_id: uuid.UUID
    token: uuid.UUID


async def claim_due_scan(sessions: Sessions, settings: Settings) -> LogisticsScanClaim | None:
    now = datetime.now(UTC)
    async with sessions() as session, session.begin():
        missing = (
            select(Order.store_id, Order.id, literal(now), literal(0))
            .join(
                LogisticsNotificationPolicy,
                LogisticsNotificationPolicy.store_id == Order.store_id,
            )
            .where(
                LogisticsNotificationPolicy.enabled.is_(True),
                Order.platform == "tiktok",
                Order.customer_id.is_not(None),
                ~exists(
                    select(LogisticsOrderScan.order_id).where(
                        LogisticsOrderScan.store_id == Order.store_id,
                        LogisticsOrderScan.order_id == Order.id,
                    )
                ),
            )
            .order_by(Order.id)
            .limit(100)
        )
        await session.execute(
            insert(LogisticsOrderScan)
            .from_select(
                ["store_id", "order_id", "next_poll_at", "failure_count"],
                missing,
            )
            .on_conflict_do_nothing(index_elements=["store_id", "order_id"])
        )
        row = await session.scalar(
            select(LogisticsOrderScan)
            .join(
                LogisticsNotificationPolicy,
                LogisticsNotificationPolicy.store_id == LogisticsOrderScan.store_id,
            )
            .where(
                LogisticsNotificationPolicy.enabled.is_(True),
                LogisticsOrderScan.next_poll_at <= now,
                or_(LogisticsOrderScan.claimed_until.is_(None), LogisticsOrderScan.claimed_until <= now),
            )
            .order_by(LogisticsOrderScan.next_poll_at, LogisticsOrderScan.store_id, LogisticsOrderScan.order_id)
            .limit(1)
            .with_for_update(skip_locked=True, of=LogisticsOrderScan)
        )
        if row is None:
            return None
        token = uuid.uuid4()
        row.claim_token, row.claimed_until = token, now + timedelta(minutes=10)
        # 即使进程退出，下一实例也不能在补查周期内重复拉取此订单。
        row.next_poll_at = now + timedelta(seconds=settings.logistics_notification_poll_seconds)
        return LogisticsScanClaim(row.store_id, row.order_id, token)


async def finish_scan(sessions: Sessions, settings: Settings, claim: LogisticsScanClaim, reason: str | None) -> None:
    now = datetime.now(UTC)
    async with sessions() as session, session.begin():
        row = await session.scalar(
            select(LogisticsOrderScan)
            .where(
                LogisticsOrderScan.store_id == claim.store_id,
                LogisticsOrderScan.order_id == claim.order_id,
                LogisticsOrderScan.claim_token == claim.token,
            )
            .with_for_update()
        )
        if row is None:
            return
        row.claimed_until, row.claim_token = None, None
        row.last_polled_at, row.last_reason = now, reason
        row.failure_count = min(row.failure_count + 1, 4) if reason else 0
        delay = settings.logistics_notification_poll_seconds * (2**row.failure_count)
        row.next_poll_at = now + timedelta(seconds=delay)


async def recover_local_notifications(sessions: Sessions, settings: Settings) -> bool:
    """仅恢复持久事件，不重取订单或物流；unknown 只读取统一发送台账对账。"""
    if not settings.logistics_notifications_enabled or not settings.real_tiktok_read_enabled:
        return False
    now = datetime.now(UTC)
    async with sessions() as session:
        rows = (
            await session.scalars(
                select(LogisticsNotification)
                .join(
                    LogisticsNotificationPolicy,
                    LogisticsNotificationPolicy.store_id == LogisticsNotification.store_id,
                )
                .where(
                    LogisticsNotificationPolicy.enabled.is_(True),
                    or_(
                        LogisticsNotification.state == "pending",
                        (LogisticsNotification.state == "reviewing")
                        & or_(
                            LogisticsNotification.review_lease_expires_at.is_(None),
                            LogisticsNotification.review_lease_expires_at <= now,
                        ),
                        (LogisticsNotification.state == "unknown") & (LogisticsNotification.mode == "external"),
                    ),
                )
                .order_by(
                    case((LogisticsNotification.state == "unknown", 1), else_=0),
                    LogisticsNotification.created_at,
                    LogisticsNotification.idempotency_key,
                )
                .limit(20)
            )
        ).all()
    repository = SqlAlchemyLogisticsRepository(sessions)

    async def block(context: BoundLogisticsEvent, reason: str) -> bool:
        token = await repository.claim(context)
        if token is None:
            return False
        await repository.finish(context, "blocked", reason, claim_token=token)
        return True

    for row in rows:
        context = BoundLogisticsEvent.model_validate(row.context_json)
        async with sessions() as session:
            policy = await session.get(LogisticsNotificationPolicy, row.store_id)
            if policy is None or not policy.enabled:
                continue
            user = await policy_authorizer(session, policy)
            agent = await bound_agent(session, row.store_id, policy.agent_id)
            if row.state == "unknown":
                if user is not None and agent is not None and row.reviewed_text is not None:
                    # 没有新 owner，也不调用 generate/deliver；未确定结果保持 unknown。
                    receipt = await SqlNotificationDelivery(sessions, settings).reconcile(
                        PreparedLogisticsNotification(
                            scope=context.scope,
                            event=context.event,
                            buyer_language=context.buyer_language,
                            idempotency_key=context.idempotency_key,
                            text=row.reviewed_text,
                        )
                    )
                    if receipt.status != "unknown":
                        await repository.finish(context, receipt.status, reference=receipt.reference)
                        return True
                continue
            if user is None or agent is None:
                if await block(context, "policy_authorization_unavailable"):
                    return True
                continue
            buyer = await session.scalar(
                select(Message.content)
                .where(
                    Message.store_id == context.scope.store_id,
                    Message.conversation_id == context.scope.conversation_id,
                    Message.customer_id == context.scope.customer_id,
                    Message.direction == "inbound",
                    Message.role == "user",
                    Message.message_type == "text",
                )
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(1)
            )
        if not buyer:
            if await block(context, "buyer_language_unavailable"):
                return True
            continue
        try:
            buyer_text = prepare_untrusted_text(buyer, source="user_message").text
            model = NativeNotificationModel(
                settings,
                agent,
                buyer_text,
                sessions=sessions,
                actor_id=user.id,
                delivery_mode="external" if policy.mode == "external" else "preview",
            )
        except Exception:
            if await block(context, "recovery_configuration_unavailable"):
                return True
            continue
        result = await build_notification_service(sessions, settings, policy, model).resume(context)
        if result.status not in {"pending", "reviewing", "context_unavailable"}:
            async with sessions() as session:
                session.add(
                    AuditLog(
                        store_id=context.scope.store_id,
                        actor_type="job",
                        actor_id=user.id,
                        action="logistics.notification.recover",
                        resource_type="order",
                        resource_id=context.scope.order_id,
                        after_data={
                            "state": result.status,
                            "input_tokens": model.input_tokens,
                            "output_tokens": model.output_tokens,
                        },
                        result="succeeded" if result.status in {"previewed", "succeeded"} else "failed",
                    )
                )
                await session.commit()
            return True
    return False


async def process_logistics_notification_cycle(sessions: Sessions, settings: Settings) -> bool:
    if not settings.logistics_notifications_enabled or not settings.real_tiktok_read_enabled:
        return False
    if await recover_local_notifications(sessions, settings):
        return True
    discovered = await discover_eligible_orders(sessions, settings)
    claim = await claim_due_scan(sessions, settings)
    if claim is None:
        return discovered
    reason: str | None = "observation_unavailable"
    try:
        async with sessions() as session:
            policy = await session.get(LogisticsNotificationPolicy, claim.store_id)
            if policy is None or not policy.enabled:
                return True
            user = await policy_authorizer(session, policy)
            agent = await bound_agent(session, claim.store_id, policy.agent_id)
            order = await session.scalar(
                select(Order).where(
                    Order.store_id == claim.store_id,
                    Order.id == claim.order_id,
                    Order.platform == "tiktok",
                )
            )
            if user is None or agent is None or order is None or order.customer_id is None:
                reason = "policy_authorization_unavailable"
                return True
            conversation = await session.scalar(
                select(Conversation)
                .where(
                    Conversation.store_id == claim.store_id,
                    Conversation.customer_id == order.customer_id,
                    Conversation.platform == "tiktok",
                    Conversation.status != "closed",
                )
                .order_by(Conversation.last_message_at.desc().nulls_last(), Conversation.id)
                .limit(1)
            )
            if conversation is None:
                reason = "conversation_unavailable"
                return True
            source = await read_verified_observations(
                session,
                user,
                claim.store_id,
                conversation.id,
                order.id,
                policy.enabled_at,
            )
            pending_unknown = (
                await session.scalars(
                    select(LogisticsNotification)
                    .where(
                        LogisticsNotification.store_id == claim.store_id,
                        LogisticsNotification.order_id == claim.order_id,
                        LogisticsNotification.state == "unknown",
                        LogisticsNotification.mode == "external",
                    )
                    .limit(50)
                )
            ).all()
        model = NativeNotificationModel(
            settings,
            agent,
            source.buyer_text,
            sessions=sessions,
            actor_id=user.id,
            delivery_mode="external" if policy.mode == "external" else "preview",
        )
        service = build_notification_service(sessions, settings, policy, model)
        for row in pending_unknown:
            await service.reconcile(BoundLogisticsEvent.model_validate(row.context_json))
        outcomes = [await service.observe_and_notify(observation) for observation in source.observations]
        reason = None if outcomes else "verified_event_unavailable"
        async with sessions() as session:
            session.add(
                AuditLog(
                    store_id=claim.store_id,
                    actor_type="job",
                    actor_id=user.id,
                    action="logistics.notification.scan",
                    resource_type="order",
                    resource_id=claim.order_id,
                    after_data={
                        "observation_count": len(outcomes),
                        "states": [item.status for item in outcomes],
                        "input_tokens": model.input_tokens,
                        "output_tokens": model.output_tokens,
                    },
                    result="succeeded" if reason is None else "failed",
                )
            )
            await session.commit()
    except Exception as error:
        # 不记录第三方响应、候选正文、买家消息或凭证。
        logger.warning("logistics_notification_scan_failed", extra={"error_type": type(error).__name__})
    finally:
        await finish_scan(sessions, settings, claim, reason)
    return True
