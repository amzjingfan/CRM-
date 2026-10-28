"""OpenAI Responses API 结构化输出适配器。"""

import time

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import ValidationError

from app.agents.core.errors import LLMErrorCode, LLMProviderError
from app.agents.core.providers.base import LLMProvider, OutputT, ProviderResult, StructuredRequest


class OpenAIProvider(LLMProvider):
    """通过 Responses API 调用 OpenAI，并仅返回 Pydantic 已验证对象。"""

    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        timeout_seconds: float,
        client: AsyncOpenAI | None = None,
    ) -> None:
        """创建关闭 SDK 重试的客户端，统一由领域服务控制重试次数。"""
        if not api_key or not model_name:
            raise LLMProviderError(
                LLMErrorCode.LLM_CONFIGURATION_ERROR,
                "OpenAI 配置不完整",
                retriable=False,
            )
        self.model_name = model_name
        self._client = client or AsyncOpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)

    async def generate_structured(
        self,
        request: StructuredRequest,
        response_schema: type[OutputT],
    ) -> ProviderResult[OutputT]:
        """执行单次结构化请求；拒绝、截断和供应商异常均转换为稳定错误码。"""
        request.ensure_safe_for_external_provider(response_schema_name=response_schema.__name__)
        started_at = time.perf_counter()
        try:
            response = await self._client.responses.parse(
                model=self.model_name,
                instructions=request.system_prompt,
                input=request.user_prompt,
                text_format=response_schema,
                max_output_tokens=request.max_output_tokens,
                store=False,
            )
        except APITimeoutError as error:
            raise LLMProviderError(LLMErrorCode.LLM_TIMEOUT, "OpenAI 调用超时", retriable=True) from error
        except RateLimitError as error:
            raise LLMProviderError(LLMErrorCode.LLM_RATE_LIMITED, "OpenAI 请求被限流", retriable=True) from error
        except APIConnectionError as error:
            raise LLMProviderError(
                LLMErrorCode.LLM_CONNECTION_ERROR,
                "OpenAI 连接失败",
                retriable=True,
            ) from error
        except AuthenticationError as error:
            raise LLMProviderError(
                LLMErrorCode.LLM_AUTHENTICATION_ERROR,
                "OpenAI 认证失败",
                retriable=False,
            ) from error
        except PermissionDeniedError as error:
            raise LLMProviderError(
                LLMErrorCode.LLM_PERMISSION_DENIED,
                "OpenAI 权限不足",
                retriable=False,
            ) from error
        except BadRequestError as error:
            raise LLMProviderError(
                LLMErrorCode.LLM_INVALID_REQUEST,
                "OpenAI 请求参数无效",
                retriable=False,
            ) from error
        except APIStatusError as error:
            raise LLMProviderError(
                LLMErrorCode.LLM_PROVIDER_ERROR,
                "OpenAI 服务异常",
                retriable=error.status_code >= 500,
            ) from error
        except (ValidationError, ValueError) as error:
            raise LLMProviderError(
                LLMErrorCode.LLM_OUTPUT_INVALID,
                "OpenAI 结构化输出无效",
                retriable=True,
            ) from error

        # OpenAI 在达到 max_output_tokens 时仍可能返回可解析的部分对象。
        # 必须先拒绝截断响应，避免不完整分类被当成正常结果写入 agent_runs。
        incomplete_details = getattr(response, "incomplete_details", None)
        if incomplete_details is not None and getattr(incomplete_details, "reason", None) == "max_output_tokens":
            raise LLMProviderError(
                LLMErrorCode.LLM_OUTPUT_INVALID,
                "OpenAI 输出因达到 Token 上限而截断",
                retriable=True,
            )

        parsed_output = response.output_parsed
        if parsed_output is None:
            has_refusal = any(
                content.type == "refusal"
                for item in response.output
                if item.type == "message"
                for content in item.content
            )
            if has_refusal:
                raise LLMProviderError(LLMErrorCode.LLM_REFUSAL, "OpenAI 拒绝处理", retriable=False)
            raise LLMProviderError(
                LLMErrorCode.LLM_OUTPUT_INVALID,
                "OpenAI 未返回完整结构化结果",
                retriable=True,
            )

        usage = response.usage
        return ProviderResult(
            provider=self.provider_name,
            model=self.model_name,
            parsed_output=parsed_output,
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
            latency_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
            provider_request_id=getattr(response, "_request_id", None),
        )
