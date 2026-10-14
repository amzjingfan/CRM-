"""DeepSeek OpenAI 兼容 Chat Completions 适配器。"""

import json
import logging
import time
from typing import cast, get_args

from openai import (
    APIConnectionError,
    APIResponseValidationError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)
from pydantic import ValidationError

from app.agent.errors import (
    LLMErrorCode,
    LLMOutputFailureKind,
    LLMOutputSchemaErrorType,
    LLMOutputSchemaIssue,
    LLMOutputSchemaPath,
    LLMProviderError,
)
from app.agent.providers.base import LLMProvider, OutputT, ProviderResult, StructuredRequest

logger = logging.getLogger(__name__)


def _safe_schema_issues(error: ValidationError) -> tuple[LLMOutputSchemaIssue, ...]:
    """仅保留预定义字段路径与错误类型，丢弃模型自造字段和所有值。"""
    allowed_paths = set(get_args(LLMOutputSchemaPath))
    allowed_types = set(get_args(LLMOutputSchemaErrorType))
    issues: list[LLMOutputSchemaIssue] = []
    for detail in error.errors(include_input=False, include_context=False, include_url=False):
        loc = detail["loc"]
        path = "root" if not loc else "unknown"
        if len(loc) == 1 and isinstance(loc[0], str) and loc[0] in allowed_paths:
            path = loc[0]
        elif loc and loc[0] == "business_claims":
            path = "business_claims"
            if len(loc) == 3 and isinstance(loc[1], int) and isinstance(loc[2], str):
                candidate = f"business_claims[].{loc[2]}"
                if candidate in allowed_paths:
                    path = candidate
        error_type = detail["type"] if detail["type"] in allowed_types else "other"
        issue = (cast(LLMOutputSchemaPath, path), cast(LLMOutputSchemaErrorType, error_type))
        if issue not in issues:
            issues.append(issue)
        if len(issues) == 8:
            break
    return tuple(issues)


class DeepSeekProvider(LLMProvider):
    """使用 DeepSeek JSON Output，并在应用侧完成 Pydantic 二次校验。

    DeepSeek 当前文档提供的是 OpenAI 兼容 Chat Completions 和 JSON Output，
    与 OpenAI Responses API 的响应结构不同，因此单独实现适配器，避免把
    供应商差异泄露到分类服务中。
    """

    provider_name = "deepseek"

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        base_url: str,
        timeout_seconds: float,
        thinking_enabled: bool = False,
        client: AsyncOpenAI | None = None,
    ) -> None:
        """创建 DeepSeek 客户端，关闭 SDK 重试并交由 Agent 服务统一限次。"""
        normalized_api_key = api_key.strip()
        normalized_model_name = model_name.strip()
        normalized_base_url = base_url.strip()
        if not normalized_api_key or not normalized_model_name or not normalized_base_url:
            raise LLMProviderError(
                LLMErrorCode.LLM_CONFIGURATION_ERROR,
                "DeepSeek 配置不完整",
                retriable=False,
            )
        self.model_name = normalized_model_name
        self.thinking_enabled = thinking_enabled
        self._client = client or AsyncOpenAI(
            api_key=normalized_api_key,
            base_url=normalized_base_url,
            timeout=timeout_seconds,
            max_retries=0,
        )

    async def generate_structured(
        self,
        request: StructuredRequest,
        response_schema: type[OutputT],
    ) -> ProviderResult[OutputT]:
        """调用 JSON Output，拒绝截断、空响应和非法结构。"""
        request.ensure_safe_for_external_provider(response_schema_name=response_schema.__name__)
        started_at = time.perf_counter()

        def mapped_error(
            error: BaseException,
            code: LLMErrorCode,
            message: str,
            *,
            retriable: bool,
        ) -> LLMProviderError:
            """记录低敏失败元数据并返回稳定异常，不复制 SDK 消息或响应正文。"""
            response_value = getattr(error, "response", None)
            headers = getattr(response_value, "headers", None)
            provider_request_id = getattr(error, "request_id", None)
            if provider_request_id is None and headers is not None:
                provider_request_id = headers.get("x-request-id")
            logger.warning(
                "deepseek_call_failed",
                extra={
                    "event": "deepseek_call_failed",
                    "trace_id": request.trace_id,
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "provider_request_id": provider_request_id,
                    "status_code": getattr(error, "status_code", None),
                    "error_code": code.value,
                    "retriable": retriable,
                    "latency_ms": max(0, int((time.perf_counter() - started_at) * 1000)),
                },
            )
            return LLMProviderError(code, message, retriable=retriable)

        try:
            response = await self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=request.max_output_tokens,
                temperature=request.temperature,
                # 当前产品 SSE 传输的是完整安全校验后的草稿，不允许
                # Provider 原生 Token 绕过 Schema 和业务安全门禁。
                stream=False,
                # V4 默认开启思考模式，短分类任务会先消耗推理 Token，256 Token
                # 预算可能尚未产生最终 JSON 就结束。意图分类固定关闭思考模式。
                extra_body={"thinking": {"type": "enabled" if self.thinking_enabled else "disabled"}},
            )
        except APITimeoutError as error:
            raise mapped_error(error, LLMErrorCode.LLM_TIMEOUT, "DeepSeek 调用超时", retriable=True) from error
        except RateLimitError as error:
            raise mapped_error(error, LLMErrorCode.LLM_RATE_LIMITED, "DeepSeek 请求被限流", retriable=True) from error
        except APIConnectionError as error:
            raise mapped_error(error, LLMErrorCode.LLM_CONNECTION_ERROR, "DeepSeek 连接失败", retriable=True) from error
        except AuthenticationError as error:
            raise mapped_error(
                error,
                LLMErrorCode.LLM_AUTHENTICATION_ERROR,
                "DeepSeek 认证失败",
                retriable=False,
            ) from error
        except PermissionDeniedError as error:
            raise mapped_error(
                error,
                LLMErrorCode.LLM_PERMISSION_DENIED,
                "DeepSeek 权限不足",
                retriable=False,
            ) from error
        except (BadRequestError, UnprocessableEntityError) as error:
            raise mapped_error(
                error,
                LLMErrorCode.LLM_INVALID_REQUEST,
                "DeepSeek 请求参数无效",
                retriable=False,
            ) from error
        except APIResponseValidationError as error:
            raise mapped_error(
                error,
                LLMErrorCode.LLM_PROVIDER_ERROR,
                "DeepSeek 响应格式异常",
                retriable=True,
            ) from error
        except APIStatusError as error:
            # SDK 没有为所有 DeepSeek 状态码提供专用异常。408 仍是请求
            # 超时；402 等业务性 4xx 不能在应用层自动重试。
            if error.status_code == 408:
                raise mapped_error(
                    error,
                    LLMErrorCode.LLM_TIMEOUT,
                    "DeepSeek 调用超时",
                    retriable=True,
                ) from error
            raise mapped_error(
                error,
                LLMErrorCode.LLM_PROVIDER_ERROR,
                "DeepSeek 服务异常",
                retriable=error.status_code >= 500,
            ) from error

        choices = getattr(response, "choices", None)
        choice = choices[0] if choices else None
        message = getattr(choice, "message", None)
        # OpenAI SDK 的 Literal 滞后于 DeepSeek 扩展值，转为普通字符串后
        # 再按 DeepSeek 官方 finish_reason 语义失败关闭。
        finish_reason = str(getattr(choice, "finish_reason", "missing_finish_reason")) if choice else "missing_choice"
        # 只有 stop 表示结构化答案正常完成。length 可能携带半截 JSON；
        # content_filter 是明确拒绝；insufficient_system_resource 是可重试的供应商中断。
        if choice is None or finish_reason != "stop":
            content = getattr(message, "content", None)
            reasoning_content = getattr(message, "reasoning_content", None)
            if finish_reason == "content_filter":
                error_code = LLMErrorCode.LLM_REFUSAL
                error_message = "DeepSeek 内容安全策略拒绝处理"
                retriable = False
            elif finish_reason == "insufficient_system_resource":
                error_code = LLMErrorCode.LLM_PROVIDER_ERROR
                error_message = "DeepSeek 推理资源不足"
                retriable = True
            else:
                error_code = LLMErrorCode.LLM_OUTPUT_INVALID
                error_message = "DeepSeek 输出未正常完成"
                retriable = True
            logger.warning(
                "deepseek_output_invalid",
                extra={
                    "event": "deepseek_output_invalid",
                    "trace_id": request.trace_id,
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "provider_request_id": getattr(response, "id", None),
                    "finish_reason": finish_reason,
                    "content_length": len(content) if isinstance(content, str) else 0,
                    "reasoning_length": len(reasoning_content) if isinstance(reasoning_content, str) else 0,
                    "error_code": error_code.value,
                },
            )
            raise LLMProviderError(error_code, error_message, retriable=retriable, output_failure_kind="unfinished")
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content:
            reasoning_content = getattr(message, "reasoning_content", None)
            logger.warning(
                "deepseek_output_invalid",
                extra={
                    "event": "deepseek_output_invalid",
                    "trace_id": request.trace_id,
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "provider_request_id": getattr(response, "id", None),
                    "finish_reason": choice.finish_reason,
                    "content_length": 0,
                    "reasoning_length": len(reasoning_content) if isinstance(reasoning_content, str) else 0,
                    "error_code": LLMErrorCode.LLM_OUTPUT_INVALID.value,
                },
            )
            raise LLMProviderError(
                LLMErrorCode.LLM_OUTPUT_INVALID,
                "DeepSeek 返回空内容",
                retriable=True,
                output_failure_kind="empty",
            )

        try:
            parsed_output = response_schema.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as error:
            failure_kind: LLMOutputFailureKind
            if isinstance(error, json.JSONDecodeError):
                failure_kind = "invalid_json"
                schema_issues: tuple[LLMOutputSchemaIssue, ...] = ()
            elif isinstance(error, ValidationError):
                failure_kind = "invalid_schema"
                schema_issues = _safe_schema_issues(error)
            else:
                failure_kind = "invalid_schema"
                schema_issues = (("unknown", "other"),)
            logger.warning(
                "deepseek_output_invalid",
                extra={
                    "event": "deepseek_output_invalid",
                    "trace_id": request.trace_id,
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "provider_request_id": getattr(response, "id", None),
                    "finish_reason": choice.finish_reason,
                    "content_length": len(content),
                    "reasoning_length": len(getattr(message, "reasoning_content", None) or ""),
                    "error_code": LLMErrorCode.LLM_OUTPUT_INVALID.value,
                },
            )
            raise LLMProviderError(
                LLMErrorCode.LLM_OUTPUT_INVALID,
                "DeepSeek JSON 结构未通过校验",
                retriable=True,
                output_failure_kind=failure_kind,
                output_schema_issues=schema_issues,
            ) from error

        usage = getattr(response, "usage", None)
        latency_ms = max(0, int((time.perf_counter() - started_at) * 1000))
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        provider_request_id = getattr(response, "id", None)
        logger.info(
            "deepseek_call_succeeded",
            extra={
                "event": "deepseek_call_succeeded",
                "trace_id": request.trace_id,
                "provider": self.provider_name,
                "model": self.model_name,
                "provider_request_id": provider_request_id,
                "finish_reason": finish_reason,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "content_length": len(content),
                "reasoning_length": len(getattr(message, "reasoning_content", None) or ""),
            },
        )
        return ProviderResult(
            provider=self.provider_name,
            model=self.model_name,
            parsed_output=parsed_output,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            provider_request_id=provider_request_id,
        )
