"""验证 Embedding 适配、重试和 FAQ Token 切分边界。"""

from collections import deque
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from openai import APITimeoutError, AsyncOpenAI
from pydantic import SecretStr

from app.agent.chunking import FaqTokenChunker
from app.agent.embeddings import (
    EmbeddingErrorCode,
    EmbeddingProviderError,
    EmbeddingService,
    OpenAIEmbeddingProvider,
    build_embedding_provider,
)
from app.shared.config.settings import Settings


class CharacterEncoding:
    """测试专用逐字符编码器，保证默认测试不下载外部编码表。"""

    def encode(self, text: str) -> list[int]:
        return [ord(character) for character in text]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(token) for token in tokens)


class FakeEmbeddingsResource:
    """模拟 OpenAI Embeddings 资源，并保留请求参数供安全断言。"""

    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = deque(outcomes)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> object:
        """返回预设结果或抛出预设异常。"""
        self.calls.append(kwargs)
        outcome = self.outcomes.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def embedding_response(*vectors: list[float]) -> object:
    """构造最小 OpenAI Embedding 响应。"""
    return SimpleNamespace(
        data=[SimpleNamespace(index=index, embedding=vector) for index, vector in enumerate(vectors)],
        usage=SimpleNamespace(prompt_tokens=12, total_tokens=12),
        _request_id="req-embedding",
    )


@pytest.mark.asyncio
async def test_openai_embedding_provider_returns_validated_1536_vectors() -> None:
    """生产适配器必须显式请求 1536 维，并按输入顺序返回向量。"""
    vector = [0.01] * 1536
    resource = FakeEmbeddingsResource([embedding_response(vector)])
    provider = OpenAIEmbeddingProvider(
        api_key="test-only",
        model_name="text-embedding-3-small",
        dimensions=1536,
        timeout_seconds=3,
        client=cast(AsyncOpenAI, SimpleNamespace(embeddings=resource)),
    )

    result = await provider.embed(["已脱敏 FAQ"])

    assert result.vectors == [vector]
    assert result.input_tokens == 12
    assert result.provider_request_id == "req-embedding"
    assert resource.calls[0]["dimensions"] == 1536
    assert resource.calls[0]["encoding_format"] == "float"


@pytest.mark.asyncio
async def test_embedding_service_retries_transient_error_within_budget() -> None:
    """超时可以重试，但总调用次数不得超过配置预算。"""
    timeout = APITimeoutError(request=httpx.Request("POST", "https://example.invalid"))
    vector = [0.02] * 1536
    resource = FakeEmbeddingsResource([timeout, embedding_response(vector)])
    provider = OpenAIEmbeddingProvider(
        api_key="test-only",
        model_name="text-embedding-3-small",
        dimensions=1536,
        timeout_seconds=3,
        client=cast(AsyncOpenAI, SimpleNamespace(embeddings=resource)),
    )

    result = await EmbeddingService(provider, max_attempts=2, batch_size=32).embed(["FAQ"])

    assert result.vectors == [vector]
    assert len(resource.calls) == 2


@pytest.mark.asyncio
async def test_embedding_provider_rejects_non_finite_vector() -> None:
    """NaN 或 Infinity 不能进入 pgvector，必须在供应商边界失败关闭。"""
    vector = [0.01] * 1536
    vector[100] = float("nan")
    resource = FakeEmbeddingsResource([embedding_response(vector)])
    provider = OpenAIEmbeddingProvider(
        api_key="test-only",
        model_name="text-embedding-3-small",
        dimensions=1536,
        timeout_seconds=3,
        client=cast(AsyncOpenAI, SimpleNamespace(embeddings=resource)),
    )

    with pytest.raises(EmbeddingProviderError) as captured:
        await provider.embed(["FAQ"])

    assert captured.value.code == EmbeddingErrorCode.EMBEDDING_OUTPUT_INVALID


def test_embedding_factory_is_disabled_by_default_and_masks_secret() -> None:
    """Embedding 默认关闭，且配置 repr 不得泄露真实密钥。"""
    settings = Settings(_env_file=None)

    with pytest.raises(EmbeddingProviderError) as captured:
        build_embedding_provider(settings)

    assert captured.value.code == EmbeddingErrorCode.EMBEDDING_CONFIGURATION_ERROR
    protected = Settings(_env_file=None, OPENAI_API_KEY="sk-test-not-real")
    assert isinstance(protected.openai_api_key, SecretStr)
    assert "sk-test-not-real" not in repr(protected)


def test_faq_chunker_preserves_question_prefix_and_token_budget() -> None:
    """长答案切分后每片必须保留问题语义，并满足 800/80 Token 约束。"""
    chunker = FaqTokenChunker(
        model_name="text-embedding-3-small",
        max_tokens=800,
        overlap_tokens=80,
        encoding=CharacterEncoding(),
    )
    answer = "物流信息会在发货后更新。" * 1200

    chunks = chunker.split("如何查询物流？", answer)

    assert len(chunks) > 1
    assert all(chunk.content.startswith("问题：如何查询物流？\n答案：") for chunk in chunks)
    assert all(chunk.token_count <= 800 for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_faq_chunker_rejects_empty_content() -> None:
    """空 FAQ 不能创建无语义向量。"""
    chunker = FaqTokenChunker(model_name="text-embedding-3-small", encoding=CharacterEncoding())

    with pytest.raises(ValueError, match="问题和答案不能为空"):
        chunker.split(" ", "")
