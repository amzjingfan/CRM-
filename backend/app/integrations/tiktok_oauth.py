"""TikTok Shop 卖家 OAuth、Token 和已授权店铺调用。"""

import hashlib
import hmac
import time
from urllib.parse import urlencode

import httpx
from pydantic import ValidationError

from app.integrations.oauth_schemas import (
    TikTokAuthorizedShop,
    TikTokShopResponse,
    TikTokTokenData,
    TikTokTokenResponse,
)
from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError, ErrorCode

TOKEN_URL = "https://auth.tiktok-shops.com/api/v2/token/get"
REFRESH_URL = "https://auth.tiktok-shops.com/api/v2/token/refresh"
SHOP_URL = "https://open-api.tiktokglobalshop.com/authorization/202309/shops"
SHOP_PATH = "/authorization/202309/shops"
AUTHORIZATION_URLS = {
    "US": "https://services.us.tiktokshop.com/open/authorize",
    "ROW": "https://services.tiktokshop.com/open/authorize",
}


def build_authorization_url(settings: Settings, state: str) -> str:
    """构造 TikTok Shop 卖家授权地址；不把 App Secret 下发浏览器。"""
    if not settings.tiktok_service_id:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok OAuth 尚未配置", 503)
    query = urlencode({"service_id": settings.tiktok_service_id, "state": state})
    return f"{AUTHORIZATION_URLS[settings.tiktok_oauth_market]}?{query}"


def generate_api_signature(path: str, params: dict[str, str | int], app_secret: str, body: bytes = b"") -> str:
    """按 TikTok Shop 202309+ 规则对路径、排序查询参数和原始正文生成 HMAC-SHA256。"""
    filtered = ((key, value) for key, value in params.items() if key not in {"sign", "access_token"})
    query = "".join(f"{key}{value}" for key, value in sorted(filtered))
    sign_input = app_secret.encode() + path.encode() + query.encode() + body + app_secret.encode()
    return hmac.new(app_secret.encode(), sign_input, hashlib.sha256).hexdigest()


class TikTokOAuthClient:
    """TikTok OAuth 和授权店铺的最小服务端客户端。"""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client

    async def exchange_code(self, auth_code: str) -> TikTokTokenData:
        """使用一次性 auth_code 交换卖家 Token。"""
        return await self._request_token(
            TOKEN_URL,
            {"auth_code": auth_code, "grant_type": "authorized_code"},
        )

    async def refresh_token(self, refresh_token: str) -> TikTokTokenData:
        """刷新卖家 Token；调用方负责将失败记录为授权过期。"""
        return await self._request_token(
            REFRESH_URL,
            {"refresh_token": refresh_token, "grant_type": "refresh_token"},
        )

    async def _request_token(self, url: str, grant_params: dict[str, str]) -> TikTokTokenData:
        """调用 Token API 并隐藏平台原始错误和凭证。"""
        secret = self.settings.tiktok_app_secret
        if self.settings.tiktok_app_key in {"", "mock-app"} or secret is None:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok OAuth 尚未配置", 503)
        params = {
            "app_key": self.settings.tiktok_app_key,
            "app_secret": secret.get_secret_value(),
            **grant_params,
        }
        try:
            if self.client is not None:
                response = await self.client.get(url, params=params)
            else:
                async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                    response = await client.get(url, params=params)
            response.raise_for_status()
            parsed = TikTokTokenResponse.model_validate(response.json())
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 授权服务暂时不可用", 502) from exc
        if parsed.code != 0 or parsed.data is None:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 授权失败", 502)
        return parsed.data

    async def get_authorized_shops(self, access_token: str) -> tuple[list[TikTokAuthorizedShop], str | None]:
        """读取当前卖家已授权店铺，用于绑定内部租户。"""
        secret = self.settings.tiktok_app_secret
        if secret is None:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok OAuth 尚未配置", 503)
        timestamp = int(time.time())
        params: dict[str, str | int] = {"app_key": self.settings.tiktok_app_key, "timestamp": timestamp}
        params["sign"] = generate_api_signature(SHOP_PATH, params, secret.get_secret_value())
        headers = {"content-type": "application/json", "x-tts-access-token": access_token}
        try:
            if self.client is not None:
                response = await self.client.get(SHOP_URL, params=params, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                    response = await client.get(SHOP_URL, params=params, headers=headers)
            response.raise_for_status()
            parsed = TikTokShopResponse.model_validate(response.json())
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 店铺信息暂时不可用", 502) from exc
        if parsed.code != 0 or parsed.data is None:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 店铺授权校验失败", 502)
        return parsed.data.shops, parsed.request_id
