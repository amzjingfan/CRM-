"""店铺与渠道管理业务规则。"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids, ensure_store_access
from app.shared.database.base import Role, User, user_roles
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount, Store, TikTokSellerAuthorization
from app.stores.repository import get_active_store, list_channels, list_stores
from app.stores.schemas import ChannelCreate, StoreAliasUpdate, StoreCreate


async def get_stores(session: AsyncSession, user: User) -> list[Store]:
    """返回当前用户允许访问的店铺。"""
    return await list_stores(session, await allowed_store_ids(session, user))


async def create_store(session: AsyncSession, user: User, payload: StoreCreate) -> Store:
    """管理员创建店铺并记录审计。"""
    store = Store(**payload.model_dump())
    session.add(store)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "店铺编码已存在", 409) from exc
    session.add(
        AuditLog(
            store_id=store.id,
            actor_type="user",
            actor_id=user.id,
            action="store.create",
            resource_type="store",
            resource_id=store.id,
            after_data={"code": store.code},
            result="succeeded",
        )
    )
    await session.commit()
    await session.refresh(store)
    return store


async def ensure_store_admin(session: AsyncSession, user: User, store_id: uuid.UUID) -> None:
    """管理员权限必须来自系统或目标店铺，不能借用其他店铺的角色。"""
    assignment = await session.scalar(
        select(user_roles.c.user_id)
        .join(Role, user_roles.c.role_id == Role.id)
        .where(
            user_roles.c.user_id == user.id,
            Role.code == "admin",
            or_(user_roles.c.store_id.is_(None), user_roles.c.store_id == store_id),
        )
    )
    if assignment is None:
        raise AppError(ErrorCode.PERMISSION_DENIED, "没有管理该店铺的权限", 403)


async def update_store_alias(
    session: AsyncSession, user: User, store_id: uuid.UUID, payload: StoreAliasUpdate
) -> Store:
    """只改展示别名，保留内部租户身份与平台绑定。"""
    await ensure_store_access(session, user, store_id)
    await ensure_store_admin(session, user, store_id)
    store = await get_active_store(session, store_id)
    if store is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    old_alias = store.alias
    alias = payload.alias.strip() if payload.alias else None
    store.metadata_json = {**(store.metadata_json or {}), "alias": alias or None}
    session.add(
        AuditLog(
            store_id=store.id,
            actor_type="user",
            actor_id=user.id,
            action="store.alias.update",
            resource_type="store",
            resource_id=store.id,
            before_data={"alias": old_alias},
            after_data={"alias": alias or None},
            result="succeeded",
        )
    )
    await session.commit()
    await session.refresh(store)
    return store


async def get_channels(session: AsyncSession, user: User) -> list[ChannelAccount]:
    """返回当前用户授权店铺的渠道账号。"""
    return await list_channels(session, await allowed_store_ids(session, user))


async def create_channel(session: AsyncSession, user: User, payload: ChannelCreate) -> ChannelAccount:
    """创建仅保存密钥引用的渠道账号。"""
    # TikTok 的真实店铺身份只能由 OAuth callback 根据平台结果建立。
    # 即使内部调用绕过 Pydantic，请求也不能伪造 connected 渠道记录。
    if str(payload.platform) == "tiktok":
        raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 渠道必须通过 OAuth 授权", 400)
    await ensure_store_access(session, user, payload.store_id)
    channel = ChannelAccount(**payload.model_dump())
    session.add(channel)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "平台店铺授权已存在", 409) from exc
    session.add(
        AuditLog(
            store_id=channel.store_id,
            actor_type="user",
            actor_id=user.id,
            action="channel.authorize",
            resource_type="channel_account",
            resource_id=channel.id,
            after_data={"platform": channel.platform, "external_store_id": channel.external_store_id},
            result="succeeded",
        )
    )
    await session.commit()
    await session.refresh(channel)
    return channel


async def delete_channel(session: AsyncSession, user: User, channel_id: uuid.UUID) -> None:
    """撤销渠道账号；跨店铺资源统一返回不存在。"""
    channel = await session.get(ChannelAccount, channel_id)
    if channel is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "渠道账号不存在", 404)
    await ensure_store_access(session, user, channel.store_id)
    if channel.platform == "tiktok":
        await ensure_store_admin(session, user, channel.store_id)
    session.add(
        AuditLog(
            store_id=channel.store_id,
            actor_type="user",
            actor_id=user.id,
            action="channel.revoke",
            resource_type="channel_account",
            resource_id=channel.id,
            before_data={"platform": channel.platform, "external_store_id": channel.external_store_id},
            result="succeeded",
        )
    )
    if channel.platform == "tiktok":
        # 删除店铺授权只撤销凭证，保留绑定与历史业务数据以便再次添加。
        grant_id = channel.seller_authorization_id
        grant = await session.get(TikTokSellerAuthorization, grant_id, with_for_update=True) if grant_id else None
        other_connected = (
            await session.scalar(
                select(ChannelAccount.id).where(
                    ChannelAccount.seller_authorization_id == grant_id,
                    ChannelAccount.id != channel.id,
                    ChannelAccount.status == "connected",
                )
            )
            if grant is not None
            else None
        )
        channel.status = "disconnected"
        channel.seller_authorization = None
        channel.seller_authorization_id = None
        channel.access_token_ref = f"revoked://{channel.id}"
        channel.refresh_token_ref = None
        channel.token_expires_at = None
        channel.metadata_json = {
            **channel.metadata_json,
            "oauth_status": "revoked",
            "revoked_at": datetime.now(UTC).isoformat(),
        }
        if grant is not None and other_connected is None:
            await session.delete(grant)
    else:
        await session.delete(channel)
    await session.commit()
