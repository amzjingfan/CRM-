"""在隔离 PostgreSQL 上验证 Phase 4 AI 低敏在线指标聚合。"""

import os
import uuid
from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.core.repository import (
    AgentRunStart,
    MarketingAgentRunCompletion,
    SqlAlchemyAgentRunRecorder,
)
from app.agents.runtime.models import AgentRun
from app.conversations.models import Conversation
from app.customers.models import Customer
from app.dashboard.aggregation import aggregate_store_day, store_zone, utc_bounds
from app.dashboard.models import MetricDaily
from app.dashboard.service import metrics as dashboard_metrics
from app.shared.database import models as _models  # noqa: F401
from app.shared.database.base import Role, User, user_roles
from app.stores.models import Store
from app.tools.models import ToolCall

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_phase4_ai_metrics_aggregate_rag_tool_ttft_and_tokens() -> None:
    """每日指标从事实表重建，不从日志文本或模型自信度伪造准确率。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id: uuid.UUID | None = None
    try:
        async with sessions() as session:
            store = Store(name="AI metrics", code=f"ai-metrics-{uuid.uuid4().hex}", timezone="UTC")
            session.add(store)
            await session.flush()
            store_id = store.id
            customer = Customer(store_id=store.id, name="指标测试客户")
            session.add(customer)
            await session.flush()
            conversation = Conversation(
                store_id=store.id,
                customer_id=customer.id,
                platform="tiktok",
                external_conversation_id=f"metrics-{uuid.uuid4().hex}",
            )
            session.add(conversation)
            await session.flush()
            run = AgentRun(
                store_id=store.id,
                conversation_id=conversation.id,
                model_provider="test",
                model_name="test",
                action="human_review",
                status="succeeded",
                retrieval_score=0.88,
                output_summary="states=CONTEXT_LOADED>KNOWLEDGE_RETRIEVED>HUMAN_REVIEW",
                first_output_latency_ms=1250,
                input_tokens=120,
                output_tokens=30,
            )
            session.add(run)
            await session.flush()
            session.add(
                ToolCall(
                    store_id=store.id,
                    agent_run_id=run.id,
                    actor_type="agent",
                    tool_name="query_order",
                    idempotency_key=f"metrics-{uuid.uuid4().hex}",
                    request_hash="a" * 64,
                    status="succeeded",
                    input_summary={"order_id_present": True},
                )
            )
            await session.commit()

            metric = await aggregate_store_day(session, store, datetime.now(UTC).date())
            await session.commit()

            assert metric.rag_run_count == 1
            assert metric.rag_hit_count == 1
            assert metric.tool_call_count == 1
            assert metric.tool_success_count == 1
            assert metric.first_output_count == 1
            assert metric.p95_first_output_latency_ms == 1250
            assert metric.input_tokens == 120
            assert metric.output_tokens == 30
            assert metric.intent_labeled_count == 0
            assert metric.intent_correct_count == 0
    finally:
        if store_id is not None:
            async with sessions() as session:
                await session.execute(delete(Store).where(Store.id == store_id))
                await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_marketing_ai_run_links_low_sensitivity_trace_to_tool_calls() -> None:
    """营销生成进入统一 agent_runs，后续工具通过 agent_run_id 形成完整链路。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id: uuid.UUID | None = None
    try:
        async with sessions() as session:
            store = Store(name="Marketing trace", code=f"marketing-trace-{uuid.uuid4().hex}")
            session.add(store)
            await session.flush()
            store_id = store.id
            customer = Customer(store_id=store.id, name="营销追踪客户")
            session.add(customer)
            await session.flush()
            conversation = Conversation(
                store_id=store.id,
                customer_id=customer.id,
                platform="shopee",
                external_conversation_id=f"marketing-{uuid.uuid4().hex}",
            )
            session.add(conversation)
            await session.commit()
            event_id = uuid.uuid4()
            recorder = SqlAlchemyAgentRunRecorder(session)
            run_id = await recorder.start(
                AgentRunStart(
                    store_id=store.id,
                    conversation_id=conversation.id,
                    trigger_message_id=None,
                    provider_name="test",
                    model_name="test",
                    prompt_version="marketing-copy-v1.0.0",
                    input_summary=f"run_type=marketing;event_id={event_id};trigger_type=bad_review",
                    trace_id=f"marketing:{event_id}",
                )
            )
            await recorder.complete_marketing(
                run_id,
                MarketingAgentRunCompletion(
                    event_id=event_id,
                    provider_name="test",
                    model_name="test",
                    prompt_version="marketing-copy-v1.0.0",
                    is_safe=True,
                    requires_human=False,
                    safety_reason_codes=[],
                    input_tokens=50,
                    output_tokens=20,
                    latency_ms=80,
                ),
            )
            session.add(
                ToolCall(
                    store_id=store.id,
                    agent_run_id=run_id,
                    actor_type="job",
                    tool_name="send_platform_message",
                    idempotency_key=f"marketing:{event_id}:message",
                    request_hash="b" * 64,
                    status="succeeded",
                    input_summary={"content_length": 20},
                    trace_id=f"marketing:{event_id}",
                    mocked=True,
                )
            )
            await session.commit()

            run = await session.get(AgentRun, run_id)
            assert run is not None
            assert run.status == "succeeded"
            assert f"event_id={event_id}" in (run.output_summary or "")
            assert "营销追踪客户" not in (run.output_summary or "")
    finally:
        if store_id is not None:
            async with sessions() as session:
                await session.execute(delete(Store).where(Store.id == store_id))
                await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_dashboard_period_p95_uses_all_raw_samples_instead_of_max_daily_p95() -> None:
    """跨日样本量不均衡时，7 天 P95 必须按周期原始运行样本计算。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_ids: set[uuid.UUID] = set()
    user_id: uuid.UUID | None = None
    try:
        async with sessions() as session:
            store = Store(name="Period P95", code=f"period-p95-{uuid.uuid4().hex}", timezone="UTC")
            user = User(
                email=f"period-p95-{uuid.uuid4().hex}@example.com",
                password_hash="not-a-real-password-hash",
                name="周期指标测试管理员",
            )
            session.add_all([store, user])
            await session.flush()
            store_ids.add(store.id)
            user_id = user.id
            admin_role = await session.scalar(select(Role).where(Role.code == "admin"))
            assert admin_role is not None
            await session.execute(
                user_roles.insert().values(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    role_id=admin_role.id,
                    store_id=None,
                )
            )
            customer = Customer(store_id=store.id, name="周期指标测试客户")
            session.add(customer)
            await session.flush()
            conversation = Conversation(
                store_id=store.id,
                customer_id=customer.id,
                platform="amazon",
                external_conversation_id=f"period-p95-{uuid.uuid4().hex}",
            )
            session.add(conversation)
            await session.flush()
            today = datetime.now(UTC).date()
            first_day = today - timedelta(days=1)
            first_created_at = datetime.combine(first_day, time(hour=12), tzinfo=UTC)
            second_created_at = datetime.combine(today, time(hour=12), tzinfo=UTC)
            session.add_all(
                [
                    AgentRun(
                        store_id=store.id,
                        conversation_id=conversation.id,
                        model_provider="test",
                        model_name="test",
                        action="human_review",
                        status="succeeded",
                        first_output_latency_ms=100,
                        created_at=first_created_at,
                    )
                    for _ in range(100)
                ]
                + [
                    AgentRun(
                        store_id=store.id,
                        conversation_id=conversation.id,
                        model_provider="test",
                        model_name="test",
                        action="human_review",
                        status="succeeded",
                        first_output_latency_ms=9000,
                        created_at=second_created_at,
                    )
                ]
            )
            session.add_all(
                [
                    MetricDaily(
                        store_id=store.id,
                        metric_date=first_day,
                        aggregation_timezone="UTC",
                        first_output_count=100,
                        p95_first_output_latency_ms=100,
                    ),
                    MetricDaily(
                        store_id=store.id,
                        metric_date=today,
                        aggregation_timezone="UTC",
                        first_output_count=1,
                        p95_first_output_latency_ms=9000,
                    ),
                ]
            )
            await session.commit()

            empty_store = Store(name="Empty P95", code=f"empty-p95-{uuid.uuid4().hex}", timezone="UTC")
            session.add(empty_store)
            await session.commit()
            store_ids.add(empty_store.id)

            seven_days = await dashboard_metrics(session, user, store.id, "7d")
            thirty_days = await dashboard_metrics(session, user, store.id, "30d")
            today_only = await dashboard_metrics(session, user, store.id, "today")
            empty = await dashboard_metrics(session, user, empty_store.id, "today")

            assert seven_days.p95_first_output_latency_ms == 100
            assert thirty_days.p95_first_output_latency_ms == 100
            assert today_only.p95_first_output_latency_ms == 9000
            assert empty.p95_first_output_latency_ms is None

            shanghai_store = Store(
                name="Timezone P95",
                code=f"timezone-p95-{uuid.uuid4().hex}",
                timezone="Asia/Shanghai",
            )
            session.add(shanghai_store)
            await session.flush()
            store_ids.add(shanghai_store.id)
            shanghai_customer = Customer(store_id=shanghai_store.id, name="时区边界客户")
            session.add(shanghai_customer)
            await session.flush()
            shanghai_conversation = Conversation(
                store_id=shanghai_store.id,
                customer_id=shanghai_customer.id,
                platform="tiktok",
                external_conversation_id=f"timezone-p95-{uuid.uuid4().hex}",
            )
            session.add(shanghai_conversation)
            await session.flush()
            local_today = datetime.now(store_zone(shanghai_store.timezone)).date()
            local_start, _ = utc_bounds(local_today, shanghai_store.timezone)
            session.add_all(
                [
                    AgentRun(
                        store_id=shanghai_store.id,
                        conversation_id=shanghai_conversation.id,
                        model_provider="test",
                        model_name="test",
                        action="human_review",
                        status="succeeded",
                        first_output_latency_ms=321,
                        created_at=local_start + timedelta(minutes=1),
                    ),
                    AgentRun(
                        store_id=shanghai_store.id,
                        conversation_id=shanghai_conversation.id,
                        model_provider="test",
                        model_name="test",
                        action="human_review",
                        status="succeeded",
                        first_output_latency_ms=9999,
                        created_at=local_start - timedelta(minutes=1),
                    ),
                    MetricDaily(
                        store_id=shanghai_store.id,
                        metric_date=local_today,
                        aggregation_timezone="Asia/Shanghai",
                        first_output_count=1,
                        p95_first_output_latency_ms=321,
                    ),
                ]
            )
            await session.commit()

            timezone_result = await dashboard_metrics(session, user, shanghai_store.id, "today")

            assert timezone_result.p95_first_output_latency_ms == 321
    finally:
        async with sessions() as session:
            if store_ids:
                await session.execute(delete(Store).where(Store.id.in_(store_ids)))
            if user_id is not None:
                await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()
