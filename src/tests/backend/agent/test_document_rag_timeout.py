"""Agent 文件检索在各耗时阶段共享一个超时预算。"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agent.embeddings import EmbeddingResult
from app.agent.rag import RagRetrievalService, RagRetrievalTimeout
from app.agent.workflow import AgentWorkflowService


@pytest.mark.asyncio
async def test_agent_routes_bound_files_to_rag_and_preserves_legacy_faq_route() -> None:
    file_id, store_id = uuid.uuid4(), uuid.uuid4()
    rag = SimpleNamespace(retrieve=AsyncMock(return_value="retrieved"))
    workflow = object.__new__(AgentWorkflowService)
    workflow.rag_service = rag
    command = SimpleNamespace(store_id=store_id, message="退货政策", knowledge_file_ids=[file_id], debug_mode=False)
    state = {"command": command, "session": object()}
    assert await workflow._retrieve(state) == "retrieved"
    assert rag.retrieve.await_args.kwargs["file_ids"] == (file_id,)
    command.knowledge_file_ids = []
    await workflow._retrieve(state)
    assert rag.retrieve.await_args.kwargs == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("slow_stage", ["embedding", "search", "rerank"])
async def test_document_retrieval_times_out_without_generating_a_result(slow_stage: str) -> None:
    file_id = uuid.uuid4()
    reached: list[str] = []

    class Embedding:
        async def embed(self, texts: list[str]) -> EmbeddingResult:
            reached.append("embedding")
            if slow_stage == "embedding":
                await asyncio.sleep(0.05)
            return EmbeddingResult(
                provider="test",
                model="bge",
                vectors=[[0.1] * 1024],
                input_tokens=1,
                latency_ms=0,
                provider_request_id=None,
            )

    class Search:
        async def hybrid_search_files(self, *args: object, **kwargs: object) -> list[object]:
            reached.append("search")
            assert args[2] == (file_id,)
            if slow_stage == "search":
                await asyncio.sleep(0.05)
            if slow_stage == "rerank":
                return [
                    SimpleNamespace(chunk_id=uuid.uuid4(), content="a", score=0.9),
                    SimpleNamespace(chunk_id=uuid.uuid4(), content="b", score=0.8),
                ]
            return []

    class Reranker:
        async def rerank(self, *args: object, **kwargs: object) -> object:
            reached.append("rerank")
            await asyncio.sleep(0.05)
            raise AssertionError("超时后不得返回候选")

    service = RagRetrievalService(
        embedding_service=Embedding(),
        search_port=Search(),
        reranking_service=Reranker(),
        dense_top_k=5,
        lexical_top_k=5,
        candidate_top_k=5,
        final_top_k=3,
        rrf_k=60,
        min_dense_score=0.5,
        min_lexical_score=0.5,
        max_context_tokens=1000,
        timeout_seconds=0.01,
    )
    with pytest.raises(RagRetrievalTimeout):
        await service.retrieve(SimpleNamespace(), uuid.uuid4(), "退款政策", file_ids=(file_id,))
    assert slow_stage in reached
    if slow_stage == "embedding":
        assert "search" not in reached
    if slow_stage == "search":
        assert "rerank" not in reached
