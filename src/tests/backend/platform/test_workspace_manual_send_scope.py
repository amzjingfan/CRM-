"""真实发送范围与工作台可见性。"""

import uuid
from types import SimpleNamespace

import pytest

from app.workspace import service


def test_only_allowlisted_tiktok_conversation_exposes_real_send(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        real_tiktok_message_write_enabled=True,
        tiktok_message_write_allowed_conversation_id="710688832392260838",
        tiktok_message_write_allowed_store_ids=None,
        allow_mock_platform_adapters=False,
    )
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    store_id = uuid.uuid4()
    allowed = SimpleNamespace(platform="tiktok", store_id=store_id, external_conversation_id="710688832392260838")
    other = SimpleNamespace(platform="tiktok", store_id=store_id, external_conversation_id="710688832392260839")
    channel = SimpleNamespace(
        store_id=store_id,
        status="connected",
        scopes=["seller.customer_service"],
        metadata_json={"shop_cipher": "test"},
        token_expires_at=None,
    )

    assert service._message_send_mode(allowed, channel) == "real"
    assert service._message_send_mode(other, channel) == "disabled"


def test_allowlisted_store_exposes_all_its_conversations_only_with_connected_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store_id = uuid.uuid4()
    settings = SimpleNamespace(
        real_tiktok_message_write_enabled=True,
        tiktok_message_write_allowed_conversation_id=None,
        tiktok_message_write_allowed_store_ids=str(store_id),
        allow_mock_platform_adapters=False,
    )
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    channel = SimpleNamespace(
        store_id=store_id,
        status="connected",
        scopes=["seller.customer_service"],
        metadata_json={"shop_cipher": "test"},
        token_expires_at=None,
    )
    first = SimpleNamespace(platform="tiktok", store_id=store_id, external_conversation_id="710688832392260838")
    second = SimpleNamespace(platform="tiktok", store_id=store_id, external_conversation_id="710688832392260839")
    other = SimpleNamespace(platform="tiktok", store_id=uuid.uuid4(), external_conversation_id="710688832392260840")

    assert service._message_send_mode(first, channel) == "real"
    assert service._message_send_mode(second, channel) == "real"
    assert service._message_send_mode(other, channel) == "disabled"
    assert service._message_send_mode(first, None) == "disabled"
    assert service._message_send_mode(first, SimpleNamespace(**{**vars(channel), "scopes": None})) == "disabled"
    assert service._message_send_mode(first, SimpleNamespace(**{**vars(channel), "metadata_json": None})) == "disabled"
    assert (
        service._message_send_mode(
            first,
            SimpleNamespace(
                store_id=store_id,
                status="disconnected",
                scopes=channel.scopes,
                metadata_json=channel.metadata_json,
                token_expires_at=None,
            ),
        )
        == "disabled"
    )
    assert (
        service._message_send_mode(
            first,
            SimpleNamespace(
                store_id=store_id,
                status="connected",
                scopes=[],
                metadata_json=channel.metadata_json,
                token_expires_at=None,
            ),
        )
        == "disabled"
    )
