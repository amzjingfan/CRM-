"""本地检索模型服务契约、HTTP 客户端和 Cross-Encoder 重排序编排。"""

import math
from dataclasses import dataclass
from enum import StrEnum

import httpx
from pydantic import BaseModel, Field, model_validator


class RetrievalModelErrorCode(StrEnum):
    """内部模型服务共享的稳定错误码。"""

    MODEL_SERVICE_TIMEOUT = "MODEL_SERVICE_TIMEOUT"
    MODEL_SERVICE_CONNECTION_ERROR = "MODEL_SERVICE_CONNECTION_ERROR"
    MODEL_SERVICE_AUTHENTICATION_ERROR = "MODEL_SERVICE_AUTHENTICATION_ERROR"
    MODEL_SERVICE_INVALID_REQUEST = "MODEL_SERVICE_INVALID_REQUEST"
    MODEL_SERVICE_UNAVAILABLE = "MODEL_SERVICE_UNAVAILABLE"
    MODEL_SERVICE_OUTPUT_INVALID = "MODEL_SERVICE_OUTPUT_INVALID"
    MODEL_SERVICE_CONFIGURATION_ERROR = "MODEL_SERVICE_CONFIGURATION_ERROR"


class RetrievalModelServiceError(Exception):
    """隐藏内部 HTTP 响应正文，只向调用方暴露稳定分类。"""

    def __init__(self, code: RetrievalModelErrorCode, message: str, *, retriable: bool) -> None:
        self.code = code
        self.retriable = retriable
        super().__init__(message)


class EmbeddingServiceRequest(BaseModel):
    """发送到单实例模型服务的批量向量请求。"""

    texts: list[str] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_texts(self) -> "EmbeddingServiceRequest":
        """限制单项正文长度，并拒绝空白输入，避免异常资源消耗。"""
        if any(not text.strip() or len(text) > 20_000 for text in self.texts):
            raise ValueError("向量文本必须为 1 到 20000 个字符")
        return self


class EmbeddingServiceResponse(BaseModel):
    """内部 BGE-M3 向量响应，不包含任何模型原始输出。"""

    provider: str
    model: str
    revision: str
    dimensions: int = Field(ge=1, le=4096)
    vectors: list[list[float]]
    input_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    request_id: str | None = None


class RerankServiceCandidate(BaseModel):
    """内部重排序候选；candidate_id 必须来自本次租户安全召回。"""

    candidate_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=20_000)


class RerankServiceRequest(BaseModel):
    """查询与有限候选集合组成的 Cross-Encoder 请求。"""

    query: str = Field(min_length=1, max_length=4000)
    candidates: list[RerankServiceCandidate] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "RerankServiceRequest":
        """候选 ID 必须唯一，防止分数回填时发生歧义。"""
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("重排序候选 ID 不能重复")
        return self


class RerankServiceScore(BaseModel):
    """单个候选的未归一化 Cross-Encoder 分数。"""

    candidate_id: str
    score: float

    @model_validator(mode="after")
    def validate_finite_score(self) -> "RerankServiceScore":
        """NaN 和 Infinity 不能进入排序与运行追踪。"""
        if not math.isfinite(self.score):
            raise ValueError("重排序分数必须为有限数值")
        return self


class RerankServiceResponse(BaseModel):
    """模型服务返回的完整候选分数集合。"""

    provider: str
    model: str
    revision: str
    scores: list[RerankServiceScore]
    latency_ms: int = Field(ge=0)
    request_id: str | None = None


class LocalRetrievalModelClient:
    """仅通过受保护的内部 HTTP 契约访问单实例模型服务。"""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """验证服务地址和内部令牌；令牌不会进入异常文本或日志。"""
        if not base_url.strip() or not token:
            raise RetrievalModelServiceError(
                RetrievalModelErrorCode.MODEL_SERVICE_CONFIGURATION_ERROR,
                "本地检索模型服务配置不完整",
                retriable=False,
            )
        self._token = token
        self._client = client or httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout_seconds)

    async def aclose(self) -> None:
        """释放应用生命周期内复用的本地模型 HTTP 连接池。"""
        await self._client.aclose()

    async def embed(self, texts: list[str]) -> EmbeddingServiceResponse:
        """调用 BGE-M3 向量端点并执行响应结构校验。"""
        request = EmbeddingServiceRequest(texts=texts)
        response = await self._post("/internal/v1/embeddings", request.model_dump(mode="json"))
        try:
            return EmbeddingServiceResponse.model_validate(response.json())
        except (ValueError, TypeError) as error:
            raise RetrievalModelServiceError(
                RetrievalModelErrorCode.MODEL_SERVICE_OUTPUT_INVALID,
                "本地向量服务返回结构无效",
                retriable=True,
            ) from error

    async def rerank(self, query: str, candidates: list["RerankCandidate"]) -> RerankServiceResponse:
        """调用 Reranker；正文只存在于单次内存请求，不写入日志。"""
        request = RerankServiceRequest(
            query=query,
            candidates=[
                RerankServiceCandidate(candidate_id=candidate.candidate_id, text=candidate.text)
                for candidate in candidates
            ],
        )
        response = await self._post("/internal/v1/rerank", request.model_dump(mode="json"))
        try:
            return RerankServiceResponse.model_validate(response.json())
        except (ValueError, TypeError) as error:
            raise RetrievalModelServiceError(
                RetrievalModelErrorCode.MODEL_SERVICE_OUTPUT_INVALID,
                "本地重排序服务返回结构无效",
                retriable=True,
            ) from error

    async def _post(self, path: str, payload: dict[str, object]) -> httpx.Response:
        """统一转换网络、认证、参数和服务端错误，禁止透传响应正文。"""
        try:
            response = await self._client.post(
                path,
                json=payload,
                headers={"Authorization": f"Bearer {self._token}"},
            )
        except httpx.TimeoutException as error:
            raise RetrievalModelServiceError(
                RetrievalModelErrorCode.MODEL_SERVICE_TIMEOUT,
                "本地检索模型服务调用超时",
                retriable=True,
            ) from error
        except httpx.RequestError as error:
            raise RetrievalModelServiceError(
                RetrievalModelErrorCode.MODEL_SERVICE_CONNECTION_ERROR,
                "本地检索模型服务连接失败",
                retriable=True,
            ) from error
        if response.status_code in {401, 403}:
            raise RetrievalModelServiceError(
                RetrievalModelErrorCode.MODEL_SERVICE_AUTHENTICATION_ERROR,
                "本地检索模型服务认证失败",
                retriable=False,
            )
        if response.status_code in {400, 404, 422}:
            raise RetrievalModelServiceError(
                RetrievalModelErrorCode.MODEL_SERVICE_INVALID_REQUEST,
                "本地检索模型服务拒绝请求",
                retriable=False,
            )
        if response.status_code == 429 or response.status_code >= 500:
            raise RetrievalModelServiceError(
                RetrievalModelErrorCode.MODEL_SERVICE_UNAVAILABLE,
                "本地检索模型服务暂不可用",
                retriable=True,
            )
        if not response.is_success:
            raise RetrievalModelServiceError(
                RetrievalModelErrorCode.MODEL_SERVICE_UNAVAILABLE,
                "本地检索模型服务异常",
                retriable=False,
            )
        return response


class RerankingErrorCode(StrEnum):
    """Agent 对外使用的稳定重排序错误码。"""

    RERANK_TIMEOUT = "RERANK_TIMEOUT"
    RERANK_CONNECTION_ERROR = "RERANK_CONNECTION_ERROR"
    RERANK_AUTHENTICATION_ERROR = "RERANK_AUTHENTICATION_ERROR"
    RERANK_INVALID_REQUEST = "RERANK_INVALID_REQUEST"
    RERANK_PROVIDER_ERROR = "RERANK_PROVIDER_ERROR"
    RERANK_OUTPUT_INVALID = "RERANK_OUTPUT_INVALID"
    RERANK_CONFIGURATION_ERROR = "RERANK_CONFIGURATION_ERROR"


class RerankingProviderError(Exception):
    """供工作流失败记录使用的安全重排序异常。"""

    def __init__(self, code: RerankingErrorCode, message: str, *, retriable: bool) -> None:
        self.code = code
        self.retriable = retriable
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class RerankCandidate:
    """从知识库租户安全端口返回的候选文本。"""

    candidate_id: str
    text: str


@dataclass(frozen=True, slots=True)
class RerankScore:
    """稳定排序后的候选 ID 和原始模型分数。"""

    candidate_id: str
    score: float


@dataclass(frozen=True, slots=True)
class RerankingResult:
    """一次重排序的顺序、模型版本和低基数资源统计。"""

    provider: str
    model: str
    revision: str
    scores: list[RerankScore]
    latency_ms: int
    provider_request_id: str | None


class RerankingService:
    """执行有界重试，并强制校验候选集合没有越权变化。"""

    def __init__(self, client: LocalRetrievalModelClient, *, max_attempts: int) -> None:
        if not 1 <= max_attempts <= 3:
            raise ValueError("重排序尝试次数必须在 1 到 3 之间")
        self.client = client
        self.max_attempts = max_attempts

    async def rerank(self, query: str, candidates: list[RerankCandidate]) -> RerankingResult:
        """按原始 Cross-Encoder 分数降序排序，同分时保持召回顺序。"""
        if not query.strip() or not candidates:
            raise RerankingProviderError(
                RerankingErrorCode.RERANK_INVALID_REQUEST,
                "重排序查询和候选不能为空",
                retriable=False,
            )
        response = await self._call_with_retry(query, candidates)
        expected_ids = [candidate.candidate_id for candidate in candidates]
        returned_ids = [item.candidate_id for item in response.scores]
        if len(returned_ids) != len(set(returned_ids)) or set(returned_ids) != set(expected_ids):
            raise RerankingProviderError(
                RerankingErrorCode.RERANK_OUTPUT_INVALID,
                "重排序候选集合与召回集合不一致",
                retriable=False,
            )
        original_rank = {candidate_id: index for index, candidate_id in enumerate(expected_ids)}
        ordered = sorted(response.scores, key=lambda item: (-item.score, original_rank[item.candidate_id]))
        return RerankingResult(
            provider=response.provider,
            model=response.model,
            revision=response.revision,
            scores=[RerankScore(candidate_id=item.candidate_id, score=item.score) for item in ordered],
            latency_ms=response.latency_ms,
            provider_request_id=response.request_id,
        )

    async def _call_with_retry(self, query: str, candidates: list[RerankCandidate]) -> RerankServiceResponse:
        """仅重试连接、超时和服务不可用，不重试认证与非法请求。"""
        last_error: RetrievalModelServiceError | None = None
        for _attempt in range(self.max_attempts):
            try:
                return await self.client.rerank(query, candidates)
            except RetrievalModelServiceError as error:
                last_error = error
                if not error.retriable:
                    raise self._translate_error(error) from error
        if last_error is None:
            raise RuntimeError("重排序尝试序列为空")
        raise self._translate_error(last_error) from last_error

    @staticmethod
    def _translate_error(error: RetrievalModelServiceError) -> RerankingProviderError:
        """把共享模型服务错误映射为 Agent 领域错误。"""
        mapping = {
            RetrievalModelErrorCode.MODEL_SERVICE_TIMEOUT: RerankingErrorCode.RERANK_TIMEOUT,
            RetrievalModelErrorCode.MODEL_SERVICE_CONNECTION_ERROR: RerankingErrorCode.RERANK_CONNECTION_ERROR,
            RetrievalModelErrorCode.MODEL_SERVICE_AUTHENTICATION_ERROR: RerankingErrorCode.RERANK_AUTHENTICATION_ERROR,
            RetrievalModelErrorCode.MODEL_SERVICE_INVALID_REQUEST: RerankingErrorCode.RERANK_INVALID_REQUEST,
            RetrievalModelErrorCode.MODEL_SERVICE_OUTPUT_INVALID: RerankingErrorCode.RERANK_OUTPUT_INVALID,
            RetrievalModelErrorCode.MODEL_SERVICE_CONFIGURATION_ERROR: RerankingErrorCode.RERANK_CONFIGURATION_ERROR,
        }
        return RerankingProviderError(
            mapping.get(error.code, RerankingErrorCode.RERANK_PROVIDER_ERROR),
            "本地重排序失败",
            retriable=error.retriable,
        )
