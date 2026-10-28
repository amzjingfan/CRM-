"""Anthropic Claude Messages API 结构化输出适配器。"""

import time

from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import ValidationError

from app.agents.core.errors import LLMErrorCode, LLMProviderError
from app.agents.core.providers.base import LLMProvider, OutputT, ProviderResult, StructuredRequest


class AnthropicProvider(LLMProvider):
    """通过 Claude Messages API 调用模型并统一响应格式。"""

    provider_name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        timeout_seconds: float,
        client: AsyncAnthropic | None = None,
    ) -> None:
        """创建关闭 SDK 重试的客户端，避免突破三次总尝试上限。"""
        if not api_key or not model_name:
            raise LLMProviderError(
                LLMErrorCode.LLM_CONFIGURATION_ERROR,
                "Anthropic 配置不完整",
                retriable=False,
            )
        self.model_name = model_name
        self._client = client or AsyncAnthropic(api_key=api_key, timeout=timeout_seconds, max_retries=0)

    async def generate_structured(
        self,
        request: StructuredRequest,
        response_schema: type[OutputT],
    ) -> ProviderResult[OutputT]:
        """执行单次结构化请求并隔离 SDK 异常和原始输出。"""
        request.ensure_safe_for_external_provider(response_schema_name=response_schema.__name__)
        started_at = time.perf_counter()
        try:
            response = await self._client.messages.parse(
                model=self.model_name,
                max_tokens=request.max_output_tokens,
                system=request.system_prompt,
                messages=[{"role": "user", "content": request.user_prompt}],
                output_format=response_schema,
            )
        except APITimeoutError as error:
            raise LLMProviderError(LLMErrorCode.LLM_TIMEOUT, "Claude 调用超时", retriable=True) from error
        except RateLimitError as error:
            raise LLMProviderError(LLMErrorCode.LLM_RATE_LIMITED, "Claude 请求被限流", retriable=True) from error
        except APIConnectionError as error:
            raise LLMProviderError(
                LLMErrorCode.LLM_CONNECTION_ERROR,
                "Claude 连接失败",
                retriable=True,
            ) from error
        except AuthenticationError as error:
            raise LLMProviderError(
                LLMErrorCode.LLM_AUTHENTICATION_ERROR,
                "Claude 认证失败",
                retriable=False,
            ) from error
        except PermissionDeniedError as error:
            raise LLMProviderError(
                LLMErrorCode.LLM_PERMISSION_DENIED,
                "Claude 权限不足",
                retriable=False,
            ) from error
        except BadRequestError as error:
            raise LLMProviderError(
                LLMErrorCode.LLM_INVALID_REQUEST,
                "Claude 请求参数无效",
                retriable=False,
            ) from error
        except APIStatusError as error:
            raise LLMProviderError(
                LLMErrorCode.LLM_PROVIDER_ERROR,
                "Claude 服务异常",
                retriable=error.status_code >= 500,
            ) from error
        except (ValidationError, ValueError) as error:
            raise LLMProviderError(
                LLMErrorCode.LLM_OUTPUT_INVALID,
                "Claude 结构化输出无效",
                retriable=True,
            ) from error

        # Claude 在 max_tokens 时可能保留部分可解析 JSON；截断结果不能进入分类服务。
        if response.stop_reason == "max_tokens":
            raise LLMProviderError(
                LLMErrorCode.LLM_OUTPUT_INVALID,
                "Claude 输出因达到 Token 上限而截断",
                retriable=True,
            )
        if response.stop_reason == "refusal":
            raise LLMProviderError(LLMErrorCode.LLM_REFUSAL, "Claude 拒绝处理", retriable=False)
        parsed_output = response.parsed_output
        if parsed_output is None:
            raise LLMProviderError(
                LLMErrorCode.LLM_OUTPUT_INVALID,
                "Claude 未返回完整结构化结果",
                retriable=True,
            )

        return ProviderResult(
            provider=self.provider_name,
            model=self.model_name,
            parsed_output=parsed_output,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
            provider_request_id=getattr(response, "_request_id", None),
        )
