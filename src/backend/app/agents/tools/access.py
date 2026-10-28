"""工具目录与执行共用的当前授权读取。"""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.metadata import ToolCatalogView, catalog_view
from app.auth.store_access import ensure_store_access
from app.shared.config.settings import get_settings
from app.shared.database.base import Permission, User, role_permissions, user_roles
from app.stores.models import ChannelAccount


async def current_permissions(session: AsyncSession, user: User, store_id: uuid.UUID) -> set[str]:
    """按当前用户、店铺重新读权限，运行快照不能抵消撤权。"""
    await ensure_store_access(session, user, store_id)
    statement = (
        select(Permission.code)
        .join(role_permissions, role_permissions.c.permission_id == Permission.id)
        .join(user_roles, user_roles.c.role_id == role_permissions.c.role_id)
        .join(User, User.id == user_roles.c.user_id)
        .where(
            User.id == user.id,
            User.status == "active",
            or_(user_roles.c.store_id == store_id, user_roles.c.store_id.is_(None)),
        )
    )
    return set((await session.scalars(statement)).all())


async def tool_catalog(session: AsyncSession, user: User, store_id: uuid.UUID) -> ToolCatalogView:
    permissions = await current_permissions(session, user, store_id)
    channel = await session.scalar(
        select(ChannelAccount).where(
            ChannelAccount.store_id == store_id,
            ChannelAccount.platform == "tiktok",
            ChannelAccount.status == "connected",
        )
    )
    return catalog_view(
        permissions=permissions,
        scopes=set(channel.scopes) if channel else set(),
        platform_available=channel is not None and get_settings().real_tiktok_read_enabled,
    )
