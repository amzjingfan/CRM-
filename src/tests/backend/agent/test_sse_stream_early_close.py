"""SSE 客户端提前关闭时，服务端必须留下低敏终止证据并释放租约。"""

import asyncio
import logging
import uuid
from contextlib import suppress
from types import SimpleNamespace

import pytest
from fastapi import Request

from app.chat import router as chat_router
from app.chat.schemas import ChatQueryRequest


async def _never_disconnected() -> bool:
    return False


def _prepare_stream(monkeypatch: pytest.MonkeyPatch, released: list[uuid.UUID]) -> tuple[object, object]:
    user = SimpleNamespace(id=uuid.uuid4())
    request = SimpleNamespace(
        state=SimpleNamespace(trace_id=str(uuid.uuid4())),
        client=SimpleNamespace(host="127.0.0.1"),
        is_disconnected=_never_disconnected,
    )

    async def allow_limits(_request: Request, _user: object) -> None:
        return None

    async def acquire(_user_id: uuid.UUID, _limit: int, _lease_seconds: int) -> str:
        return "test-lease"

    async def release(user_id: uuid.UUID, lease_token: str) -> None:
        assert lease_token == "test-lease"
        released.append(user_id)

    async def reconcile(*_args: object, **_kwargs: object) -> bool:
        return False

    monkeypatch.setattr(chat_router, "_enforce_chat_limits", allow_limits)
    monkeypatch.setattr(chat_router, "acquire_chat_stream", acquire)
    monkeypatch.setattr(chat_router, "release_chat_stream", release)
    monkeypatch.setattr(chat_router, "reconcile_cancelled_sse_agent_run", reconcile)
    return user, request


@pytest.mark.asyncio
async def test_transport_closes_after_accepted_without_workflow(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    released: list[uuid.UUID] = []
    user, request = _prepare_stream(monkeypatch, released)
    response = await chat_router.chat_query(
        ChatQueryRequest(session_id=uuid.uuid4()),
        request,
        SimpleNamespace(),
        user,  # type: ignore[arg-type]
    )

    with caplog.at_level(logging.INFO, logger=chat_router.__name__):
        accepted = await anext(response.body_iterator)
        await response.body_iterator.aclose()

    assert "event: accepted" in accepted
    assert released == [user.id]
    assert any(
        record.message == "chat_stream_closed_early" and record.trace_id == request.state.trace_id
        for record in caplog.records
    )
    assert not any(record.message == "chat_stream_completed" for record in caplog.records)


@pytest.mark.asyncio
async def test_early_close_is_logged_when_lease_release_is_cancelled_after_server_release(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    released: list[uuid.UUID] = []
    user, request = _prepare_stream(monkeypatch, released)

    async def release_then_cancel(user_id: uuid.UUID, lease_token: str) -> None:
        assert lease_token == "test-lease"
        released.append(user_id)
        raise asyncio.CancelledError

    monkeypatch.setattr(chat_router, "release_chat_stream", release_then_cancel)
    response = await chat_router.chat_query(
        ChatQueryRequest(session_id=uuid.uuid4()),
        request,
        SimpleNamespace(),
        user,  # type: ignore[arg-type]
    )

    with caplog.at_level(logging.INFO, logger=chat_router.__name__):
        assert "event: accepted" in await anext(response.body_iterator)
        with pytest.raises(asyncio.CancelledError):
            await response.body_iterator.aclose()

    assert released == [user.id]
    assert [record.message for record in caplog.records if record.message == "chat_stream_closed_early"] == [
        "chat_stream_closed_early"
    ]


@pytest.mark.asyncio
async def test_transport_cancellation_stops_workflow_and_releases_lease(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    released: list[uuid.UUID] = []
    user, request = _prepare_stream(monkeypatch, released)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def suggest(*_args: object, **_kwargs: object) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(chat_router, "suggest_for_user", suggest)
    response = await chat_router.chat_query(
        ChatQueryRequest(session_id=uuid.uuid4()),
        request,
        SimpleNamespace(),
        user,  # type: ignore[arg-type]
    )

    with caplog.at_level(logging.INFO, logger=chat_router.__name__):
        assert "event: accepted" in await anext(response.body_iterator)
        await anext(response.body_iterator)
        await anext(response.body_iterator)
        pending = asyncio.create_task(anext(response.body_iterator))
        await asyncio.wait_for(started.wait(), timeout=1)
        pending.cancel()
        with suppress(asyncio.CancelledError, StopAsyncIteration):
            await pending

    assert cancelled.is_set()
    assert released == [user.id]
    assert any(
        record.message == "chat_stream_closed_early" and record.trace_id == request.state.trace_id
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_transport_cancel_reconciles_running_agent_before_releasing_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    released: list[uuid.UUID] = []
    user, request = _prepare_stream(monkeypatch, released)
    events: list[str] = []
    started = asyncio.Event()

    async def suggest(*_args: object, **_kwargs: object) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            events.append("workflow_cancelled")

    async def reconcile(*_args: object, **_kwargs: object) -> bool:
        events.append("agent_run_failed")
        return True

    async def release(user_id: uuid.UUID, lease_token: str) -> None:
        assert lease_token == "test-lease"
        released.append(user_id)
        events.append("lease_released")

    monkeypatch.setattr(chat_router, "suggest_for_user", suggest)
    monkeypatch.setattr(chat_router, "reconcile_cancelled_sse_agent_run", reconcile, raising=False)
    monkeypatch.setattr(chat_router, "release_chat_stream", release)
    response = await chat_router.chat_query(
        ChatQueryRequest(session_id=uuid.uuid4()),
        request,
        SimpleNamespace(),
        user,  # type: ignore[arg-type]
    )

    assert "event: accepted" in await anext(response.body_iterator)
    await anext(response.body_iterator)
    await anext(response.body_iterator)
    pending = asyncio.create_task(anext(response.body_iterator))
    await asyncio.wait_for(started.wait(), timeout=1)
    pending.cancel()
    with suppress(asyncio.CancelledError, StopAsyncIteration):
        await pending

    assert events == ["workflow_cancelled", "agent_run_failed", "lease_released"]
    assert released == [user.id]


@pytest.mark.asyncio
async def test_cancel_audit_failure_still_releases_stream_lease(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    released: list[uuid.UUID] = []
    user, request = _prepare_stream(monkeypatch, released)
    started = asyncio.Event()

    async def suggest(*_args: object, **_kwargs: object) -> None:
        started.set()
        await asyncio.Event().wait()

    async def audit_unavailable(*_args: object, **_kwargs: object) -> bool:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(chat_router, "suggest_for_user", suggest)
    monkeypatch.setattr(chat_router, "reconcile_cancelled_sse_agent_run", audit_unavailable)
    response = await chat_router.chat_query(
        ChatQueryRequest(session_id=uuid.uuid4()),
        request,
        SimpleNamespace(),
        user,  # type: ignore[arg-type]
    )

    assert "event: accepted" in await anext(response.body_iterator)
    await anext(response.body_iterator)
    await anext(response.body_iterator)
    pending = asyncio.create_task(anext(response.body_iterator))
    await asyncio.wait_for(started.wait(), timeout=1)
    with caplog.at_level(logging.ERROR, logger=chat_router.__name__):
        pending.cancel()
        with pytest.raises(RuntimeError, match="audit unavailable"):
            await pending
    assert released == [user.id]
    assert any(
        record.message == "chat_stream_agent_cancel_reconcile_failed" and record.error_type == "RuntimeError"
        for record in caplog.records
    )
