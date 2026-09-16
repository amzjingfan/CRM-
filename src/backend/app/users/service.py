"""团队成员、角色范围和管理员保护规则。"""

import uuid
from collections import defaultdict

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.repository import find_role_by_code
from app.auth.security import hash_password
from app.auth.store_access import allowed_store_ids, ensure_store_access
from app.shared.database.base import Role, User, user_roles
from app.shared.exceptions.errors import AppError, ErrorCode
from app.users.schemas import TeamMemberCreate, TeamMemberUpdate, TeamMemberView, TeamRoleAssignment


async def _assignment_rows(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[TeamRoleAssignment]]:
    grouped: dict[uuid.UUID, list[TeamRoleAssignment]] = defaultdict(list)
    if not user_ids:
        return grouped
    rows = (
        await session.execute(
            select(user_roles.c.user_id, Role.code, user_roles.c.store_id)
            .join(Role, Role.id == user_roles.c.role_id)
            .where(user_roles.c.user_id.in_(user_ids))
            .order_by(Role.code, user_roles.c.store_id)
        )
    ).all()
    for user_id, role, store_id in rows:
        grouped[user_id].append(TeamRoleAssignment(role=role, store_id=store_id))
    return grouped


async def _views(session: AsyncSession, users: list[User]) -> list[TeamMemberView]:
    assignments = await _assignment_rows(session, [item.id for item in users])
    return [
        TeamMemberView(
            id=item.id,
            name=item.name,
            email=item.email,
            status=item.status,  # type: ignore[arg-type]
            assignments=assignments.get(item.id, []),
            last_login_at=item.last_login_at,
            created_at=item.created_at,
        )
        for item in users
    ]


async def list_team(session: AsyncSession, actor: User) -> list[TeamMemberView]:
    store_ids = await allowed_store_ids(session, actor)
    role_codes = {role.code for role in actor.roles}
    if "admin" in role_codes:
        users = list((await session.scalars(select(User).order_by(User.created_at, User.id))).all())
        return await _views(session, users)
    if not store_ids:
        return []
    user_ids = list(
        (
            await session.scalars(select(user_roles.c.user_id).where(user_roles.c.store_id.in_(store_ids)).distinct())
        ).all()
    )
    users = list((await session.scalars(select(User).where(User.id.in_(user_ids)).order_by(User.created_at))).all())
    return await _views(session, users)


async def _validate_assignments(
    session: AsyncSession,
    actor: User,
    assignments: list[TeamRoleAssignment],
) -> list[tuple[Role, uuid.UUID | None]]:
    seen: set[tuple[str, uuid.UUID | None]] = set()
    result: list[tuple[Role, uuid.UUID | None]] = []
    for assignment in assignments:
        key = (assignment.role, assignment.store_id)
        if key in seen:
            continue
        seen.add(key)
        if assignment.store_id is not None:
            await ensure_store_access(session, actor, assignment.store_id)
        role = await find_role_by_code(session, assignment.role)
        if role is None:
            raise AppError(ErrorCode.VALIDATION_ERROR, "角色不存在", 422)
        result.append((role, assignment.store_id))
    return result


async def _replace_assignments(
    session: AsyncSession,
    target: User,
    assignments: list[tuple[Role, uuid.UUID | None]],
) -> None:
    await session.execute(delete(user_roles).where(user_roles.c.user_id == target.id))
    for role, store_id in assignments:
        await session.execute(
            user_roles.insert().values(
                id=uuid.uuid4(),
                user_id=target.id,
                role_id=role.id,
                store_id=store_id,
            )
        )


async def _active_system_admin_count(session: AsyncSession) -> int:
    value = await session.scalar(
        select(func.count(func.distinct(User.id)))
        .select_from(User)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(User.status == "active", Role.code == "admin", user_roles.c.store_id.is_(None))
    )
    return int(value or 0)


async def create_member(
    session: AsyncSession,
    actor: User,
    payload: TeamMemberCreate,
) -> TeamMemberView:
    assignments = await _validate_assignments(session, actor, payload.assignments)
    member = User(
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.temporary_password),
        name=payload.name,
        status="active",
    )
    session.add(member)
    try:
        await session.flush()
        await _replace_assignments(session, member, assignments)
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "员工邮箱已存在", 409) from exc
    session.add(
        AuditLog(
            actor_type="user",
            actor_id=actor.id,
            action="team.member.create",
            resource_type="user",
            resource_id=member.id,
            after_data={"email": member.email, "assignment_count": len(assignments)},
            result="succeeded",
        )
    )
    await session.commit()
    await session.refresh(member)
    return (await _views(session, [member]))[0]


async def update_member(
    session: AsyncSession,
    actor: User,
    member_id: uuid.UUID,
    payload: TeamMemberUpdate,
) -> TeamMemberView:
    member = await session.get(User, member_id)
    if member is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "员工不存在", 404)
    if payload.name is not None:
        member.name = payload.name
    if payload.assignments is not None:
        assignments = await _validate_assignments(session, actor, payload.assignments)
        existing_admin = await session.scalar(
            select(user_roles.c.id)
            .join(Role, Role.id == user_roles.c.role_id)
            .where(user_roles.c.user_id == member.id, Role.code == "admin", user_roles.c.store_id.is_(None))
        )
        remains_admin = any(role.code == "admin" and store_id is None for role, store_id in assignments)
        if existing_admin is not None and not remains_admin and await _active_system_admin_count(session) <= 1:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "不能移除最后一个有效管理员", 409)
        await _replace_assignments(session, member, assignments)
    session.add(
        AuditLog(
            actor_type="user",
            actor_id=actor.id,
            action="team.member.update",
            resource_type="user",
            resource_id=member.id,
            after_data={"name": member.name},
            result="succeeded",
        )
    )
    await session.commit()
    return (await _views(session, [member]))[0]


async def disable_member(session: AsyncSession, actor: User, member_id: uuid.UUID) -> None:
    if member_id == actor.id:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "不能禁用当前登录用户", 409)
    member = await session.get(User, member_id)
    if member is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "员工不存在", 404)
    is_admin = await session.scalar(
        select(user_roles.c.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(user_roles.c.user_id == member.id, Role.code == "admin", user_roles.c.store_id.is_(None))
    )
    if is_admin is not None and member.status == "active" and await _active_system_admin_count(session) <= 1:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "不能禁用最后一个有效管理员", 409)
    member.status = "disabled"
    session.add(
        AuditLog(
            actor_type="user",
            actor_id=actor.id,
            action="team.member.disable",
            resource_type="user",
            resource_id=member.id,
            before_data={"status": "active"},
            after_data={"status": "disabled"},
            result="succeeded",
        )
    )
    await session.commit()


async def delete_member_permanently(session: AsyncSession, actor: User, member_id: uuid.UUID) -> None:
    """永久删除已禁用且没有受保护业务引用的员工。"""
    if member_id == actor.id:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "不能删除当前登录用户", 409)
    member = await session.get(User, member_id)
    if member is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "员工不存在", 404)
    if member.status != "disabled":
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "请先禁用员工，再执行永久删除", 409)

    session.add(
        AuditLog(
            actor_type="user",
            actor_id=actor.id,
            action="team.member.delete",
            resource_type="user",
            resource_id=member.id,
            before_data={"email": member.email, "status": member.status},
            after_data={"deleted": True},
            result="succeeded",
        )
    )
    await session.delete(member)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        # 已产生知识、营销等受保护业务记录的员工必须保留禁用身份，避免历史责任人丢失。
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "该员工已有业务记录，只能保留已禁用状态", 409) from exc
