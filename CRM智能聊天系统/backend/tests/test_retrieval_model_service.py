"""验证内部模型服务认证、BGE 响应和输入边界。"""

from fastapi.testclient import TestClient

from app.retrieval_model_service.engine import EngineEmbeddingResult, EngineRerankResult
from app.retrieval_model_service.main import create_model_service_app


class FakeRetrievalEngine:
    """不加载真实权重的确定性模型引擎。"""

    embedding_model = "BAAI/bge-m3"
    embedding_revision = "embedding-revision"
    reranker_model = "BAAI/bge-reranker-large"
    reranker_revision = "reranker-revision"
    dimensions = 1024
    device = "cpu"

    def __init__(self) -> None:
        self.loaded = False

    def load(self) -> None:
        self.loaded = True

    def embed(self, texts: list[str]) -> EngineEmbeddingResult:
        assert self.loaded
        return EngineEmbeddingResult(vectors=[[0.1] * 1024 for _ in texts], input_tokens=10)

    def rerank(self, query: str, passages: list[str]) -> EngineRerankResult:
        assert self.loaded
        assert query
        return EngineRerankResult(scores=[float(index) for index, _ in enumerate(passages)])


def test_model_service_requires_internal_bearer_token() -> None:
    """推理端点不能因位于内部网络就省略认证。"""
    app = create_model_service_app(engine=FakeRetrievalEngine(), internal_token="internal-test-token")

    with TestClient(app) as client:
        response = client.post("/internal/v1/embeddings", json={"texts": ["FAQ"]})

    assert response.status_code == 401
    assert response.json()["detail"] == "MODEL_SERVICE_AUTHENTICATION_REQUIRED"


def test_model_service_returns_1024_vectors_without_exposing_paths() -> None:
    """服务只返回契约字段，不暴露本机模型路径或权重信息。"""
    app = create_model_service_app(engine=FakeRetrievalEngine(), internal_token="internal-test-token")

    with TestClient(app) as client:
        response = client.post(
            "/internal/v1/embeddings",
            json={"texts": ["FAQ"]},
            headers={"Authorization": "Bearer internal-test-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dimensions"] == 1024
    assert len(payload["vectors"][0]) == 1024
    assert "path" not in str(payload).lower()


def test_model_service_rerank_preserves_candidate_ids() -> None:
    """服务返回的候选 ID 必须逐项来自请求，供 Agent 再次做集合校验。"""
    app = create_model_service_app(engine=FakeRetrievalEngine(), internal_token="internal-test-token")

    with TestClient(app) as client:
        response = client.post(
            "/internal/v1/rerank",
            json={
                "query": "退货",
                "candidates": [
                    {"candidate_id": "a", "text": "第一条"},
                    {"candidate_id": "b", "text": "第二条"},
                ],
            },
            headers={"Authorization": "Bearer internal-test-token"},
        )

    assert response.status_code == 200
    assert response.json()["scores"] == [
        {"candidate_id": "a", "score": 0.0},
        {"candidate_id": "b", "score": 1.0},
    ]
