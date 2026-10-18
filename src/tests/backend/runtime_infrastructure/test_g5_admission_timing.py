"""G5 数值分段不得把凭证、身份或业务正文写入日志。"""

import json
import logging
import uuid
from types import SimpleNamespace

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import dependencies as auth_dependencies
from app.chat import router as chat_router
from app.chat.schemas import ChatQueryRequest
from app.shared.logging.setup import JsonFormatter


@pytest.mark.asyncio
async def test_g5_auth_logs_only_numeric_duration(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    token = "test-sensitive-access-token"

    async def resolve(_session: object, _token: str) -> object:
        assert _token == token
        return user

    monkeypatch.setattr(auth_dependencies, "resolve_access_user", resolve)
    monkeypatch.setattr(auth_dependencies, "get_settings", lambda: SimpleNamespace(sse_load_test_enabled=True))
    request = SimpleNamespace(
        headers={"Authorization": f"Bearer {token}"},
        url=SimpleNamespace(path="/v1/chat/query"),
        state=SimpleNamespace(trace_id=str(uuid.uuid4())),
    )
    with caplog.at_level(logging.INFO, logger=auth_dependencies.__name__):
        resolved = await auth_dependencies.get_current_user(
            SimpleNamespace(), request, HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), None
        )

    records = [row for row in caplog.records if getattr(row, "event", "") == "g5_chat_auth_timing"]
    assert resolved is user
    assert len(records) == 1
    assert isinstance(records[0].latency_ms, int) and records[0].latency_ms >= 0
    assert token not in records[0].getMessage()
    assert not any(hasattr(records[0], name) for name in ("token", "user_id", "content"))
    formatted = json.loads(JsonFormatter().format(records[0]))
    assert formatted["event"] == "g5_chat_auth_timing"
    assert formatted["latency_ms"] == records[0].latency_ms
    assert token not in str(formatted)


@pytest.mark.asyncio
async def test_g5_route_logs_bounded_admission_phases(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    user = SimpleNamespace(id=uuid.uuid4())

    async def allow_limits(*_args: object) -> None:
        return None

    async def acquire(*_args: object) -> str:
        return "test-lease"

    monkeypatch.setattr(chat_router, "_enforce_chat_limits", allow_limits)
    monkeypatch.setattr(chat_router, "acquire_chat_stream", acquire)
    monkeypatch.setattr(
        chat_router,
        "get_settings",
        lambda: SimpleNamespace(sse_load_test_enabled=True, chat_user_concurrency=2, chat_stream_lease_seconds=660),
    )
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(agent_runtime=None)),
        state=SimpleNamespace(trace_id=str(uuid.uuid4())),
        client=SimpleNamespace(host="127.0.0.1"),
    )
    with caplog.at_level(logging.INFO, logger=chat_router.__name__):
        await chat_router.chat_query(ChatQueryRequest(session_id=uuid.uuid4()), request, SimpleNamespace(), user)  # type: ignore[arg-type]

    events = [getattr(row, "event", "") for row in caplog.records]
    for name in ("g5_chat_limit_timing", "g5_chat_lease_timing"):
        matches = [row for row in caplog.records if getattr(row, "event", "") == name]
        assert len(matches) == 1, events
        assert isinstance(matches[0].latency_ms, int) and matches[0].latency_ms >= 0


@pytest.mark.asyncio
async def test_normal_auth_has_no_g5_timing(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    async def resolve(_session: object, _token: str) -> object:
        return object()

    monkeypatch.setattr(auth_dependencies, "resolve_access_user", resolve)
    monkeypatch.setattr(auth_dependencies, "get_settings", lambda: SimpleNamespace(sse_load_test_enabled=False))
    request = SimpleNamespace(
        headers={"Authorization": "Bearer test-token"},
        url=SimpleNamespace(path="/v1/chat/query"),
        state=SimpleNamespace(trace_id=str(uuid.uuid4())),
    )
    with caplog.at_level(logging.INFO, logger=auth_dependencies.__name__):
        await auth_dependencies.get_current_user(
            SimpleNamespace(), request, HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token"), None
        )
    assert not any(getattr(row, "event", "") == "g5_chat_auth_timing" for row in caplog.records)
