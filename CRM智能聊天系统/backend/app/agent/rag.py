"""FAQ RAG 查询服务：脱敏、向量化、租户检索和上下文预算。"""

import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.embeddings import EmbeddingResult
from app.agent.retrieval_models import RerankCandidate, RerankingResult
from app.agent.security import sanitize_prompt_text
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
    reranker_provider: str | None = None
    reranker_model: str | None = None
    reranker_revision: str | None = None
    reranker_latency_ms: int = 0
    candidate_count: int = 0


class RagRetrievalService:
    """使用可信 store_id 执行 Top-K FAQ 检索，不访问其他业务表。"""

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

    async def retrieve(
        self,
        session: AsyncSession,
        store_id: uuid.UUID,
        query: str,
    ) -> RagRetrievalResult:
        """检索 FAQ，并按分数顺序装入不超过 Token 预算的上下文。"""
        sanitized_query = sanitize_prompt_text(query).strip()
        if not sanitized_query:
            raise ValueError("RAG 查询不能为空")
        embedding_result = await self.embedding_service.embed([sanitized_query])
        if len(embedding_result.vectors) != 1:
            raise RuntimeError("查询 Embedding 返回数量错误")
        candidates = await self.search_port.hybrid_search(
            session,
            store_id,
            sanitized_query,
            embedding_result.vectors[0],
            dense_top_k=self.dense_top_k,
            lexical_top_k=self.lexical_top_k,
            candidate_top_k=self.candidate_top_k,
            rrf_k=self.rrf_k,
        )
        if not candidates:
            return RagRetrievalResult(
                hits=[],
                top_score=0,
                context_tokens=0,
                embedding_provider=embedding_result.provider,
                embedding_model=embedding_result.model,
                embedding_input_tokens=embedding_result.input_tokens,
                embedding_latency_ms=embedding_result.latency_ms,
                candidate_count=0,
            )
        reranking_result = await self.reranking_service.rerank(
            sanitized_query,
            [RerankCandidate(candidate_id=str(candidate.chunk_id), text=candidate.content) for candidate in candidates],
        )
        candidates_by_id = {str(candidate.chunk_id): candidate for candidate in candidates}
        reranked_candidates: list[KnowledgeRetrievalHit] = []
        for item in reranking_result.scores[: self.final_top_k]:
            candidate = candidates_by_id[item.candidate_id].model_copy(update={"reranker_score": item.score})
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
            reranker_provider=reranking_result.provider,
            reranker_model=reranking_result.model,
            reranker_revision=reranking_result.revision,
            reranker_latency_ms=reranking_result.latency_ms,
            candidate_count=len(candidates),
        )
