"""工作台统一搜索和待人工审阅译文的边界测试。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.draft_translation import (
    DraftTranslationModelOutput,
    DraftTranslationService,
)
from app.shared.exceptions.errors import AppError, ErrorCode
from app.workspace import service as workspace_service
from app.workspace.schemas import DraftTranslationRequest, SessionSearchRequest


def test_draft_translation_accepts_only_displayed_target_languages() -> None:
    supported = ("en", "id", "fil", "ms", "th", "my", "vi", "pt", "es", "pl", "fr", "zh-TW", "zh-CN")
    for language in supported:
        assert DraftTranslationRequest(source_text="你好", target_language=language).target_language == language
        assert (
            DraftTranslationModelOutput(target_language=language, translated_text="Hello").target_language == language
        )
    with pytest.raises(ValidationError):
        DraftTranslationRequest(source_text="你好", target_language="unsupported")


def test_search_request_rejects_unbounded_terms_and_invalid_scope() -> None:
    with pytest.raises(ValidationError):
        SessionSearchRequest(terms=["x"] * 21)
    with pytest.raises(ValidationError):
        SessionSearchRequest(search_scope="unsupported", q="buyer")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_search_validates_batch_bounds_before_store_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=AsyncSession)
    actor = SimpleNamespace(id=uuid.uuid4())
    allowed = AsyncMock(return_value={uuid.uuid4()})
    listing = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(workspace_service, "allowed_store_ids", allowed)
    monkeypatch.setattr(workspace_service, "list_conversations", listing)

    with pytest.raises(AppError) as conflict:
        await workspace_service.get_session_list(
            session, actor, "all", None, None, None, 1, 30, "all", "buyer", ["order"]
        )
    assert conflict.value.code == ErrorCode.VALIDATION_ERROR
    with pytest.raises(AppError):
        await workspace_service.get_session_list(
            session, actor, "all", None, None, None, 1, 30, "all", None, ["x"] * 21
        )
    allowed.assert_not_awaited()
    listing.assert_not_awaited()

    await workspace_service.get_session_list(
        session,
        actor,
        "all",
        None,
        None,
        None,
        1,
        30,
        "all",
        None,
        [" Alice ", "Alice", "O-7"],
    )
    assert listing.await_args.args[-2:] == ("all", ("Alice", "O-7"))

    await workspace_service.get_session_list(session, actor, "all", None, None, None, 1, 30, "buyer", "Test Buyer", [])
    assert listing.await_args.args[-2:] == ("buyer", ("Test Buyer",))


@pytest.mark.asyncio
async def test_draft_translation_registers_safe_prompt_and_does_not_send() -> None:
    generator = SimpleNamespace(
        generate=AsyncMock(
            return_value=SimpleNamespace(
                parsed_output=DraftTranslationModelOutput(target_language="en", translated_text="Hello!"),
                provider="deepseek",
                model="deepseek-chat",
                input_tokens=9,
                output_tokens=3,
            )
        )
    )
    result = await DraftTranslationService(generator).translate(
        source_text="你好！", target_language="en", trace_id="test"
    )
    assert result.translated_text == "Hello!"
    request = generator.generate.await_args.args[0]
    request.ensure_safe_for_external_provider(response_schema_name="DraftTranslationModelOutput")
    assert "你好！" in request.user_prompt
    assert generator.generate.await_count == 1

    with pytest.raises(ValueError, match="需脱敏"):
        await DraftTranslationService(generator).translate(
            source_text="Contact me at buyer@example.com",
            target_language="en",
            trace_id="test",
        )
    assert generator.generate.await_count == 1


@pytest.mark.asyncio
async def test_workspace_draft_translation_is_store_scoped_audited_and_preview_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=AsyncSession)
    session.commit = AsyncMock()
    actor = SimpleNamespace(id=uuid.uuid4())
    conversation_id, store_id = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(
        workspace_service,
        "get_settings",
        lambda: SimpleNamespace(
            workspace_message_translation_enabled=True,
            llm_primary_model="deepseek-chat",
        ),
    )
    monkeypatch.setattr(workspace_service, "allowed_store_ids", AsyncMock(return_value={store_id}))
    lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(workspace_service, "find_conversation", lookup)
    provider = Mock()
    monkeypatch.setattr(workspace_service, "build_provider", provider)
    with pytest.raises(AppError) as denied:
        await workspace_service.translate_draft(session, actor, conversation_id, "你好", "en", "trace")
    assert denied.value.code == ErrorCode.RESOURCE_NOT_FOUND
    provider.assert_not_called()

    lookup.return_value = SimpleNamespace(id=conversation_id, store_id=store_id, platform="tiktok", status="active")
    monkeypatch.setattr(workspace_service, "_connected_send_channel", AsyncMock(return_value=None))
    monkeypatch.setattr(workspace_service, "_message_send_mode", lambda *_args: "real")
    translated = AsyncMock(
        return_value=SimpleNamespace(
            source_text_sha256="a" * 64,
            target_language="en",
            translated_text="Hello!",
            provider="deepseek",
            model="deepseek-chat",
            input_tokens=9,
            output_tokens=3,
        )
    )
    monkeypatch.setattr(workspace_service.DraftTranslationService, "translate", translated)
    result = await workspace_service.translate_draft(session, actor, conversation_id, "你好", "en", "trace")
    assert result.translated_text == "Hello!"
    assert lookup.await_args.args[2] == {store_id}
    assert session.add.call_args.args[0].action == "draft.translate"
    assert "你好" not in str(session.add.call_args.args[0].after_data)
    session.commit.assert_awaited_once()
    translated.assert_awaited_once()
