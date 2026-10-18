"""G5 数值分段不得把凭证、身份或业务正文写入日志。"""

import json
import logging
import uuid
from types import SimpleNamespace

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import dependencies as auth_dependencies
from app.auth import service as auth_service
from app.chat import router as chat_router
from app.chat import service as chat_service
from app.chat.schemas import ChatQueryRequest
from app.shared.logging.setup import JsonFormatter


@pytest.mark.asyncio
async def test_g5_auth_logs_only_numeric_duration(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    token = "test-sensitive-access-token"

    async def resolve(_session: object, _token: str, timing_ms: dict[str, int] | None = None) -> object:
        assert _token == token
        if timing_ms is not None:
            timing_ms.update(decode=1, connection=2, lookup=3)
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
    for event, duration in (
        ("g5_chat_auth_decode_timing", 1),
        ("g5_chat_auth_connection_timing", 2),
        ("g5_chat_auth_lookup_timing", 3),
    ):
        row = next(row for row in caplog.records if getattr(row, "event", "") == event)
        assert row.latency_ms == duration
        assert token not in str(json.loads(JsonFormatter().format(row)))


@pytest.mark.asyncio
async def test_g5_auth_splits_connection_wait_from_user_query(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    user_id = uuid.uuid4()
    user = SimpleNamespace(status="active")

    class Session:
        async def connection(self) -> object:
            order.append("connection")
            return object()

    def decode(_token: str, _kind: str) -> dict[str, str]:
        order.append("decode")
        return {"sub": str(user_id)}

    async def lookup(_session: object, _user_id: uuid.UUID) -> object:
        assert _user_id == user_id
        order.append("lookup")
        return user

    monkeypatch.setattr(auth_service, "decode_token", decode)
    monkeypatch.setattr(auth_service, "find_user_by_id", lookup)
    timing_ms: dict[str, int] = {}
    assert await auth_service.resolve_access_user(Session(), "synthetic-token", timing_ms=timing_ms) is user  # type: ignore[arg-type]
    assert order == ["decode", "connection", "lookup"]
    assert set(timing_ms) == {"decode", "connection", "lookup"}
    assert all(type(duration) is int and duration >= 0 for duration in timing_ms.values())


@pytest.mark.asyncio
async def test_g5_auth_rejects_bad_token_before_acquiring_database_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    class Session:
        async def connection(self) -> object:
            pytest.fail("invalid token must not acquire a database connection")

    def reject(_token: str, _kind: str) -> dict[str, str]:
        raise ValueError("invalid synthetic token")

    monkeypatch.setattr(auth_service, "decode_token", reject)
    with pytest.raises(ValueError, match="invalid synthetic token"):
        await auth_service.resolve_access_user(Session(), "synthetic-token", timing_ms={})  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_g5_context_logs_store_conversation_and_config_phases(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    store_id = uuid.uuid4()
    result = object()

    async def stores(_session: object, _user: object) -> set[uuid.UUID]:
        return {store_id}

    async def conversation(
        _session: object, _id: uuid.UUID, _trigger: object, store_ids: set[uuid.UUID]
    ) -> tuple[object, object]:
        assert store_ids == {store_id}
        return SimpleNamespace(store_id=store_id), object()

    async def config(_session: object, _store_id: uuid.UUID) -> object:
        assert _store_id == store_id
        return object()

    async def run(*_args: object, **_kwargs: object) -> object:
        return result

    monkeypatch.setattr(chat_service, "allowed_store_ids", stores)
    monkeypatch.setattr(chat_service, "_conversation_and_trigger", conversation)
    monkeypatch.setattr(chat_service, "find_enabled_config", config)
    monkeypatch.setattr(chat_service, "run_agent_for_message", run)
    monkeypatch.setattr(chat_service, "suggestion_view", lambda value: value)
    monkeypatch.setattr(
        chat_service,
        "get_settings",
        lambda: SimpleNamespace(sse_load_test_enabled=True, ai_synthetic_demo_enabled=False),
    )
    trace_id = str(uuid.uuid4())
    with caplog.at_level(logging.INFO, logger=chat_service.__name__):
        assert (
            await chat_service.suggest_for_user(
                object(),
                SimpleNamespace(roles=[]),
                uuid.uuid4(),
                None,
                trace_id,  # type: ignore[arg-type]
            )
            is result
        )
    for event in (
        "g5_chat_context_store_timing",
        "g5_chat_context_conversation_timing",
        "g5_chat_context_config_timing",
    ):
        row = next(row for row in caplog.records if getattr(row, "event", "") == event)
        assert type(row.latency_ms) is int and row.latency_ms >= 0
        assert json.loads(JsonFormatter().format(row))["trace_id"] == trace_id


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
