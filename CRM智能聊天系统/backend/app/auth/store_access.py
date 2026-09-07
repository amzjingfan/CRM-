"""店铺级授权查询，所有业务 Repository 必须使用该边界。"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.database.base import Role, User, user_roles
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import Store


async def allowed_store_ids(session: AsyncSession, user: User) -> set[uuid.UUID]:
    """返回用户可访问店铺；系统级 admin 可访问全部有效店铺。"""
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


async def ensure_store_access(session: AsyncSession, user: User, store_id: uuid.UUID) -> None:
    """跨店铺访问统一伪装成资源不存在，避免租户信息泄露。"""
    if store_id not in await allowed_store_ids(session, user):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
