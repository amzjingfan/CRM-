"""部门多店咨询派单：仅调整 CRM 会话归属，不触发平台发送。"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids_for_permission
from app.conversations.models import Conversation
from app.reception_assignment.models import ReceptionDepartmentAgent, ReceptionDepartmentConfig
from app.reception_assignment.rules import AssignmentCandidate, choose_candidate
from app.shared.database.base import User, UserLoginSession
from app.stores.models import Store
from app.users.models import department_members, department_stores

OFFLINE_REQUEUE_GRACE = timedelta(minutes=2)


async def dispatch_conversation(
    session: AsyncSession, conversation_id: uuid.UUID, *, now: datetime | None = None
) -> uuid.UUID | None:
    """部门统一开关下按店铺授权选人；人工归属绝不自动覆盖。"""
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
    store_active = await session.scalar(
        select(Store.id).where(Store.id == conversation.store_id, Store.status == "active", Store.deleted_at.is_(None))
    )
    if store_active is None:
        conversation.assignment_wait_reason = "store_inactive"
        return None
    department_id = await session.scalar(
        select(department_stores.c.department_id).where(department_stores.c.store_id == conversation.store_id)
    )
    if department_id is None:
        conversation.assignment_wait_reason = "department_unlinked"
        conversation.next_assignment_attempt_at = instant + timedelta(seconds=30)
        return None
    # 同部门所有店铺共用这把锁，跨店负载计数及归属写入串行化。
    config = await session.scalar(
        select(ReceptionDepartmentConfig)
        .where(ReceptionDepartmentConfig.department_id == department_id)
        .with_for_update()
    )
    if config is None or not config.enabled:
        conversation.assignment_wait_reason = "not_configured" if config is None else "disabled"
        return None
    candidates = (
        await session.execute(
            select(ReceptionDepartmentAgent, User)
            .join(User, User.id == ReceptionDepartmentAgent.user_id)
            .join(
                department_members,
                and_(
                    department_members.c.user_id == User.id,
                    department_members.c.department_id == department_id,
                ),
            )
            .where(
                ReceptionDepartmentAgent.department_id == department_id,
                ReceptionDepartmentAgent.auto_enabled.is_(True),
                User.status == "active",
            )
        )
    ).all()
    eligible = [
        (agent, user)
        for agent, user in candidates
        if conversation.store_id in await allowed_store_ids_for_permission(session, user, "workspace.reply")
    ]
    if not eligible:
        conversation.assignment_wait_reason = "no_eligible_agent"
        conversation.next_assignment_attempt_at = instant + timedelta(seconds=30)
        return None
    department_store_ids = select(department_stores.c.store_id).where(
        department_stores.c.department_id == department_id
    )
    pending_rows = (
        await session.execute(
            select(Conversation.assigned_user_id, func.count(Conversation.id))
            .where(
                Conversation.store_id.in_(department_store_ids),
                Conversation.status.in_(["active", "transferred"]),
                Conversation.awaiting_reply_since.is_not(None),
                Conversation.assigned_user_id.is_not(None),
            )
            .group_by(Conversation.assigned_user_id)
        )
    ).all()
    pending: dict[uuid.UUID | None, int] = {row[0]: row[1] for row in pending_rows}
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
    online_ids = set(
        (
            await session.scalars(
                select(UserLoginSession.user_id).where(
                    UserLoginSession.user_id.in_([user.id for _, user in eligible]),
                    UserLoginSession.revoked_at.is_(None),
                    UserLoginSession.expires_at > instant,
                )
            )
        ).all()
    )
    decision = choose_candidate(
        [
            AssignmentCandidate(
                user_id=user.id,
                pending_count=pending.get(user.id, 0),
                online=user.id in online_ids,
                last_assigned_at=agent.last_assigned_at,
            )
            for agent, user in eligible
        ],
        now=instant,
        recent_responder_id=recent[0] if recent else None,
        recent_reply_at=recent[1] if recent else None,
    )
    if decision is None:
        conversation.assignment_wait_reason = "no_online_agent"
        conversation.next_assignment_attempt_at = instant + timedelta(seconds=30)
        return None
    selected = next(agent for agent, _ in eligible if agent.user_id == decision.user_id)
    conversation.assigned_user_id = decision.user_id
    conversation.assignment_source = "auto"
    conversation.assignment_wait_reason = None
    conversation.next_assignment_attempt_at = None
    selected.last_assigned_at = instant
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
    """限量重试部门多店队列；首次历史回填不会入队。"""
    instant = now or datetime.now(UTC)
    ids = (
        await session.scalars(
            select(Conversation.id)
            .join(department_stores, department_stores.c.store_id == Conversation.store_id)
            .join(
                ReceptionDepartmentConfig, ReceptionDepartmentConfig.department_id == department_stores.c.department_id
            )
            .where(
                ReceptionDepartmentConfig.enabled.is_(True),
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
    """退出或会话过期两分钟后重派；人工归属保持不变。"""
    instant = now or datetime.now(UTC)
    stale_before = instant - OFFLINE_REQUEUE_GRACE
    was_online = exists(
        select(UserLoginSession.id).where(
            UserLoginSession.user_id == Conversation.assigned_user_id,
            UserLoginSession.expires_at > stale_before,
            or_(UserLoginSession.revoked_at.is_(None), UserLoginSession.revoked_at > stale_before),
        )
    )
    ids = (
        await session.scalars(
            select(Conversation.id)
            .join(department_stores, department_stores.c.store_id == Conversation.store_id)
            .join(
                ReceptionDepartmentConfig, ReceptionDepartmentConfig.department_id == department_stores.c.department_id
            )
            .where(
                ReceptionDepartmentConfig.enabled.is_(True),
                Conversation.status.in_(["active", "transferred"]),
                Conversation.assignment_source == "auto",
                Conversation.assigned_user_id.is_not(None),
                Conversation.awaiting_reply_since.is_not(None),
                ~was_online,
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
