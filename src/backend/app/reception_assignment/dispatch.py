"""店铺咨询派单：仅修改 CRM 会话归属，不触发平台发送。"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.conversations.models import Conversation
from app.reception_assignment.models import ReceptionAgentConfig, ReceptionStoreConfig
from app.reception_assignment.rules import PRESENCE_TTL, AssignmentCandidate, choose_candidate
from app.shared.database.base import Permission, Role, User, role_permissions, user_roles
from app.users.models import department_members, department_stores

OFFLINE_REQUEUE_GRACE = timedelta(minutes=2)


async def dispatch_conversation(
    session: AsyncSession, conversation_id: uuid.UUID, *, now: datetime | None = None
) -> uuid.UUID | None:
    """锁定会话和店铺配置后选择负责人；人工归属永不被自动覆盖。"""
    instant = now or datetime.now(UTC)
    conversation = await session.scalar(
        select(Conversation).where(Conversation.id == conversation_id).with_for_update()
    )
    if conversation is None:
        return None
    if conversation.assigned_user_id is not None:
        return conversation.assigned_user_id
    if conversation.status not in ("active", "transferred") or conversation.awaiting_reply_since is None:
        return None
    # 同店所有派单都锁此行，使容量计数与写入串行化。
    store_config = await session.scalar(
        select(ReceptionStoreConfig).where(ReceptionStoreConfig.store_id == conversation.store_id).with_for_update()
    )
    if store_config is None or not store_config.enabled:
        conversation.assignment_wait_reason = "not_configured" if store_config is None else "disabled"
        return None
    department_store_id = await session.scalar(
        select(department_stores.c.store_id).where(
            department_stores.c.department_id == store_config.department_id,
            department_stores.c.store_id == conversation.store_id,
        )
    )
    if department_store_id is None:
        conversation.assignment_wait_reason = "department_unlinked"
        conversation.next_assignment_attempt_at = instant + timedelta(seconds=30)
        return None
    eligible_rows = (
        await session.execute(
            select(ReceptionAgentConfig, User)
            .join(User, User.id == ReceptionAgentConfig.user_id)
            .join(department_members, department_members.c.user_id == User.id)
            .join(user_roles, user_roles.c.user_id == User.id)
            .join(Role, Role.id == user_roles.c.role_id)
            .join(role_permissions, role_permissions.c.role_id == Role.id)
            .join(Permission, Permission.id == role_permissions.c.permission_id)
            .where(
                ReceptionAgentConfig.store_id == conversation.store_id,
                ReceptionAgentConfig.auto_enabled.is_(True),
                User.status == "active",
                department_members.c.department_id == store_config.department_id,
                user_roles.c.store_id == conversation.store_id,
                Permission.code == "workspace.reply",
            )
            .distinct()
        )
    ).all()
    if not eligible_rows:
        conversation.assignment_wait_reason = "no_eligible_agent"
        conversation.next_assignment_attempt_at = instant + timedelta(seconds=30)
        return None
    pending_rows = (
        await session.execute(
            select(Conversation.assigned_user_id, func.count(Conversation.id))
            .where(
                Conversation.store_id == conversation.store_id,
                Conversation.status.in_(["active", "transferred"]),
                Conversation.awaiting_reply_since.is_not(None),
                Conversation.assigned_user_id.is_not(None),
            )
            .group_by(Conversation.assigned_user_id)
        )
    ).all()
    pending = {user_id: count for user_id, count in pending_rows}
    recent = (
        await session.execute(
            select(Conversation.last_human_responder_id, Conversation.last_human_replied_at)
            .where(
                Conversation.store_id == conversation.store_id,
                Conversation.customer_id == conversation.customer_id,
                Conversation.last_human_responder_id.is_not(None),
                Conversation.last_human_replied_at.is_not(None),
            )
            .order_by(Conversation.last_human_replied_at.desc())
            .limit(1)
        )
    ).first()
    decision = choose_candidate(
        [
            AssignmentCandidate(
                user_id=agent.user_id,
                pending_count=pending.get(agent.user_id, 0),
                capacity=agent.capacity,
                last_seen_at=agent.last_heartbeat_at,
                last_assigned_at=agent.last_assigned_at,
                accepting=agent.accepting,
            )
            for agent, _user in eligible_rows
        ],
        now=instant,
        recent_responder_id=recent[0] if recent else None,
        recent_reply_at=recent[1] if recent else None,
    )
    if decision is None:
        online = any(
            item.accepting
            and item.last_heartbeat_at is not None
            and instant - PRESENCE_TTL <= item.last_heartbeat_at <= instant + timedelta(seconds=5)
            for item, _user in eligible_rows
        )
        conversation.assignment_wait_reason = "all_at_capacity" if online else "no_online_agent"
        conversation.next_assignment_attempt_at = instant + timedelta(seconds=30)
        return None
    agent = next(config for config, _user in eligible_rows if config.user_id == decision.user_id)
    conversation.assigned_user_id = decision.user_id
    conversation.assignment_source = "auto"
    conversation.assignment_wait_reason = None
    conversation.next_assignment_attempt_at = None
    agent.last_assigned_at = instant
    session.add(
        AuditLog(
            store_id=conversation.store_id,
            actor_type="system",
            action="conversation.assign.auto",
            resource_type="conversation",
            resource_id=conversation.id,
            after_data={"assigned_user_id": str(decision.user_id), "reason": decision.reason},
            result="succeeded",
        )
    )
    await session.flush()
    return decision.user_id


async def dispatch_queued(session: AsyncSession, *, now: datetime | None = None, limit: int = 50) -> int:
    """限量重试已开启店铺的新咨询；首次历史回填不会进入队列。"""
    instant = now or datetime.now(UTC)
    ids = (
        await session.scalars(
            select(Conversation.id)
            .join(ReceptionStoreConfig, ReceptionStoreConfig.store_id == Conversation.store_id)
            .where(
                ReceptionStoreConfig.enabled.is_(True),
                Conversation.status.in_(["active", "transferred"]),
                Conversation.assigned_user_id.is_(None),
                Conversation.awaiting_reply_since.is_not(None),
                or_(
                    Conversation.next_assignment_attempt_at.is_(None),
                    Conversation.next_assignment_attempt_at <= instant,
                ),
            )
            .order_by(Conversation.next_assignment_attempt_at.asc().nullsfirst(), Conversation.awaiting_reply_since)
            .with_for_update(of=Conversation, skip_locked=True)
            .limit(limit)
        )
    ).all()
    assigned = 0
    for conversation_id in ids:
        if await dispatch_conversation(session, conversation_id, now=instant) is not None:
            assigned += 1
    return assigned


async def requeue_offline_auto_assignments(
    session: AsyncSession, *, now: datetime | None = None, limit: int = 50
) -> int:
    """离线宽限期后重派自动归属；人工归属和已回复会话保持原样。"""
    instant = now or datetime.now(UTC)
    stale_before = instant - OFFLINE_REQUEUE_GRACE
    ids = (
        await session.scalars(
            select(Conversation.id)
            .join(ReceptionStoreConfig, ReceptionStoreConfig.store_id == Conversation.store_id)
            .outerjoin(
                ReceptionAgentConfig,
                and_(
                    ReceptionAgentConfig.store_id == Conversation.store_id,
                    ReceptionAgentConfig.user_id == Conversation.assigned_user_id,
                ),
            )
            .where(
                ReceptionStoreConfig.enabled.is_(True),
                Conversation.status.in_(["active", "transferred"]),
                Conversation.assignment_source == "auto",
                Conversation.assigned_user_id.is_not(None),
                Conversation.awaiting_reply_since.is_not(None),
                or_(
                    ReceptionAgentConfig.last_heartbeat_at.is_(None),
                    ReceptionAgentConfig.last_heartbeat_at < stale_before,
                ),
            )
            .order_by(Conversation.awaiting_reply_since, Conversation.id)
            .with_for_update(of=Conversation, skip_locked=True)
            .limit(limit)
        )
    ).all()
    reassigned = 0
    for conversation_id in ids:
        conversation = await session.get(Conversation, conversation_id)
        if conversation is None or conversation.assigned_user_id is None or conversation.assignment_source != "auto":
            continue
        previous_owner = conversation.assigned_user_id
        # 与首次派单及管理员配置保持 store -> agent 的锁顺序，避免互等。
        store_config = await session.scalar(
            select(ReceptionStoreConfig).where(ReceptionStoreConfig.store_id == conversation.store_id).with_for_update()
        )
        if store_config is None or not store_config.enabled:
            continue
        setting = await session.scalar(
            select(ReceptionAgentConfig)
            .where(
                ReceptionAgentConfig.store_id == conversation.store_id,
                ReceptionAgentConfig.user_id == previous_owner,
            )
            .with_for_update()
        )
        if setting is not None and setting.last_heartbeat_at is not None and setting.last_heartbeat_at >= stale_before:
            continue
        conversation.assigned_user_id = None
        conversation.assignment_source = None
        session.add(
            AuditLog(
                store_id=conversation.store_id,
                actor_type="system",
                action="conversation.assign.auto_requeue",
                resource_type="conversation",
                resource_id=conversation.id,
                before_data={"assigned_user_id": str(previous_owner)},
                result="succeeded",
            )
        )
        if await dispatch_conversation(session, conversation.id, now=instant) is not None:
            reassigned += 1
    return reassigned
