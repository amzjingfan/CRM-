"""编排 FAQ 切分、Embedding 和版本安全持久化。"""

import logging
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.rag.chunking import FaqTokenChunker
from app.agents.rag.embeddings import EmbeddingResult, EmbeddingService
from app.knowledge_base.schemas import KnowledgeSafetyMetadata, VectorChunkInput
from app.knowledge_base.vector_port import KnowledgeVectorPort

logger = logging.getLogger(__name__)


class EmbeddingClient(Protocol):
    """向量化服务只依赖批量 embed 行为，便于离线确定性测试。"""

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """返回与输入顺序一致的固定维度向量。"""
        ...


@dataclass(frozen=True, slots=True)
class VectorizationCycleResult:
    """一次 Worker 周期的低基数统计。"""

    claimed: int
    succeeded: int
    failed: int
    stale: int


class KnowledgeVectorizationService:
    """只通过知识库内部端口处理 FAQ，不直接写知识 ORM。"""

    def __init__(
        self,
        *,
        vector_port: KnowledgeVectorPort,
        embedding_service: EmbeddingClient,
        chunker: FaqTokenChunker,
        claim_limit: int = 10,
    ) -> None:
        if not 1 <= claim_limit <= 50:
            raise ValueError("向量化单次认领数量必须在 1 到 50 之间")
        self.vector_port = vector_port
        self.embedding_service = embedding_service
        self.chunker = chunker
        self.claim_limit = claim_limit

    async def process_cycle(self, session: AsyncSession) -> VectorizationCycleResult:
        """处理一批已发布 FAQ；单文档失败不阻断同批其他文档。"""
        documents = await self.vector_port.claim_pending_documents(session, self.claim_limit)
        succeeded = 0
        failed = 0
        stale = 0
        for document in documents:
            try:
                safety_metadata = KnowledgeSafetyMetadata.model_validate(
                    {
                        "statement_type": document.statement_type,
                        "customer_scope": document.customer_scope,
                        "publication_approval": document.publication_approval,
                        "semantic_schema_version": document.semantic_schema_version,
                        "approved_by": document.approved_by,
                        "approved_at": document.approved_at,
                        "store_id": document.store_id,
                        "document_version": document.document_version,
                        "approved_document_version": document.document_version,
                    }
                )
                text_chunks = self.chunker.split(document.question, document.answer)
                embedding_result = await self.embedding_service.embed([chunk.content for chunk in text_chunks])
                vector_chunks = [
                    VectorChunkInput(
                        chunk_index=text_chunk.chunk_index,
                        content=text_chunk.content,
                        token_count=text_chunk.token_count,
                        embedding=embedding,
                        metadata={
                            "source_type": "faq",
                            "document_version": document.document_version,
                            "category_id": str(document.category_id) if document.category_id else None,
                            "knowledge_safety": safety_metadata.model_dump(mode="json"),
                        },
                    )
                    for text_chunk, embedding in zip(text_chunks, embedding_result.vectors, strict=True)
                ]
                replaced = await self.vector_port.replace_document_chunks(
                    session,
                    document.store_id,
                    document.id,
                    document.document_version,
                    vector_chunks,
                )
                if replaced:
                    succeeded += 1
                    logger.info(
                        "knowledge_vectorization_succeeded",
                        extra={
                            "store_id": str(document.store_id),
                            "document_id": str(document.id),
                            "document_version": document.document_version,
                            "chunk_count": len(vector_chunks),
                            "provider": embedding_result.provider,
                            "model": embedding_result.model,
                            "input_tokens": embedding_result.input_tokens,
                            "latency_ms": embedding_result.latency_ms,
                        },
                    )
                else:
                    stale += 1
                    logger.warning(
                        "knowledge_vectorization_stale",
                        extra={
                            "store_id": str(document.store_id),
                            "document_id": str(document.id),
                            "document_version": document.document_version,
                        },
                    )
            except Exception as error:
                # 日志只记录异常类型和稳定实体标识，绝不记录 FAQ 正文或供应商响应。
                failed += 1
                await self.vector_port.mark_vectorization_failed(
                    session,
                    document.store_id,
                    document.id,
                    document.document_version,
                )
                logger.warning(
                    "knowledge_vectorization_failed",
                    extra={
                        "store_id": str(document.store_id),
                        "document_id": str(document.id),
                        "document_version": document.document_version,
                        "error_type": type(error).__name__,
                    },
                )
        return VectorizationCycleResult(
            claimed=len(documents),
            succeeded=succeeded,
            failed=failed,
            stale=stale,
        )


def build_vectorization_service(
    embedding_service: EmbeddingService,
    *,
    model_name: str,
) -> KnowledgeVectorizationService:
    """为 jobs Worker 构建生产向量化服务。"""
    from app.knowledge_base.vector_port import SqlAlchemyKnowledgeVectorPort

    return KnowledgeVectorizationService(
        vector_port=SqlAlchemyKnowledgeVectorPort(),
        embedding_service=embedding_service,
        chunker=FaqTokenChunker(model_name=model_name, max_tokens=800, overlap_tokens=80),
    )
