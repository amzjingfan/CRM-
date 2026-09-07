"""验证 FAQ 向量化任务的版本、安全和失败边界。"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.chunking import FaqTokenChunker
from app.agent.embeddings import EmbeddingResult
from app.agent.vectorization import KnowledgeVectorizationService
from app.knowledge_base.models import KnowledgeDocument
from app.knowledge_base.schemas import KnowledgeSafetyMetadata, VectorChunkInput


class CharacterEncoding:
    """测试专用逐字符编码器。"""

    def encode(self, text: str) -> list[int]:
        return [ord(character) for character in text]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(token) for token in tokens)


class DeterministicEmbeddingService:
    """返回固定维度向量，不访问公网。"""

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        return EmbeddingResult(
            provider="fake",
            model="fake-bge-m3",
            vectors=[[float(index + 1) / 100] * 1024 for index, _ in enumerate(texts)],
            input_tokens=sum(len(text) for text in texts),
            latency_ms=1,
            provider_request_id="fake-request",
        )


class FailingEmbeddingService:
    """模拟向量供应商最终失败。"""

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        raise RuntimeError("provider response must not be persisted")


@dataclass
class MemoryVectorPort:
    """记录 Agent 对知识库内部端口的调用。"""

    documents: list[KnowledgeDocument]

    def __post_init__(self) -> None:
        self.replaced: list[tuple[uuid.UUID, int, list[VectorChunkInput]]] = []
        self.failed: list[tuple[uuid.UUID, int]] = []

    async def claim_pending_documents(self, session: AsyncSession, limit: int) -> list[KnowledgeDocument]:
        return self.documents[:limit]

    async def replace_document_chunks(
        self,
        session: AsyncSession,
        store_id: uuid.UUID,
        document_id: uuid.UUID,
        document_version: int,
        chunks: list[VectorChunkInput],
    ) -> bool:
        self.replaced.append((document_id, document_version, chunks))
        return True

    async def mark_vectorization_failed(
        self,
        session: AsyncSession,
        store_id: uuid.UUID,
        document_id: uuid.UUID,
        document_version: int,
    ) -> bool:
        self.failed.append((document_id, document_version))
        return True


def document() -> KnowledgeDocument:
    """构造不依赖数据库连接的已发布 FAQ。"""
    return KnowledgeDocument(
        id=uuid.uuid4(),
        store_id=uuid.uuid4(),
        category_id=uuid.uuid4(),
        source_type="faq",
        title="退货期限",
        question="商品可以在几天内退货？",
        answer="签收后七天内可以申请退货。",
        source="policy",
        tags=["退货"],
        status="published",
        vectorization_status="processing",
        document_version=3,
        content_hash="a" * 64,
        statement_type="policy",
        customer_scope="generic",
        publication_approval="approved_for_internal_review",
        semantic_schema_version=1,
        approved_by=uuid.uuid4(),
        approved_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_vectorization_cycle_replaces_current_document_chunks() -> None:
    """向量化成功必须通过知识端口原子替换，不能由 Agent 直接写 ORM。"""
    faq = document()
    port = MemoryVectorPort([faq])
    service = KnowledgeVectorizationService(
        vector_port=port,
        embedding_service=DeterministicEmbeddingService(),
        chunker=FaqTokenChunker(model_name="fake", encoding=CharacterEncoding()),
        claim_limit=5,
    )

    result = await service.process_cycle(cast(AsyncSession, object()))

    assert result.claimed == 1
    assert result.succeeded == 1
    assert result.failed == 0
    assert port.failed == []
    assert len(port.replaced) == 1
    chunks = port.replaced[0][2]
    assert chunks[0].content.startswith("问题：商品可以在几天内退货？")
    assert chunks[0].metadata == {
        "source_type": "faq",
        "document_version": 3,
        "category_id": str(faq.category_id),
        "knowledge_safety": KnowledgeSafetyMetadata(
            statement_type="policy",
            customer_scope="generic",
            publication_approval="approved_for_internal_review",
            semantic_schema_version=1,
            approved_by=faq.approved_by,
            approved_at=faq.approved_at,
            store_id=faq.store_id,
            document_version=3,
            approved_document_version=3,
        ).model_dump(mode="json"),
    }


@pytest.mark.asyncio
async def test_vectorization_failure_marks_only_claimed_version_failed() -> None:
    """供应商失败必须落失败状态，但错误正文不能进入知识数据。"""
    faq = document()
    port = MemoryVectorPort([faq])
    service = KnowledgeVectorizationService(
        vector_port=port,
        embedding_service=FailingEmbeddingService(),
        chunker=FaqTokenChunker(model_name="fake", encoding=CharacterEncoding()),
        claim_limit=5,
    )

    result = await service.process_cycle(cast(AsyncSession, object()))

    assert result.succeeded == 0
    assert result.failed == 1
    assert port.replaced == []
    assert port.failed == [(faq.id, faq.document_version)]
