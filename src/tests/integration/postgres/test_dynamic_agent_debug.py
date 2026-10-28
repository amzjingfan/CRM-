"""动态调试在隔离 PostgreSQL 留低敏运行记录，不写平台消息。"""

import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.management.config_models import AgentConfig
from app.agents.management.models import AgentConfigVersion
from app.agents.management.schemas import AgentDebugRequest
from app.agents.orchestration.aggregator import ReviewedSuggestion
from app.agents.orchestration.coordinator import SpecialistResult
from app.agents.orchestration.router import RoutedAgent, RoutePlan
from app.agents.orchestration.service import DynamicRunResult
from app.agents.runtime.models import AgentRun
from app.agents.runtime.state import RunPhase
from app.agents.tools.loop import ToolEvent
from app.shared.database.base import User
from app.stores.models import Store
from app.tools.models import ToolCall

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_v2_debug_records_route_and_returns_review_only(monkeypatch) -> None:
    assert TEST_DATABASE_URL is not None
    from app.agents.management import debug

    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="调试测试", code=f"debug-v2-{uuid.uuid4().hex}")
    user = User(
        id=uuid.uuid4(),
        email=f"agent-v2-{uuid.uuid4().hex}@example.test",
        name="合成坐席",
        password_hash="unused",
    )
    config = AgentConfig(
        id=uuid.uuid4(),
        store_id=store.id,
        name="订单 Agent",
        code="order-agent",
        status="enabled",
        published_version=1,
    )
    version = AgentConfigVersion(
        store_id=store.id,
        agent_config_id=config.id,
        version=1,
        name="订单 Agent",
        code="order-agent",
        description="查询订单",
        agent_type="service",
        model_provider="deepseek",
        model_name="deepseek-chat",
        prompt_sections={},
        prompt_hash="hash",
        tool_names=[],
        file_ids=[],
        ready_for_v2=True,
    )
    settings = SimpleNamespace(
        agent_debug_enabled=True,
        embedding_enabled=True,
        real_tiktok_read_enabled=False,
        agent_debug_timeout_seconds=5,
        llm_primary_provider="deepseek",
        llm_primary_model="deepseek-chat",
        llm_fallback_provider=None,
        llm_fallback_model=None,
    )

    result = DynamicRunResult(
        phase=RunPhase.REVIEW_READY,
        route=RoutePlan((RoutedAgent(config.id, "查订单"),), 1, 2, 2),
        specialists=(
            SpecialistResult(
                config.id,
                "订单信息供坐席复核",
                tool_events=(
                    ToolEvent("call-test", "search_customer_orders", "succeeded"),
                    ToolEvent("call-note", "add_internal_note", "permission_denied"),
                ),
            ),
        ),
        suggestion=ReviewedSuggestion("订单信息供坐席复核", "human_review", None, (config.id,), (), 2, 2),
        reason_code=None,
    )
    monkeypatch.setattr(debug, "get_settings", lambda: settings)
    monkeypatch.setattr(debug, "get_config", AsyncMock(return_value=config))
    monkeypatch.setattr(debug, "user_permissions", lambda _user: {"agent.manage"})
    monkeypatch.setattr(debug, "execute_model_run", AsyncMock(return_value=result))
    try:
        async with sessions() as session:
            session.add_all([store, user])
            await session.flush()
            session.add(config)
            await session.flush()
            session.add(version)
            await session.commit()
            view = await debug.run_agent_debug_v2(
                session,
                user,
                config.id,
                AgentDebugRequest(message="我的订单在哪"),
                "trace-v2",
                None,
            )
            assert view.content == "订单信息供坐席复核"
            assert view.send_performed is False
            assert view.routed_agents[0]["id"] == str(config.id)
            run = await session.scalar(select(AgentRun).where(AgentRun.id == view.agent_run_id))
            assert run is not None and run.status == "succeeded"
            assert run.phase == "review_ready"
            assert run.snapshot_hash and run.snapshot_ref
            assert "我的订单在哪" not in (run.input_summary or "")
            child = await session.scalar(select(AgentRun).where(AgentRun.parent_run_id == run.id))
            assert child is not None and child.agent_config_id == config.id
            assert child.config_version == 1
            calls = (await session.scalars(select(ToolCall).where(ToolCall.agent_run_id == child.id))).all()
            assert {item.tool_name for item in calls} == {"search_customer_orders", "add_internal_note"}
            assert {item.status for item in calls} == {"succeeded", "failed"}
            assert "我的订单在哪" not in str([item.input_summary for item in calls])
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()
        await engine.dispose()
