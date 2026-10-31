"""调试草稿必须在模型结束之前交付，关闭页面必须取消运行。"""

import asyncio
import json
import uuid

import pytest

from app.agents.management import debug_stream
from app.agents.management.schemas import AgentDebugView
from app.shared.exceptions.errors import AppError, ErrorCode


def result() -> AgentDebugView:
    return AgentDebugView(
        agent_run_id=uuid.uuid4(),
        content="已核实最新物流",
        action="human_review",
        terminal_state="review_ready",
        citations=[],
        tool_calls=[],
        trace_id="trace",
    )


def data(event: str) -> dict:
    return json.loads(event.split("data: ", 1)[1])


@pytest.mark.asyncio
async def test_draft_arrives_before_model_finishes() -> None:
    finish = asyncio.Event()

    async def run(sink):
        await sink(0, "正在生成")
        await finish.wait()
        return result()

    events = debug_stream.stream_debug_events(run, trace_id="trace")
    assert "event: accepted" in await anext(events)
    draft = await asyncio.wait_for(anext(events), 1)
    assert data(draft) == {"part_index": 0, "text": "正在生成", "unverified": True, "sendable": False}
    assert not finish.is_set()
    finish.set()
    remaining = [event async for event in events if not event.startswith(":")]
    assert [event.splitlines()[0] for event in remaining] == ["event: result", "event: done"]
    assert data(remaining[0])["content"] == "已核实最新物流"


@pytest.mark.asyncio
async def test_close_cancels_pending_model_and_waits_for_cleanup() -> None:
    started, cleaned = asyncio.Event(), asyncio.Event()

    async def run(sink):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    events = debug_stream.stream_debug_events(run, trace_id="trace")
    await anext(events)
    await asyncio.wait_for(started.wait(), 1)
    await events.aclose()
    assert cleaned.is_set()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [AppError(ErrorCode.RESOURCE_NOT_FOUND, "当前店铺会话不存在", 404), RuntimeError("secret")]
)
async def test_failure_is_terminal_and_does_not_leak_exception(error: Exception) -> None:
    async def run(sink):
        raise error

    events = [event async for event in debug_stream.stream_debug_events(run, trace_id="trace")]
    assert [event.splitlines()[0] for event in events] == ["event: accepted", "event: error", "event: done"]
    assert "secret" not in "".join(events)
    assert data(events[1])["message"] == (error.message if isinstance(error, AppError) else "Agent 动态调试失败")


@pytest.mark.asyncio
async def test_last_draft_is_drained_before_result() -> None:
    async def run(sink):
        for index in range(100):
            await sink(0, str(index))
        return result()

    events = [event async for event in debug_stream.stream_debug_events(run, trace_id="trace")]
    assert data(events[-3])["text"] == "99"
    assert len(events) <= 67


@pytest.mark.asyncio
async def test_stream_route_releases_only_owned_lease_and_enables_draft_progress(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.agents.management import router
    from app.agents.management.schemas import AgentDebugRequest

    settings = SimpleNamespace(
        agent_v2_debug_enabled=True,
        agent_debug_enabled=True,
        chat_query_limit=10,
        chat_query_window_seconds=60,
        chat_user_concurrency=2,
        chat_stream_lease_seconds=300,
    )
    monkeypatch.setattr(router, "get_settings", lambda: settings)
    monkeypatch.setattr(router, "get_config", AsyncMock())
    monkeypatch.setattr(router, "consume_chat_query", AsyncMock(return_value=True))
    monkeypatch.setattr(router, "acquire_chat_stream", AsyncMock(return_value="owned-lease"))
    release = AsyncMock()
    monkeypatch.setattr(router, "release_chat_stream", release)

    async def run(*args, progress):
        assert progress.reply_plan
        await progress.on_draft(0, "草稿")
        return result()

    monkeypatch.setattr(router, "run_agent_debug_v2", run)
    request = SimpleNamespace(
        client=None,
        app=SimpleNamespace(state=SimpleNamespace(agent_runtime=None)),
        state=SimpleNamespace(trace_id="trace"),
    )
    user = SimpleNamespace(id=uuid.uuid4())
    response = await router.debug_agent_stream(
        uuid.uuid4(), AgentDebugRequest(message="查物流"), request, AsyncMock(), user
    )
    events = [event async for event in response.body_iterator]
    assert any("event: draft" in event for event in events)
    release.assert_awaited_once_with(user.id, "owned-lease")
    assert response.headers["x-accel-buffering"] == "no"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "disabled,denied,exhausted", [(True, False, False), (False, True, False), (False, False, True)]
)
async def test_stream_preflight_never_starts_model_when_guard_fails(monkeypatch, disabled, denied, exhausted):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.agents.management import router
    from app.agents.management.schemas import AgentDebugRequest

    monkeypatch.setattr(
        router,
        "get_settings",
        lambda: SimpleNamespace(
            agent_v2_debug_enabled=not disabled,
            agent_debug_enabled=True,
            chat_query_limit=10,
            chat_query_window_seconds=60,
            chat_user_concurrency=2,
            chat_stream_lease_seconds=300,
        ),
    )
    monkeypatch.setattr(
        router,
        "get_config",
        AsyncMock(side_effect=AppError(ErrorCode.PERMISSION_DENIED, "禁止", 403) if denied else None),
    )
    monkeypatch.setattr(router, "consume_chat_query", AsyncMock(return_value=True))
    monkeypatch.setattr(router, "acquire_chat_stream", AsyncMock(return_value=None if exhausted else "lease"))
    run = AsyncMock()
    monkeypatch.setattr(router, "run_agent_debug_v2", run)
    request = SimpleNamespace(client=None)
    with pytest.raises(AppError):
        await router.debug_agent_stream(
            uuid.uuid4(), AgentDebugRequest(message="查物流"), request, AsyncMock(), SimpleNamespace(id=uuid.uuid4())
        )
    run.assert_not_awaited()


@pytest.mark.parametrize(
    "relative",
    ["nginx/nginx.conf", "nginx/nginx-tunnel.conf", "staging/rootless/public-nginx/staging.overselfx.com.conf"],
)
def test_both_proxy_layers_explicitly_disable_debug_stream_buffering(relative):
    from _support import REPOSITORY_ROOT

    config = (REPOSITORY_ROOT / "src/deploy" / relative).read_text(encoding="utf-8")
    start = config.find("location ~ ^/v1/agents/[0-9a-f-]+/debug/stream$ {")
    assert start >= 0, "debug stream needs a dedicated no-buffer route at every proxy layer"
    block = config[start : config.index("}", start)]
    assert "proxy_buffering off;" in block
    assert "proxy_cache off;" in block
    assert "proxy_read_timeout 240s;" in block
    if relative.startswith("nginx/"):
        assert "proxy_pass_header X-Accel-Buffering;" in block


@pytest.mark.asyncio
async def test_asgi_disconnect_finishes_cancel_audit_and_redis_release(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.agents.management import router
    from app.agents.management.schemas import AgentDebugRequest

    monkeypatch.setattr(
        router,
        "get_settings",
        lambda: SimpleNamespace(
            agent_v2_debug_enabled=True,
            agent_debug_enabled=True,
            chat_query_limit=10,
            chat_query_window_seconds=60,
            chat_user_concurrency=2,
            chat_stream_lease_seconds=300,
        ),
    )
    monkeypatch.setattr(router, "get_config", AsyncMock())
    monkeypatch.setattr(router, "consume_chat_query", AsyncMock(return_value=True))
    monkeypatch.setattr(router, "acquire_chat_stream", AsyncMock(return_value="owned-lease"))
    started = asyncio.Event()
    completed = []

    async def run(*args, progress):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0.01)
            completed.append("audit")

    async def release(*args):
        await asyncio.sleep(0.01)
        completed.append("release")

    monkeypatch.setattr(router, "run_agent_debug_v2", run)
    monkeypatch.setattr(router, "release_chat_stream", release)
    request = SimpleNamespace(
        client=None,
        app=SimpleNamespace(state=SimpleNamespace(agent_runtime=None)),
        state=SimpleNamespace(trace_id="trace"),
    )
    response = await router.debug_agent_stream(
        uuid.uuid4(), AgentDebugRequest(message="test"), request, AsyncMock(), SimpleNamespace(id=uuid.uuid4())
    )

    async def receive():
        await started.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        pass

    await asyncio.wait_for(response({"type": "http", "asgi": {"spec_version": "2.0"}}, receive, send), 2)
    assert completed == ["audit", "release"]
