"""真实只读冒烟入口不能把签名请求 URL 或店铺/订单标识写入输出。"""

import json
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import verify_tiktok_readonly as smoke_script


def test_tiktok_readonly_script_redacts_http_client_request_url() -> None:
    """若入口重新使用普通文本 INFO 日志，本测试会暴露合成签名 URL。"""
    backend_dir = Path(__file__).resolve().parents[3] / "backend"
    code = """
import asyncio
import logging
import runpy

def skip_main(coroutine):
    coroutine.close()

asyncio.run = skip_main
runpy.run_module('scripts.verify_tiktok_readonly', run_name='__main__')
logging.getLogger('httpx').info(
    'HTTP Request: GET https://open-api.tiktokglobalshop.com/order/202507/orders/123456789'
    '?app_key=unit-app-key&shop_cipher=unit-shop-cipher&sign=unit-signature'
)
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    combined_output = result.stdout + result.stderr
    for sentinel in ("unit-app-key", "unit-shop-cipher", "unit-signature", "123456789"):
        assert sentinel not in combined_output
    events = [json.loads(line) for line in result.stderr.splitlines() if line.startswith("{")]
    assert any(event["event"] == "http_client_request" for event in events)


def test_tiktok_readonly_script_redacts_uncaught_error_chain() -> None:
    """平台解析异常即使携带订单内容，也只能形成低敏错误事件和非零退出。"""
    backend_dir = Path(__file__).resolve().parents[3] / "backend"
    code = """
import asyncio
import runpy

def fail_main(coroutine):
    coroutine.close()
    raise RuntimeError('synthetic-order-marker') from ValueError('synthetic-shop-marker')

asyncio.run = fail_main
runpy.run_module('scripts.verify_tiktok_readonly', run_name='__main__')
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 1
    combined_output = result.stdout + result.stderr
    assert "synthetic-order-marker" not in combined_output
    assert "synthetic-shop-marker" not in combined_output
    events = [json.loads(line) for line in result.stderr.splitlines() if line.startswith("{")]
    assert len(events) == 1
    assert events[0]["event"] == "tiktok_readonly_smoke_failed"
    assert events[0]["exception_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_tiktok_readonly_script_keeps_count_only_success_summary(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """安全日志配置不应抹去验收所需的聚合计数。"""

    class SessionStub:
        async def __aenter__(self) -> "SessionStub":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get(self, *_args: object) -> object:
            return object()

    class ReadClientStub:
        async def get_active_shops(self) -> tuple[list[object], None]:
            return [object(), object()], None

        async def get_webhooks(self) -> tuple[list[object], None]:
            return [object()], None

        async def search_orders(self, **_kwargs: object) -> tuple[list[object], None, None]:
            return [], None, None

        async def get_conversations(self, **_kwargs: object) -> tuple[list[object], None, None]:
            return [], None, None

    monkeypatch.setattr(smoke_script, "get_settings", lambda: SimpleNamespace(real_tiktok_read_enabled=True))
    monkeypatch.setattr(smoke_script, "session_factory", SessionStub)
    monkeypatch.setattr(smoke_script, "TikTokReadClient", lambda *_args: ReadClientStub())

    await smoke_script.verify(uuid.uuid4())

    assert json.loads(capsys.readouterr().out) == {
        "event": "tiktok_readonly_smoke_succeeded",
        "shops": 2,
        "webhooks": 1,
        "orders": 0,
        "tracking_packages": 0,
        "conversations": 0,
        "messages": 0,
    }
