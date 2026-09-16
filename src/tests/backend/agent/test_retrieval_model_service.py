"""验证内部模型服务认证、BGE 响应、日志事件和输入边界。"""

import json
import logging
from io import StringIO
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.retrieval_model_service import main as model_service_main
from app.retrieval_model_service.engine import EngineEmbeddingResult, EngineRerankResult, RetrievalEngineError
from app.retrieval_model_service.main import create_model_service_app
from app.shared.logging.setup import JsonFormatter, TraceIdFilter


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


class FailingRetrievalEngine(FakeRetrievalEngine):
    """用稳定错误模拟模型推理失败，禁止测试加载真实权重。"""

    def embed(self, texts: list[str]) -> EngineEmbeddingResult:
        raise RetrievalEngineError("MODEL_EMBED_FAILED")

    def rerank(self, query: str, passages: list[str]) -> EngineRerankResult:
        raise RetrievalEngineError("MODEL_RERANK_FAILED")


class LoadFailingRetrievalEngine(FakeRetrievalEngine):
    """模拟模型资产加载失败。"""

    def load(self) -> None:
        raise RetrievalEngineError("MODEL_ASSET_MISSING")


def json_log_handler(stream: StringIO) -> logging.Handler:
    """创建与生产一致的 JSON Handler，供真实 logger 路径断言。"""
    handler = logging.StreamHandler(stream)
    handler.addFilter(TraceIdFilter())
    handler.setFormatter(JsonFormatter())
    return handler


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


@pytest.mark.parametrize(
    ("path", "body", "expected_event"),
    [
        ("/internal/v1/embeddings", {"texts": ["FAQ"]}, "retrieval_embedding_failed"),
        (
            "/internal/v1/rerank",
            {"query": "退货", "candidates": [{"candidate_id": "a", "text": "第一条"}]},
            "retrieval_rerank_failed",
        ),
    ],
)
def test_model_service_failures_emit_stable_json_events(
    path: str,
    body: dict[str, object],
    expected_event: str,
) -> None:
    """模型失败必须经真实 logger/handler 输出可告警的固定事件。"""
    stream = StringIO()
    handler = json_log_handler(stream)
    logger = model_service_main.logger
    previous_handlers = logger.handlers[:]
    previous_level = logger.level
    previous_propagate = logger.propagate
    logger.handlers = [handler]
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    try:
        app = create_model_service_app(engine=FailingRetrievalEngine(), internal_token="internal-test-token")
        with TestClient(app) as client:
            response = client.post(
                path,
                json=body,
                headers={"Authorization": "Bearer internal-test-token"},
            )
    finally:
        logger.handlers = previous_handlers
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate

    payload = json.loads(stream.getvalue())
    assert response.status_code == 503
    assert payload["event"] == expected_event
    assert payload["message"] == expected_event


def test_configured_model_service_installs_unified_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uvicorn 工厂入口必须在加载模型前安装统一 JSON 日志。"""
    settings = SimpleNamespace(log_level="WARNING")
    configured_levels: list[str] = []
    sentinel_app = object()
    monkeypatch.setattr(model_service_main, "get_settings", lambda: settings)
    monkeypatch.setattr(model_service_main, "configure_logging", configured_levels.append)
    monkeypatch.setattr(model_service_main, "build_app", lambda received: sentinel_app)

    result = model_service_main.create_configured_app()

    assert result is sentinel_app
    assert configured_levels == ["WARNING"]


def test_model_service_load_failure_emits_stable_json_event() -> None:
    """模型启动失败必须保留独立事件，供容器启动告警识别。"""
    stream = StringIO()
    handler = json_log_handler(stream)
    logger = model_service_main.logger
    previous_handlers = logger.handlers[:]
    previous_level = logger.level
    previous_propagate = logger.propagate
    logger.handlers = [handler]
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    try:
        app = create_model_service_app(engine=LoadFailingRetrievalEngine(), internal_token="internal-test-token")
        with pytest.raises(RetrievalEngineError, match="MODEL_ASSET_MISSING"):
            with TestClient(app):
                pass
    finally:
        logger.handlers = previous_handlers
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate

    payload = json.loads(stream.getvalue())
    assert payload["event"] == "retrieval_model_service_load_failed"
    assert payload["message"] == "retrieval_model_service_load_failed"
    assert payload["error_code"] == "MODEL_ASSET_MISSING"
