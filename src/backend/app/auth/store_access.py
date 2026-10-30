"""店铺级授权查询，所有业务 Repository 必须使用该边界。"""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.models import Conversation
from app.shared.database.base import Permission, Role, User, role_permissions, user_roles
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import Store


async def allowed_store_ids(session: AsyncSession, user: User, permission_code: str | None = None) -> set[uuid.UUID]:
    """返回用户可访问店铺；系统级 admin 可访问全部有效店铺。"""
    if permission_code is not None:
        return await allowed_store_ids_for_permission(session, user, permission_code)
    role_rows = (
        await session.execute(
            select(Role.code, user_roles.c.store_id)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(user_roles.c.user_id == user.id)
        )
    ).all()
    if any(code == "admin" and store_id is None for code, store_id in role_rows):
        return set(
            (await session.scalars(select(Store.id).where(Store.status == "active", Store.deleted_at.is_(None)))).all()
        )
    return {store_id for _, store_id in role_rows if store_id is not None}


async def allowed_store_ids_for_permission(session: AsyncSession, user: User, permission_code: str) -> set[uuid.UUID]:
    """按同一条店铺角色授权核对权限，防止跨店角色的权限并集越权。"""
    rows = (
        await session.execute(
            select(Role.code, user_roles.c.store_id)
            .select_from(user_roles)
            .join(Role, Role.id == user_roles.c.role_id)
            .outerjoin(role_permissions, role_permissions.c.role_id == Role.id)
            .outerjoin(Permission, Permission.id == role_permissions.c.permission_id)
            .where(
                user_roles.c.user_id == user.id,
                or_(Role.code == "admin", Permission.code == permission_code),
            )
            .distinct()
        )
    ).all()
    if any(code == "admin" and store_id is None for code, store_id in rows):
        return await allowed_store_ids(session, user)
    return {store_id for _, store_id in rows if store_id is not None}


async def ensure_store_access(session: AsyncSession, user: User, store_id: uuid.UUID) -> None:
    """跨店铺访问统一伪装成资源不存在，避免租户信息泄露。"""
    if store_id not in await allowed_store_ids(session, user):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)


async def supervised_store_ids(session: AsyncSession, user: User) -> set[uuid.UUID]:
    """返回可监督全部会话的店铺；普通客服只能查看本人及待领取队列。"""
    rows = (
        await session.execute(
            select(Role.code, user_roles.c.store_id)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(user_roles.c.user_id == user.id, Role.code.in_(["admin", "supervisor"]))
        )
    ).all()
    if any(code == "admin" and store_id is None for code, store_id in rows):
        return await allowed_store_ids(session, user)
    return {store_id for _, store_id in rows if store_id is not None}


async def ensure_conversation_access(
    session: AsyncSession, actor: User, conversation: Conversation, *, owner_required: bool = False
) -> None:
    """主管可监督本店；客服仅可看自己的会话和待领取队列，写入需已领取。"""
    if conversation.assigned_user_id == actor.id:
        return
    if conversation.store_id in await supervised_store_ids(session, actor):
        return
    if not owner_required and conversation.assigned_user_id is None:
        return
    raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
