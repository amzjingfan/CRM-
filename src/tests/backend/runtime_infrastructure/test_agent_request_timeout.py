"""HTTP 外层应容纳 Agent 运行预算，其余请求仍受原有总超时保护。"""

import asyncio
from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from app import main


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "method", "status"),
    [
        ("/v1/agents/00000000-0000-4000-8000-000000000001/debug", "POST", 200),
        ("/v1/agents/00000000-0000-4000-8000-000000000001/debug", "GET", 504),
        ("/v1/agents/not-a-uuid/debug", "POST", 504),
        ("/v1/agents/00000000-0000-4000-8000-000000000001/debug/extra", "POST", 504),
        ("/v1/workspace/sessions", "GET", 504),
        ("/v1/workspace/sessions/00000000-0000-4000-8000-000000000001/suggest", "POST", 200),
        ("/v1/workspace/sessions/00000000-0000-4000-8000-000000000001/suggest", "GET", 504),
        ("/v1/workspace/sessions/not-a-uuid/suggest", "POST", 504),
    ],
)
async def test_only_real_debug_endpoint_receives_its_configured_run_budget(monkeypatch, path, method, status):
    monkeypatch.setattr(
        main, "settings", SimpleNamespace(request_timeout_seconds=0.01, agent_debug_timeout_seconds=0.08)
    )
    request = Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": ("test", 80),
        }
    )

    async def slow_response(_request):
        await asyncio.sleep(0.03)
        return JSONResponse({"code": 0})

    result = await main.add_trace_id(request, slow_response)
    assert result.status_code == status


@pytest.mark.asyncio
async def test_debug_http_request_remains_bounded_when_handler_stalls(monkeypatch):
    monkeypatch.setattr(
        main, "settings", SimpleNamespace(request_timeout_seconds=0.01, agent_debug_timeout_seconds=0.03)
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/agents/00000000-0000-4000-8000-000000000001/debug",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": ("test", 80),
        }
    )
    stopped = asyncio.Event()

    async def stalled(_request):
        try:
            await asyncio.sleep(30)
        finally:
            stopped.set()

    result = await main.add_trace_id(request, stalled)
    assert result.status_code == 504
    assert stopped.is_set()
