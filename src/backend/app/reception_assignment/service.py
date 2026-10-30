"""接待配置和本人在线状态；部门关系与店铺权限必须同时满足。"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids
from app.conversations.models import Conversation
from app.reception_assignment.models import ReceptionAgentConfig, ReceptionStoreConfig
from app.reception_assignment.rules import PRESENCE_TTL
from app.reception_assignment.schemas import (
    OwnReceptionStoreView,
    ReceptionAgentView,
    ReceptionHeartbeatView,
    ReceptionStoreInput,
    ReceptionStoreView,
)
from app.shared.database.base import Permission, Role, User, role_permissions, user_roles
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import Store
from app.users.models import department_members, department_stores


async def _department_store(session: AsyncSession, actor: User, department_id: uuid.UUID, store_id: uuid.UUID) -> None:
    if store_id not in await allowed_store_ids(session, actor, "settings.team"):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "店铺不存在", 404)
    valid = await session.scalar(
        select(Store.id)
        .join(department_stores, department_stores.c.store_id == Store.id)
        .where(
            Store.id == store_id,
            Store.status == "active",
            Store.deleted_at.is_(None),
            department_stores.c.department_id == department_id,
        )
    )
    if valid is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "部门负责店铺不存在", 404)


async def _reply_user_ids(session: AsyncSession, store_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        (
            await session.scalars(
                select(user_roles.c.user_id)
                .join(Role, Role.id == user_roles.c.role_id)
                .join(role_permissions, role_permissions.c.role_id == Role.id)
                .join(Permission, Permission.id == role_permissions.c.permission_id)
                .where(user_roles.c.store_id == store_id, Permission.code == "workspace.reply")
                .distinct()
            )
        ).all()
    )


async def get_store_reception(
    session: AsyncSession, actor: User, department_id: uuid.UUID, store_id: uuid.UUID
) -> ReceptionStoreView:
    await _department_store(session, actor, department_id, store_id)
    config = await session.get(ReceptionStoreConfig, store_id)
    if config is not None and config.department_id != department_id:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "店铺已归另一部门接待", 409)
    members = (
        await session.execute(
            select(User.id, User.name, User.status)
            .join(department_members, department_members.c.user_id == User.id)
            .where(department_members.c.department_id == department_id)
            .order_by(User.name, User.id)
        )
    ).all()
    agent_configs = {
        item.user_id: item
        for item in (
            await session.scalars(select(ReceptionAgentConfig).where(ReceptionAgentConfig.store_id == store_id))
        ).all()
    }
    reply_users = await _reply_user_ids(session, store_id)
    pending_rows = (
        await session.execute(
            select(Conversation.assigned_user_id, func.count(Conversation.id))
            .where(
                Conversation.store_id == store_id,
                Conversation.status.in_(["active", "transferred"]),
                Conversation.awaiting_reply_since.is_not(None),
                Conversation.assigned_user_id.is_not(None),
            )
            .group_by(Conversation.assigned_user_id)
        )
    ).all()
    pending = {user_id: count for user_id, count in pending_rows}
    queue_count = int(
        await session.scalar(
            select(func.count(Conversation.id)).where(
                Conversation.store_id == store_id,
                Conversation.status.in_(["active", "transferred"]),
                Conversation.awaiting_reply_since.is_not(None),
                Conversation.assigned_user_id.is_(None),
            )
        )
        or 0
    )
    queue_reason_rows = (
        await session.execute(
            select(Conversation.assignment_wait_reason, func.count(Conversation.id))
            .where(
                Conversation.store_id == store_id,
                Conversation.status.in_(["active", "transferred"]),
                Conversation.awaiting_reply_since.is_not(None),
                Conversation.assigned_user_id.is_(None),
            )
            .group_by(Conversation.assignment_wait_reason)
        )
    ).all()
    valid_owner_ids = {user_id for user_id, _name, status in members if status == "active" and user_id in reply_users}
    takeover_filter = (
        Conversation.store_id == store_id,
        Conversation.status.in_(["active", "transferred"]),
        Conversation.assignment_source == "manual",
        Conversation.assigned_user_id.is_not(None),
        Conversation.assigned_user_id.not_in(valid_owner_ids),
    )
    takeover_count = int(await session.scalar(select(func.count(Conversation.id)).where(*takeover_filter)) or 0)
    takeover_ids = list(
        (
            await session.scalars(select(Conversation.id).where(*takeover_filter).order_by(Conversation.id).limit(20))
        ).all()
    )
    now = datetime.now(UTC)

    def is_online(user_id: uuid.UUID) -> bool:
        setting = agent_configs.get(user_id)
        seen = setting.last_heartbeat_at if setting else None
        return seen is not None and now - PRESENCE_TTL <= seen <= now

    return ReceptionStoreView(
        store_id=store_id,
        department_id=department_id,
        enabled=config.enabled if config else False,
        queue_count=queue_count,
        queue_reasons={reason or "pending": count for reason, count in queue_reason_rows},
        takeover_count=takeover_count,
        takeover_conversation_ids=takeover_ids,
        agents=[
            ReceptionAgentView(
                user_id=user_id,
                name=name,
                active=status == "active" and user_id in reply_users,
                auto_enabled=agent_configs[user_id].auto_enabled if user_id in agent_configs else False,
                accepting=agent_configs[user_id].accepting if user_id in agent_configs else True,
                capacity=agent_configs[user_id].capacity if user_id in agent_configs else 20,
                pending_count=pending.get(user_id, 0),
                online=is_online(user_id),
                last_heartbeat_at=(agent_configs[user_id].last_heartbeat_at if user_id in agent_configs else None),
            )
            for user_id, name, status in members
        ],
    )


async def configure_store_reception(
    session: AsyncSession,
    actor: User,
    department_id: uuid.UUID,
    store_id: uuid.UUID,
    payload: ReceptionStoreInput,
) -> ReceptionStoreView:
    """管理员一次保存店铺开关与本店接待名单，先验证全部成员。"""
    admin_id = await session.scalar(
        select(user_roles.c.user_id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(user_roles.c.user_id == actor.id, user_roles.c.store_id.is_(None), Role.code == "admin")
    )
    if admin_id is None:
        raise AppError(ErrorCode.PERMISSION_DENIED, "只有管理员可配置接待", 403)
    await _department_store(session, actor, department_id, store_id)
    member_ids = set(
        (
            await session.scalars(
                select(department_members.c.user_id).where(department_members.c.department_id == department_id)
            )
        ).all()
    )
    if any(agent.user_id not in member_ids for agent in payload.agents):
        raise AppError(ErrorCode.VALIDATION_ERROR, "接待客服必须属于负责部门", 422)
    reply_users = await _reply_user_ids(session, store_id)
    if any(agent.auto_enabled and agent.user_id not in reply_users for agent in payload.agents):
        raise AppError(ErrorCode.VALIDATION_ERROR, "接待客服缺少本店回复权限", 422)
    config = await session.scalar(
        select(ReceptionStoreConfig).where(ReceptionStoreConfig.store_id == store_id).with_for_update()
    )
    if config is None:
        config = ReceptionStoreConfig(store_id=store_id, department_id=department_id)
        session.add(config)
    elif config.department_id != department_id:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "店铺已归另一部门接待", 409)
    before_enabled = config.enabled
    config.enabled = payload.enabled
    current = {
        item.user_id: item
        for item in (
            await session.scalars(select(ReceptionAgentConfig).where(ReceptionAgentConfig.store_id == store_id))
        ).all()
    }
    before_agents = [
        {"user_id": str(item.user_id), "auto_enabled": item.auto_enabled, "capacity": item.capacity}
        for item in sorted(current.values(), key=lambda value: str(value.user_id))
    ]
    for item in current.values():
        item.auto_enabled = False
    for agent in payload.agents:
        setting = current.get(agent.user_id)
        if setting is None:
            setting = ReceptionAgentConfig(store_id=store_id, user_id=agent.user_id)
            session.add(setting)
        setting.auto_enabled = agent.auto_enabled
        setting.capacity = agent.capacity
        current[agent.user_id] = setting
    after_agents = [
        {"user_id": str(item.user_id), "auto_enabled": item.auto_enabled, "capacity": item.capacity}
        for item in sorted(current.values(), key=lambda value: str(value.user_id))
    ]
    session.add(
        AuditLog(
            store_id=store_id,
            actor_type="user",
            actor_id=actor.id,
            action="reception.assignment.configure",
            resource_type="store",
            resource_id=store_id,
            before_data={"enabled": before_enabled, "agents": before_agents},
            after_data={"enabled": payload.enabled, "agents": after_agents},
            result="succeeded",
        )
    )
    await session.commit()
    return await get_store_reception(session, actor, department_id, store_id)


async def heartbeat(
    session: AsyncSession, actor: User, store_id: uuid.UUID, *, accepting: bool
) -> ReceptionHeartbeatView:
    """登录客服只能续期或暂停自己的店铺接待资格。"""
    if actor.status != "active" or store_id not in await allowed_store_ids(session, actor, "workspace.reply"):
        raise AppError(ErrorCode.PERMISSION_DENIED, "没有本店接待权限", 403)
    config = await session.scalar(
        select(ReceptionStoreConfig).where(
            ReceptionStoreConfig.store_id == store_id, ReceptionStoreConfig.enabled.is_(True)
        )
    )
    setting = await session.scalar(
        select(ReceptionAgentConfig)
        .where(
            ReceptionAgentConfig.store_id == store_id,
            ReceptionAgentConfig.user_id == actor.id,
            ReceptionAgentConfig.auto_enabled.is_(True),
        )
        .with_for_update()
    )
    member = (
        await session.scalar(
            select(department_members.c.user_id).where(
                department_members.c.department_id == config.department_id,
                department_members.c.user_id == actor.id,
            )
        )
        if config is not None
        else None
    )
    if config is None or setting is None or member is None:
        raise AppError(ErrorCode.PERMISSION_DENIED, "当前店铺未启用本人自动接待", 403)
    if setting.accepting != accepting:
        session.add(
            AuditLog(
                store_id=store_id,
                actor_type="user",
                actor_id=actor.id,
                action="reception.assignment.presence",
                resource_type="user",
                resource_id=actor.id,
                after_data={"accepting": accepting},
                result="succeeded",
            )
        )
    setting.accepting = accepting
    setting.last_heartbeat_at = datetime.now(UTC)
    await session.commit()
    return ReceptionHeartbeatView(
        store_id=store_id, accepting=setting.accepting, last_heartbeat_at=setting.last_heartbeat_at
    )


async def own_reception_stores(session: AsyncSession, actor: User) -> list[OwnReceptionStoreView]:
    """仅返回本人在当前有效店铺的自动接待资格，不暴露其他员工在线状态。"""
    reply_stores = await allowed_store_ids(session, actor, "workspace.reply")
    if not reply_stores or actor.status != "active":
        return []
    rows = (
        (
            await session.execute(
                select(ReceptionAgentConfig)
                .join(ReceptionStoreConfig, ReceptionStoreConfig.store_id == ReceptionAgentConfig.store_id)
                .join(department_stores, department_stores.c.store_id == ReceptionStoreConfig.store_id)
                .join(
                    department_members,
                    department_members.c.department_id == ReceptionStoreConfig.department_id,
                )
                .join(Store, Store.id == ReceptionStoreConfig.store_id)
                .where(
                    ReceptionAgentConfig.user_id == actor.id,
                    ReceptionAgentConfig.store_id.in_(reply_stores),
                    ReceptionAgentConfig.auto_enabled.is_(True),
                    ReceptionStoreConfig.enabled.is_(True),
                    department_stores.c.department_id == ReceptionStoreConfig.department_id,
                    department_members.c.user_id == actor.id,
                    Store.status == "active",
                    Store.deleted_at.is_(None),
                )
                .order_by(ReceptionAgentConfig.store_id)
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    return [
        OwnReceptionStoreView(
            store_id=row.store_id,
            accepting=row.accepting,
            online=(row.last_heartbeat_at is not None and now - PRESENCE_TTL <= row.last_heartbeat_at <= now),
        )
        for row in rows
    ]
