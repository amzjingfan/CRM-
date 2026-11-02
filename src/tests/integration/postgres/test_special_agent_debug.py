"""专用 Agent 调试读取真实持久历史，预演不得改变客户业务状态。"""

import os
import time
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

import app.shared.database.models  # noqa: F401
from app.agents.management.config_models import AgentConfig
from app.agents.management.models import AgentConfigVersion
from app.agents.memory.models import AgentSessionMemory
from app.agents.runtime.models import AgentRun
from app.agents.tools.models import AgentCollaborationEntry
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.shared.database.base import Role, User, user_roles
from app.stores.models import Store
from app.tools.models import ToolCall

URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="未提供隔离 PostgreSQL")


@pytest.fixture
async def debug_scope():
    engine = create_async_engine(URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id, other_store, customer_id, conversation_id, user_id, agent_id = (uuid.uuid4() for _ in range(6))
    ids = (uuid.uuid4(), uuid.uuid4())
    now = datetime.now(UTC)
    async with sessions() as session:
        session.add_all(
            [
                Store(id=store_id, name="合成兜底调试店", code=f"special-debug-{store_id.hex}"),
                Store(id=other_store, name="隔离店", code=f"special-debug-{other_store.hex}"),
                User(id=user_id, name="合成坐席", password_hash="unused", email=f"{user_id.hex}@example.test"),
            ]
        )
        await session.flush()
        role = await session.scalar(select(Role).where(Role.code == "admin"))
        await session.execute(insert(user_roles).values(user_id=user_id, role_id=role.id, store_id=store_id))
        session.add(
            Customer(id=customer_id, store_id=store_id, platform="tiktok", external_customer_id=uuid.uuid4().hex)
        )
        await session.flush()
        session.add(
            Conversation(
                id=conversation_id,
                store_id=store_id,
                customer_id=customer_id,
                platform="tiktok",
                external_conversation_id=uuid.uuid4().hex,
                status="active",
            )
        )
        session.add(
            AgentConfig(
                id=agent_id,
                store_id=store_id,
                name="合成兜底Agent",
                code="fallback",
                status="enabled",
                published_version=1,
            )
        )
        await session.flush()
        session.add(
            AgentConfigVersion(
                store_id=store_id,
                agent_config_id=agent_id,
                version=1,
                name="合成兜底Agent",
                code="fallback",
                agent_type="fallback",
                model_provider="openai",
                model_name="synthetic",
                prompt_sections={},
                prompt_hash="synthetic",
                ready_for_v2=True,
                file_ids=[],
                tool_names=["query_conversation_messages", "create_handoff_request", "add_internal_note"],
            )
        )
        for offset, message_id in enumerate(ids):
            session.add(
                Message(
                    id=message_id,
                    store_id=store_id,
                    conversation_id=conversation_id,
                    customer_id=customer_id,
                    platform="tiktok",
                    external_message_id=uuid.uuid4().hex,
                    direction="inbound",
                    role="user",
                    message_type="text",
                    content="An earlier unresolved synthetic question.",
                    status="received",
                    created_at=now - timedelta(minutes=3 - offset),
                )
            )
        await session.flush()
        for offset, message_id in enumerate(ids):
            session.add(
                AgentRun(
                    store_id=store_id,
                    agent_config_id=agent_id,
                    conversation_id=conversation_id,
                    trigger_message_id=message_id,
                    model_provider="openai",
                    model_name="synthetic",
                    action="human_review",
                    status="succeeded",
                    input_summary="mode=formal-v2;candidate_count=1",
                    error_code="no_matching_agent",
                    created_at=now - timedelta(minutes=2 - offset),
                )
            )
        session.add(
            AgentSessionMemory(
                store_id=store_id,
                conversation_id=conversation_id,
                customer_id=customer_id,
                revision=1,
                summary="",
                summary_source_ids=[str(item) for item in ids],
                facts_json=[],
            )
        )
        await session.commit()
    try:
        yield SimpleNamespace(
            sessions=sessions,
            store_id=store_id,
            other_store=other_store,
            customer_id=customer_id,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_id=agent_id,
            message_ids=ids,
        )
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id.in_([store_id, other_store])))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "history",
    [
        "valid",
        "missing",
        "failed",
        "resolved",
        "latest_failed",
        "latest_resolved",
        "foreign_store",
        "foreign_customer",
        "debug_only",
        "child_only",
        "outbound",
        "duplicate",
        "no_conversation",
    ],
)
async def test_debug_uses_actual_formal_history_and_only_previews_fallback_tools(debug_scope, monkeypatch, history):
    from app.agents.management import debug
    from app.agents.management.schemas import AgentDebugRequest
    from app.agents.orchestration.coordinator import SpecialistResult
    from app.agents.orchestration.fallback import FIXED_FALLBACK
    from app.agents.orchestration.service import execute_dynamic_run
    from app.agents.providers.tool_calling import FunctionCall, ToolTurn
    from app.agents.tools.business import AgentBusinessExecutor
    from app.agents.tools.catalog import AgentToolContext, build_agent_tools
    from app.agents.tools.loop import run_tool_loop

    shop = debug_scope
    settings = SimpleNamespace(
        agent_debug_enabled=True,
        embedding_enabled=False,
        real_tiktok_read_enabled=False,
        llm_primary_provider="openai",
        llm_primary_model="synthetic",
        agent_debug_timeout_seconds=5,
    )
    monkeypatch.setattr(debug, "get_settings", lambda: settings)
    monkeypatch.setattr(debug, "validate_tool_model", lambda *args: None)
    monkeypatch.setattr(debug, "user_permissions", lambda user: {"agent.manage", "workspace.view", "workspace.reply"})
    async with shop.sessions() as session:
        latest = await session.scalar(select(AgentRun).where(AgentRun.trigger_message_id == shop.message_ids[1]))
        if history == "missing":
            await session.delete(latest)
        elif history == "failed":
            latest.status = "failed"
        elif history == "resolved":
            latest.error_code = None
        elif history == "foreign_store":
            latest.store_id = shop.other_store
        elif history in {"latest_failed", "latest_resolved"}:
            session.add(
                AgentRun(
                    store_id=shop.store_id,
                    conversation_id=shop.conversation_id,
                    trigger_message_id=shop.message_ids[1],
                    model_provider="openai",
                    model_name="synthetic",
                    action="human_review",
                    status="failed" if history == "latest_failed" else "succeeded",
                    input_summary="mode=formal-v2;candidate_count=1",
                    error_code="deadline_exceeded" if history == "latest_failed" else None,
                )
            )
        elif history == "foreign_customer":
            customer = Customer(store_id=shop.store_id, platform="tiktok", external_customer_id=uuid.uuid4().hex)
            session.add(customer)
            await session.flush()
            message = await session.get(Message, shop.message_ids[1])
            message.customer_id = customer.id
        elif history == "debug_only":
            latest.input_summary = "mode=debug-v2;scope=single"
        elif history == "child_only":
            first = await session.scalar(select(AgentRun).where(AgentRun.trigger_message_id == shop.message_ids[0]))
            latest.parent_run_id = first.id
        elif history == "outbound":
            message = await session.get(Message, shop.message_ids[1])
            message.direction, message.role = "outbound", "assistant"
        elif history == "duplicate":
            memory = await session.scalar(
                select(AgentSessionMemory).where(AgentSessionMemory.store_id == shop.store_id)
            )
            memory.summary_source_ids = [str(shop.message_ids[0]), str(shop.message_ids[0])]
        await session.commit()
        memory_before = await session.scalar(
            select(AgentSessionMemory).where(AgentSessionMemory.store_id == shop.store_id)
        )
        sources_before = list(memory_before.summary_source_ids)

    class ToolModel:
        def __init__(self):
            self.calls = 0

        async def complete(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return ToolTurn(
                    None,
                    (
                        FunctionCall("history", "query_conversation_messages", {}),
                        FunctionCall(
                            "handoff", "create_handoff_request", {"content": "Please review the unresolved question."}
                        ),
                        FunctionCall(
                            "note", "add_internal_note", {"content": "Two previous rounds remain unresolved."}
                        ),
                    ),
                    {"role": "assistant", "content": None},
                    3,
                    4,
                )
            return ToolTurn("Internal intentions previewed.", (), {}, 1, 1)

    async def execute(**kwargs):
        assert kwargs["preview_only"] is True
        assert kwargs["progress"].fallback_due is (history == "valid")

        async def worker(selection):
            async with shop.sessions() as session:
                user = await session.get(User, shop.user_id)
                executor = AgentBusinessExecutor(
                    session,
                    user,
                    kwargs["snapshot"],
                    kwargs["run_id"],
                    frozenset(kwargs["permissions"]),
                    "synthetic-debug",
                    preview_only=True,
                )
                selected = kwargs["agents"][0]
                tools = build_agent_tools(
                    selected.tool_names,
                    context=AgentToolContext(
                        shop.store_id,
                        kwargs["run_id"],
                        None,
                        shop.customer_id,
                        frozenset(kwargs["permissions"]),
                        "debug",
                    ),
                    executor=SimpleNamespace(execute=AsyncMock()),
                    business_executor=executor,
                )
                result = await run_tool_loop(
                    provider=ToolModel(), messages=(), tools=tools, deadline=time.monotonic() + 3, max_output_tokens=256
                )
                return SpecialistResult(
                    selection.agent_id, result.answer, tool_events=result.events, observations=result.observations
                )

        return await execute_dynamic_run(
            question=kwargs["question"],
            snapshot=kwargs["snapshot"],
            router=ToolModel(),
            aggregator=ToolModel(),
            worker=worker,
            deadline=kwargs["deadline"],
            max_catalog_tokens=4096,
            progress=kwargs["progress"],
        )

    monkeypatch.setattr(debug, "execute_model_run", execute)
    async with shop.sessions() as session:
        user = await session.scalar(select(User).where(User.id == shop.user_id).options(selectinload(User.roles)))
        result = await debug.run_agent_debug_v2(
            session,
            user,
            shop.agent_id,
            AgentDebugRequest(
                message="Please review my unresolved question.",
                conversation_id=None if history == "no_conversation" else shop.conversation_id,
            ),
            str(uuid.uuid4()),
            None,
        )
        assert result.send_performed is False
        if history == "valid":
            assert result.content == FIXED_FALLBACK["en"]
            assert {item["tool_name"]: item["status"] for item in result.tool_events} == {
                "query_conversation_messages": "succeeded",
                "create_handoff_request": "previewed",
                "add_internal_note": "previewed",
            }
            child = await session.scalar(select(AgentRun).where(AgentRun.parent_run_id == result.agent_run_id))
            records = (await session.scalars(select(ToolCall).where(ToolCall.agent_run_id == child.id))).all()
            previews = [row for row in records if row.tool_name != "query_conversation_messages"]
            assert len(previews) == 2 and all(
                row.output_summary.get("result_status") == "previewed" for row in previews
            )
        else:
            assert result.reason_code != "fallback_third_round" and result.tool_events == []
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AgentCollaborationEntry)
                .where(AgentCollaborationEntry.store_id == shop.store_id)
            )
            == 0
        )
        assert (
            await session.scalar(select(func.count()).select_from(Message).where(Message.store_id == shop.store_id))
            == 2
        )
        memory = await session.scalar(select(AgentSessionMemory).where(AgentSessionMemory.store_id == shop.store_id))
        assert memory.revision == 1 and memory.summary_source_ids == sources_before


@pytest.mark.asyncio
async def test_selected_event_preview_http_requires_csrf_exact_binding_and_real_context(debug_scope, monkeypatch):
    import httpx
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    from app.agents.management import debug
    from app.agents.management import router as management_router
    from app.agents.tools.logistics_updates.integration import ManualLogisticsPreview
    from app.agents.tools.logistics_updates.models import LogisticsNotificationPolicy
    from app.auth.dependencies import get_current_user
    from app.orders.models import Order
    from app.shared.database.session import get_db_session
    from app.shared.exceptions.errors import AppError

    shop = debug_scope
    settings = SimpleNamespace(
        agent_debug_enabled=True, agent_v2_debug_enabled=True, chat_query_limit=10, chat_query_window_seconds=60
    )
    monkeypatch.setattr(debug, "get_settings", lambda: settings)
    monkeypatch.setattr(management_router, "get_settings", lambda: settings)
    monkeypatch.setattr(management_router, "consume_chat_query", AsyncMock(return_value=True))
    preview = AsyncMock(
        return_value=ManualLogisticsPreview(
            status="previewed",
            preview_text="An official verified node.",
            citations=["chunk"],
            tool_calls=[{"name": "query_logistics", "status": "succeeded"}],
        )
    )
    monkeypatch.setattr(debug, "manual_preview", preview)
    async with shop.sessions() as session:
        version = await session.scalar(
            select(AgentConfigVersion).where(AgentConfigVersion.agent_config_id == shop.agent_id)
        )
        version.agent_type = "logistics_event"
        session.add(
            LogisticsNotificationPolicy(
                store_id=shop.store_id, agent_id=shop.agent_id, mode="preview", enabled=False, revision=1
            )
        )
        order = Order(
            store_id=shop.store_id,
            customer_id=shop.customer_id,
            platform="tiktok",
            external_order_id="771100",
            status="IN_TRANSIT",
            currency="USD",
        )
        session.add(order)
        await session.commit()
        local_id = order.id
    app = FastAPI()
    app.include_router(management_router.router)

    @app.exception_handler(AppError)
    async def error_handler(request, error):
        return JSONResponse(status_code=error.status_code, content={"code": error.code.value})

    async def db():
        async with shop.sessions() as session:
            yield session

    async def user():
        async with shop.sessions() as session:
            return await session.get(User, shop.user_id)

    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[get_current_user] = user
    path = f"/agents/{shop.agent_id}/logistics-event-preview"
    payload = {"conversation_id": str(shop.conversation_id), "external_order_id": "771100", "package_id": "123"}
    auth = {"Authorization": "Bearer synthetic-test"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post(path, json=payload)).status_code == 403
        assert (
            await client.post(path, json={**payload, "event": {"description": "forged"}}, headers=auth)
        ).status_code == 422
        assert (
            await client.post(path, json={**payload, "conversation_id": str(uuid.uuid4())}, headers=auth)
        ).status_code == 404
        assert (
            await client.post(path, json={**payload, "external_order_id": "771101"}, headers=auth)
        ).status_code == 404
        result = await client.post(path, json=payload, headers=auth)
        assert result.status_code == 200 and result.json()["data"]["citations"] == ["chunk"]
        assert preview.await_args.args[2].order_id == local_id
        async with shop.sessions() as session:
            policy = await session.get(LogisticsNotificationPolicy, shop.store_id)
            policy.agent_id = None
            await session.commit()
        assert (await client.post(path, json=payload, headers=auth)).status_code == 409
        assert preview.await_count == 1
