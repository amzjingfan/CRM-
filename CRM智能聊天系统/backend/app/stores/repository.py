"""店铺与渠道持久化查询。"""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.stores.models import ChannelAccount, Store


async def list_stores(session: AsyncSession, store_ids: set[uuid.UUID]) -> list[Store]:
    """按授权集合查询有效店铺。"""
    if not store_ids:
        return []
    return list(
        (
            await session.scalars(
                select(Store).where(Store.id.in_(store_ids), Store.deleted_at.is_(None)).order_by(Store.created_at)
            )
        ).all()
    )


async def list_channels(session: AsyncSession, store_ids: set[uuid.UUID]) -> list[ChannelAccount]:
    """按授权集合查询渠道账号。"""
    if not store_ids:
        return []
    return list(
        (
            await session.scalars(
                select(ChannelAccount).where(ChannelAccount.store_id.in_(store_ids)).order_by(ChannelAccount.created_at)
            )
        ).all()
    )


async def get_active_store(session: AsyncSession, store_id: uuid.UUID) -> Store | None:
    """按主键读取有效店铺，禁用或软删除店铺不可新增授权。"""
    store: Store | None = await session.scalar(
        select(Store).where(Store.id == store_id, Store.status == "active", Store.deleted_at.is_(None))
    )
    return store


async def find_channel_by_store_platform(
    session: AsyncSession,
    store_id: uuid.UUID,
    platform: str,
) -> ChannelAccount | None:
    """读取店铺已有平台账号，供 OAuth 续授权原子更新。"""
    channel: ChannelAccount | None = await session.scalar(
        select(ChannelAccount).where(ChannelAccount.store_id == store_id, ChannelAccount.platform == platform)
    )
    return channel


async def find_channel_by_external_store(
    session: AsyncSession,
    platform: str,
    external_store_id: str,
) -> ChannelAccount | None:
    """查找外部店铺绑定，防止同一 TikTok 店铺跨租户重复绑定。"""
    channel: ChannelAccount | None = await session.scalar(
        select(ChannelAccount).where(
            ChannelAccount.platform == platform,
            ChannelAccount.external_store_id == external_store_id,
        )
    )
    return channel


async def claim_tiktok_channel_for_refresh(
    session: AsyncSession,
    refresh_before: datetime,
) -> ChannelAccount | None:
    """原子认领一个即将过期的 TikTok 渠道，避免多 Jobs Worker 重复刷新。

    行锁会持续到刷新服务提交成功或失败状态。`SKIP LOCKED` 使并行 Worker
    可以处理其他店铺，同时保证同一个渠道在任一时刻只有一个刷新请求。
    """
    channel: ChannelAccount | None = await session.scalar(
        select(ChannelAccount)
        .where(
            ChannelAccount.platform == "tiktok",
            ChannelAccount.status == "connected",
            ChannelAccount.refresh_token_ref.is_not(None),
            ChannelAccount.token_expires_at.is_not(None),
            ChannelAccount.token_expires_at <= refresh_before,
        )
        .order_by(ChannelAccount.token_expires_at, ChannelAccount.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    return channel
