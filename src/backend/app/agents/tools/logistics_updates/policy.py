"""店铺通知策略和已复核预览的管理服务。"""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.access import current_permissions
from app.audit.models import AuditLog
from app.conversations.models import Conversation
from app.shared.config.settings import Settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode

from .authorization import NOTIFICATION_PERMISSIONS, bound_agent
from .contracts import DeliveryMode
from .models import LogisticsNotification, LogisticsNotificationPolicy


class LogisticsPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool
    agent_id: uuid.UUID | None = None
    mode: DeliveryMode = "preview"
    expected_revision: int = Field(ge=0)


class LogisticsPolicyView(BaseModel):
    store_id: uuid.UUID
    agent_id: uuid.UUID | None = None
    enabled: bool = False
    mode: DeliveryMode = "preview"
    enabled_at: datetime | None = None
    revision: int = 0
    global_enabled: bool = False
    real_delivery_enabled: bool = False
    last_scan_at: datetime | None = None


class LogisticsNotificationView(BaseModel):
    notification_key: str
    conversation_id: uuid.UUID
    state: str
    reason: str | None = None
    mode: DeliveryMode
    event_at: datetime
    buyer_language: str
    preview_text: str | None = None
    created_at: datetime


async def require_policy_access(session: AsyncSession, user: User, store_id: uuid.UUID) -> set[str]:
    permissions = await current_permissions(session, user, store_id)
    if "workspace.reply" not in permissions:
        raise AppError(ErrorCode.PERMISSION_DENIED, "没有当前店铺回复权限", 403)
    return permissions


def policy_view(
    store_id: uuid.UUID, row: LogisticsNotificationPolicy | None, settings: Settings
) -> LogisticsPolicyView:
    return LogisticsPolicyView(
        store_id=store_id,
        agent_id=row.agent_id if row else None,
        enabled=bool(row and row.enabled),
        mode="external" if row and row.mode == "external" else "preview",
        enabled_at=row.enabled_at if row else None,
        revision=row.revision if row else 0,
        global_enabled=settings.logistics_notifications_enabled,
        real_delivery_enabled=settings.real_tiktok_logistics_notifications_enabled,
        last_scan_at=row.last_scan_at if row else None,
    )


async def get_policy(session: AsyncSession, user: User, store_id: uuid.UUID, settings: Settings) -> LogisticsPolicyView:
    await require_policy_access(session, user, store_id)
    return policy_view(store_id, await session.get(LogisticsNotificationPolicy, store_id), settings)


async def update_policy(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    payload: LogisticsPolicyUpdate,
    settings: Settings,
) -> LogisticsPolicyView:
    permissions = await require_policy_access(session, user, store_id)
    if payload.enabled and not NOTIFICATION_PERMISSIONS.issubset(permissions):
        raise AppError(ErrorCode.PERMISSION_DENIED, "启用物流通知还需当前店铺订单权限", 403)
    if payload.mode == "external" and not settings.real_tiktok_logistics_notifications_enabled:
        raise AppError(ErrorCode.PERMISSION_DENIED, "真实物流通知未获部署授权", 403)
    if payload.agent_id is not None and await bound_agent(session, store_id, payload.agent_id) is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, "须选择同店已启用且已发布物流通知工具的 Agent", 422)
    if payload.enabled and payload.agent_id is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, "启用物流通知必须选择 Agent", 422)
    await session.execute(
        insert(LogisticsNotificationPolicy)
        .values(
            store_id=store_id,
            enabled=False,
            mode="preview",
            revision=0,
        )
        .on_conflict_do_nothing(index_elements=["store_id"])
    )
    row = await session.scalar(
        select(LogisticsNotificationPolicy)
        .where(
            LogisticsNotificationPolicy.store_id == store_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None or row.revision != payload.expected_revision:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "通知策略已更新，请刷新重试", 409)
    changed_authority = row.agent_id != payload.agent_id or row.mode != payload.mode or not row.enabled
    if payload.enabled and changed_authority:
        row.enabled_at = datetime.now(UTC)
    row.enabled, row.agent_id, row.mode = payload.enabled, payload.agent_id, payload.mode
    row.authorized_by = user.id
    row.revision += 1
    session.add(
        AuditLog(
            store_id=store_id,
            actor_type="user",
            actor_id=user.id,
            action="logistics.notification.policy.update",
            resource_type="logistics_notification_policy",
            resource_id=store_id,
            after_data={"enabled": row.enabled, "mode": row.mode, "revision": row.revision},
            result="succeeded",
        )
    )
    await session.commit()
    await session.refresh(row)
    return policy_view(store_id, row, settings)


async def list_notifications(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    *,
    conversation_id: uuid.UUID | None = None,
    offset: int = 0,
    notification_key: str | None = None,
) -> list[LogisticsNotificationView]:
    await require_policy_access(session, user, store_id)
    query = select(LogisticsNotification).where(LogisticsNotification.store_id == store_id)
    if conversation_id is not None:
        found = await session.scalar(
            select(Conversation.id).where(
                Conversation.id == conversation_id,
                Conversation.store_id == store_id,
            )
        )
        if found is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
        query = query.where(LogisticsNotification.conversation_id == conversation_id)
    if notification_key is not None:
        query = query.where(LogisticsNotification.idempotency_key == notification_key)
    rows = (
        await session.scalars(query.order_by(LogisticsNotification.created_at.desc()).offset(offset).limit(50))
    ).all()
    from .contracts import BoundLogisticsEvent

    result = []
    for row in rows:
        context = BoundLogisticsEvent.model_validate(row.context_json)
        result.append(
            LogisticsNotificationView(
                notification_key=row.idempotency_key,
                conversation_id=row.conversation_id,
                state=row.state,
                reason=row.reason,
                mode="external" if row.mode == "external" else "preview",
                event_at=context.event.occurred_at,
                buyer_language=context.buyer_language,
                preview_text=row.reviewed_text
                if row.state in {"previewed", "succeeded", "unknown", "failed"}
                else None,
                created_at=row.created_at,
            )
        )
    return result
