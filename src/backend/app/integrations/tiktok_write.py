"""TikTok Shop 人工确认普通消息写客户端。"""

import json
import logging
import time
import uuid

import httpx
from pydantic import ValidationError

from app.integrations.oauth_service import decrypt_tiktok_access_token
from app.integrations.schemas import SendMessageCommand, SendMessageResult
from app.integrations.tiktok_http import create_tiktok_http_client
from app.integrations.tiktok_oauth import generate_api_signature
from app.integrations.tiktok_read import (
    API_BASE_URL,
    PERMISSION_DENIED_CODES,
    TOKEN_EXPIRED_CODES,
    TOKEN_INVALID_CODES,
    TRANSIENT_PLATFORM_CODES,
    TikTokApiEnvelope,
)
from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount

SEND_MESSAGE_PATH_TEMPLATE = "/customer_service/202606/conversations/{conversation_id}/messages"
CUSTOMER_SERVICE_SCOPE = "seller.customer_service"
TIKTOK_TEXT_MAX_LENGTH = 2_000
# 写请求的内部错误不能证明平台没有产生副作用。该集合独立于只读重试
# 白名单：真实消息仍只调用一次，命中后进入 unknown 和人工对账。
WRITE_UNKNOWN_PLATFORM_CODES = TRANSIENT_PLATFORM_CODES | {45101001}

logger = logging.getLogger(__name__)


def is_tiktok_send_target_allowed(settings: Settings, store_id: uuid.UUID, conversation_id: str) -> bool:
    """部署总开关与单会话/店铺范围必须同时匹配，空范围永不放行。"""
    if not settings.real_tiktok_message_write_enabled:
        return False
    allowed_conversation = settings.tiktok_message_write_allowed_conversation_id
    if allowed_conversation:
        return conversation_id == allowed_conversation
    allowed_stores = settings.tiktok_message_write_allowed_store_ids
    if not allowed_stores:
        return False
    return str(store_id) in allowed_stores.split(",")


class TikTokMessageClient:
    """只执行一次已人工确认的 TikTok 文本发送请求。

    TikTok 写接口没有可由本系统控制的远端幂等键。发生传输错误、5xx、
    平台内部错误或成功响应契约不完整时，不能确认平台是否已接收，因此
    返回 ``unknown``，并由上层停止自动重试、进入人工对账。
    """

    def __init__(
        self,
        settings: Settings,
        channel: ChannelAccount,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not settings.real_tiktok_message_write_enabled:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 普通消息写入未启用", 503)
        if channel.platform != "tiktok" or channel.status != "connected":
            raise AppError(ErrorCode.TOKEN_INVALID, "TikTok 渠道未连接", 401)
        shop_cipher = channel.metadata_json.get("shop_cipher")
        if not isinstance(shop_cipher, str) or not shop_cipher:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 店铺标识缺失，请重新授权", 503)
        secret = settings.tiktok_app_secret
        if secret is None:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 普通消息写入未配置", 503)
        if CUSTOMER_SERVICE_SCOPE not in set(channel.scopes):
            raise AppError(ErrorCode.PERMISSION_DENIED, "TikTok 客服消息权限不足，请重新授权", 403)

        self.settings = settings
        self.channel = channel
        self.client = client
        self.shop_cipher = shop_cipher
        self.app_secret = secret.get_secret_value()
        self.access_token = decrypt_tiktok_access_token(channel, settings)

    async def send_text_message(self, command: SendMessageCommand) -> SendMessageResult:
        """按官方 202606 契约发送一次人工文本或物流卡片，不自动重试。"""
        if not command.human_confirmed:
            return self._failed("REAL_WRITE_REQUIRES_HUMAN_CONFIRMATION")
        if not command.external_conversation_id.isdigit():
            return self._failed("TIKTOK_CONVERSATION_ID_INVALID")
        if not is_tiktok_send_target_allowed(self.settings, self.channel.store_id, command.external_conversation_id):
            return self._failed("TIKTOK_CONVERSATION_NOT_ALLOWED")
        if command.message_type == "text" and len(command.content) > TIKTOK_TEXT_MAX_LENGTH:
            return self._failed("TIKTOK_MESSAGE_TOO_LONG")
        if command.message_type == "logistics_card" and not command.card_order_id:
            return self._failed("TIKTOK_LOGISTICS_CARD_ORDER_REQUIRED")

        path = SEND_MESSAGE_PATH_TEMPLATE.format(conversation_id=command.external_conversation_id)
        # 官方 content 字段本身是序列化后的 JSON 字符串；紧凑序列化保证
        # 签名正文与实际发送字节完全一致。
        card_content = {"order_id": command.card_order_id}
        if command.card_package_id:
            card_content["package_id"] = command.card_package_id
        body = {
            "type": "LOGISTICS_CARD" if command.message_type == "logistics_card" else "TEXT",
            "content": json.dumps(
                card_content if command.message_type == "logistics_card" else {"content": command.content},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "sender_role": "CUSTOMER_SERVICE",
        }
        body_bytes = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        params: dict[str, str | int] = {
            "app_key": self.settings.tiktok_app_key,
            "shop_cipher": self.shop_cipher,
            "timestamp": int(time.time()),
        }
        params["sign"] = generate_api_signature(path, params, self.app_secret, body_bytes)
        headers = {"content-type": "application/json", "x-tts-access-token": self.access_token}

        try:
            response = await self._send(path, params, headers, body_bytes)
        except httpx.TransportError:
            return self._unknown("TIKTOK_MESSAGE_RESULT_UNKNOWN")

        if response.status_code >= 500:
            return self._unknown("TIKTOK_MESSAGE_RESULT_UNKNOWN")
        if response.status_code == 429:
            return self._failed("TIKTOK_RATE_LIMITED")
        if response.status_code == 401:
            return self._failed("TIKTOK_TOKEN_EXPIRED")
        if response.status_code == 403:
            return self._failed("TIKTOK_PERMISSION_DENIED")
        if response.status_code >= 300:
            return self._failed("TIKTOK_MESSAGE_REJECTED")

        try:
            envelope = TikTokApiEnvelope.model_validate(response.json())
        except (ValueError, ValidationError):
            return self._unknown("TIKTOK_MESSAGE_RESULT_UNKNOWN")
        if envelope.code in WRITE_UNKNOWN_PLATFORM_CODES:
            self._log_platform_error(envelope)
            return self._unknown("TIKTOK_MESSAGE_RESULT_UNKNOWN")
        if envelope.code in TOKEN_EXPIRED_CODES:
            return self._failed("TIKTOK_TOKEN_EXPIRED")
        if envelope.code in TOKEN_INVALID_CODES:
            return self._failed("TIKTOK_TOKEN_INVALID")
        if envelope.code in PERMISSION_DENIED_CODES:
            return self._failed("TIKTOK_PERMISSION_DENIED")
        if envelope.code != 0:
            self._log_platform_error(envelope)
            return self._failed("TIKTOK_MESSAGE_REJECTED")
        message_id = envelope.data.get("message_id") if envelope.data else None
        if not isinstance(message_id, str) or not message_id.isdigit():
            return self._unknown("TIKTOK_MESSAGE_RESULT_UNKNOWN")
        return SendMessageResult(external_message_id=message_id, status="sent", mock=False)

    async def _send(
        self,
        path: str,
        params: dict[str, str | int],
        headers: dict[str, str],
        body: bytes,
    ) -> httpx.Response:
        """发送唯一一次请求；测试客户端用于离线验证精确契约。"""
        url = f"{API_BASE_URL}{path}"
        if self.client is not None:
            return await self.client.post(url, params=params, headers=headers, content=body)
        async with create_tiktok_http_client(self.settings) as client:
            return await client.post(url, params=params, headers=headers, content=body)

    @staticmethod
    def _failed(error_code: str) -> SendMessageResult:
        """返回确定失败；调用方可由人工创建新的幂等请求。"""
        return SendMessageResult(status="failed", mock=False, error_code=error_code)

    @staticmethod
    def _unknown(error_code: str) -> SendMessageResult:
        """返回不可确认结果；调用方必须停止重试并人工对账。"""
        return SendMessageResult(status="unknown", mock=False, error_code=error_code)

    @staticmethod
    def _log_platform_error(envelope: TikTokApiEnvelope) -> None:
        """只记录平台请求 ID 和数值错误码，不记录正文、Token 或消息。"""
        logger.warning(
            "tiktok_message_api_failed",
            extra={"provider_request_id": envelope.request_id, "provider_error_code": envelope.code},
        )
