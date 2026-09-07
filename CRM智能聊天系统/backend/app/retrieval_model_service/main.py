"""本地 BGE 单实例内部服务入口，不注册到公开 CRM API。"""

import asyncio
import logging
import secrets
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException

from app.agent.retrieval_models import (
    EmbeddingServiceRequest,
    EmbeddingServiceResponse,
    RerankServiceRequest,
    RerankServiceResponse,
    RerankServiceScore,
)
from app.retrieval_model_service.engine import RetrievalEngine, RetrievalEngineError, TransformersBgeEngine
from app.shared.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def create_model_service_app(*, engine: RetrievalEngine, internal_token: str) -> FastAPI:
    """组装仅内部可访问的模型服务，推理端点统一使用 Bearer Token。"""
    if not internal_token:
        raise RuntimeError("MODEL_SERVICE_TOKEN_MISSING")

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """启动时一次性加载两套模型，禁止 backend/jobs 重复占用显存。"""
        try:
            await asyncio.to_thread(engine.load)
        except RetrievalEngineError as error:
            logger.error("retrieval_model_service_load_failed", extra={"error_code": str(error)})
            raise
        yield

    app = FastAPI(title="CRM Internal Retrieval Model Service", version="1.0.0", lifespan=lifespan)

    def require_internal_token(authorization: str | None = Header(default=None)) -> None:
        """使用常量时间比较校验内部令牌，避免在日志或响应中回显令牌。"""
        scheme, _, credential = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(credential, internal_token):
            raise HTTPException(status_code=401, detail="MODEL_SERVICE_AUTHENTICATION_REQUIRED")

    @app.get("/internal/health")
    async def health() -> dict[str, object]:
        """仅暴露低敏运行状态，不返回本机模型路径、哈希或设备明细。"""
        return {
            "status": "ok",
            "embedding_model": engine.embedding_model,
            "reranker_model": engine.reranker_model,
            "dimensions": engine.dimensions,
        }

    @app.post(
        "/internal/v1/embeddings",
        response_model=EmbeddingServiceResponse,
        dependencies=[Depends(require_internal_token)],
    )
    async def embeddings(request: EmbeddingServiceRequest) -> EmbeddingServiceResponse:
        """生成 BGE-M3 Dense 向量；异常响应不包含客户文本和底层堆栈。"""
        started_at = time.perf_counter()
        request_id = str(uuid.uuid4())
        try:
            result = await asyncio.to_thread(engine.embed, request.texts)
        except RetrievalEngineError as error:
            logger.warning("retrieval_embedding_failed", extra={"request_id": request_id, "error_code": str(error)})
            raise HTTPException(status_code=503, detail="MODEL_SERVICE_UNAVAILABLE") from error
        return EmbeddingServiceResponse(
            provider="local_bge",
            model=engine.embedding_model,
            revision=engine.embedding_revision,
            dimensions=engine.dimensions,
            vectors=result.vectors,
            input_tokens=result.input_tokens,
            latency_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
            request_id=request_id,
        )

    @app.post(
        "/internal/v1/rerank",
        response_model=RerankServiceResponse,
        dependencies=[Depends(require_internal_token)],
    )
    async def rerank(request: RerankServiceRequest) -> RerankServiceResponse:
        """对租户安全候选执行 Cross-Encoder 评分，不改变候选集合。"""
        started_at = time.perf_counter()
        request_id = str(uuid.uuid4())
        try:
            result = await asyncio.to_thread(
                engine.rerank,
                request.query,
                [candidate.text for candidate in request.candidates],
            )
        except RetrievalEngineError as error:
            logger.warning("retrieval_rerank_failed", extra={"request_id": request_id, "error_code": str(error)})
            raise HTTPException(status_code=503, detail="MODEL_SERVICE_UNAVAILABLE") from error
        return RerankServiceResponse(
            provider="local_bge",
            model=engine.reranker_model,
            revision=engine.reranker_revision,
            scores=[
                RerankServiceScore(candidate_id=candidate.candidate_id, score=score)
                for candidate, score in zip(request.candidates, result.scores, strict=True)
            ],
            latency_ms=max(0, int((time.perf_counter() - started_at) * 1000)),
            request_id=request_id,
        )

    return app


def build_app(settings: Settings) -> FastAPI:
    """从集中配置构建生产模型服务；模型路径仅用于本进程加载。"""
    if settings.retrieval_model_service_token is None:
        raise RuntimeError("MODEL_SERVICE_TOKEN_MISSING")
    engine = TransformersBgeEngine(
        embedding_path=settings.bge_m3_model_path,
        reranker_path=settings.bge_reranker_model_path,
        device=settings.retrieval_model_device,
        use_fp16=settings.retrieval_model_use_fp16,
        embedding_batch_size=settings.embedding_batch_size,
        reranker_batch_size=settings.reranker_batch_size,
        embedding_max_length=settings.embedding_max_length,
        reranker_max_length=settings.reranker_max_length,
        verify_hashes=settings.retrieval_model_verify_hashes,
    )
    return create_model_service_app(
        engine=engine,
        internal_token=settings.retrieval_model_service_token.get_secret_value(),
    )


def create_configured_app() -> FastAPI:
    """供 Uvicorn ``--factory`` 使用，避免普通后端导入时加载本地模型。"""
    return build_app(get_settings())
