"""人工媒体上传凭据；上传本身不向买家发送消息。"""

import base64
import binascii
import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import UploadFile
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids, ensure_conversation_access
from app.integrations.tiktok_write import TikTokMessageClient, is_tiktok_send_target_allowed
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount, Store
from app.workspace.repository import find_conversation

IMAGE_MAX_BYTES = 10 * 1024 * 1024
VIDEO_MIN_BYTES = 10 * 1024 * 1024
VIDEO_MAX_BYTES = 100 * 1024 * 1024
MEDIA_TOKEN_SECONDS = 20 * 60


class MediaClaim(BaseModel):
    """仅服务器签发，绑定坐席、会话和店铺的短时平台资源。"""

    kind: Literal["image", "video"]
    value: str = Field(min_length=1, max_length=4096)
    store_id: uuid.UUID
    conversation_id: uuid.UUID
    actor_id: uuid.UUID
    send_idempotency_key: str = Field(min_length=1, max_length=200)
    expires_at: int
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)


class MediaUploadView(BaseModel):
    kind: Literal["image", "video"]
    file_name: str
    upload_token: str


def _encode_claim(claim: MediaClaim) -> str:
    payload = base64.urlsafe_b64encode(claim.model_dump_json().encode()).rstrip(b"=").decode()
    digest = hmac.new(get_settings().jwt_secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{digest}"


def verify_media_claim(
    token: str, *, store_id: uuid.UUID, conversation_id: uuid.UUID, actor_id: uuid.UUID, idempotency_key: str
) -> MediaClaim:
    """工具层再次核对签名与身份，Agent 不能自行构造媒体发送参数。"""
    try:
        payload, digest = token.split(".", 1)
        if len(payload) > 8192 or len(digest) != 64:
            raise ValueError("invalid token length")
        expected = hmac.new(get_settings().jwt_secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(digest, expected):
            raise ValueError("invalid signature")
        claim = MediaClaim.model_validate_json(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, ValidationError, UnicodeError, json.JSONDecodeError, binascii.Error) as error:
        raise AppError(ErrorCode.VALIDATION_ERROR, "媒体上传凭据无效", 422) from error
    if (
        claim.expires_at <= int(time.time())
        or claim.store_id != store_id
        or claim.conversation_id != conversation_id
        or claim.actor_id != actor_id
        or claim.send_idempotency_key != idempotency_key
    ):
        raise AppError(ErrorCode.PERMISSION_DENIED, "媒体上传凭据已过期或不属于当前会话", 403)
    return claim


def _media_kind(upload: UploadFile, header: bytes, size: int) -> tuple[Literal["image", "video"], str]:
    mime = upload.content_type or ""
    image_magic = (
        (mime == "image/jpeg" and header.startswith(b"\xff\xd8\xff"))
        or (mime == "image/png" and header.startswith(b"\x89PNG\r\n\x1a\n"))
        or (mime == "image/gif" and header[:6] in {b"GIF87a", b"GIF89a"})
        or (mime == "image/webp" and header.startswith(b"RIFF") and header[8:12] == b"WEBP")
    )
    if image_magic and 0 < size <= IMAGE_MAX_BYTES:
        return "image", mime
    video_magic = (mime in {"video/mp4", "video/quicktime"} and header[4:8] == b"ftyp") or (
        mime == "video/webm" and header.startswith(b"\x1a\x45\xdf\xa3")
    )
    if video_magic and VIDEO_MIN_BYTES <= size <= VIDEO_MAX_BYTES:
        return "video", mime
    raise AppError(
        ErrorCode.VALIDATION_ERROR,
        "仅支持 JPG/PNG/GIF/WebP 图片（不超过 10 MB）或 10–100 MB 的 MP4/MOV/WebM 视频",
        422,
    )


async def upload_media(
    session: AsyncSession, user: User, session_id: uuid.UUID, upload: UploadFile, idempotency_key: str
) -> MediaUploadView:
    """先核对店铺和真实发送白名单，再上传至当前授权店铺的 TikTok。"""
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, user, "workspace.reply")
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    await ensure_conversation_access(session, user, conversation, owner_required=True)
    settings = get_settings()
    channel = await session.scalar(
        select(ChannelAccount)
        .join(Store, Store.id == ChannelAccount.store_id)
        .where(
            ChannelAccount.store_id == conversation.store_id,
            ChannelAccount.platform == "tiktok",
            ChannelAccount.status == "connected",
            Store.status == "active",
            Store.deleted_at.is_(None),
        )
    )
    if (
        conversation.status == "closed"
        or not settings.real_tiktok_message_write_enabled
        or not is_tiktok_send_target_allowed(settings, conversation.store_id, conversation.external_conversation_id)
        or channel is None
        or "seller.customer_service" not in (channel.scopes or [])
        or (channel.token_expires_at is not None and channel.token_expires_at <= datetime.now(UTC))
    ):
        raise AppError(ErrorCode.PERMISSION_DENIED, "当前会话未开放真实媒体发送", 403)
    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)
    header = upload.file.read(16)
    upload.file.seek(0)
    kind, mime = _media_kind(upload, header, size)
    client = TikTokMessageClient(settings, channel)
    width: int | None = None
    height: int | None = None
    if kind == "image":
        value, width, height = await client.upload_image(upload.file, mime)
    else:
        value = await client.upload_video(upload.file, size, mime, conversation.external_conversation_id)
    claim = MediaClaim(
        kind=kind,
        value=value,
        width=width,
        height=height,
        store_id=conversation.store_id,
        conversation_id=conversation.id,
        actor_id=user.id,
        send_idempotency_key=idempotency_key,
        expires_at=int(time.time()) + MEDIA_TOKEN_SECONDS,
    )
    session.add(
        AuditLog(
            store_id=conversation.store_id,
            actor_type="user",
            actor_id=user.id,
            action="message.media_upload",
            resource_type="conversation",
            resource_id=conversation.id,
            after_data={"kind": kind, "size_bytes": size},
            result="succeeded",
        )
    )
    await session.commit()
    display_name = (upload.filename or "media").replace("\\", "/").rsplit("/", 1)[-1][:200]
    return MediaUploadView(kind=kind, file_name=display_name, upload_token=_encode_claim(claim))
