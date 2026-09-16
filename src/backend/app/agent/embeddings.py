"""Embedding 供应商适配、错误转换和有界批处理。"""

import math
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

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

from app.agent.retrieval_models import (
    LocalRetrievalModelClient,
    RetrievalModelErrorCode,
    RetrievalModelServiceError,
)
from app.shared.config.settings import Settings


class EmbeddingErrorCode(StrEnum):
    """屏蔽供应商 SDK 差异的稳定 Embedding 错误码。"""

    EMBEDDING_TIMEOUT = "EMBEDDING_TIMEOUT"
    EMBEDDING_RATE_LIMITED = "EMBEDDING_RATE_LIMITED"
    EMBEDDING_CONNECTION_ERROR = "EMBEDDING_CONNECTION_ERROR"
    EMBEDDING_AUTHENTICATION_ERROR = "EMBEDDING_AUTHENTICATION_ERROR"
    EMBEDDING_PERMISSION_DENIED = "EMBEDDING_PERMISSION_DENIED"
    EMBEDDING_INVALID_REQUEST = "EMBEDDING_INVALID_REQUEST"
    EMBEDDING_PROVIDER_ERROR = "EMBEDDING_PROVIDER_ERROR"
    EMBEDDING_OUTPUT_INVALID = "EMBEDDING_OUTPUT_INVALID"
    EMBEDDING_CONFIGURATION_ERROR = "EMBEDDING_CONFIGURATION_ERROR"


class EmbeddingProviderError(Exception):
    """表示已完成安全转换、不会暴露供应商响应正文的异常。"""

    def __init__(self, code: EmbeddingErrorCode, message: str, *, retriable: bool) -> None:
        self.code = code
        self.retriable = retriable
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """一次或多次批处理合并后的向量和资源统计。"""

    provider: str
    model: str
    vectors: list[list[float]]
    input_tokens: int
    latency_ms: int
    provider_request_id: str | None


class EmbeddingProvider(Protocol):
    """生产 Provider 和确定性测试 Provider 共同遵守的最小契约。"""

    provider_name: str
    model_name: str
    dimensions: int

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """把一批非空文本转换为固定维度向量。"""
        ...


class OpenAIEmbeddingProvider:
    """通过 OpenAI Embeddings API 生成 1536 维 FAQ 向量。"""

    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        dimensions: int,
        timeout_seconds: float,
        client: AsyncOpenAI | None = None,
    ) -> None:
        """创建关闭 SDK 重试的客户端，避免叠加成不可控调用次数。"""
        if not api_key or not model_name:
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_CONFIGURATION_ERROR,
                "OpenAI Embedding 配置不完整",
                retriable=False,
            )
        if dimensions != 1536:
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_CONFIGURATION_ERROR,
                "Embedding 维度必须与知识库 1536 维字段一致",
                retriable=False,
            )
        self.model_name = model_name
        self.dimensions = dimensions
        self._client = client or AsyncOpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """执行单次批量向量请求，并在数据库边界前验证所有数值。"""
        if not texts or any(not text.strip() for text in texts):
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_INVALID_REQUEST,
                "Embedding 输入不能为空",
                retriable=False,
            )
        started_at = time.perf_counter()
        try:
            response = await self._client.embeddings.create(
                model=self.model_name,
                input=texts,
                dimensions=self.dimensions,
                encoding_format="float",
            )
        except APITimeoutError as error:
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_TIMEOUT, "OpenAI Embedding 调用超时", retriable=True
            ) from error
        except RateLimitError as error:
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_RATE_LIMITED, "OpenAI Embedding 请求被限流", retriable=True
            ) from error
        except APIConnectionError as error:
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_CONNECTION_ERROR, "OpenAI Embedding 连接失败", retriable=True
            ) from error
        except AuthenticationError as error:
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_AUTHENTICATION_ERROR, "OpenAI Embedding 认证失败", retriable=False
            ) from error
        except PermissionDeniedError as error:
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_PERMISSION_DENIED, "OpenAI Embedding 权限不足", retriable=False
            ) from error
        except BadRequestError as error:
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_INVALID_REQUEST, "OpenAI Embedding 请求参数无效", retriable=False
            ) from error
        except APIStatusError as error:
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_PROVIDER_ERROR,
                "OpenAI Embedding 服务异常",
                retriable=error.status_code >= 500,
            ) from error

        ordered_data = sorted(response.data, key=lambda item: item.index)
        vectors = [item.embedding for item in ordered_data]
        if len(vectors) != len(texts) or any(len(vector) != self.dimensions for vector in vectors):
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_OUTPUT_INVALID,
                "OpenAI Embedding 返回数量或维度错误",
                retriable=True,
            )
        if any(not math.isfinite(value) for vector in vectors for value in vector):
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_OUTPUT_INVALID,
                "OpenAI Embedding 返回非有限数值",
                retriable=True,
            )
        usage = getattr(response, "usage", None)
        return EmbeddingResult(
            provider=self.provider_name,
            model=self.model_name,
            vectors=vectors,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            latency_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
            provider_request_id=getattr(response, "_request_id", None),
        )


class LocalBgeEmbeddingProvider:
    """通过内部单实例模型服务生成 BGE-M3 1024 维 Dense 向量。"""

    provider_name = "local_bge"

    def __init__(
        self,
        *,
        client: LocalRetrievalModelClient,
        model_name: str,
        dimensions: int,
    ) -> None:
        """在首次调用前固定模型和维度，防止 1536/1024 混写。"""
        if model_name.strip().lower() not in {"baai/bge-m3", "bge-m3"} or dimensions != 1024:
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_CONFIGURATION_ERROR,
                "本地 BGE-M3 必须使用 1024 维配置",
                retriable=False,
            )
        self.client = client
        self.model_name = "BAAI/bge-m3"
        self.dimensions = dimensions

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """调用本地服务并在数据库写入前校验数量、维度和有限数值。"""
        if not texts or any(not text.strip() for text in texts):
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_INVALID_REQUEST,
                "Embedding 输入不能为空",
                retriable=False,
            )
        try:
            response = await self.client.embed(texts)
        except RetrievalModelServiceError as error:
            raise self._translate_error(error) from error
        if response.model.lower() not in {"baai/bge-m3", "bge-m3"} or response.dimensions != self.dimensions:
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_OUTPUT_INVALID,
                "本地 BGE-M3 返回模型或维度不一致",
                retriable=False,
            )
        if len(response.vectors) != len(texts) or any(len(vector) != self.dimensions for vector in response.vectors):
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_OUTPUT_INVALID,
                "本地 BGE-M3 返回数量或维度错误",
                retriable=True,
            )
        if any(not math.isfinite(value) for vector in response.vectors for value in vector):
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_OUTPUT_INVALID,
                "本地 BGE-M3 返回非有限数值",
                retriable=True,
            )
        return EmbeddingResult(
            provider=self.provider_name,
            model=self.model_name,
            vectors=response.vectors,
            input_tokens=response.input_tokens,
            latency_ms=response.latency_ms,
            provider_request_id=response.request_id,
        )

    @staticmethod
    def _translate_error(error: RetrievalModelServiceError) -> EmbeddingProviderError:
        """把内部模型服务错误映射到既有 Embedding 稳定错误码。"""
        mapping = {
            RetrievalModelErrorCode.MODEL_SERVICE_TIMEOUT: EmbeddingErrorCode.EMBEDDING_TIMEOUT,
            RetrievalModelErrorCode.MODEL_SERVICE_CONNECTION_ERROR: EmbeddingErrorCode.EMBEDDING_CONNECTION_ERROR,
            RetrievalModelErrorCode.MODEL_SERVICE_AUTHENTICATION_ERROR: (
                EmbeddingErrorCode.EMBEDDING_AUTHENTICATION_ERROR
            ),
            RetrievalModelErrorCode.MODEL_SERVICE_INVALID_REQUEST: EmbeddingErrorCode.EMBEDDING_INVALID_REQUEST,
            RetrievalModelErrorCode.MODEL_SERVICE_OUTPUT_INVALID: EmbeddingErrorCode.EMBEDDING_OUTPUT_INVALID,
            RetrievalModelErrorCode.MODEL_SERVICE_CONFIGURATION_ERROR: (
                EmbeddingErrorCode.EMBEDDING_CONFIGURATION_ERROR
            ),
        }
        return EmbeddingProviderError(
            mapping.get(error.code, EmbeddingErrorCode.EMBEDDING_PROVIDER_ERROR),
            "本地 BGE-M3 Embedding 调用失败",
            retriable=error.retriable,
        )


class EmbeddingService:
    """按固定批量和总尝试次数调用 Embedding Provider。"""

    def __init__(self, provider: EmbeddingProvider, *, max_attempts: int, batch_size: int) -> None:
        if not 1 <= max_attempts <= 3:
            raise ValueError("Embedding 尝试次数必须在 1 到 3 之间")
        if not 1 <= batch_size <= 128:
            raise ValueError("Embedding 批量大小必须在 1 到 128 之间")
        self.provider = provider
        self.max_attempts = max_attempts
        self.batch_size = batch_size

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """分批生成向量；任何批次失败都不会返回部分结果。"""
        if not texts:
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_INVALID_REQUEST,
                "Embedding 输入不能为空",
                retriable=False,
            )
        started_at = time.perf_counter()
        vectors: list[list[float]] = []
        input_tokens = 0
        request_ids: list[str] = []
        for offset in range(0, len(texts), self.batch_size):
            batch = texts[offset : offset + self.batch_size]
            result = await self._embed_batch(batch)
            vectors.extend(result.vectors)
            input_tokens += result.input_tokens
            if result.provider_request_id:
                request_ids.append(result.provider_request_id)
        return EmbeddingResult(
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            vectors=vectors,
            input_tokens=input_tokens,
            latency_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
            provider_request_id=",".join(request_ids) or None,
        )

    async def _embed_batch(self, texts: list[str]) -> EmbeddingResult:
        """仅对瞬时错误执行有界重试，认证和配置错误立即失败。"""
        last_error: EmbeddingProviderError | None = None
        for _attempt in range(self.max_attempts):
            try:
                return await self.provider.embed(texts)
            except EmbeddingProviderError as error:
                last_error = error
                if not error.retriable:
                    raise
        if last_error is None:
            raise RuntimeError("Embedding 尝试序列为空")
        raise last_error


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """根据类型化配置构建白名单 Embedding Provider。"""
    if not settings.embedding_enabled:
        raise EmbeddingProviderError(
            EmbeddingErrorCode.EMBEDDING_CONFIGURATION_ERROR,
            "Embedding 功能未启用",
            retriable=False,
        )
    provider_name = settings.embedding_provider.strip().lower()
    if provider_name == "local_bge":
        if settings.retrieval_model_service_token is None:
            raise EmbeddingProviderError(
                EmbeddingErrorCode.EMBEDDING_CONFIGURATION_ERROR,
                "未配置内部检索模型服务令牌",
                retriable=False,
            )
        return LocalBgeEmbeddingProvider(
            client=LocalRetrievalModelClient(
                base_url=settings.retrieval_model_service_url,
                token=settings.retrieval_model_service_token.get_secret_value(),
                timeout_seconds=settings.embedding_timeout_seconds,
            ),
            model_name=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    if provider_name != "openai":
        raise EmbeddingProviderError(
            EmbeddingErrorCode.EMBEDDING_CONFIGURATION_ERROR,
            "不支持的 Embedding 供应商",
            retriable=False,
        )
    # 1024 维数据库切换后 OpenAI Provider 仅保留适配层历史兼容，不能成为
    # knowledge_chunks 的生产写入方；显式配置到 1536 时仍可供独立评测使用。
    if settings.openai_api_key is None:
        raise EmbeddingProviderError(
            EmbeddingErrorCode.EMBEDDING_CONFIGURATION_ERROR,
            "未配置 OpenAI API Key",
            retriable=False,
        )
    return OpenAIEmbeddingProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model_name=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
