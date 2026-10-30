"""普通客服可转交自己的会话，不能领取给别人或操作别人会话。"""

import os
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.conversations.models import Conversation
from app.customers.models import Customer
from app.shared.database import models as _models  # noqa: F401
from app.shared.database.base import Role, User, user_roles
from app.shared.exceptions.errors import AppError
from app.stores.models import Store
from app.workspace.service import assign_session, get_session_list, transfer_session

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="需要隔离 PostgreSQL 测试库")


@pytest.mark.asyncio
async def test_agent_can_claim_queue_and_transfer_own_conversation_only() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id, customer_id, first_id, second_id = (uuid.uuid4() for _ in range(4))
    try:
        async with sessions() as session:
            role_id = await session.scalar(select(Role.id).where(Role.code == "agent"))
            assert role_id is not None
            session.add_all(
                [
                    Store(id=store_id, name="归属测试", code=f"owner_{store_id.hex}", status="active"),
                    User(id=first_id, login_name=f"f{first_id.hex[:12]}", name="客服甲", password_hash="test"),
                    User(id=second_id, login_name=f"s{second_id.hex[:12]}", name="客服乙", password_hash="test"),
                ]
            )
            await session.flush()
            session.add(Customer(id=customer_id, store_id=store_id, platform="tiktok"))
            await session.flush()
            first = Conversation(
                store_id=store_id,
                customer_id=customer_id,
                platform="tiktok",
                external_conversation_id=f"first_{uuid.uuid4().hex}",
                assigned_user_id=first_id,
            )
            second = Conversation(
                store_id=store_id,
                customer_id=customer_id,
                platform="tiktok",
                external_conversation_id=f"second_{uuid.uuid4().hex}",
                assigned_user_id=second_id,
            )
            queue = Conversation(
                store_id=store_id,
                customer_id=customer_id,
                platform="tiktok",
                external_conversation_id=f"queue_{uuid.uuid4().hex}",
            )
            session.add_all([first, second, queue])
            await session.execute(user_roles.insert().values(user_id=first_id, role_id=role_id, store_id=store_id))
            await session.execute(user_roles.insert().values(user_id=second_id, role_id=role_id, store_id=store_id))
            await session.commit()
            actor = await session.get(User, first_id)
            assert actor is not None

            with pytest.raises(AppError) as denied_claim:
                await assign_session(session, actor, queue.id, second_id)
            assert denied_claim.value.status_code == 403
            await assign_session(session, actor, queue.id, first_id)
            with pytest.raises(AppError) as denied_direct_transfer:
                await assign_session(session, actor, first.id, second_id)
            assert denied_direct_transfer.value.status_code == 403
            with pytest.raises(AppError) as denied_other:
                await transfer_session(session, actor, second.id, "交接", first_id, f"other-{uuid.uuid4()}")
            assert denied_other.value.status_code == 404
            backup = await session.get(User, second_id)
            assert backup is not None
            backup.status = "disabled"
            await session.flush()
            with pytest.raises(AppError) as denied_inactive:
                await transfer_session(session, actor, first.id, "交接", second_id, f"inactive-{uuid.uuid4()}")
            assert denied_inactive.value.status_code == 422
            backup.status = "active"
            await session.flush()
            result = await transfer_session(session, actor, first.id, "交接", second_id, f"own-{uuid.uuid4()}")
            assert result.status == "transferred"
            await session.refresh(first)
            assert first.assigned_user_id == second_id and first.assignment_source == "manual"
            listing = await get_session_list(session, actor, "all", None, store_id, None, 1, 20)
            assert {item.id for item in listing.items} == {queue.id}
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.execute(delete(user_roles).where(user_roles.c.user_id.in_([first_id, second_id])))
            await session.execute(delete(User).where(User.id.in_([first_id, second_id])))
            await session.commit()
        await engine.dispose()
