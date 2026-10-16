"""隔离 PostgreSQL 上验证真实会话回填与工作台查询。"""

import os
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.integrations.conversation_sync as conversation_sync
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.integrations.conversation_sync import process_tiktok_conversation_sync_cycle, sync_tiktok_channel
from app.integrations.tiktok_read import TikTokConversation, TikTokConversationMessage
from app.shared.config.settings import Settings
from app.stores.models import ChannelAccount, Store
from app.workspace.repository import list_conversations, list_messages

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


class FakeReadClient:
    """只替代外部平台调用，保留真实同步和数据库行为。"""

    def __init__(self) -> None:
        self.message_calls = 0

    async def get_conversations(self, page_size: int = 20, page_token: str | None = None):
        buyer = {"im_user_id": "101", "user_id": "901", "nickname": "Buyer", "role": "BUYER"}
        if page_token is None:
            return (
                [
                    TikTokConversation.model_validate(
                        {
                            "id": "501",
                            "create_time": 1_700_000_000,
                            "participants": [buyer],
                            "latest_message": {"id": "703"},
                        }
                    )
                ],
                "next",
                None,
            )
        assert page_token == "next"
        return (
            [
                TikTokConversation.model_validate(
                    {
                        "id": "502",
                        "create_time": 1_700_000_100,
                        "participants": [buyer],
                        "latest_message": {"id": "704"},
                    }
                )
            ],
            None,
            None,
        )

    async def get_conversation_messages(self, conversation_id: str, page_size: int = 10, page_token: str | None = None):
        self.message_calls += 1
        if conversation_id == "501" and page_token is None:
            return (
                [
                    TikTokConversationMessage.model_validate(
                        {
                            "id": "703",
                            "content": '{"content":"Reply"}',
                            "create_time": 1_700_000_003,
                            "sender": {"im_user_id": "102", "role": "CUSTOMER_SERVICE"},
                            "type": "TEXT",
                        }
                    ),
                    TikTokConversationMessage.model_validate(
                        {
                            "id": "702",
                            "content": '{"content":"hidden"}',
                            "create_time": 1_700_000_002,
                            "sender": {"im_user_id": "103", "role": "SYSTEM"},
                            "type": "NOTIFICATION",
                            "is_visible": False,
                        }
                    ),
                ],
                "older",
                None,
            )
        if conversation_id == "501" and page_token == "older":
            return (
                [
                    TikTokConversationMessage.model_validate(
                        {
                            "id": "701",
                            "content": '{"content":"Hello"}',
                            "create_time": 1_700_000_001,
                            "sender": {"im_user_id": "101", "role": "BUYER"},
                            "type": "TEXT",
                        }
                    )
                ],
                None,
                None,
            )
        assert conversation_id == "502" and page_token is None
        return (
            [
                TikTokConversationMessage.model_validate(
                    {
                        "id": "704",
                        "content": '{"content":"Welcome"}',
                        "create_time": 1_700_000_101,
                        "sender": {"im_user_id": "103", "role": "SYSTEM"},
                        "type": "NOTIFICATION",
                    }
                )
            ],
            None,
            None,
        )


@pytest.mark.asyncio
async def test_disabled_cycle_never_queries_channels() -> None:
    """默认关闭时不得访问真实店铺或数据库。"""

    class NoDatabase:
        async def scalars(self, *_args: object):
            raise AssertionError("disabled sync queried database")

    settings = Settings(_env_file=None, TIKTOK_CONVERSATION_SYNC_ENABLED=False)  # type: ignore[call-arg]
    assert await process_tiktok_conversation_sync_cycle(NoDatabase(), settings) == 0  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_enabled_cycle_imports_only_connected_tiktok_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    """周期任务必须走受控渠道，不能扫描其他平台或未连接账号。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    client = FakeReadClient()
    try:
        async with sessions() as setup:
            setup.add(Store(id=store_id, name="Cycle test", code=f"sync-cycle-{uuid.uuid4().hex}"))
            await setup.flush()
            setup.add(
                ChannelAccount(
                    id=channel_id,
                    store_id=store_id,
                    platform="tiktok",
                    external_store_id=f"{uuid.uuid4().int}",
                    display_name="Cycle test",
                    access_token_ref="encrypted:v1:test",
                    status="connected",
                    scopes=["seller.customer_service"],
                )
            )
            await setup.commit()
        monkeypatch.setattr(conversation_sync, "TikTokReadClient", lambda _settings, _channel: client)
        settings = Settings(_env_file=None, TIKTOK_CONVERSATION_SYNC_ENABLED=True)  # type: ignore[call-arg]
        async with sessions() as session:
            assert await process_tiktok_conversation_sync_cycle(session, settings) == 1
            rows, count = await list_conversations(
                session, {store_id}, uuid.uuid4(), "all", "tiktok", None, None, 1, 20
            )
            assert count == 2
            assert all(row[0].platform == "tiktok" for row in rows)
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(Store).where(Store.id == store_id))
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_backfill_all_pages_exposes_real_conversations_without_duplicates() -> None:
    """漏掉会话分页、历史分页或仅有系统消息的会话都会破坏工作台完整性。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id = uuid.uuid4()
    channel_id = uuid.uuid4()
    client = FakeReadClient()
    try:
        async with sessions() as session:
            session.add(Store(id=store_id, name="Sync test", code=f"sync-{uuid.uuid4().hex}"))
            await session.flush()
            session.add(
                ChannelAccount(
                    id=channel_id,
                    store_id=store_id,
                    platform="tiktok",
                    external_store_id=f"{uuid.uuid4().int}",
                    display_name="Sync test",
                    access_token_ref="encrypted:v1:test",
                    status="connected",
                    scopes=["seller.customer_service"],
                )
            )
            await session.commit()

        async with sessions() as session:
            channel = await session.get(ChannelAccount, channel_id)
            assert channel is not None
            await sync_tiktok_channel(session, channel, client)
            rows, count = await list_conversations(
                session, {store_id}, uuid.uuid4(), "all", "tiktok", None, None, 1, 20
            )
            assert count == 2
            assert {row[0].external_conversation_id for row in rows} == {"501", "502"}
            assert {row[2].content for row in rows if row[2]} == {"Reply", "Welcome"}
            first = next(row[0] for row in rows if row[0].external_conversation_id == "501")
            messages, total = await list_messages(session, first.id, 1, 20)
            assert total == 2
            assert [(message.external_message_id, message.role, message.content) for message in messages] == [
                ("701", "user", "Hello"),
                ("703", "agent", "Reply"),
            ]
            assert all(message.raw_payload.get("delivery_mode") != "mock" for message in messages)
            assert client.message_calls == 3

            await sync_tiktok_channel(session, channel, client)
            assert client.message_calls == 3
            assert (
                len((await session.scalars(select(Conversation).where(Conversation.store_id == store_id))).all()) == 2
            )
            assert len((await session.scalars(select(Message).where(Message.store_id == store_id))).all()) == 3
            assert len((await session.scalars(select(Customer).where(Customer.store_id == store_id))).all()) == 1
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(Store).where(Store.id == store_id))
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_failed_channel_does_not_block_next_connected_store(monkeypatch: pytest.MonkeyPatch) -> None:
    """第一个店铺接口失败后，事务回滚仍可继续同步第二个店铺。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_ids = [uuid.uuid4(), uuid.uuid4()]
    channel_ids = sorted([uuid.uuid4(), uuid.uuid4()])

    class FailingClient:
        async def get_conversations(self, **_kwargs: object):
            raise RuntimeError("upstream unavailable")

    def make_client(_settings: Settings, channel: ChannelAccount):
        return FailingClient() if channel.id == channel_ids[0] else FakeReadClient()

    try:
        async with sessions() as setup:
            for index in range(2):
                setup.add(Store(id=store_ids[index], name="Cycle test", code=f"sync-fail-{uuid.uuid4().hex}"))
                await setup.flush()
                setup.add(
                    ChannelAccount(
                        id=channel_ids[index],
                        store_id=store_ids[index],
                        platform="tiktok",
                        external_store_id=f"{uuid.uuid4().int}",
                        display_name="Cycle test",
                        access_token_ref="encrypted:v1:test",
                        status="connected",
                        scopes=["seller.customer_service"],
                    )
                )
            await setup.commit()
        monkeypatch.setattr(conversation_sync, "TikTokReadClient", make_client)
        settings = Settings(_env_file=None, TIKTOK_CONVERSATION_SYNC_ENABLED=True)  # type: ignore[call-arg]
        async with sessions() as session:
            assert await process_tiktok_conversation_sync_cycle(session, settings) == 1
            assert (await session.scalar(select(Conversation).where(Conversation.store_id == store_ids[0]))) is None
            assert (await session.scalar(select(Conversation).where(Conversation.store_id == store_ids[1]))) is not None
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(Store).where(Store.id.in_(store_ids)))
            await cleanup.commit()
        await engine.dispose()
