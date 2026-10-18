"""验证 FAQ RAG 查询脱敏、租户边界和上下文预算。"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.embeddings import EmbeddingResult
from app.agent.rag import RagRetrievalService
from app.agent.retrieval_models import RerankingResult, RerankScore
from app.knowledge_base.schemas import (
    KnowledgeCustomerScope,
    KnowledgePublicationApproval,
    KnowledgeRetrievalHit,
    KnowledgeSafetyMetadata,
    KnowledgeStatementType,
)


class CapturingEmbeddingService:
    """记录 Embedding 输入并返回固定查询向量。"""

    def __init__(self) -> None:
        self.texts: list[str] = []

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        self.texts.extend(texts)
        return EmbeddingResult(
            provider="fake",
            model="fake-bge-m3",
            vectors=[[0.1] * 1024 for _ in texts],
            input_tokens=8,
            latency_ms=2,
            provider_request_id="fake-query",
        )


@dataclass
class MemorySearchPort:
    """模拟知识库租户安全检索端口。"""

    hits: list[KnowledgeRetrievalHit]

    def __post_init__(self) -> None:
        self.session: AsyncSession | None = None
        self.store_id: uuid.UUID | None = None
        self.query_text: str | None = None
        self.dense_top_k: int | None = None
        self.lexical_top_k: int | None = None
        self.candidate_top_k: int | None = None
        self.rrf_k: int | None = None

    async def hybrid_search(
        self,
        session: AsyncSession,
        store_id: uuid.UUID,
        query_text: str,
        query_embedding: list[float],
        *,
        dense_top_k: int,
        lexical_top_k: int,
        candidate_top_k: int,
        rrf_k: int,
    ) -> list[KnowledgeRetrievalHit]:
        assert len(query_embedding) == 1024
        self.session = session
        self.store_id = store_id
        self.query_text = query_text
        self.dense_top_k = dense_top_k
        self.lexical_top_k = lexical_top_k
        self.candidate_top_k = candidate_top_k
        self.rrf_k = rrf_k
        return self.hits


class FixedRerankingService:
    """按测试给定顺序返回 Cross-Encoder 结果。"""

    def __init__(self, ordered_ids: list[str] | None = None) -> None:
        self.ordered_ids = ordered_ids
        self.query: str | None = None

    async def rerank(self, query: str, candidates: list[object]) -> RerankingResult:
        self.query = query
        candidate_ids = [str(candidate.candidate_id) for candidate in candidates]
        ordered_ids = self.ordered_ids or candidate_ids
        return RerankingResult(
            provider="local_bge",
            model="BAAI/bge-reranker-large",
            revision="test-revision",
            scores=[
                RerankScore(candidate_id=item_id, score=float(len(ordered_ids) - index))
                for index, item_id in enumerate(ordered_ids)
            ],
            latency_ms=3,
            provider_request_id="rerank-test",
        )


def hit(*, score: float, token_count: int, label: str) -> KnowledgeRetrievalHit:
    """构造不含真实客户数据的检索命中。"""
    return KnowledgeRetrievalHit(
        document_id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        category_id=uuid.uuid4(),
        document_version=2,
        chunk_index=0,
        content=f"问题：退货期限\n答案：{label}",
        token_count=token_count,
        score=score,
        source_label=label,
        safety_metadata=KnowledgeSafetyMetadata(
            statement_type=KnowledgeStatementType.POLICY,
            customer_scope=KnowledgeCustomerScope.GENERIC,
            publication_approval=KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
            approved_by=uuid.uuid4(),
            approved_at=datetime.now(UTC),
            store_id=uuid.uuid4(),
            document_version=2,
            approved_document_version=2,
        ),
    )


@pytest.mark.asyncio
async def test_rag_retrieval_sanitizes_query_and_forwards_store_scope() -> None:
    """客户标识不得发送给 Embedding，可信店铺 ID 必须下推到端口。"""
    store_id = uuid.uuid4()
    embedding = CapturingEmbeddingService()
    port = MemorySearchPort([hit(score=0.91, token_count=50, label="退货政策")])
    service = RagRetrievalService(
        embedding_service=embedding,
        search_port=port,
        reranking_service=FixedRerankingService(),
        dense_top_k=20,
        lexical_top_k=20,
        candidate_top_k=20,
        final_top_k=5,
        rrf_k=60,
        min_dense_score=0.45,
        min_lexical_score=0.10,
        max_context_tokens=6000,
    )

    result = await service.retrieve(
        cast(AsyncSession, object()),
        store_id,
        "订单 AB123456789 怎么退货？请联系 buyer@example.com",
    )

    assert port.store_id == store_id
    assert port.dense_top_k == 20
    assert port.lexical_top_k == 20
    assert port.candidate_top_k == 20
    assert port.rrf_k == 60
    assert "AB123456789" not in embedding.texts[0]
    assert "buyer@example.com" not in embedding.texts[0]
    assert "AB123456789" not in str(port.query_text)
    assert "buyer@example.com" not in str(port.query_text)
    assert result.top_score == 0.91
    assert [item.chunk_id for item in result.hits] == [item.chunk_id for item in port.hits]
    assert result.hits[0].reranker_score is None
    assert type(result.embedding_wait_ms) is int and result.embedding_wait_ms >= 0
    assert type(result.search_wall_ms) is int and result.search_wall_ms >= 0


@pytest.mark.asyncio
async def test_rag_closes_own_search_session_before_model_reranking() -> None:
    """数据库查询完成即释放连接，后续模型等待不占用请求会话。"""
    events: list[str] = []
    caller_session = cast(AsyncSession, object())
    search_session = cast(AsyncSession, object())
    port = MemorySearchPort(
        [hit(score=0.91, token_count=20, label="第一条"), hit(score=0.82, token_count=20, label="第二条")]
    )

    @asynccontextmanager
    async def search_session_factory() -> AsyncIterator[AsyncSession]:
        events.append("opened")
        try:
            yield search_session
        finally:
            events.append("closed")

    class CheckingReranker(FixedRerankingService):
        async def rerank(self, query: str, candidates: list[object]) -> RerankingResult:
            assert events[-1] == "closed"
            events.append("reranked")
            return await super().rerank(query, candidates)

    service = RagRetrievalService(
        embedding_service=CapturingEmbeddingService(),
        search_port=port,
        reranking_service=CheckingReranker(),
        search_session_factory=search_session_factory,
        dense_top_k=20,
        lexical_top_k=20,
        candidate_top_k=20,
        final_top_k=5,
        rrf_k=60,
        min_dense_score=0.45,
        min_lexical_score=0.10,
        max_context_tokens=100,
    )

    result = await service.retrieve(caller_session, uuid.uuid4(), "退货流程？")

    assert len(result.hits) == 2
    assert port.session is search_session
    assert port.session is not caller_session
    assert events == ["opened", "closed", "reranked"]


@pytest.mark.asyncio
async def test_rag_search_session_closes_on_query_failure() -> None:
    """检索失败关闭时同样释放独立会话，不在后续请求中留连接。"""
    events: list[str] = []

    @asynccontextmanager
    async def search_session_factory() -> AsyncIterator[AsyncSession]:
        events.append("opened")
        try:
            yield cast(AsyncSession, object())
        finally:
            events.append("closed")

    class FailingSearchPort(MemorySearchPort):
        async def hybrid_search(
            self,
            session: AsyncSession,
            store_id: uuid.UUID,
            query_text: str,
            query_embedding: list[float],
            *,
            dense_top_k: int,
            lexical_top_k: int,
            candidate_top_k: int,
            rrf_k: int,
        ) -> list[KnowledgeRetrievalHit]:
            raise RuntimeError("search unavailable")

    service = RagRetrievalService(
        embedding_service=CapturingEmbeddingService(),
        search_port=FailingSearchPort([]),
        reranking_service=FixedRerankingService(),
        search_session_factory=search_session_factory,
        dense_top_k=20,
        lexical_top_k=20,
        candidate_top_k=20,
        final_top_k=5,
        rrf_k=60,
        min_dense_score=0.45,
        min_lexical_score=0.10,
        max_context_tokens=100,
    )

    with pytest.raises(RuntimeError, match="search unavailable"):
        await service.retrieve(cast(AsyncSession, object()), uuid.uuid4(), "退货流程？")
    assert events == ["opened", "closed"]


@pytest.mark.asyncio
async def test_rag_search_session_closes_when_stream_is_cancelled() -> None:
    """浏览器断线取消检索时，独立事务不能留在数据库连接池。"""
    events: list[str] = []
    search_started = asyncio.Event()

    @asynccontextmanager
    async def search_session_factory() -> AsyncIterator[AsyncSession]:
        events.append("opened")
        try:
            yield cast(AsyncSession, object())
        finally:
            events.append("closed")

    class BlockingSearchPort(MemorySearchPort):
        async def hybrid_search(
            self,
            session: AsyncSession,
            store_id: uuid.UUID,
            query_text: str,
            query_embedding: list[float],
            *,
            dense_top_k: int,
            lexical_top_k: int,
            candidate_top_k: int,
            rrf_k: int,
        ) -> list[KnowledgeRetrievalHit]:
            search_started.set()
            await asyncio.Event().wait()
            return []

    service = RagRetrievalService(
        embedding_service=CapturingEmbeddingService(),
        search_port=BlockingSearchPort([]),
        reranking_service=FixedRerankingService(),
        search_session_factory=search_session_factory,
        dense_top_k=20,
        lexical_top_k=20,
        candidate_top_k=20,
        final_top_k=5,
        rrf_k=60,
        min_dense_score=0.45,
        min_lexical_score=0.10,
        max_context_tokens=100,
    )
    task = asyncio.create_task(service.retrieve(cast(AsyncSession, object()), uuid.uuid4(), "退货流程？"))
    await search_started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert events == ["opened", "closed"]


@pytest.mark.asyncio
async def test_single_candidate_skips_ordering_only_rerank_without_weakening_score_gate() -> None:
    """只有一条候选时排序不变，仍按 Dense/词法分数与上下文预算筛选。"""
    reranker = FixedRerankingService()
    candidate = hit(score=0.91, token_count=30, label="已审批政策")
    service = RagRetrievalService(
        embedding_service=CapturingEmbeddingService(),
        search_port=MemorySearchPort([candidate]),
        reranking_service=reranker,
        dense_top_k=20,
        lexical_top_k=20,
        candidate_top_k=20,
        final_top_k=5,
        rrf_k=60,
        min_dense_score=0.45,
        min_lexical_score=0.10,
        max_context_tokens=100,
    )

    result = await service.retrieve(cast(AsyncSession, object()), uuid.uuid4(), "退货政策是什么？")

    assert [item.chunk_id for item in result.hits] == [candidate.chunk_id]
    assert result.top_score == 0.91
    assert result.reranker_provider is None
    assert reranker.query is None


@pytest.mark.asyncio
async def test_same_store_query_coalesces_local_embedding_across_workflows() -> None:
    """重复问句共用短时向量结果，每个请求仍独立执行店铺知识检索。"""

    class DelayedLocalEmbedding(CapturingEmbeddingService):
        provider_name = "local_bge"
        model_name = "BAAI/bge-m3"
        dimensions = 1024

        def __init__(self) -> None:
            super().__init__()
            self.provider = self
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.calls = 0

        async def embed(self, texts: list[str]) -> EmbeddingResult:
            self.calls += 1
            self.started.set()
            await self.release.wait()
            return await super().embed(texts)

    embedding = DelayedLocalEmbedding()
    store_id = uuid.uuid4()
    ports = [MemorySearchPort([hit(score=0.91, token_count=20, label="退货政策")]) for _ in range(50)]
    services = [
        RagRetrievalService(
            embedding_service=embedding,
            search_port=port,
            reranking_service=FixedRerankingService(),
            dense_top_k=20,
            lexical_top_k=20,
            candidate_top_k=20,
            final_top_k=5,
            rrf_k=60,
            min_dense_score=0.45,
            min_lexical_score=0.10,
            max_context_tokens=100,
        )
        for port in ports
    ]
    tasks = [
        asyncio.create_task(service.retrieve(cast(AsyncSession, object()), store_id, "本店的退货流程？"))
        for service in services
    ]
    await embedding.started.wait()
    await asyncio.sleep(0)
    embedding.release.set()
    results = await asyncio.gather(*tasks)

    assert embedding.calls == 1
    assert all(result.hits for result in results)
    assert all(port.store_id == store_id for port in ports)
    assert sum(result.embedding_input_tokens for result in results) == 8
    cached = await services[0].retrieve(cast(AsyncSession, object()), store_id, "本店的退货流程？")
    assert cached.embedding_input_tokens == 0
    assert embedding.calls == 1
    await services[0].retrieve(cast(AsyncSession, object()), uuid.uuid4(), "本店的退货流程？")
    assert embedding.calls == 2


@pytest.mark.asyncio
async def test_failed_local_embedding_is_not_shared_with_later_request() -> None:
    """本地模型错误不得进入短期缓存，下一请求必须重新获取向量。"""

    class FailOnceEmbedding(CapturingEmbeddingService):
        provider_name = "local_bge"
        model_name = "BAAI/bge-m3"
        dimensions = 1024

        def __init__(self) -> None:
            super().__init__()
            self.provider = self
            self.calls = 0

        async def embed(self, texts: list[str]) -> EmbeddingResult:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("local model unavailable")
            return await super().embed(texts)

    embedding = FailOnceEmbedding()
    service = RagRetrievalService(
        embedding_service=embedding,
        search_port=MemorySearchPort([]),
        reranking_service=FixedRerankingService(),
        dense_top_k=20,
        lexical_top_k=20,
        candidate_top_k=20,
        final_top_k=5,
        rrf_k=60,
        min_dense_score=0.45,
        min_lexical_score=0.10,
        max_context_tokens=100,
    )
    store_id = uuid.uuid4()

    with pytest.raises(RuntimeError, match="local model unavailable"):
        await service.retrieve(cast(AsyncSession, object()), store_id, "退款规则")
    result = await service.retrieve(cast(AsyncSession, object()), store_id, "退款规则")

    assert result.hits == []
    assert embedding.calls == 2


@pytest.mark.asyncio
async def test_last_cancelled_waiter_stops_unused_local_embedding() -> None:
    """已无人等待的本地推理不得在后台继续占用模型容量。"""

    class BlockingLocalEmbedding(CapturingEmbeddingService):
        provider_name = "local_bge"
        model_name = "BAAI/bge-m3"
        dimensions = 1024

        def __init__(self) -> None:
            super().__init__()
            self.provider = self
            self.started = asyncio.Event()
            self.release = asyncio.Event()
            self.cancelled = asyncio.Event()

        async def embed(self, texts: list[str]) -> EmbeddingResult:
            self.started.set()
            try:
                await self.release.wait()
            except asyncio.CancelledError:
                self.cancelled.set()
                raise
            return await super().embed(texts)

    embedding = BlockingLocalEmbedding()
    service = RagRetrievalService(
        embedding_service=embedding,
        search_port=MemorySearchPort([]),
        reranking_service=FixedRerankingService(),
        dense_top_k=20,
        lexical_top_k=20,
        candidate_top_k=20,
        final_top_k=5,
        rrf_k=60,
        min_dense_score=0.45,
        min_lexical_score=0.10,
        max_context_tokens=100,
    )
    task = asyncio.create_task(service.retrieve(cast(AsyncSession, object()), uuid.uuid4(), "本店退货流程"))
    await embedding.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    try:
        assert embedding.cancelled.is_set()
    finally:
        embedding.release.set()


@pytest.mark.asyncio
async def test_rag_retrieval_respects_context_token_budget() -> None:
    """即使数据库返回 Top 5，也不能把超预算知识全部塞入 Prompt。"""
    embedding = CapturingEmbeddingService()
    hits = [
        hit(score=0.95, token_count=70, label="第一条"),
        hit(score=0.90, token_count=50, label="第二条"),
        hit(score=0.85, token_count=20, label="第三条"),
    ]
    service = RagRetrievalService(
        embedding_service=embedding,
        search_port=MemorySearchPort(hits),
        reranking_service=FixedRerankingService(),
        dense_top_k=20,
        lexical_top_k=20,
        candidate_top_k=20,
        final_top_k=5,
        rrf_k=60,
        min_dense_score=0.45,
        min_lexical_score=0.10,
        max_context_tokens=100,
    )

    result = await service.retrieve(cast(AsyncSession, object()), uuid.uuid4(), "退货政策是什么？")

    assert [item.source_label for item in result.hits] == ["第一条", "第三条"]
    assert result.context_tokens == 90


@pytest.mark.asyncio
async def test_rag_uses_reranker_order_before_final_top_k() -> None:
    """混合召回只生成候选，最终 Top-K 必须服从 Cross-Encoder 顺序。"""
    candidates = [
        hit(score=0.93, token_count=20, label="Dense 第一"),
        hit(score=0.82, token_count=20, label="Reranker 第一"),
    ]
    reranker = FixedRerankingService([str(candidates[1].chunk_id), str(candidates[0].chunk_id)])
    service = RagRetrievalService(
        embedding_service=CapturingEmbeddingService(),
        search_port=MemorySearchPort(candidates),
        reranking_service=reranker,
        dense_top_k=20,
        lexical_top_k=20,
        candidate_top_k=20,
        final_top_k=1,
        rrf_k=60,
        min_dense_score=0.45,
        min_lexical_score=0.10,
        max_context_tokens=100,
    )

    result = await service.retrieve(cast(AsyncSession, object()), uuid.uuid4(), "退货")

    assert [item.source_label for item in result.hits] == ["Reranker 第一"]
    assert result.top_score == 0.82
    assert result.reranker_model == "BAAI/bge-reranker-large"


@pytest.mark.asyncio
async def test_rag_rejects_candidates_below_dense_and_lexical_gates() -> None:
    """无答案候选同时低于两路门禁时不得进入生成上下文。"""
    weak = hit(score=0.30, token_count=20, label="弱相关")
    weak = weak.model_copy(update={"dense_score": 0.30, "lexical_score": 0.02})
    service = RagRetrievalService(
        embedding_service=CapturingEmbeddingService(),
        search_port=MemorySearchPort([weak]),
        reranking_service=FixedRerankingService(),
        dense_top_k=20,
        lexical_top_k=20,
        candidate_top_k=20,
        final_top_k=5,
        rrf_k=60,
        min_dense_score=0.45,
        min_lexical_score=0.10,
        max_context_tokens=100,
    )

    result = await service.retrieve(cast(AsyncSession, object()), uuid.uuid4(), "完全无关的问题")

    assert result.hits == []
    assert result.top_score == 0
