"""为答案生成和安全复核提供统一的两次结构化调用预算。"""

from app.agent.errors import LLMErrorCode, LLMProviderError
from app.agent.providers.base import LLMProvider, OutputT, ProviderResult, StructuredRequest


class StructuredGenerationService:
    """在主/备用 Provider 之间执行最多两次结构化生成。"""

    def __init__(
        self,
        primary_provider: LLMProvider,
        fallback_provider: LLMProvider | None,
        *,
        max_attempts: int = 2,
    ) -> None:
        if not 1 <= max_attempts <= 2:
            raise ValueError("答案节点尝试次数必须在 1 到 2 之间")
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider
        self.max_attempts = max_attempts

    async def generate(
        self,
        request: StructuredRequest,
        response_schema: type[OutputT],
    ) -> ProviderResult[OutputT]:
        """只重试瞬时错误；模型拒绝、认证和配置错误立即失败。"""
        providers = [self.primary_provider]
        if self.max_attempts == 2:
            providers.append(self.fallback_provider or self.primary_provider)
        last_error: LLMProviderError | None = None
        for provider in providers:
            try:
                result = await provider.generate_structured(request, response_schema)
                # Provider 已执行结构解析，这里再次校验可防止测试或未来适配器绕过契约。
                parsed = response_schema.model_validate(result.parsed_output)
                return ProviderResult(
                    provider=result.provider,
                    model=result.model,
                    parsed_output=parsed,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    latency_ms=result.latency_ms,
                    provider_request_id=result.provider_request_id,
                )
            except LLMProviderError as error:
                last_error = error
                if error.code == LLMErrorCode.LLM_REFUSAL or not error.retriable:
                    raise
        if last_error is None:
            raise RuntimeError("结构化生成尝试序列为空")
        raise last_error
