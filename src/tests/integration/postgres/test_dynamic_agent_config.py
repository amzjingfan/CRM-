"""动态 Agent 注册表在真实 PostgreSQL 约束下允许同店多配置。"""

import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.management.config_models import AgentConfig
from app.agents.management.schemas import AgentConfigUpdate
from app.shared.exceptions.errors import AppError
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_publish_refreshes_preloaded_draft_after_another_transaction_updates(monkeypatch):
    from app.agents.management import service

    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="并发发布测试", code=f"agent-publish-race-{uuid.uuid4().hex}")
    store_id = store.id
    config = AgentConfig(
        id=uuid.uuid4(),
        store_id=store.id,
        name="原稿",
        code="race",
        draft_revision=1,
        draft_model_provider="deepseek",
        draft_model_name="deepseek-v4-flash",
        draft_prompt_sections=SECTIONS,
    )
    review = AsyncMock(return_value=(3, 1))
    monkeypatch.setattr(service, "review_configured_prompt", review)
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(service, "validate_tool_model", lambda *_: None)
    try:
        async with sessions() as session:
            session.add(store)
            await session.flush()
            session.add(config)
            await session.commit()
            assert await session.get(AgentConfig, config.id) is config
            async with sessions() as writer:
                changed = await writer.get(AgentConfig, config.id)
                changed.draft_revision = 2
                changed.draft_prompt_sections = {**SECTIONS, "identity": "新稿"}
                await writer.commit()
            try:
                with pytest.raises(AppError) as error:
                    await service.publish_agent(
                        session, store_id=store.id, config_id=config.id, expected_revision=1, publisher_id=None
                    )
                assert error.value.status_code == 409
                review.assert_not_awaited()
            finally:
                await session.rollback()
    finally:
        async with sessions() as cleanup:
            await cleanup.execute(delete(Store).where(Store.id == store_id))
            await cleanup.commit()
        await engine.dispose()


SECTIONS = {
    "identity": "你是本店物流专员。",
    "service_scope": "只解释订单物流，不承诺送达。",
    "tool_rules": "授权只读工具可查询，写入需人工确认。",
    "escalation": "物流状态缺失、矛盾或超时需升级。",
    "language_format": "使用买家语言，给出一段建议。",
    "compliance": "不得泄露个人资料或自动发送。",
    "clarification": "信息不足先澄清，故障则转人工。",
}


@pytest.mark.asyncio
async def test_store_can_keep_two_enabled_agents() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="多 Agent 测试", code=f"agents-{uuid.uuid4().hex}")
    try:
        async with sessions() as session:
            session.add(store)
            await session.flush()
            session.add_all(
                [
                    AgentConfig(store_id=store.id, name="物流", code="shipping", status="enabled"),
                    AgentConfig(
                        store_id=store.id,
                        name="售后",
                        code="returns",
                        status="enabled",
                        knowledge_scope={"agent_type": "operations", "file_ids": []},
                    ),
                ]
            )
            await session.commit()
            total = await session.scalar(
                select(func.count())
                .select_from(AgentConfig)
                .where(AgentConfig.store_id == store.id, AgentConfig.status == "enabled")
            )
            assert total == 2
            from app.agents.management.repository import list_enabled_agents

            candidates = await list_enabled_agents(session, store.id)
            assert {item.code for item in candidates} == {"shipping", "returns"}
            assert {item.agent_type for item in candidates} == {"service", "operations"}
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_published_agent_version_is_immutable_and_rejects_stale_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="版本测试", code=f"agent-version-{uuid.uuid4().hex}")
    config = AgentConfig(
        id=uuid.uuid4(),
        store_id=store.id,
        name="物流 Agent",
        code="shipping",
        description="读取物流状态",
        enabled_tools=["query_logistics"],
        knowledge_scope={"agent_type": "service", "file_ids": []},
        draft_model_provider="deepseek",
        draft_model_name="deepseek-v4-flash",
        draft_prompt_sections=SECTIONS,
    )
    try:
        async with sessions() as session:
            session.add(store)
            await session.flush()
            session.add(config)
            await session.commit()

            from app.agents.management import service

            monkeypatch.setattr(
                service,
                "get_settings",
                lambda: SimpleNamespace(
                    llm_primary_provider="deepseek",
                    llm_primary_model="deepseek-v4-flash",
                    llm_fallback_provider=None,
                    llm_fallback_model=None,
                ),
            )
            monkeypatch.setattr(service, "review_configured_prompt", AsyncMock(return_value=(11, 2)))
            first = await service.publish_agent(
                session,
                store_id=store.id,
                config_id=config.id,
                expected_revision=1,
                publisher_id=None,
            )
            assert first.version == 1
            assert first.tool_names == ["query_logistics"]
            assert first.ready_for_v2 is True

            config.description = "已改为售后 Agent"
            config.enabled_tools = ["query_order"]
            await session.commit()
            await session.refresh(first)
            assert first.description == "读取物流状态"
            assert first.tool_names == ["query_logistics"]

            with pytest.raises(AppError) as error:
                await service.publish_agent(
                    session,
                    store_id=store.id,
                    config_id=config.id,
                    expected_revision=1,
                    publisher_id=None,
                )
            assert error.value.status_code == 409
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_publish_rejects_incomplete_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="未完成提示词", code=f"agent-prompt-{uuid.uuid4().hex}")
    config = AgentConfig(
        id=uuid.uuid4(),
        store_id=store.id,
        name="草稿",
        code="draft",
        draft_model_provider="deepseek",
        draft_model_name="deepseek-v4-flash",
        draft_prompt_sections={"identity": "只有第一段"},
    )
    try:
        async with sessions() as session:
            session.add(store)
            await session.flush()
            session.add(config)
            await session.commit()
            from app.agents.management import service

            monkeypatch.setattr(
                service,
                "get_settings",
                lambda: SimpleNamespace(
                    llm_primary_provider="deepseek",
                    llm_primary_model="deepseek-v4-flash",
                    llm_fallback_provider=None,
                    llm_fallback_model=None,
                ),
            )
            with pytest.raises(AppError) as error:
                await service.publish_agent(
                    session,
                    store_id=store.id,
                    config_id=config.id,
                    expected_revision=1,
                    publisher_id=None,
                )
            assert error.value.status_code == 422
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(service.AgentConfigVersion)
                    .where(service.AgentConfigVersion.agent_config_id == config.id)
                )
                == 0
            )
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_saved_draft_publishes_exact_revision_and_keeps_prior_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="草稿发布", code=f"agent-edit-{uuid.uuid4().hex}")
    config = AgentConfig(id=uuid.uuid4(), store_id=store.id, name="物流", code="shipping")
    try:
        async with sessions() as session:
            session.add(store)
            await session.flush()
            session.add(config)
            await session.commit()
            from app.agents.management import config_service as draft_service
            from app.agents.management import service as publish_service

            monkeypatch.setattr(draft_service, "get_config", AsyncMock(return_value=config))
            monkeypatch.setattr(
                publish_service,
                "get_settings",
                lambda: SimpleNamespace(
                    llm_primary_provider="deepseek",
                    llm_primary_model="deepseek-v4-flash",
                    llm_fallback_provider=None,
                    llm_fallback_model=None,
                ),
            )
            saved = await draft_service.update_config(
                session,
                SimpleNamespace(id=uuid.uuid4()),  # type: ignore[arg-type]
                config.id,
                AgentConfigUpdate(
                    model_provider="deepseek",
                    model_name="deepseek-v4-flash",
                    prompt_sections=SECTIONS,
                    expected_revision=1,
                ),
            )
            assert saved.draft_revision == 2
            assert saved.prompt_sections == SECTIONS
            monkeypatch.setattr(publish_service, "review_configured_prompt", AsyncMock(return_value=(11, 2)))
            first = await publish_service.publish_agent(
                session,
                store_id=store.id,
                config_id=config.id,
                expected_revision=2,
                publisher_id=None,
            )
            assert first.version == 1
            assert first.prompt_sections == SECTIONS
            assert first.prompt_hash is not None
            assert config.draft_revision == 3
            config.draft_prompt_sections = {**SECTIONS, "identity": "新的身份"}
            await session.commit()
            await session.refresh(first)
            assert first.prompt_sections["identity"] == SECTIONS["identity"]
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.commit()
        await engine.dispose()
