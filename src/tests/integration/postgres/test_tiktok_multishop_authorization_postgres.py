"""隔离 PostgreSQL 上验证多店卖家授权的真实迁移、绑定与凭证加载。"""

import hashlib
import os
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.integrations.credential_crypto import encrypt_credential
from app.integrations.models import TikTokOAuthJob
from app.integrations.oauth_schemas import TikTokAuthorizedShop, TikTokTokenData
from app.integrations.oauth_service import decrypt_tiktok_access_token, select_tiktok_oauth_shops
from app.shared.config.settings import Settings
from app.shared.database.base import Role, User, user_roles
from app.stores.models import ChannelAccount, Store, TikTokSellerAuthorization
from app.stores.repository import claim_tiktok_seller_for_refresh

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_two_shops_persist_one_seller_grant_and_load_shared_token() -> None:
    """真实外键、JSONB 与 selectin 读取下，两家店共用一个授权且隔离 ID 不变。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id, job_id = uuid.uuid4(), uuid.uuid4()
    shop_ids = [f"multishop-{uuid.uuid4().hex}" for _ in range(2)]
    grant_hash = hashlib.sha256(f"seller-{uuid.uuid4().hex}".encode()).hexdigest()
    settings = Settings(
        _env_file=None,
        TIKTOK_APP_KEY="unit-test-app-key",
        TIKTOK_SERVICE_ID="unit-test-service-id",
        TIKTOK_APP_SECRET="unit-test-app-secret-value",
        TIKTOK_OAUTH_REDIRECT_URI="https://www.example.com/v1/integrations/tiktok/oauth/callback",
        TIKTOK_CREDENTIAL_ENCRYPTION_KEY="unit-test-encryption-key-with-at-least-32-characters",
        TIKTOK_EGRESS_PROXY_URL="socks5h://127.0.0.1:1080",
        TIKTOK_REQUIRED_SCOPES="seller.authorization.info",
    )
    now = int(time.time())
    token = TikTokTokenData(
        access_token="access-token-unit-test-value",
        access_token_expire_in=now + 3600,
        refresh_token="refresh-token-unit-test-value",
        refresh_token_expire_in=now + 86400,
        open_id=grant_hash,
        seller_name="Synthetic Seller",
        seller_base_region="GB",
        user_type=0,
        granted_scopes=["seller.authorization.info"],
    )
    shops = [
        TikTokAuthorizedShop(
            id=shop_id,
            cipher=f"cipher-{index}",
            code=f"SHOP-{index}",
            name=f"Synthetic shop {index}",
            region="GB",
            seller_type="LOCAL",
        )
        for index, shop_id in enumerate(shop_ids)
    ]

    class FakeClient:
        async def get_authorized_shops(self, access_token: str) -> tuple[list[TikTokAuthorizedShop], str]:
            assert access_token == token.access_token
            return shops, "synthetic-request"

    store_ids: list[uuid.UUID] = []
    try:
        async with sessions() as session:
            user = User(
                id=user_id, email=f"multishop-{uuid.uuid4().hex}@example.invalid", password_hash="unused", name="Test"
            )
            session.add(user)
            admin_role_id = await session.scalar(select(Role.id).where(Role.code == "admin"))
            assert admin_role_id is not None
            await session.flush()
            await session.execute(user_roles.insert().values(user_id=user_id, role_id=admin_role_id, store_id=None))
            key = settings.tiktok_credential_encryption_key
            assert key is not None
            session.add(
                TikTokOAuthJob(
                    id=job_id,
                    user_id=user_id,
                    return_to="/settings/stores",
                    status="selection_required",
                    selection_expires_at=datetime.now(UTC) + timedelta(minutes=5),
                    selection_shops=[shop.model_dump() for shop in shops],
                    selection_token_cipher=encrypt_credential(
                        token.model_dump_json(), key.get_secret_value(), f"tiktok:oauth-job:{job_id}:selection"
                    ),
                )
            )
            await session.commit()
            await select_tiktok_oauth_shops(
                session,
                user,
                job_id,
                shop_ids,
                settings,
                FakeClient(),  # type: ignore[arg-type]
            )

        async with sessions() as verify:
            channels = list(
                (
                    await verify.scalars(select(ChannelAccount).where(ChannelAccount.external_store_id.in_(shop_ids)))
                ).all()
            )
            store_ids = [channel.store_id for channel in channels]
            assert len(channels) == 2 and len(set(store_ids)) == 2
            assert len({channel.seller_authorization_id for channel in channels}) == 1
            assert all(decrypt_tiktok_access_token(channel, settings) == token.access_token for channel in channels)
            grant = await verify.get(TikTokSellerAuthorization, channels[0].seller_authorization_id)
            assert grant is not None and set(grant.authorized_shop_ids) == set(shop_ids)
            job = await verify.get(TikTokOAuthJob, job_id)
            assert job is not None and job.status == "connected" and job.selection_token_cipher is None
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(User).where(User.id == user_id))
            if store_ids:
                await cleanup.execute(delete(Store).where(Store.id.in_(store_ids)))
            await cleanup.execute(
                delete(TikTokSellerAuthorization).where(
                    TikTokSellerAuthorization.open_id_hash == hashlib.sha256(token.open_id.encode()).hexdigest()
                )
            )
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_two_workers_cannot_refresh_the_same_seller_grant() -> None:
    """多店共用 Token 时按卖家行加锁，第二个 Worker 不得重复轮换。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    grant_id = uuid.uuid4()
    try:
        async with sessions() as setup:
            setup.add(
                TikTokSellerAuthorization(
                    id=grant_id,
                    app_key="unit-test-app-key",
                    open_id_hash=uuid.uuid4().hex,
                    access_token_ref="encrypted:v1:synthetic",
                    refresh_token_ref="encrypted:v1:synthetic",
                    access_expires_at=datetime.now(UTC) + timedelta(minutes=30),
                    refresh_expires_at=datetime.now(UTC) + timedelta(days=1),
                    next_refresh_at=datetime.now(UTC) - timedelta(seconds=1),
                    scopes=[],
                    authorized_shop_ids=["synthetic-a", "synthetic-b"],
                    status="connected",
                )
            )
            await setup.commit()
        async with sessions() as first, sessions() as second:
            ready_at = datetime.now(UTC)
            first_claim = await claim_tiktok_seller_for_refresh(first, ready_at)
            second_claim = await claim_tiktok_seller_for_refresh(second, ready_at)
            assert first_claim is not None and first_claim.id == grant_id
            assert second_claim is None
            await first.rollback()
            await second.rollback()
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(TikTokSellerAuthorization).where(TikTokSellerAuthorization.id == grant_id))
            await cleanup.commit()
        await engine.dispose()
