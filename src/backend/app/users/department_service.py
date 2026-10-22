"""部门组织关系管理；不改变用户的店铺角色授权。"""

import uuid
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids, ensure_store_access
from app.shared.database.base import User, user_roles
from app.shared.exceptions.errors import AppError, ErrorCode
from app.users.department_schemas import DepartmentCreate, DepartmentUpdate, DepartmentView
from app.users.models import Department, department_members, department_stores
from app.users.schemas import TeamMemberView
from app.users.service import list_team


async def _visible_department(
    session: AsyncSession, actor: User, department_id: uuid.UUID
) -> tuple[Department, list[uuid.UUID]]:
    department = await session.get(Department, department_id)
    if department is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "部门不存在", 404)
    store_ids = list(
        (
            await session.scalars(
                select(department_stores.c.store_id).where(department_stores.c.department_id == department_id)
            )
        ).all()
    )
    if not set(store_ids).intersection(await allowed_store_ids(session, actor)):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "部门不存在", 404)
    return department, store_ids


async def _view(session: AsyncSession, actor: User, department: Department) -> DepartmentView:
    _, store_ids = await _visible_department(session, actor, department.id)
    allowed = await allowed_store_ids(session, actor)
    return DepartmentView(
        id=department.id,
        name=department.name,
        store_ids=sorted(set(store_ids).intersection(allowed), key=str),
        created_at=department.created_at,
    )


async def list_departments(session: AsyncSession, actor: User) -> list[DepartmentView]:
    allowed = await allowed_store_ids(session, actor)
    if not allowed:
        return []
    departments = list(
        (
            await session.scalars(
                select(Department)
                .join(department_stores)
                .where(department_stores.c.store_id.in_(allowed))
                .distinct()
                .order_by(Department.name)
            )
        ).all()
    )
    return [await _view(session, actor, item) for item in departments]


async def get_department(session: AsyncSession, actor: User, department_id: uuid.UUID) -> DepartmentView:
    department, _ = await _visible_department(session, actor, department_id)
    return await _view(session, actor, department)


async def _validate_stores(session: AsyncSession, actor: User, store_ids: list[uuid.UUID]) -> None:
    for store_id in store_ids:
        await ensure_store_access(session, actor, store_id)


async def create_department(session: AsyncSession, actor: User, payload: DepartmentCreate) -> DepartmentView:
    await _validate_stores(session, actor, payload.store_ids)
    department = Department(name=payload.name.strip())
    session.add(department)
    try:
        await session.flush()
        for store_id in payload.store_ids:
            await session.execute(department_stores.insert().values(department_id=department.id, store_id=store_id))
        session.add(
            AuditLog(
                actor_type="user",
                actor_id=actor.id,
                action="department.create",
                resource_type="department",
                resource_id=department.id,
                after_data={"name": department.name, "store_count": len(payload.store_ids)},
                result="succeeded",
            )
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "部门名称已存在", 409) from exc
    await session.refresh(department)
    return await _view(session, actor, department)


async def update_department(
    session: AsyncSession, actor: User, department_id: uuid.UUID, payload: DepartmentUpdate
) -> DepartmentView:
    department, _ = await _visible_department(session, actor, department_id)
    if payload.name is not None:
        department.name = payload.name.strip()
    if payload.store_ids is not None:
        await _validate_stores(session, actor, payload.store_ids)
        await session.execute(delete(department_stores).where(department_stores.c.department_id == department_id))
        for store_id in payload.store_ids:
            await session.execute(department_stores.insert().values(department_id=department_id, store_id=store_id))
    session.add(
        AuditLog(
            actor_type="user",
            actor_id=actor.id,
            action="department.update",
            resource_type="department",
            resource_id=department_id,
            after_data={"name": department.name},
            result="succeeded",
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "部门名称已存在", 409) from exc
    return await _view(session, actor, department)


async def delete_department(session: AsyncSession, actor: User, department_id: uuid.UUID) -> None:
    department, _ = await _visible_department(session, actor, department_id)
    member_id = await session.scalar(
        select(department_members.c.user_id).where(department_members.c.department_id == department_id).limit(1)
    )
    if member_id is not None:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "请先移除部门成员", 409)
    session.add(
        AuditLog(
            actor_type="user",
            actor_id=actor.id,
            action="department.delete",
            resource_type="department",
            resource_id=department_id,
            before_data={"name": department.name},
            after_data={"deleted": True},
            result="succeeded",
        )
    )
    await session.delete(department)
    await session.commit()


async def list_members(session: AsyncSession, actor: User, department_id: uuid.UUID) -> list[TeamMemberView]:
    await _visible_department(session, actor, department_id)
    member_ids = set(
        (
            await session.scalars(
                select(department_members.c.user_id).where(department_members.c.department_id == department_id)
            )
        ).all()
    )
    return [item for item in await list_team(session, actor) if item.id in member_ids]


async def add_member(session: AsyncSession, actor: User, department_id: uuid.UUID, member_id: uuid.UUID) -> None:
    _, department_store_ids = await _visible_department(session, actor, department_id)
    member = await session.get(User, member_id)
    if member is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "员工不存在", 404)
    if member.status != "active":
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "已停用员工不能加入部门", 409)
    role_store_ids = set(
        (await session.scalars(select(user_roles.c.store_id).where(user_roles.c.user_id == member_id))).all()
    )
    if None not in role_store_ids and not role_store_ids.intersection(department_store_ids):
        raise AppError(ErrorCode.VALIDATION_ERROR, "账号店铺范围与部门不匹配", 422)
    try:
        await session.execute(department_members.insert().values(department_id=department_id, user_id=member_id))
        session.add(
            AuditLog(
                actor_type="user",
                actor_id=actor.id,
                action="department.member.add",
                resource_type="department",
                resource_id=department_id,
                after_data={"member_id": str(member_id)},
                result="succeeded",
            )
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "员工已在该部门", 409) from exc


async def remove_member(session: AsyncSession, actor: User, department_id: uuid.UUID, member_id: uuid.UUID) -> None:
    await _visible_department(session, actor, department_id)
    result = cast(
        CursorResult[Any],
        await session.execute(
            delete(department_members).where(
                department_members.c.department_id == department_id,
                department_members.c.user_id == member_id,
            )
        ),
    )
    if result.rowcount == 0:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "部门成员不存在", 404)
    session.add(
        AuditLog(
            actor_type="user",
            actor_id=actor.id,
            action="department.member.remove",
            resource_type="department",
            resource_id=department_id,
            after_data={"member_id": str(member_id)},
            result="succeeded",
        )
    )
    await session.commit()
