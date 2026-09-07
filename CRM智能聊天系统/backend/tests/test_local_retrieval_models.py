"""验证本地 BGE 模型服务客户端、重排序和失败关闭边界。"""

import uuid

import httpx
import pytest

from app.agent.embeddings import EmbeddingErrorCode, EmbeddingProviderError, LocalBgeEmbeddingProvider
from app.agent.retrieval_models import (
    LocalRetrievalModelClient,
    RerankCandidate,
    RerankingErrorCode,
    RerankingProviderError,
    RerankingService,
)


def model_transport(request: httpx.Request) -> httpx.Response:
    """返回不含真实模型和客户数据的确定性内部服务响应。"""
    assert request.headers["authorization"] == "Bearer test-internal-token"
    if request.url.path.endswith("/embeddings"):
        return httpx.Response(
            200,
            json={
                "provider": "local_bge",
                "model": "BAAI/bge-m3",
                "revision": "5617a9f61b028005a4858fdac845db406aefb181",
                "dimensions": 1024,
                "vectors": [[0.01] * 1024],
                "input_tokens": 8,
                "latency_ms": 4,
                "request_id": "local-embedding-request",
            },
        )
    return httpx.Response(
        200,
        json={
            "provider": "local_bge",
            "model": "BAAI/bge-reranker-large",
            "revision": "55611d7bca2a7133960a6d3b71e083071bbfc312",
            "scores": [
                {"candidate_id": "candidate-b", "score": 4.2},
                {"candidate_id": "candidate-a", "score": -0.5},
            ],
            "latency_ms": 6,
            "request_id": "local-rerank-request",
        },
    )


@pytest.mark.asyncio
async def test_local_bge_embedding_provider_validates_1024_dimensions() -> None:
    """本地 Provider 必须只接受与 BGE-M3 数据库结构一致的 1024 维向量。"""
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(model_transport), base_url="http://model")
    client = LocalRetrievalModelClient(
        base_url="http://model",
        token="test-internal-token",
        timeout_seconds=3,
        client=http_client,
    )
    provider = LocalBgeEmbeddingProvider(client=client, model_name="BAAI/bge-m3", dimensions=1024)

    result = await provider.embed(["已脱敏查询"])

    assert result.provider == "local_bge"
    assert result.model == "BAAI/bge-m3"
    assert len(result.vectors[0]) == 1024
    assert result.provider_request_id == "local-embedding-request"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_local_bge_embedding_rejects_dimension_mismatch() -> None:
    """配置维度与 BGE-M3 不一致时应在网络调用前失败，禁止新旧向量混写。"""
    client = LocalRetrievalModelClient(
        base_url="http://model",
        token="test-internal-token",
        timeout_seconds=3,
        client=httpx.AsyncClient(transport=httpx.MockTransport(model_transport), base_url="http://model"),
    )

    with pytest.raises(EmbeddingProviderError) as captured:
        LocalBgeEmbeddingProvider(client=client, model_name="BAAI/bge-m3", dimensions=1536)

    assert captured.value.code == EmbeddingErrorCode.EMBEDDING_CONFIGURATION_ERROR


@pytest.mark.asyncio
async def test_reranking_service_uses_model_order_and_preserves_candidate_boundary() -> None:
    """Cross-Encoder 只能重排已召回候选，不能增加或丢失候选 ID。"""
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(model_transport), base_url="http://model")
    client = LocalRetrievalModelClient(
        base_url="http://model",
        token="test-internal-token",
        timeout_seconds=3,
        client=http_client,
    )
    service = RerankingService(client, max_attempts=1)
    candidates = [
        RerankCandidate(candidate_id="candidate-a", text="第一条"),
        RerankCandidate(candidate_id="candidate-b", text="第二条"),
    ]

    result = await service.rerank("已脱敏查询", candidates)

    assert [item.candidate_id for item in result.scores] == ["candidate-b", "candidate-a"]
    assert result.scores[0].score == 4.2
    await http_client.aclose()


@pytest.mark.asyncio
async def test_reranking_service_rejects_unknown_candidate_id() -> None:
    """模型服务返回越界候选 ID 时必须失败关闭，避免跨租户内容被注入结果。"""

    def invalid_transport(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "provider": "local_bge",
                "model": "BAAI/bge-reranker-large",
                "revision": "test",
                "scores": [{"candidate_id": str(uuid.uuid4()), "score": 1.0}],
                "latency_ms": 1,
                "request_id": "invalid",
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(invalid_transport), base_url="http://model")
    client = LocalRetrievalModelClient(
        base_url="http://model",
        token="test-internal-token",
        timeout_seconds=3,
        client=http_client,
    )
    service = RerankingService(client, max_attempts=1)

    with pytest.raises(RerankingProviderError) as captured:
        await service.rerank("查询", [RerankCandidate(candidate_id="allowed", text="内容")])

    assert captured.value.code == RerankingErrorCode.RERANK_OUTPUT_INVALID
    await http_client.aclose()
