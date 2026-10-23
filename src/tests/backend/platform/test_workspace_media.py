"""客服媒体文件门禁和一次性上传凭据。"""

import io
import time
import uuid

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.workspace import media


def test_media_claim_is_bound_to_exact_actor_conversation_and_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        media,
        "get_settings",
        lambda: type("Settings", (), {"jwt_secret_key": "unit-test-secret-key-with-at-least-32-bytes"})(),
    )
    claim = media.MediaClaim(
        kind="video",
        value="verified-video-id",
        store_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        actor_id=uuid.uuid4(),
        send_idempotency_key="media-send-1",
        expires_at=int(time.time()) + 60,
    )
    token = media._encode_claim(claim)
    assert (
        media.verify_media_claim(
            token,
            store_id=claim.store_id,
            conversation_id=claim.conversation_id,
            actor_id=claim.actor_id,
            idempotency_key=claim.send_idempotency_key,
        )
        == claim
    )
    with pytest.raises(Exception, match="不属于当前会话"):
        media.verify_media_claim(
            token,
            store_id=uuid.uuid4(),
            conversation_id=claim.conversation_id,
            actor_id=claim.actor_id,
            idempotency_key=claim.send_idempotency_key,
        )
    with pytest.raises(Exception, match="不属于当前会话"):
        media.verify_media_claim(
            token,
            store_id=claim.store_id,
            conversation_id=claim.conversation_id,
            actor_id=claim.actor_id,
            idempotency_key="different-send",
        )
    with pytest.raises(Exception, match="凭据无效"):
        media.verify_media_claim(
            token[:-1] + ("0" if token[-1] != "0" else "1"),
            store_id=claim.store_id,
            conversation_id=claim.conversation_id,
            actor_id=claim.actor_id,
            idempotency_key=claim.send_idempotency_key,
        )


def test_media_file_type_and_size_are_checked_before_platform_upload() -> None:
    small_video = UploadFile(
        file=io.BytesIO(b"\0\0\0\0ftyp"), filename="short.mp4", headers=Headers({"content-type": "video/mp4"})
    )
    with pytest.raises(Exception, match="10–100 MB"):
        media._media_kind(small_video, b"\0\0\0\0ftyp", 9 * 1024 * 1024)
    fake_image = UploadFile(
        file=io.BytesIO(b"not an image"), filename="fake.png", headers=Headers({"content-type": "image/png"})
    )
    with pytest.raises(Exception, match="JPG/PNG"):
        media._media_kind(fake_image, b"not an image", 100)
    image = UploadFile(
        file=io.BytesIO(b"\x89PNG\r\n\x1a\n"), filename="real.png", headers=Headers({"content-type": "image/png"})
    )
    assert media._media_kind(image, b"\x89PNG\r\n\x1a\n", 10 * 1024 * 1024) == ("image", "image/png")
