"""动态调试在读取真实会话和平台数据前守住授权与总时限。"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

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
                id=agent_id,
                config_version=1,
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
async def test_dynamic_run_respects_deadline_and_does_not_prefetch_latest_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_id, agent_id = _setup(monkeypatch, tools=("query_order",))
    monkeypatch.setattr(debug, "user_permissions", lambda _user: {"workspace.view"})
    conversation = SimpleNamespace(id=uuid.uuid4(), store_id=store_id, customer_id=uuid.uuid4(), platform="tiktok")
    session = SimpleNamespace(scalar=AsyncMock(return_value=conversation), add=Mock(), commit=AsyncMock())
    user = SimpleNamespace(id=uuid.uuid4(), roles=[SimpleNamespace(code="operator")])

    async def slow_run(**_args: object) -> None:
        await asyncio.sleep(0.1)

    monkeypatch.setattr(
        debug,
        "freeze_debug_context",
        AsyncMock(return_value=SimpleNamespace(snapshot_hash="test", low_sensitive_reference=lambda: {})),
    )
    monkeypatch.setattr(debug, "load_memory", AsyncMock(return_value=SimpleNamespace(summary="", facts=())))
    monkeypatch.setattr(debug, "execute_model_run", slow_run)
    monkeypatch.setattr(debug, "persist_dynamic_result", AsyncMock())

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
    assert session.scalar.await_count == 1


@pytest.mark.asyncio
async def test_cancelled_debug_persists_tool_progress_and_terminal_state(monkeypatch: pytest.MonkeyPatch) -> None:
    _, agent_id = _setup(monkeypatch)
    monkeypatch.setattr(debug, "user_permissions", lambda _user: {"agent.manage"})
    session = SimpleNamespace(add=Mock(), commit=AsyncMock())
    user = SimpleNamespace(id=uuid.uuid4(), roles=[SimpleNamespace(code="admin")])
    monkeypatch.setattr(
        debug,
        "freeze_debug_context",
        AsyncMock(return_value=SimpleNamespace(snapshot_hash="test", low_sensitive_reference=lambda: {})),
    )

    async def cancelled(**kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(debug, "execute_model_run", cancelled)
    persist = AsyncMock()
    monkeypatch.setattr(debug, "persist_dynamic_result", persist)
    with pytest.raises(asyncio.CancelledError):
        await debug.run_agent_debug_v2(session, user, agent_id, AgentDebugRequest(message="查物流"), "trace", None)
    persist.assert_awaited_once()
    run = persist.await_args.kwargs["run"]
    assert run.status == "failed"
    assert run.error_code == "DYNAMIC_RUN_CANCELLED"
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_debug_keeps_all_reviewed_reply_parts(monkeypatch: pytest.MonkeyPatch) -> None:
    _, agent_id = _setup(monkeypatch)
    monkeypatch.setattr(debug, "user_permissions", lambda _user: {"agent.manage"})
    session = SimpleNamespace(add=Mock(side_effect=lambda row: setattr(row, "id", uuid.uuid4())), commit=AsyncMock())
    user = SimpleNamespace(id=uuid.uuid4(), roles=[SimpleNamespace(code="admin")])
    monkeypatch.setattr(
        debug,
        "freeze_debug_context",
        AsyncMock(return_value=SimpleNamespace(snapshot_hash="test", low_sensitive_reference=lambda: {})),
    )
    outcome = SimpleNamespace(
        suggestion=SimpleNamespace(content="First", reply_parts=("First", "Second")),
        specialists=(),
        route=SimpleNamespace(selections=()),
        phase=SimpleNamespace(value="review_ready"),
        reason_code=None,
    )
    monkeypatch.setattr(debug, "execute_model_run", AsyncMock(return_value=outcome))
    monkeypatch.setattr(debug, "persist_dynamic_result", AsyncMock())
    response = await debug.run_agent_debug_v2(
        session, user, agent_id, AgentDebugRequest(message="两项问题"), "trace", None
    )
    assert response.content == "First\n\nSecond"
