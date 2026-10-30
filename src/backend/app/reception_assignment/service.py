"""部门统一派单配置与登录在线状态。"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids, allowed_store_ids_for_permission
from app.conversations.models import Conversation
from app.reception_assignment.models import ReceptionDepartmentAgent, ReceptionDepartmentConfig
from app.reception_assignment.schemas import (
    ReceptionDepartmentAgentView,
    ReceptionDepartmentInput,
    ReceptionDepartmentView,
)
from app.shared.database.base import Role, User, UserLoginSession, user_roles
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import Store
from app.users.models import department_members, department_stores


async def _department_stores(session: AsyncSession, actor: User, department_id: uuid.UUID) -> list[uuid.UUID]:
    store_ids = list(
        (
            await session.scalars(
                select(department_stores.c.store_id)
                .join(Store, Store.id == department_stores.c.store_id)
                .where(
                    department_stores.c.department_id == department_id,
                    Store.status == "active",
                    Store.deleted_at.is_(None),
                )
            )
        ).all()
    )
    if not store_ids or not set(store_ids).issubset(await allowed_store_ids(session, actor, "settings.team")):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "部门不存在或无权管理", 404)
    return store_ids


async def get_department_reception(
    session: AsyncSession, actor: User, department_id: uuid.UUID
) -> ReceptionDepartmentView:
    store_ids = await _department_stores(session, actor, department_id)
    config = await session.get(ReceptionDepartmentConfig, department_id)
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
            await session.scalars(
                select(ReceptionDepartmentAgent).where(ReceptionDepartmentAgent.department_id == department_id)
            )
        ).all()
    }
    now = datetime.now(UTC)
    online_ids = set(
        (
            await session.scalars(
                select(UserLoginSession.user_id).where(
                    UserLoginSession.user_id.in_([user_id for user_id, _, _ in members]),
                    UserLoginSession.revoked_at.is_(None),
                    UserLoginSession.expires_at > now,
                )
            )
        ).all()
    )
    agents = []
    for user_id, name, status in members:
        user = await session.get(User, user_id)
        eligible = (
            sorted(
                set(store_ids).intersection(await allowed_store_ids_for_permission(session, user, "workspace.reply")),
                key=str,
            )
            if user is not None and status == "active"
            else []
        )
        agents.append(
            ReceptionDepartmentAgentView(
                user_id=user_id,
                name=name,
                active=bool(eligible),
                eligible_store_ids=eligible,
                auto_enabled=agent_configs[user_id].auto_enabled if user_id in agent_configs else False,
                online=user_id in online_ids and status == "active",
            )
        )
    queue_count = int(
        await session.scalar(
            select(func.count(Conversation.id)).where(
                Conversation.store_id.in_(store_ids),
                Conversation.status.in_(["active", "transferred"]),
                Conversation.awaiting_reply_since.is_not(None),
                Conversation.assigned_user_id.is_(None),
            )
        )
        or 0
    )
    reasons = (
        await session.execute(
            select(Conversation.assignment_wait_reason, func.count(Conversation.id))
            .where(
                Conversation.store_id.in_(store_ids),
                Conversation.status.in_(["active", "transferred"]),
                Conversation.awaiting_reply_since.is_not(None),
                Conversation.assigned_user_id.is_(None),
            )
            .group_by(Conversation.assignment_wait_reason)
        )
    ).all()
    return ReceptionDepartmentView(
        department_id=department_id,
        store_ids=store_ids,
        enabled=config.enabled if config else False,
        queue_count=queue_count,
        queue_reasons={reason or "pending": count for reason, count in reasons},
        agents=agents,
    )


async def configure_department_reception(
    session: AsyncSession, actor: User, department_id: uuid.UUID, payload: ReceptionDepartmentInput
) -> ReceptionDepartmentView:
    """一次保存部门开关和参与名单；不改变角色、店铺授权或买家消息。"""
    admin_id = await session.scalar(
        select(user_roles.c.user_id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(user_roles.c.user_id == actor.id, user_roles.c.store_id.is_(None), Role.code == "admin")
    )
    if admin_id is None:
        raise AppError(ErrorCode.PERMISSION_DENIED, "只有管理员可配置接待", 403)
    await _department_stores(session, actor, department_id)
    current_view = await get_department_reception(session, actor, department_id)
    by_user = {agent.user_id: agent for agent in current_view.agents}
    if any(item.user_id not in by_user for item in payload.agents):
        raise AppError(ErrorCode.VALIDATION_ERROR, "接待客服必须属于负责部门", 422)
    if any(item.auto_enabled and not by_user[item.user_id].active for item in payload.agents):
        raise AppError(ErrorCode.VALIDATION_ERROR, "接待客服缺少部门店铺回复权限", 422)
    config = await session.scalar(
        select(ReceptionDepartmentConfig)
        .where(ReceptionDepartmentConfig.department_id == department_id)
        .with_for_update()
    )
    if config is None:
        config = ReceptionDepartmentConfig(department_id=department_id)
        session.add(config)
    before_enabled = config.enabled
    config.enabled = payload.enabled
    old = {
        item.user_id: item
        for item in (
            await session.scalars(
                select(ReceptionDepartmentAgent).where(ReceptionDepartmentAgent.department_id == department_id)
            )
        ).all()
    }
    before_agents = [str(item.user_id) for item in old.values() if item.auto_enabled]
    for item in old.values():
        item.auto_enabled = False
    for agent_input in payload.agents:
        setting = old.get(agent_input.user_id)
        if setting is None:
            setting = ReceptionDepartmentAgent(department_id=department_id, user_id=agent_input.user_id)
            session.add(setting)
        setting.auto_enabled = agent_input.auto_enabled
    session.add(
        AuditLog(
            actor_type="user",
            actor_id=actor.id,
            action="reception.assignment.configure",
            resource_type="department",
            resource_id=department_id,
            before_data={"enabled": before_enabled, "agents": sorted(before_agents)},
            after_data={
                "enabled": payload.enabled,
                "agents": sorted(str(item.user_id) for item in payload.agents if item.auto_enabled),
            },
            result="succeeded",
        )
    )
    await session.commit()
    return await get_department_reception(session, actor, department_id)
