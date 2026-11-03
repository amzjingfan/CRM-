"""每店自动回复策略及会话暂停；新店默认 off。"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.repository import list_enabled_agents
from app.agents.tools.access import current_permissions
from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids
from app.conversations.models import Conversation
from app.shared.config.settings import Settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount, Store

POLICY_KEY = "agent_automation"
AUTOMATION_PERMISSIONS = frozenset({"agent.manage", "workspace.view", "workspace.reply"})


class StoreAutomationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["off", "preview", "auto"] = "off"
    revision: int = Field(default=0, ge=0, strict=True)
    authorized_by: uuid.UUID | None = None
    enabled_at: datetime | None = None

    @model_validator(mode="after")
    def validate_grant(self) -> "StoreAutomationPolicy":
        if self.mode != "off" and (
            self.authorized_by is None or self.enabled_at is None or self.enabled_at.tzinfo is None
        ):
            raise ValueError("启用的自动化策略必须绑定操作者和带时区的生效时间")
        return self


class AutomationPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["off", "preview", "auto"]
    expected_revision: int = Field(ge=0)


class AutomationPolicyView(StoreAutomationPolicy):
    store_id: uuid.UUID
    global_enabled: bool


class ConversationAutomationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paused: bool
    expected_revision: int = Field(ge=0)


class ConversationAutomationView(BaseModel):
    conversation_id: uuid.UUID
    paused: bool
    revision: int


def policy_from_store(store: Store) -> StoreAutomationPolicy:
    return StoreAutomationPolicy.model_validate((store.metadata_json or {}).get(POLICY_KEY, {}))


async def authorized_store(
    session: AsyncSession, user: User, store_id: uuid.UUID, permission: str, *, for_update: bool = False
) -> Store:
    if store_id not in await allowed_store_ids(session, user, permission):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "店铺不存在", 404)
    statement = select(Store).where(Store.id == store_id, Store.status == "active", Store.deleted_at.is_(None))
    row = await session.scalar(statement.with_for_update() if for_update else statement)
    if row is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "店铺不存在", 404)
    return row


async def get_policy(
    session: AsyncSession, user: User, store_id: uuid.UUID, settings: Settings
) -> AutomationPolicyView:
    store = await authorized_store(session, user, store_id, "agent.view")
    return AutomationPolicyView(
        **policy_from_store(store).model_dump(),
        store_id=store_id,
        global_enabled=settings.tiktok_automation_effective_enabled,
    )


async def set_policy(
    session: AsyncSession, user: User, store_id: uuid.UUID, payload: AutomationPolicyUpdate, settings: Settings
) -> AutomationPolicyView:
    store = await authorized_store(session, user, store_id, "agent.manage", for_update=True)
    old = policy_from_store(store)
    if old.revision != payload.expected_revision:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "自动化策略已更新，请刷新后重试", 409)
    if payload.mode != "off":
        if not AUTOMATION_PERMISSIONS <= await current_permissions(session, user, store_id):
            raise AppError(ErrorCode.PERMISSION_DENIED, "开启自动化需要店铺回复和 Agent 管理权限", 403)
        channel = await session.scalar(
            select(ChannelAccount.id).where(
                ChannelAccount.store_id == store_id,
                ChannelAccount.platform == "tiktok",
                ChannelAccount.status == "connected",
            )
        )
        if channel is None or not await list_enabled_agents(session, store_id):
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "请先发布并启用当前 TikTok 店铺的 Agent", 409)
        if payload.mode == "auto" and not settings.tiktok_automation_effective_enabled:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "部署自动投递开关尚未开启", 409)
    policy = StoreAutomationPolicy(
        mode=payload.mode,
        revision=old.revision + 1,
        authorized_by=user.id if payload.mode != "off" else None,
        enabled_at=datetime.now(UTC) if payload.mode != "off" else None,
    )
    store.metadata_json = {**(store.metadata_json or {}), POLICY_KEY: policy.model_dump(mode="json")}
    session.add(
        AuditLog(
            store_id=store_id,
            actor_type="user",
            actor_id=user.id,
            action="agent.automation.policy_updated",
            resource_type="store",
            resource_id=store_id,
            after_data={"mode": policy.mode, "revision": policy.revision},
            result="succeeded",
        )
    )
    await session.commit()
    return AutomationPolicyView(
        **policy.model_dump(), store_id=store_id, global_enabled=settings.tiktok_automation_effective_enabled
    )


async def conversation_policy(
    session: AsyncSession, user: User, conversation_id: uuid.UUID, payload: ConversationAutomationUpdate | None = None
) -> ConversationAutomationView:
    stores = await allowed_store_ids(session, user, "workspace.reply" if payload else "workspace.view")
    statement = select(Conversation).where(Conversation.id == conversation_id, Conversation.store_id.in_(stores))
    row = await session.scalar(statement.with_for_update() if payload is not None else statement)
    if row is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    metadata = row.metadata_json or {}
    raw_revision = metadata.get("automation_revision", 0)
    if not isinstance(raw_revision, int) or isinstance(raw_revision, bool) or raw_revision < 0:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "会话自动化版本无效", 409)
    revision = raw_revision
    paused = metadata.get("automation_paused", False) is True
    if payload is not None:
        if payload.expected_revision != revision:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "会话自动化状态已更新，请刷新", 409)
        revision += 1
        paused = payload.paused
        row.metadata_json = {**metadata, "automation_paused": paused, "automation_revision": revision}
        session.add(
            AuditLog(
                store_id=row.store_id,
                actor_type="user",
                actor_id=user.id,
                action="conversation.automation.updated",
                resource_type="conversation",
                resource_id=row.id,
                after_data={"paused": paused, "revision": revision},
                result="succeeded",
            )
        )
        await session.commit()
    return ConversationAutomationView(conversation_id=row.id, paused=paused, revision=revision)
