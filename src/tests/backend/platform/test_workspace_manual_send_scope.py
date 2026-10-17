"""受控真实发送窗口的工作台可见性。"""

from types import SimpleNamespace

import pytest

from app.workspace import service


def test_only_allowlisted_tiktok_conversation_exposes_real_send(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        real_tiktok_message_write_enabled=True,
        tiktok_message_write_allowed_conversation_id="710688832392260838",
        allow_mock_platform_adapters=False,
    )
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    allowed = SimpleNamespace(platform="tiktok", external_conversation_id="710688832392260838")
    other = SimpleNamespace(platform="tiktok", external_conversation_id="710688832392260839")

    assert service._message_send_mode(allowed) == "real"
    assert service._message_send_mode(other) == "disabled"
