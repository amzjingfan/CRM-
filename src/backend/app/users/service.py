"""团队成员、角色范围和管理员保护规则。"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.repository import find_role_by_code
from app.auth.security import hash_password
from app.auth.store_access import ensure_store_access
from app.shared.database.base import Role, User, UserLoginSession, user_roles
from app.shared.exceptions.errors import AppError, ErrorCode
from app.users.models import department_members
from app.users.schemas import TeamMemberCreate, TeamMemberUpdate, TeamMemberView, TeamRoleAssignment, TeamRoleView


async def _assignment_rows(session: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[TeamRoleView]]:
    grouped: dict[uuid.UUID, list[TeamRoleView]] = defaultdict(list)
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
        grouped[user_id].append(TeamRoleView(role=role, store_id=store_id))
    return grouped


async def _views(session: AsyncSession, users: list[User]) -> list[TeamMemberView]:
    assignments = await _assignment_rows(session, [item.id for item in users])
    departments: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    if users:
        rows = (
            await session.execute(
                select(department_members.c.user_id, department_members.c.department_id).where(
                    department_members.c.user_id.in_([item.id for item in users])
                )
            )
        ).all()
        for user_id, department_id in rows:
            departments[user_id].append(department_id)
    return [
        TeamMemberView(
            id=item.id,
            login_name=item.login_name,
            name=item.name,
            email=item.email,
            phone=item.phone,
            timezone=item.timezone,
            max_concurrent_sessions=item.max_concurrent_sessions,
            status=item.status,  # type: ignore[arg-type]
            assignments=assignments.get(item.id, []),
            department_ids=departments.get(item.id, []),
            last_login_at=item.last_login_at,
            created_at=item.created_at,
        )
        for item in users
    ]


async def list_team(session: AsyncSession, actor: User) -> list[TeamMemberView]:
    """所有已登录员工可见账号目录，只有管理员看到联系方式并可修改。"""
    users = list((await session.scalars(select(User).order_by(User.created_at, User.id))).all())
    views = await _views(session, users)
    system_admin = await session.scalar(
        select(user_roles.c.user_id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(user_roles.c.user_id == actor.id, Role.code == "admin", user_roles.c.store_id.is_(None))
    )
    if system_admin is None:
        for item in views:
            # 旧账号只用邮箱登录；目录仍显示登录标识，但不暴露独立联系方式。
            item.login_name = item.login_name or item.email
            item.email = None
            item.phone = None
            item.last_login_at = None
    return views


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
    if payload.department_id is not None:
        from app.users.department_service import _visible_department

        _, department_store_ids = await _visible_department(session, actor, payload.department_id)
        if not any(store_id is None or store_id in department_store_ids for _, store_id in assignments):
            raise AppError(ErrorCode.VALIDATION_ERROR, "账号店铺范围与部门不匹配", 422)
    member = User(
        login_name=payload.login_name,
        email=str(payload.email).lower() if payload.email else None,
        password_hash=hash_password(payload.temporary_password),
        name=payload.name,
        phone=payload.phone,
        timezone=payload.timezone,
        max_concurrent_sessions=payload.max_concurrent_sessions,
        auth_version=0,
        status="active",
    )
    session.add(member)
    try:
        await session.flush()
        await _replace_assignments(session, member, assignments)
        if payload.department_id is not None:
            await session.execute(
                department_members.insert().values(department_id=payload.department_id, user_id=member.id)
            )
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "登录账号或邮箱已存在", 409) from exc
    session.add(
        AuditLog(
            actor_type="user",
            actor_id=actor.id,
            action="team.member.create",
            resource_type="user",
            resource_id=member.id,
            after_data={
                "login_name": member.login_name,
                "assignments": [
                    {"role": role.code, "store_id": str(store_id) if store_id else None}
                    for role, store_id in assignments
                ],
            },
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
    # 与自动投递保持用户→角色的锁顺序，撤权提交后不可继续使用旧授权。
    member = await session.get(User, member_id, with_for_update=True, populate_existing=True)
    if member is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "员工不存在", 404)
    role_change_before: list[dict[str, str | None]] | None = None
    role_change_after: list[dict[str, str | None]] | None = None
    if payload.name is not None:
        member.name = payload.name
    if "email" in payload.model_fields_set:
        if payload.email is None and member.login_name is None:
            raise AppError(ErrorCode.VALIDATION_ERROR, "旧账号必须保留登录邮箱", 422)
        member.email = str(payload.email).lower() if payload.email else None
    if "phone" in payload.model_fields_set:
        member.phone = payload.phone
    if payload.timezone is not None:
        member.timezone = payload.timezone
    if payload.max_concurrent_sessions is not None:
        member.max_concurrent_sessions = payload.max_concurrent_sessions
    if payload.assignments is not None:
        assignments = await _validate_assignments(session, actor, payload.assignments)
        role_change_before = [
            {"role": item.role, "store_id": str(item.store_id) if item.store_id else None}
            for item in (await _assignment_rows(session, [member.id]))[member.id]
        ]
        role_change_after = [
            {"role": role.code, "store_id": str(store_id) if store_id else None} for role, store_id in assignments
        ]
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
            before_data={"assignments": role_change_before} if role_change_before is not None else None,
            after_data={
                "name": member.name,
                "email_present": member.email is not None,
                **({"assignments": role_change_after} if role_change_after is not None else {}),
            },
            result="succeeded",
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "登录邮箱已存在", 409) from exc
    return (await _views(session, [member]))[0]


async def change_member_password(session: AsyncSession, actor: User, member_id: uuid.UUID, password: str) -> None:
    """重置员工密码并使此前全部 Access/Refresh Token 失效。"""
    member = await session.get(User, member_id)
    if member is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "员工不存在", 404)
    member.password_hash = hash_password(password)
    member.auth_version = (member.auth_version or 0) + 1
    await session.execute(
        update(UserLoginSession)
        .where(UserLoginSession.user_id == member_id, UserLoginSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    session.add(
        AuditLog(
            actor_type="user",
            actor_id=actor.id,
            action="team.member.password_change",
            resource_type="user",
            resource_id=member.id,
            after_data={"password_changed": True},
            result="succeeded",
        )
    )
    await session.commit()


async def disable_member(session: AsyncSession, actor: User, member_id: uuid.UUID) -> None:
    if member_id == actor.id:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "不能禁用当前登录用户", 409)
    member = await session.get(User, member_id, with_for_update=True, populate_existing=True)
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
    await session.execute(
        update(UserLoginSession)
        .where(UserLoginSession.user_id == member_id, UserLoginSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
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
