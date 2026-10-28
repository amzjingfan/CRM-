"""已绑定文件的 RAG 查询服务：脱敏、向量化、租户检索和上下文预算。"""

import asyncio
import hashlib
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, replace
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.security import sanitize_prompt_text
from app.agents.rag.embeddings import EmbeddingResult
from app.agents.rag.retrieval_models import RerankCandidate, RerankingResult
from app.knowledge_base.schemas import KnowledgeRetrievalHit
from app.knowledge_base.vector_port import KnowledgeSearchPort


class QueryEmbeddingClient(Protocol):
    """查询侧只依赖批量 Embedding 行为。"""

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """把已脱敏查询转换为固定维度向量。"""
        ...


class QueryRerankingClient(Protocol):
    """查询侧只依赖受控候选重排序，不接触数据库或业务动作。"""

    async def rerank(self, query: str, candidates: list[RerankCandidate]) -> RerankingResult:
        """返回与输入候选集合完全一致的稳定排序结果。"""
        ...


@dataclass(slots=True)
class _CachedQueryEmbedding:
    task: asyncio.Task[EmbeddingResult]
    expires_at: float
    waiters: int = 0


_QUERY_EMBEDDING_TTL_SECONDS = 3.0
_QUERY_EMBEDDING_CACHE_LIMIT = 128
_QueryKey = tuple[asyncio.AbstractEventLoop, uuid.UUID, str, int, bytes]
_query_embeddings: OrderedDict[_QueryKey, _CachedQueryEmbedding] = OrderedDict()


async def _embed_query(
    service: QueryEmbeddingClient,
    store_id: uuid.UUID,
    query: str,
) -> EmbeddingResult:
    """短时共用同店同模型的查询向量；知识审批与店铺检索每次重新执行。"""
    provider = getattr(service, "provider", None)
    if getattr(provider, "provider_name", None) != "local_bge":
        return await service.embed([query])
    model = getattr(provider, "model_name", None)
    dimensions = getattr(provider, "dimensions", None)
    if not isinstance(model, str) or not isinstance(dimensions, int):
        return await service.embed([query])
    loop = asyncio.get_running_loop()
    key = (loop, store_id, model, dimensions, hashlib.sha256(query.encode("utf-8")).digest())
    now = loop.time()
    for old_key, old_entry in list(_query_embeddings.items()):
        if old_entry.task.done() and old_entry.expires_at <= now:
            _query_embeddings.pop(old_key, None)
    entry = _query_embeddings.get(key)
    created = entry is None
    if entry is None:
        while len(_query_embeddings) >= _QUERY_EMBEDDING_CACHE_LIMIT:
            _query_embeddings.popitem(last=False)
        task = asyncio.create_task(service.embed([query]))
        entry = _CachedQueryEmbedding(task=task, expires_at=float("inf"))
        _query_embeddings[key] = entry

        def finish(done: asyncio.Task[EmbeddingResult]) -> None:
            if _query_embeddings.get(key) is not entry:
                return
            if done.cancelled() or done.exception() is not None:
                _query_embeddings.pop(key, None)
            else:
                entry.expires_at = loop.time() + _QUERY_EMBEDDING_TTL_SECONDS

        task.add_done_callback(finish)
    else:
        _query_embeddings.move_to_end(key)
    entry.waiters += 1
    try:
        result = await asyncio.shield(entry.task)
        # 同一向量只产生一次模型用量；复用请求仍单独记录检索总耗时。
        return result if created else replace(result, input_tokens=0, latency_ms=0, provider_request_id=None)
    finally:
        entry.waiters -= 1
        if entry.waiters == 0 and not entry.task.done():
            if _query_embeddings.get(key) is entry:
                _query_embeddings.pop(key, None)
            entry.task.cancel()


@dataclass(frozen=True, slots=True)
class RagRetrievalResult:
    """供 Agent 工作流消费的检索结果和安全资源统计。"""

    hits: list[KnowledgeRetrievalHit]
    top_score: float
    context_tokens: int
    embedding_provider: str
    embedding_model: str
    embedding_input_tokens: int
    embedding_latency_ms: int
    embedding_wait_ms: int | None = None
    search_wall_ms: int | None = None
    search_acquire_ms: int | None = None
    search_query_ms: int | None = None
    reranker_provider: str | None = None
    reranker_model: str | None = None
    reranker_revision: str | None = None
    reranker_latency_ms: int = 0
    candidate_count: int = 0


class RagRetrievalTimeout(TimeoutError):
    """Embedding、数据库检索和重排共享的总时限已耗尽。"""


class RagRetrievalService:
    """只在可信店铺和显式绑定文件范围内检索。"""

    def __init__(
        self,
        *,
        embedding_service: QueryEmbeddingClient,
        search_port: KnowledgeSearchPort,
        reranking_service: QueryRerankingClient,
        dense_top_k: int,
        lexical_top_k: int,
        candidate_top_k: int,
        final_top_k: int,
        rrf_k: int,
        min_dense_score: float,
        min_lexical_score: float,
        max_context_tokens: int,
        search_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] | None = None,
        timeout_seconds: float = 12.0,
    ) -> None:
        if not 1 <= dense_top_k <= 100 or not 1 <= lexical_top_k <= 100:
            raise ValueError("混合检索单路候选数必须在 1 到 100 之间")
        if not 1 <= final_top_k <= candidate_top_k <= 100:
            raise ValueError("RAG 候选数必须不小于最终 Top-K，且不得超过 100")
        if not 1 <= rrf_k <= 1000:
            raise ValueError("RRF K 必须在 1 到 1000 之间")
        if not 0 <= min_dense_score <= 1 or not 0 <= min_lexical_score <= 1:
            raise ValueError("RAG Dense/词法最低分数必须在 0 到 1 之间")
        if max_context_tokens < 1:
            raise ValueError("RAG 上下文预算必须大于 0")
        if not 0 < timeout_seconds <= 120:
            raise ValueError("RAG 全链路超时必须在 0 到 120 秒之间")
        self.embedding_service = embedding_service
        self.search_port = search_port
        self.reranking_service = reranking_service
        self.dense_top_k = dense_top_k
        self.lexical_top_k = lexical_top_k
        self.candidate_top_k = candidate_top_k
        self.final_top_k = final_top_k
        self.rrf_k = rrf_k
        self.min_dense_score = min_dense_score
        self.min_lexical_score = min_lexical_score
        self.max_context_tokens = max_context_tokens
        self.search_session_factory = search_session_factory
        self.timeout_seconds = timeout_seconds

    async def retrieve(
        self,
        session: AsyncSession,
        store_id: uuid.UUID,
        query: str,
        file_ids: tuple[uuid.UUID, ...],
    ) -> RagRetrievalResult:
        """对 Embedding、检索连接/SQL、重排施加同一个总时限。"""
        try:
            async with asyncio.timeout(self.timeout_seconds):
                return await self._retrieve_unbounded(session, store_id, query, file_ids)
        except TimeoutError as error:
            raise RagRetrievalTimeout("RAG_RETRIEVAL_TIMEOUT") from error

    async def _retrieve_unbounded(
        self, session: AsyncSession, store_id: uuid.UUID, query: str, file_ids: tuple[uuid.UUID, ...]
    ) -> RagRetrievalResult:
        """显式文件范围可为空；绝不回退到整店 FAQ。"""
        sanitized_query = sanitize_prompt_text(query).strip()
        if not sanitized_query:
            raise ValueError("RAG 查询不能为空")
        embedding_started_at = time.perf_counter_ns()
        embedding_result = await _embed_query(self.embedding_service, store_id, sanitized_query)
        embedding_wait_ms = max(0, (time.perf_counter_ns() - embedding_started_at) // 1_000_000)
        if len(embedding_result.vectors) != 1:
            raise RuntimeError("查询 Embedding 返回数量错误")
        search_started_at = time.perf_counter_ns()

        async def search(search_session: AsyncSession) -> list[KnowledgeRetrievalHit]:
            return await self.search_port.hybrid_search_files(
                search_session,
                store_id,
                file_ids,
                sanitized_query,
                embedding_result.vectors[0],
                dense_top_k=self.dense_top_k,
                lexical_top_k=self.lexical_top_k,
                candidate_top_k=self.candidate_top_k,
                rrf_k=self.rrf_k,
            )

        search_acquire_ms: int | None = None
        search_query_ms: int | None = None
        if self.search_session_factory is None:
            candidates = await search(session)
        else:
            # 检索事务在模型重排/独立安全复核前结束，取消或失败也释放连接。
            async with self.search_session_factory() as search_session:
                # 仅记录固定数值：先获取连接，再区分等待连接和两路 SQL/融合的耗时。
                acquire = getattr(search_session, "connection", None)
                if callable(acquire):
                    acquire_started_at = time.perf_counter_ns()
                    await acquire()
                    search_acquire_ms = max(0, (time.perf_counter_ns() - acquire_started_at) // 1_000_000)
                query_started_at = time.perf_counter_ns()
                candidates = await search(search_session)
                search_query_ms = max(0, (time.perf_counter_ns() - query_started_at) // 1_000_000)
        search_wall_ms = max(0, (time.perf_counter_ns() - search_started_at) // 1_000_000)
        if not candidates:
            return RagRetrievalResult(
                hits=[],
                top_score=0,
                context_tokens=0,
                embedding_provider=embedding_result.provider,
                embedding_model=embedding_result.model,
                embedding_input_tokens=embedding_result.input_tokens,
                embedding_latency_ms=embedding_result.latency_ms,
                embedding_wait_ms=embedding_wait_ms,
                search_wall_ms=search_wall_ms,
                search_acquire_ms=search_acquire_ms,
                search_query_ms=search_query_ms,
                candidate_count=0,
            )
        reranking_result: RerankingResult | None = None
        ordered_candidates = candidates
        if len(candidates) > 1:
            reranking_result = await self.reranking_service.rerank(
                sanitized_query,
                [
                    RerankCandidate(candidate_id=str(candidate.chunk_id), text=candidate.content)
                    for candidate in candidates
                ],
            )
            candidates_by_id = {str(candidate.chunk_id): candidate for candidate in candidates}
            ordered_candidates = [
                candidates_by_id[item.candidate_id].model_copy(update={"reranker_score": item.score})
                for item in reranking_result.scores
            ]
        reranked_candidates: list[KnowledgeRetrievalHit] = []
        for candidate in ordered_candidates[: self.final_top_k]:
            dense_score = max(candidate.score, candidate.dense_score)
            if dense_score >= self.min_dense_score or candidate.lexical_score >= self.min_lexical_score:
                reranked_candidates.append(candidate)
        selected: list[KnowledgeRetrievalHit] = []
        context_tokens = 0
        for candidate in reranked_candidates:
            if context_tokens + candidate.token_count > self.max_context_tokens:
                continue
            selected.append(candidate)
            context_tokens += candidate.token_count
        return RagRetrievalResult(
            hits=selected,
            top_score=selected[0].score if selected else 0.0,
            context_tokens=context_tokens,
            embedding_provider=embedding_result.provider,
            embedding_model=embedding_result.model,
            embedding_input_tokens=embedding_result.input_tokens,
            embedding_latency_ms=embedding_result.latency_ms,
            embedding_wait_ms=embedding_wait_ms,
            search_wall_ms=search_wall_ms,
            search_acquire_ms=search_acquire_ms,
            search_query_ms=search_query_ms,
            reranker_provider=reranking_result.provider if reranking_result else None,
            reranker_model=reranking_result.model if reranking_result else None,
            reranker_revision=reranking_result.revision if reranking_result else None,
            reranker_latency_ms=reranking_result.latency_ms if reranking_result else 0,
            candidate_count=len(candidates),
        )
