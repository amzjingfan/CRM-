"""基础健康检查测试。"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app import main
from app.main import app


def test_health_endpoint_returns_ok() -> None:
    """健康检查应返回 200 和统一响应结构。"""
    with TestClient(app) as client:
        response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert response.json()["data"]["status"] == "ok"
    assert response.headers["Server-Timing"].startswith("app;dur=")
    assert ", tiktok;dur=0" in response.headers["Server-Timing"]


@pytest.mark.asyncio
async def test_lifespan_owns_and_closes_shared_agent_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """进程级连接池必须在服务退出时关闭，不能落入请求级清理。"""
    closed = False

    class Runtime:
        async def aclose(self) -> None:
            nonlocal closed
            closed = True

    runtime = Runtime()
    monkeypatch.setattr(main, "build_shared_agent_runtime", lambda _settings: runtime, raising=False)
    async with main.lifespan(app):
        assert app.state.agent_runtime is runtime
        assert closed is False
    assert closed is True


@pytest.mark.parametrize(
    "untrusted_trace_id",
    [
        "private customer address in trace header",
        "00000000000040008000000000000000",
        "{00000000-0000-4000-8000-000000000000}",
    ],
)
def test_untrusted_client_trace_id_is_replaced_with_server_uuid(untrusted_trace_id: str) -> None:
    """客户端 Trace ID 只允许 UUID；任意正文不得进入请求状态、响应和日志链路。"""
    with TestClient(app) as client:
        response = client.get("/v1/health", headers={"X-Trace-Id": untrusted_trace_id})

    returned_trace_id = response.headers["X-Trace-Id"]
    assert returned_trace_id != untrusted_trace_id
    assert str(uuid.UUID(returned_trace_id)) == returned_trace_id
    try:
        normalized_untrusted = str(uuid.UUID(untrusted_trace_id))
    except ValueError:
        normalized_untrusted = None
    assert returned_trace_id != normalized_untrusted
