"""基础接待配置查询，查询条件始终携带授权店铺与个人范围。"""

import uuid

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.reception.models import (
    ReceptionGroup,
    ReceptionMutation,
    ReceptionPolicy,
    ReceptionPolicyStore,
    ReceptionReply,
)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def find_group(session: AsyncSession, item_id: uuid.UUID, store_ids: set[uuid.UUID]) -> ReceptionGroup | None:
    if not store_ids:
        return None
    result: ReceptionGroup | None = await session.scalar(
        select(ReceptionGroup).where(ReceptionGroup.id == item_id, ReceptionGroup.store_id.in_(store_ids))
    )
    return result


async def list_groups(
    session: AsyncSession,
    store_id: uuid.UUID,
    scope: str,
    owner_id: uuid.UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[ReceptionGroup], int]:
    filters = [ReceptionGroup.store_id == store_id, ReceptionGroup.scope == scope]
    if scope == "personal":
        filters.append(ReceptionGroup.owner_user_id == owner_id)
    total = await session.scalar(select(func.count()).select_from(ReceptionGroup).where(*filters)) or 0
    items = (
        await session.scalars(
            select(ReceptionGroup)
            .where(*filters)
            .order_by(ReceptionGroup.sort_order, ReceptionGroup.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return list(items), total


async def group_has_replies(session: AsyncSession, group_id: uuid.UUID) -> bool:
    return bool(await session.scalar(select(ReceptionReply.id).where(ReceptionReply.group_id == group_id).limit(1)))


async def find_reply(session: AsyncSession, item_id: uuid.UUID, store_ids: set[uuid.UUID]) -> ReceptionReply | None:
    if not store_ids:
        return None
    result: ReceptionReply | None = await session.scalar(
        select(ReceptionReply).where(ReceptionReply.id == item_id, ReceptionReply.store_id.in_(store_ids))
    )
    return result


async def list_replies(
    session: AsyncSession,
    store_id: uuid.UUID,
    scope: str,
    owner_id: uuid.UUID | None,
    group_id: uuid.UUID | None,
    q: str | None,
    page: int,
    page_size: int,
    shortcut: str | None = None,
) -> tuple[list[ReceptionReply], int]:
    filters = [ReceptionReply.store_id == store_id, ReceptionReply.scope == scope]
    if scope == "personal":
        filters.append(ReceptionReply.owner_user_id == owner_id)
    if group_id:
        filters.append(ReceptionReply.group_id == group_id)
    if shortcut:
        filters.append(ReceptionReply.shortcut == shortcut)
    if q:
        # 关键词只用于参数化模糊查找，通配符按普通字符处理。
        pattern = f"%{_escape_like(q)}%"
        filters.append(
            or_(
                ReceptionReply.shortcut.ilike(pattern, escape="\\"),
                cast(ReceptionReply.tags, Text).ilike(pattern, escape="\\"),
                cast(ReceptionReply.messages, Text).ilike(pattern, escape="\\"),
            )
        )
    total = await session.scalar(select(func.count()).select_from(ReceptionReply).where(*filters)) or 0
    items = (
        await session.scalars(
            select(ReceptionReply)
            .where(*filters)
            .order_by(ReceptionReply.sort_order, ReceptionReply.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return list(items), total


async def shortcut_exists(
    session: AsyncSession,
    store_id: uuid.UUID,
    scope: str,
    owner_id: uuid.UUID | None,
    shortcut: str,
    exclude_id: uuid.UUID | None = None,
) -> bool:
    filters = [
        ReceptionReply.store_id == store_id,
        ReceptionReply.scope == scope,
        ReceptionReply.shortcut == shortcut,
    ]
    if scope == "personal":
        filters.append(ReceptionReply.owner_user_id == owner_id)
    if exclude_id:
        filters.append(ReceptionReply.id != exclude_id)
    return bool(await session.scalar(select(ReceptionReply.id).where(*filters).limit(1)))


async def find_policy(session: AsyncSession, item_id: uuid.UUID, store_ids: set[uuid.UUID]) -> ReceptionPolicy | None:
    if not store_ids:
        return None
    result: ReceptionPolicy | None = await session.scalar(
        select(ReceptionPolicy)
        .join(ReceptionPolicyStore)
        .where(ReceptionPolicy.id == item_id, ReceptionPolicyStore.store_id.in_(store_ids))
        .options(selectinload(ReceptionPolicy.stores))
    )
    return result


async def list_policies(
    session: AsyncSession,
    store_id: uuid.UUID,
    kind: str,
    allowed_store_ids: set[uuid.UUID],
    page: int,
    page_size: int,
) -> tuple[list[ReceptionPolicy], int]:
    unauthorized = select(ReceptionPolicyStore.policy_id).where(ReceptionPolicyStore.store_id.not_in(allowed_store_ids))
    filters = [
        ReceptionPolicyStore.store_id == store_id,
        ReceptionPolicy.kind == kind,
        ReceptionPolicy.id.not_in(unauthorized),
    ]
    total = (
        await session.scalar(
            select(func.count()).select_from(ReceptionPolicy).join(ReceptionPolicyStore).where(*filters)
        )
        or 0
    )
    items = (
        await session.scalars(
            select(ReceptionPolicy)
            .join(ReceptionPolicyStore)
            .where(*filters)
            .options(selectinload(ReceptionPolicy.stores))
            .order_by(ReceptionPolicy.sort_order, ReceptionPolicy.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return list(items), total


async def find_mutation(session: AsyncSession, actor_id: uuid.UUID, key_hash: str) -> ReceptionMutation | None:
    result: ReceptionMutation | None = await session.scalar(
        select(ReceptionMutation).where(ReceptionMutation.actor_id == actor_id, ReceptionMutation.key_hash == key_hash)
    )
    return result
