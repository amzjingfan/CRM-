"""动态调试在读取真实会话和平台数据前守住授权与总时限。"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.management import debug
from app.agents.management.schemas import AgentDebugRequest
from app.shared.exceptions.errors import AppError


def _setup(monkeypatch: pytest.MonkeyPatch, *, tools: tuple[str, ...] = ()) -> tuple[uuid.UUID, uuid.UUID]:
    store_id, agent_id = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(
        debug,
        "get_settings",
        lambda: SimpleNamespace(
            agent_debug_enabled=True,
            embedding_enabled=False,
            real_tiktok_read_enabled=True,
            agent_debug_timeout_seconds=0.01,
            llm_primary_provider="deepseek",
            llm_primary_model="deepseek-chat",
        ),
    )
    monkeypatch.setattr(debug, "validate_tool_model", lambda *_args: None)
    monkeypatch.setattr(debug, "get_config", AsyncMock(return_value=SimpleNamespace(id=agent_id, store_id=store_id)))
    monkeypatch.setattr(
        debug,
        "get_published_agent",
        AsyncMock(
            return_value=SimpleNamespace(
                ready_for_v2=True,
                file_ids=(),
                tool_names=tools,
            )
        ),
    )
    monkeypatch.setattr(debug, "require_knowledge_view_for_binding", lambda *_args: None)
    return store_id, agent_id


@pytest.mark.asyncio
async def test_conversation_context_requires_workspace_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    _, agent_id = _setup(monkeypatch)
    monkeypatch.setattr(debug, "user_permissions", lambda _user: {"agent.manage"})
    session = SimpleNamespace(scalar=AsyncMock())
    user = SimpleNamespace(roles=[SimpleNamespace(code="operator")])

    with pytest.raises(AppError) as error:
        await debug.run_agent_debug_v2(
            session, user, agent_id, AgentDebugRequest(message="查订单", conversation_id=uuid.uuid4()), "trace", None
        )

    assert error.value.status_code == 403
    session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_cross_store_conversation_is_not_read(monkeypatch: pytest.MonkeyPatch) -> None:
    _, agent_id = _setup(monkeypatch)
    monkeypatch.setattr(debug, "user_permissions", lambda _user: {"workspace.view"})
    session = SimpleNamespace(scalar=AsyncMock(return_value=None))
    user = SimpleNamespace(roles=[SimpleNamespace(code="operator")])

    with pytest.raises(AppError) as error:
        await debug.run_agent_debug_v2(
            session, user, agent_id, AgentDebugRequest(message="查订单", conversation_id=uuid.uuid4()), "trace", None
        )

    assert error.value.status_code == 404
    assert "conversations.store_id" in str(session.scalar.await_args.args[0])


@pytest.mark.asyncio
async def test_live_order_lookup_respects_debug_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    store_id, agent_id = _setup(monkeypatch, tools=("query_order",))
    monkeypatch.setattr(debug, "user_permissions", lambda _user: {"workspace.view"})
    conversation = SimpleNamespace(id=uuid.uuid4(), store_id=store_id, customer_id=uuid.uuid4(), platform="tiktok")
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[conversation, None]))
    user = SimpleNamespace(roles=[SimpleNamespace(code="operator")])

    async def slow_lookup(*_args: object) -> None:
        await asyncio.sleep(0.1)

    monkeypatch.setattr(debug, "latest_verified_live_order", slow_lookup)

    with pytest.raises(AppError) as error:
        await debug.run_agent_debug_v2(
            session,
            user,
            agent_id,
            AgentDebugRequest(message="订单物流在哪", conversation_id=conversation.id),
            "trace",
            None,
        )

    assert error.value.status_code == 504
