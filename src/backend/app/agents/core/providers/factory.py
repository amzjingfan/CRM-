"""根据经过类型校验的配置构建白名单模型适配器。"""

from app.agents.core.errors import LLMErrorCode, LLMProviderError
from app.agents.core.providers.anthropic_provider import AnthropicProvider
from app.agents.core.providers.base import LLMProvider
from app.agents.core.providers.deepseek_provider import DeepSeekProvider
from app.agents.core.providers.openai_provider import OpenAIProvider
from app.shared.config.settings import Settings


def build_provider(provider_name: str, model_name: str | None, settings: Settings) -> LLMProvider:
    """仅允许显式支持的 Provider，缺少模型名或密钥时立即失败。"""
    normalized_name = provider_name.strip().lower()
    if not model_name:
        raise LLMProviderError(LLMErrorCode.LLM_CONFIGURATION_ERROR, "未配置模型名称", retriable=False)
    if normalized_name == "openai":
        if settings.openai_api_key is None:
            raise LLMProviderError(LLMErrorCode.LLM_CONFIGURATION_ERROR, "未配置 OpenAI API Key", retriable=False)
        return OpenAIProvider(
            api_key=settings.openai_api_key.get_secret_value(),
            model_name=model_name,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if normalized_name == "anthropic":
        if settings.anthropic_api_key is None:
            raise LLMProviderError(LLMErrorCode.LLM_CONFIGURATION_ERROR, "未配置 Anthropic API Key", retriable=False)
        return AnthropicProvider(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model_name=model_name,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if normalized_name == "deepseek":
        if settings.deepseek_api_key is None:
            raise LLMProviderError(LLMErrorCode.LLM_CONFIGURATION_ERROR, "未配置 DeepSeek API Key", retriable=False)
        return DeepSeekProvider(
            api_key=settings.deepseek_api_key.get_secret_value(),
            model_name=model_name,
            base_url=settings.deepseek_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
            thinking_enabled=settings.deepseek_thinking_enabled,
        )
    raise LLMProviderError(
        LLMErrorCode.LLM_CONFIGURATION_ERROR,
        "不支持的模型供应商",
        retriable=False,
    )


def build_provider_pair(settings: Settings) -> tuple[LLMProvider, LLMProvider | None]:
    """在 AI 显式启用后构建主模型及可选备用模型。"""
    if not settings.llm_enabled:
        raise LLMProviderError(LLMErrorCode.LLM_CONFIGURATION_ERROR, "AI 功能未启用", retriable=False)
    primary = build_provider(settings.llm_primary_provider, settings.llm_primary_model, settings)
    fallback = None
    if settings.llm_fallback_provider and settings.llm_fallback_model:
        fallback = build_provider(settings.llm_fallback_provider, settings.llm_fallback_model, settings)
    return primary, fallback
