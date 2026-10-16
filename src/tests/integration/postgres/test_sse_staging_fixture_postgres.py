"""在隔离 PostgreSQL 验证 G5 合成会话的 FK、权限与事务边界。"""

import os
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audit.models import AuditLog
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.shared.database import models as _models  # noqa: F401
from app.shared.database.base import Role, User, role_permissions, user_roles
from app.stores.models import Store
from scripts import prepare_sse_staging_fixture as fixture
from scripts.check_sse_staging_fixture import ReadinessError, check_readiness

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_fixture_is_scoped_and_rolls_back_on_isolated_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setattr(fixture, "hash_password", lambda _password: "test-hash")
    monkeypatch.setattr(fixture, "create_access_token", lambda user_id: f"test-{user_id}")
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    run_id = uuid.uuid4()
    try:
        async with sessions() as session:
            await session.begin()
            assert (await check_readiness(session, "staging"))["ready"] is True
            payload = await fixture.provision_fixture(session, run_id)
            store_id = uuid.UUID(payload["manifest"]["store_id"])
            role_id = uuid.UUID(payload["manifest"]["role_id"])
            assert await session.get(Store, store_id) is not None
            assert await session.get(Role, role_id) is not None
            assert (
                await session.scalar(select(func.count()).select_from(Customer).where(Customer.store_id == store_id))
                == 50
            )
            assert (
                await session.scalar(
                    select(func.count()).select_from(Conversation).where(Conversation.store_id == store_id)
                )
                == 50
            )
            assert (
                await session.scalar(select(func.count()).select_from(Message).where(Message.store_id == store_id))
                == 50
            )
            assignments = (await session.execute(select(user_roles).where(user_roles.c.role_id == role_id))).all()
            assert len(assignments) == 50
            assert {row.store_id for row in assignments} == {store_id}
            permissions = (
                await session.execute(select(role_permissions).where(role_permissions.c.role_id == role_id))
            ).all()
            assert len(permissions) == 1
            audit = await session.scalar(select(AuditLog).where(AuditLog.resource_id == store_id))
            assert audit is not None and audit.action == "g5.fixture.provision"
            assert len(payload["clients"]) == 50
            with pytest.raises(ReadinessError) as readiness_error:
                await check_readiness(session, "staging")
            assert readiness_error.value.stage == "existing_fixture"
            for user_id in payload["manifest"]["user_ids"]:
                assert await session.get(User, uuid.UUID(user_id)) is not None
            await session.rollback()
        async with sessions() as session:
            assert await session.get(Store, store_id) is None
    finally:
        await engine.dispose()
