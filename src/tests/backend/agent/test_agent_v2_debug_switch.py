"""调试 API 仅能进入动态 Agent；关闭开关时失败关闭。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.shared.exceptions.errors import AppError


@pytest.mark.asyncio
async def test_debug_api_dispatches_dynamic_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.management import router

    expected = object()
    target = AsyncMock(return_value=expected)
    monkeypatch.setattr(
        router,
        "get_settings",
        lambda: SimpleNamespace(agent_v2_debug_enabled=True, chat_query_limit=10, chat_query_window_seconds=60),
    )
    monkeypatch.setattr(router, "consume_chat_query", AsyncMock(return_value=True))
    monkeypatch.setattr(router, "run_agent_debug_v2", target)
    request = SimpleNamespace(
        client=None,
        app=SimpleNamespace(state=SimpleNamespace(agent_runtime=None)),
        state=SimpleNamespace(trace_id="trace"),
    )
    session, user, agent_id, payload = AsyncMock(), SimpleNamespace(id=uuid.uuid4()), uuid.uuid4(), SimpleNamespace()

    response = await router.debug_agent(agent_id, payload, request, session, user)

    assert response.data is expected
    target.assert_awaited_once_with(session, user, agent_id, payload, "trace", None)


@pytest.mark.asyncio
async def test_debug_api_disabled_does_not_call_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.management import router

    target = AsyncMock()
    monkeypatch.setattr(
        router,
        "get_settings",
        lambda: SimpleNamespace(agent_v2_debug_enabled=False, chat_query_limit=10, chat_query_window_seconds=60),
    )
    monkeypatch.setattr(router, "consume_chat_query", AsyncMock(return_value=True))
    monkeypatch.setattr(router, "run_agent_debug_v2", target)
    request = SimpleNamespace(
        client=None,
        app=SimpleNamespace(state=SimpleNamespace(agent_runtime=None)),
        state=SimpleNamespace(trace_id="trace"),
    )

    with pytest.raises(AppError) as error:
        await router.debug_agent(
            uuid.uuid4(), SimpleNamespace(), request, AsyncMock(), SimpleNamespace(id=uuid.uuid4())
        )

    assert error.value.status_code == 503
    target.assert_not_awaited()


@pytest.mark.asyncio
async def test_formal_flag_disabled_does_not_fall_back_to_faq(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.chat import service

    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(agent_v2_formal_enabled=False))
    with pytest.raises(AppError) as error:
        await service.run_agent_for_message(
            AsyncMock(), SimpleNamespace(), SimpleNamespace(), SimpleNamespace(), "trace", set()
        )

    assert error.value.status_code == 503
