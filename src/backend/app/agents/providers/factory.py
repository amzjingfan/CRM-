"""只为已配置模型构建短生命周期原生 function-calling 客户端。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from app.agents.orchestration.router import RouteModelPort
from app.agents.providers.anthropic_tool_calling import AnthropicToolCallingProvider
from app.agents.providers.budget import BudgetedToolProvider
from app.agents.providers.tool_calling import DeepSeekToolCallingProvider, OpenAIToolCallingProvider
from app.agents.runtime.context import ModelLimits
from app.shared.config.settings import Settings

NATIVE_TOOL_PROVIDERS = frozenset({"deepseek", "openai", "anthropic"})


def model_limits(settings: Settings, provider: str, model_name: str) -> ModelLimits:
    """窗口由项目模型配置提供，默认保守预算不代表供应商宣称的最大窗口。"""
    validate_tool_model(settings, provider, model_name)
    primary = (provider, model_name) == (settings.llm_primary_provider, settings.llm_primary_model)
    window = settings.llm_primary_context_window_tokens if primary else settings.llm_fallback_context_window_tokens
    return ModelLimits(window, output_reserve_tokens=settings.llm_max_output_tokens, safety_margin_tokens=1024)


def validate_tool_model(settings: Settings, provider: str | None, model_name: str | None) -> None:
    """只有项目当前配置的原生工具模型能发布和运行，未知模型失败关闭。"""
    configured = {
        (settings.llm_primary_provider, settings.llm_primary_model),
        (settings.llm_fallback_provider, settings.llm_fallback_model),
    }
    if not provider or not model_name or (provider, model_name) not in configured:
        raise ValueError("tool_model_not_configured")
    if provider not in NATIVE_TOOL_PROVIDERS:
        raise ValueError("tool_provider_unsupported")


@asynccontextmanager
async def tool_provider(settings: Settings, provider: str, model_name: str) -> AsyncIterator[RouteModelPort]:
    """请求完成或取消时关闭 Provider 连接；不在日志中输出密钥。"""
    validate_tool_model(settings, provider, model_name)
    if provider == "deepseek":
        secret = settings.deepseek_api_key
        if secret is None:
            raise ValueError("tool_provider_credentials_missing")
        client = AsyncOpenAI(
            api_key=secret.get_secret_value(),
            base_url=settings.deepseek_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )
        try:
            adapter = DeepSeekToolCallingProvider(
                model_name=model_name,
                client=client,
                thinking_enabled=settings.deepseek_thinking_enabled,
            )
            yield BudgetedToolProvider(adapter, model_limits(settings, provider, model_name))
        finally:
            await client.close()
    elif provider == "openai":
        secret = settings.openai_api_key
        if secret is None:
            raise ValueError("tool_provider_credentials_missing")
        client = AsyncOpenAI(
            api_key=secret.get_secret_value(),
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )
        try:
            yield BudgetedToolProvider(
                OpenAIToolCallingProvider(model_name=model_name, client=client),
                model_limits(settings, provider, model_name),
            )
        finally:
            await client.close()
    elif provider == "anthropic":
        secret = settings.anthropic_api_key
        if secret is None:
            raise ValueError("tool_provider_credentials_missing")
        anthropic_client = AsyncAnthropic(
            api_key=secret.get_secret_value(),
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )
        try:
            yield BudgetedToolProvider(
                AnthropicToolCallingProvider(model_name=model_name, client=anthropic_client),
                model_limits(settings, provider, model_name),
            )
        finally:
            await anthropic_client.close()
    else:
        raise ValueError("tool_provider_unsupported")
