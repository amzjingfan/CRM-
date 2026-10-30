"""模板 HTTP 边界与 DTO 拒绝未知私密字段。"""

import pytest
from pydantic import ValidationError


def test_lifecycle_dtos_reject_unknown_and_ambiguous_source() -> None:
    from app.agents.management.templates.lifecycle_schemas import (
        TemplateCreate,
        TemplateFromAgent,
        TemplateUpdate,
    )

    draft = TemplateCreate(code="service", name="客服")
    assert draft.config.default_agent_name == "客服"
    assert draft.config.suggested_code == "service"
    with pytest.raises(ValidationError):
        TemplateUpdate(expected_revision=1, file_ids=[])
    with pytest.raises(ValidationError):
        TemplateUpdate(expected_revision=1, name=None)
    with pytest.raises(ValidationError):
        TemplateFromAgent(
            code="service",
            name="客服",
            source_agent_id="00000000-0000-0000-0000-000000000001",
        )
    with pytest.raises(ValidationError):
        TemplateFromAgent(
            code="service",
            name="客服",
            source_agent_id="00000000-0000-0000-0000-000000000001",
            source_version=1,
            source_draft_revision=1,
        )


@pytest.mark.parametrize(
    ("primary", "fallback", "expected"),
    [
        ("unsupported-provider", "openai", ["openai"]),
        ("deepseek", "unsupported-provider", ["deepseek"]),
        ("openai", "unsupported-provider", ["openai"]),
        ("anthropic", "unsupported-provider", ["anthropic"]),
        ("unsupported-provider", None, []),
        (None, None, []),
    ],
)
def test_template_catalog_only_offers_configured_native_tool_models(
    monkeypatch: pytest.MonkeyPatch, primary: str | None, fallback: str | None, expected: list[str]
) -> None:
    from app.agents.management import config_service
    from app.agents.management.templates.service import template_catalog
    from app.agents.providers.factory import validate_tool_model
    from app.shared.config.settings import get_settings

    settings = get_settings().model_copy(
        update={
            "llm_primary_provider": primary or "openai",
            "llm_primary_model": "configured-primary" if primary else None,
            "llm_fallback_provider": fallback,
            "llm_fallback_model": "configured-fallback" if fallback else None,
        }
    )
    monkeypatch.setattr(config_service, "get_settings", lambda: settings)
    options = config_service.runtime_view().model_options
    for option in options:
        if option["provider"] == "unsupported-provider":
            with pytest.raises(ValueError, match="tool_provider_unsupported"):
                validate_tool_model(settings, option["provider"], option["model_name"])
    actual = template_catalog().model_options
    assert actual == [option for option in options if option["provider"] in expected]
    assert [option["provider"] for option in actual] == expected
    for option in actual:
        validate_tool_model(settings, option["provider"], option["model_name"])
