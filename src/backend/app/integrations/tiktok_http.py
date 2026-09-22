"""TikTok 专用、失败关闭的固定出口 HTTP 客户端。"""

import httpx

from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError, ErrorCode


def create_tiktok_http_client(settings: Settings) -> httpx.AsyncClient:
    """构造只走显式 SOCKS5H 的客户端；缺失代理时禁止直连回退。"""
    proxy = settings.tiktok_egress_proxy_url
    if not proxy:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 固定出口尚未配置", 503)
    return httpx.AsyncClient(
        timeout=settings.request_timeout_seconds,
        proxy=proxy,
        trust_env=False,
    )
