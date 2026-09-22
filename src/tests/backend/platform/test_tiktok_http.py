"""TikTok 固定出口 HTTP 客户端测试。"""

import pytest

from app.integrations import tiktok_http
from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError


def test_tiktok_http_client_uses_explicit_socks_and_ignores_proxy_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """移除显式 proxy 或恢复环境代理信任会破坏固定出口边界。"""
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_async_client(**kwargs: object) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(tiktok_http.httpx, "AsyncClient", fake_async_client)
    settings = Settings(
        _env_file=None,
        APP_ENV="development",
        TIKTOK_EGRESS_PROXY_URL="socks5h://127.0.0.1:1080",
    )

    assert tiktok_http.create_tiktok_http_client(settings) is sentinel
    assert captured == {
        "timeout": settings.request_timeout_seconds,
        "proxy": "socks5h://127.0.0.1:1080",
        "trust_env": False,
    }


def test_tiktok_http_client_refuses_direct_fallback() -> None:
    """缺少代理时不得构造会从业务服务器直连 TikTok 的客户端。"""
    with pytest.raises(AppError, match="固定出口"):
        tiktok_http.create_tiktok_http_client(Settings(_env_file=None))
