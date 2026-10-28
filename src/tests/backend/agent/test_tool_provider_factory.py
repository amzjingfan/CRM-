"""Agent 只能使用项目当前配置且具有原生工具协议的模型。"""

from types import SimpleNamespace

import pytest

from app.agents.providers.factory import validate_tool_model


def test_rejects_model_not_in_project_configuration() -> None:
    settings = SimpleNamespace(
        llm_primary_provider="deepseek",
        llm_primary_model="deepseek-chat",
        llm_fallback_provider=None,
        llm_fallback_model=None,
    )
    with pytest.raises(ValueError, match="not_configured"):
        validate_tool_model(settings, "openai", "gpt-4.1")


def test_all_current_native_provider_families_are_supported() -> None:
    for provider in ("deepseek", "openai", "anthropic"):
        settings = SimpleNamespace(
            llm_primary_provider=provider,
            llm_primary_model="configured-model",
            llm_fallback_provider=None,
            llm_fallback_model=None,
        )
        validate_tool_model(settings, provider, "configured-model")
