"""TikTok Shop 人工确认普通消息写客户端。"""

import json
import logging
import time
import uuid
from typing import BinaryIO
from urllib.parse import urlsplit

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
UPLOAD_IMAGE_PATH = "/customer_service/202309/images/upload"
UPLOAD_FILE_INIT_PATH = "/open/202512/file/init"
VIDEO_CHUNK_BYTES = 20 * 1024 * 1024
VIDEO_MIN_CHUNK_BYTES = 5 * 1024 * 1024
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

    def _signed_params(self, path: str, body: bytes = b"") -> dict[str, str | int]:
        params: dict[str, str | int] = {
            "app_key": self.settings.tiktok_app_key,
            "shop_cipher": self.shop_cipher,
            "timestamp": int(time.time()),
        }
        params["sign"] = generate_api_signature(path, params, self.app_secret, body)
        return params

    @staticmethod
    def _upload_data(response: httpx.Response) -> dict[str, object]:
        if response.status_code >= 300:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 媒体上传失败", 503)
        try:
            envelope = TikTokApiEnvelope.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 媒体上传响应无效", 503) from error
        if envelope.code != 0 or not isinstance(envelope.data, dict):
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 媒体上传失败", 503)
        return envelope.data

    async def upload_image(self, file: BinaryIO, mime: str) -> tuple[str, int, int]:
        """按官方客服图片接口上传，不把本地文件保存在业务库。"""
        path = UPLOAD_IMAGE_PATH
        extension = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp"}[mime]
        try:
            if self.client is not None:
                response = await self.client.post(
                    f"{API_BASE_URL}{path}",
                    params=self._signed_params(path),
                    headers={"x-tts-access-token": self.access_token},
                    files={"data": (f"message-image.{extension}", file, mime)},
                    timeout=120,
                )
            else:
                async with create_tiktok_http_client(self.settings) as client:
                    response = await client.post(
                        f"{API_BASE_URL}{path}",
                        params=self._signed_params(path),
                        headers={"x-tts-access-token": self.access_token},
                        files={"data": (f"message-image.{extension}", file, mime)},
                        timeout=120,
                    )
        except httpx.TransportError as error:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 图片上传未确认，请重新选择文件", 503) from error
        data = self._upload_data(response)
        url, width, height = data.get("url"), data.get("width"), data.get("height")
        try:
            image_url = urlsplit(url) if isinstance(url, str) else None
        except ValueError as error:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 图片上传响应缺少有效图片信息", 503) from error
        if (
            not isinstance(url, str)
            or image_url is None
            or image_url.scheme != "https"
            or not image_url.hostname
            or image_url.username
            or image_url.password
            or not isinstance(width, int)
            or not isinstance(height, int)
            or isinstance(width, bool)
            or isinstance(height, bool)
            or width <= 0
            or height <= 0
        ):
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 图片上传响应缺少有效图片信息", 503)
        return url, width, height

    async def upload_video(self, file: BinaryIO, size: int, mime: str, conversation_id: str) -> str:
        """大视频按 20 MB 分片顺序上传；平台最后一片返回资源 ID。"""
        if not conversation_id.isdigit():
            raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 会话 ID 无效", 422)
        chunks: list[int] = []
        remaining = size
        while remaining:
            chunk_size = min(remaining, VIDEO_CHUNK_BYTES)
            chunks.append(chunk_size)
            remaining -= chunk_size
        if len(chunks) > 1 and chunks[-1] < VIDEO_MIN_CHUNK_BYTES:
            chunks[-2] += chunks.pop()
        path = UPLOAD_FILE_INIT_PATH
        target_path = f"[POST]{SEND_MESSAGE_PATH_TEMPLATE.format(conversation_id=conversation_id)}"
        extension = {"video/webm": ".webm", "video/quicktime": ".mov"}.get(mime, ".mp4")
        body = json.dumps(
            {
                "file_size": size,
                "file_name": f"message-{uuid.uuid4().hex}{extension}",
                "total_chunk_count": len(chunks),
                "file_type": "video",
                "target_path": target_path,
            },
            separators=(",", ":"),
        ).encode()
        try:
            if self.client is not None:
                return await self._upload_video_with_client(self.client, file, chunks, mime, path, body)
            async with create_tiktok_http_client(self.settings) as client:
                return await self._upload_video_with_client(client, file, chunks, mime, path, body)
        except httpx.TransportError as error:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 视频上传未确认，请重新选择文件", 503) from error

    async def _upload_video_with_client(
        self, client: httpx.AsyncClient, file: BinaryIO, chunks: list[int], mime: str, path: str, body: bytes
    ) -> str:
        response = await client.post(
            f"{API_BASE_URL}{path}",
            params=self._signed_params(path, body),
            headers={"content-type": "application/json", "x-tts-access-token": self.access_token},
            content=body,
            timeout=120,
        )
        data = self._upload_data(response)
        upload_url, upload_token = data.get("upload_url"), data.get("upload_token")
        if not isinstance(upload_url, str) or not isinstance(upload_token, str) or not upload_token:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 视频上传初始化响应无效", 503)
        try:
            parsed = urlsplit(upload_url)
            port = parsed.port
        except ValueError as error:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 视频上传地址无效", 503) from error
        # 平台返回 URL 仍是外部输入；仅允许官方固定出口域，禁止重定向到内网。
        if (
            parsed.scheme != "https"
            or parsed.hostname != "open-api.tiktokglobalshop.com"
            or parsed.username
            or parsed.password
            or port
            or parsed.fragment
            or not parsed.path.startswith("/file/")
        ):
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 视频上传地址无效", 503)
        for number, chunk_size in enumerate(chunks, 1):
            chunk = file.read(chunk_size)
            if len(chunk) != chunk_size:
                raise AppError(ErrorCode.VALIDATION_ERROR, "视频文件读取不完整", 422)
            response = await client.put(
                upload_url,
                params={
                    "upload_token": upload_token,
                    "chunk_num": number,
                    "app_key": self.settings.tiktok_app_key,
                    "shop_cipher": self.shop_cipher,
                },
                headers={"content-type": mime, "x-tts-access-token": self.access_token},
                content=chunk,
                timeout=120,
            )
            data = self._upload_data(response)
            if number < len(chunks) and not isinstance(data.get("part_id"), str):
                raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 视频分片响应无效", 503)
        resource_id = data.get("resource_id")
        if not isinstance(resource_id, str) or not resource_id or len(resource_id) > 200:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 视频资源 ID 缺失", 503)
        return resource_id

    async def send_text_message(self, command: SendMessageCommand) -> SendMessageResult:
        """按官方 202606 契约发送一次人工消息，不自动重试。"""
        notification_allowed = (
            command.logistics_notification_authorized
            and self.settings.tiktok_automation_effective_enabled
            and self.settings.app_env != "production"
            and command.message_type == "text"
            and self.settings.logistics_notifications_enabled
            and self.settings.real_tiktok_logistics_notifications_enabled
        )
        automation_allowed = (
            command.automation_authorized
            and self.settings.tiktok_automation_effective_enabled
            and self.settings.app_env != "production"
            and command.sender_role in {"ROBOT", "SYSTEM"}
        )
        if command.sender_role != "CUSTOMER_SERVICE" and not (automation_allowed or notification_allowed):
            return SendMessageResult(status="failed", mock=False, error_code="AUTOMATION_IDENTITY_INVALID")
        if not command.human_confirmed and not notification_allowed and not automation_allowed:
            return self._failed("REAL_WRITE_REQUIRES_HUMAN_CONFIRMATION")
        if not command.external_conversation_id.isdigit():
            return self._failed("TIKTOK_CONVERSATION_ID_INVALID")
        if not is_tiktok_send_target_allowed(self.settings, self.channel.store_id, command.external_conversation_id):
            return self._failed("TIKTOK_CONVERSATION_NOT_ALLOWED")
        if command.message_type == "text" and len(command.content) > TIKTOK_TEXT_MAX_LENGTH:
            return self._failed("TIKTOK_MESSAGE_TOO_LONG")
        if command.message_type == "logistics_card" and not command.card_order_id:
            return self._failed("TIKTOK_LOGISTICS_CARD_ORDER_REQUIRED")
        if command.message_type == "order_card" and not command.card_order_id:
            return self._failed("TIKTOK_ORDER_CARD_ORDER_REQUIRED")
        if command.message_type in {"image", "video"} and not command.media_value:
            return self._failed("TIKTOK_MEDIA_RESOURCE_REQUIRED")
        if command.message_type == "image" and (not command.media_width or not command.media_height):
            return self._failed("TIKTOK_IMAGE_SIZE_REQUIRED")

        path = SEND_MESSAGE_PATH_TEMPLATE.format(conversation_id=command.external_conversation_id)
        # 官方 content 字段本身是序列化后的 JSON 字符串；紧凑序列化保证
        # 签名正文与实际发送字节完全一致。
        card_content: dict[str, object] = {"order_id": command.card_order_id}
        if command.message_type == "logistics_card" and command.card_package_id:
            card_content["package_id"] = command.card_package_id
        content: dict[str, object]
        if command.message_type in {"logistics_card", "order_card"}:
            content = card_content
        elif command.message_type == "image":
            content = {"url": command.media_value, "width": command.media_width, "height": command.media_height}
        elif command.message_type == "video":
            content = {"vid": command.media_value}
        else:
            content = {"content": command.content}
        body = {
            "type": command.message_type.upper(),
            "content": json.dumps(content, ensure_ascii=False, separators=(",", ":")),
            "sender_role": command.sender_role,
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
