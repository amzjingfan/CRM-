"""店铺与渠道管理业务规则。"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids, ensure_store_access
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount, Store
from app.stores.repository import list_channels, list_stores
from app.stores.schemas import ChannelCreate, StoreCreate


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
    if channel.platform == "tiktok" and channel.access_token_ref.startswith("encrypted:v1:"):
        # OAuth 撤销必须保留低敏生命周期和审计证据，同时立即破坏凭证可用性。
        channel.status = "disconnected"
        channel.access_token_ref = f"revoked://{channel.id}"
        channel.refresh_token_ref = None
        channel.token_expires_at = None
        channel.metadata_json = {
            **channel.metadata_json,
            "oauth_status": "revoked",
            "revoked_at": datetime.now(UTC).isoformat(),
        }
    else:
        await session.delete(channel)
    await session.commit()
