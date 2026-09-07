"""在隔离 PostgreSQL 上验证 TikTok OAuth 渠道唯一性。"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.stores.models import ChannelAccount, Store
from app.stores.repository import claim_tiktok_channel_for_refresh

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_same_store_cannot_bind_two_tiktok_channels() -> None:
    """数据库必须兜底阻止两个并发 callback 为同一店铺建立多个 TikTok 渠道。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id = uuid.uuid4()
    store = Store(id=store_id, name="TikTok OAuth unique", code=f"tiktok-oauth-{uuid.uuid4().hex}")
    try:
        async with sessions() as session:
            session.add(store)
            await session.commit()

            session.add_all(
                [
                    ChannelAccount(
                        store_id=store.id,
                        platform="tiktok",
                        external_store_id=f"tiktok-{uuid.uuid4().hex}",
                        display_name="TikTok One",
                        access_token_ref="encrypted:v1:test-one",
                    ),
                    ChannelAccount(
                        store_id=store.id,
                        platform="tiktok",
                        external_store_id=f"tiktok-{uuid.uuid4().hex}",
                        display_name="TikTok Two",
                        access_token_ref="encrypted:v1:test-two",
                    ),
                ]
            )
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_due_tiktok_channel_refresh_claim_uses_skip_locked() -> None:
    """两个 Jobs Worker 并发扫描时，同一渠道只能被其中一个事务认领。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    try:
        async with sessions() as setup_session:
            setup_session.add(Store(id=store_id, name="Refresh lock", code=f"refresh-lock-{uuid.uuid4().hex}"))
            await setup_session.flush()
            setup_session.add(
                ChannelAccount(
                    id=channel_id,
                    store_id=store_id,
                    platform="tiktok",
                    external_store_id=f"tiktok-{uuid.uuid4().hex}",
                    display_name="Refresh Lock",
                    access_token_ref="encrypted:v1:test-access",
                    refresh_token_ref="encrypted:v1:test-refresh",
                    token_expires_at=datetime.now(UTC) + timedelta(minutes=5),
                )
            )
            await setup_session.commit()

        refresh_before = datetime.now(UTC) + timedelta(hours=1)
        async with sessions() as first_session, sessions() as second_session:
            first_claim = await claim_tiktok_channel_for_refresh(first_session, refresh_before)
            second_claim = await claim_tiktok_channel_for_refresh(second_session, refresh_before)

            assert first_claim is not None and first_claim.id == channel_id
            assert second_claim is None
            await first_session.rollback()
            await second_session.rollback()
    finally:
        async with sessions() as cleanup_session:
            await cleanup_session.execute(delete(Store).where(Store.id == store_id))
            await cleanup_session.commit()
        await engine.dispose()
