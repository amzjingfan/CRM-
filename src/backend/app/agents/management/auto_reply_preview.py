"""每店独立的多 Agent 自动建议预演策略；只生成坐席待审阅草稿。"""

import uuid
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.config_models import AgentConfig
from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import Store

POLICY_KEY = "agent_auto_reply_preview"


class AutoReplyPreviewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    expected_revision: int = Field(ge=0)


class AutoReplyPreviewView(BaseModel):
    store_id: uuid.UUID
    enabled: bool
    revision: int
    mode: Literal["review_preview"] = "review_preview"
    send_performed: Literal[False] = False


@dataclass(frozen=True, slots=True)
class PreviewPolicy:
    enabled: bool = False
    revision: int = 0
    actor_id: uuid.UUID | None = None


def policy_from_store(store: Store) -> PreviewPolicy:
    """缺失策略默认关闭；损坏的启用记录不会自动获得执行身份。"""
    raw = (store.metadata_json or {}).get(POLICY_KEY)
    if raw is None:
        return PreviewPolicy()
    if not isinstance(raw, dict):
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "自动建议策略数据无效", 409)
    revision = raw.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "自动建议策略版本无效", 409)
    enabled = raw.get("enabled")
    if not isinstance(enabled, bool):
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "自动建议策略状态无效", 409)
    actor_raw = raw.get("actor_id")
    try:
        actor_id = uuid.UUID(actor_raw) if isinstance(actor_raw, str) else None
    except ValueError:
        actor_id = None
    return PreviewPolicy(enabled and actor_id is not None, revision, actor_id)


async def _authorized_store(
    session: AsyncSession, user: User, store_id: uuid.UUID, permission: str, *, lock: bool = False
) -> Store:
    if store_id not in await allowed_store_ids(session, user, permission):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "店铺不存在", 404)
    statement = select(Store).where(Store.id == store_id, Store.status == "active", Store.deleted_at.is_(None))
    if lock:
        statement = statement.with_for_update()
    store = await session.scalar(statement)
    if store is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "店铺不存在", 404)
    return store


async def get_policy(session: AsyncSession, user: User, store_id: uuid.UUID) -> AutoReplyPreviewView:
    store = await _authorized_store(session, user, store_id, "agent.view")
    state = policy_from_store(store)
    return AutoReplyPreviewView(store_id=store_id, enabled=state.enabled, revision=state.revision)


async def set_policy(
    session: AsyncSession, user: User, store_id: uuid.UUID, payload: AutoReplyPreviewUpdate
) -> AutoReplyPreviewView:
    store = await _authorized_store(session, user, store_id, "agent.manage", lock=True)
    state = policy_from_store(store)
    if state.revision != payload.expected_revision:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "自动建议策略已更新，请刷新后重试", 409)
    if payload.enabled:
        if store_id not in await allowed_store_ids(session, user, "workspace.view"):
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "店铺不存在", 404)
        enabled_agent_id = await session.scalar(
            select(AgentConfig.id)
            .where(
                AgentConfig.store_id == store_id,
                AgentConfig.status == "enabled",
                AgentConfig.deleted_at.is_(None),
                AgentConfig.published_version.is_not(None),
            )
            .limit(1)
        )
        if enabled_agent_id is None:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "请先发布并启用当前店铺的 Agent", 409)
    next_revision = state.revision + 1
    store.metadata_json = {
        **(store.metadata_json or {}),
        POLICY_KEY: {
            "enabled": payload.enabled,
            "revision": next_revision,
            "actor_id": str(user.id) if payload.enabled else None,
        },
    }
    session.add(
        AuditLog(
            store_id=store_id,
            actor_type="user",
            actor_id=user.id,
            action="agent.auto_reply_preview.policy_updated",
            resource_type="store",
            resource_id=store_id,
            after_data={"enabled": payload.enabled, "revision": next_revision},
            result="succeeded",
        )
    )
    await session.commit()
    return AutoReplyPreviewView(store_id=store_id, enabled=payload.enabled, revision=next_revision)
