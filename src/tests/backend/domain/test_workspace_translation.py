"""工作台单条译文必须保持店铺隔离，并且只在显式开关下调用模型。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.config.settings import Settings
from app.shared.exceptions.errors import AppError, ErrorCode
from app.workspace import service as workspace_service


def test_workspace_translation_requires_configured_deepseek_without_enabling_general_llm() -> None:
    with pytest.raises(ValidationError, match="工作台消息翻译仅限非生产环境且必须配置 DeepSeek 模型"):
        Settings(_env_file=None, WORKSPACE_MESSAGE_TRANSLATION_ENABLED=True)
    settings = Settings(
        _env_file=None,
        WORKSPACE_MESSAGE_TRANSLATION_ENABLED=True,
        LLM_ENABLED=False,
        LLM_PRIMARY_PROVIDER="deepseek",
        LLM_PRIMARY_MODEL="deepseek-chat",
        DEEPSEEK_API_KEY="test-key",
    )
    assert settings.workspace_message_translation_enabled is True
    assert settings.llm_enabled is False
    with pytest.raises(ValueError, match="工作台消息翻译仅限非生产环境且必须配置 DeepSeek 模型"):
        settings.model_copy(update={"app_env": "production"}).validate_enabled_local_bge()


@pytest.mark.asyncio
async def test_translation_disabled_never_reads_or_calls_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    session = Mock(spec=AsyncSession)
    monkeypatch.setattr(
        workspace_service, "get_settings", lambda: SimpleNamespace(workspace_message_translation_enabled=False)
    )
    lookup = AsyncMock()
    monkeypatch.setattr(workspace_service, "find_conversation", lookup)

    with pytest.raises(AppError) as caught:
        await workspace_service.translate_message(
            session, SimpleNamespace(id=uuid.uuid4()), uuid.uuid4(), uuid.uuid4(), "trace"
        )
    assert caught.value.status_code == 503
    lookup.assert_not_awaited()


@pytest.mark.asyncio
async def test_translation_cannot_cross_store_or_conversation(monkeypatch: pytest.MonkeyPatch) -> None:
    session = Mock(spec=AsyncSession)
    session.scalar = AsyncMock(return_value=None)
    user = SimpleNamespace(id=uuid.uuid4())
    store_id, session_id, message_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(
        workspace_service,
        "get_settings",
        lambda: SimpleNamespace(workspace_message_translation_enabled=True),
    )
    monkeypatch.setattr(workspace_service, "allowed_store_ids", AsyncMock(return_value={store_id}))
    find = AsyncMock(return_value=None)
    monkeypatch.setattr(workspace_service, "find_conversation", find)
    provider = Mock()
    monkeypatch.setattr(workspace_service, "build_provider", provider)

    with pytest.raises(AppError) as denied:
        await workspace_service.translate_message(session, user, session_id, message_id, "trace")
    assert denied.value.code == ErrorCode.RESOURCE_NOT_FOUND
    session.scalar.assert_not_awaited()
    provider.assert_not_called()

    find.return_value = SimpleNamespace(id=session_id, store_id=store_id, platform="tiktok")
    with pytest.raises(AppError) as missing:
        await workspace_service.translate_message(session, user, session_id, message_id, "trace")
    assert missing.value.code == ErrorCode.RESOURCE_NOT_FOUND
    provider.assert_not_called()

    find.return_value = SimpleNamespace(id=session_id, store_id=store_id, platform="shopee")
    with pytest.raises(AppError) as unsupported:
        await workspace_service.translate_message(session, user, session_id, message_id, "trace")
    assert unsupported.value.code == ErrorCode.VALIDATION_ERROR
    provider.assert_not_called()


@pytest.mark.asyncio
async def test_translation_uses_stored_message_and_returns_chinese(monkeypatch: pytest.MonkeyPatch) -> None:
    session = Mock(spec=AsyncSession)
    store_id, session_id, message_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    session.scalar = AsyncMock(
        return_value=SimpleNamespace(id=message_id, content="Is the black one available?", message_type="text")
    )
    monkeypatch.setattr(
        workspace_service,
        "get_settings",
        lambda: SimpleNamespace(workspace_message_translation_enabled=True, llm_primary_model="deepseek-chat"),
    )
    monkeypatch.setattr(workspace_service, "allowed_store_ids", AsyncMock(return_value={store_id}))
    monkeypatch.setattr(
        workspace_service,
        "find_conversation",
        AsyncMock(return_value=SimpleNamespace(id=session_id, store_id=store_id, platform="tiktok")),
    )
    provider = Mock()
    monkeypatch.setattr(workspace_service, "build_provider", Mock(return_value=provider))
    translate = AsyncMock(
        return_value=SimpleNamespace(
            message_translation="请问黑色还有货吗？",
            provider="deepseek",
            model="deepseek-chat",
            input_tokens=21,
            output_tokens=13,
        )
    )
    monkeypatch.setattr(workspace_service.TranslationService, "translate_bundle", translate)

    result = await workspace_service.translate_message(
        session, SimpleNamespace(id=uuid.uuid4()), session_id, message_id, "trace"
    )
    assert result.message_id == message_id
    assert result.translated_text == "请问黑色还有货吗？"
    assert translate.await_args.kwargs["message"] == "Is the black one available?"
    assert translate.await_args.kwargs["draft_reply"] is None
    assert translate.await_args.kwargs["target_language"] == "zh-CN"
    assert session.scalar.await_args.args[0].compile().params["conversation_id_1"] == session_id
    assert session.add.call_args.args[0].after_data["input_tokens"] == 21
    assert "Is the black one available?" not in str(session.add.call_args.args[0].after_data)
    session.commit.assert_awaited_once()
