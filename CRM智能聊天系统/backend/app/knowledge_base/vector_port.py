"""全栈层提供给 AI 工程师的知识向量持久化端口。"""

import uuid
from collections.abc import Mapping
from typing import Any, Protocol, cast

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_base.models import KnowledgeChunk, KnowledgeDocument
from app.knowledge_base.schemas import (
    KnowledgePublicationApproval,
    KnowledgeRetrievalHit,
    KnowledgeSafetyMetadata,
    KnowledgeStatementType,
    VectorChunkInput,
)
from app.shared.exceptions.errors import AppError, ErrorCode


async def pending_documents(session: AsyncSession, store_id: uuid.UUID, limit: int = 50) -> list[KnowledgeDocument]:
    """获取已发布且待向量化文档；AI 调用方仍需提供可信店铺上下文。"""
    return list(
        (
            await session.scalars(
                select(KnowledgeDocument)
                .where(
                    KnowledgeDocument.store_id == store_id,
                    KnowledgeDocument.status == "published",
                    KnowledgeDocument.vectorization_status == "pending",
                    KnowledgeDocument.statement_type != KnowledgeStatementType.UNKNOWN,
                    KnowledgeDocument.publication_approval.in_(
                        [
                            KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
                            KnowledgePublicationApproval.APPROVED_FOR_PUBLIC_REPLY,
                        ]
                    ),
                    KnowledgeDocument.deleted_at.is_(None),
                )
                .order_by(KnowledgeDocument.updated_at, KnowledgeDocument.id)
                .limit(limit)
            )
        ).all()
    )


async def claim_pending_documents(session: AsyncSession, limit: int = 10) -> list[KnowledgeDocument]:
    """跨店铺原子认领待向量化文档，避免多个 Worker 重复处理。

    认领事务只负责把当前版本从 pending 改为 processing 并立即提交；
    外部 Embedding 调用发生在事务之外，防止长事务占用连接和行锁。
    """
    documents = list(
        (
            await session.scalars(
                select(KnowledgeDocument)
                .where(
                    KnowledgeDocument.status == "published",
                    KnowledgeDocument.vectorization_status == "pending",
                    KnowledgeDocument.statement_type != KnowledgeStatementType.UNKNOWN,
                    KnowledgeDocument.publication_approval.in_(
                        [
                            KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
                            KnowledgePublicationApproval.APPROVED_FOR_PUBLIC_REPLY,
                        ]
                    ),
                    KnowledgeDocument.deleted_at.is_(None),
                )
                .order_by(KnowledgeDocument.updated_at, KnowledgeDocument.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
    )
    for document in documents:
        document.vectorization_status = "processing"
    if documents:
        await session.commit()
    return documents


async def replace_document_chunks(
    session: AsyncSession,
    store_id: uuid.UUID,
    document_id: uuid.UUID,
    document_version: int,
    chunks: list[VectorChunkInput],
) -> bool:
    """在同一事务中替换切片；版本漂移时拒绝写入，避免新正文使用旧向量。"""
    document = await session.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.store_id == store_id,
            KnowledgeDocument.status == "published",
            KnowledgeDocument.document_version == document_version,
            KnowledgeDocument.vectorization_status == "processing",
            KnowledgeDocument.statement_type != KnowledgeStatementType.UNKNOWN,
            KnowledgeDocument.publication_approval.in_(
                [
                    KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
                    KnowledgePublicationApproval.APPROVED_FOR_PUBLIC_REPLY,
                ]
            ),
            KnowledgeDocument.deleted_at.is_(None),
        )
    )
    if document is None:
        return False
    if not chunks:
        raise AppError(ErrorCode.VALIDATION_ERROR, "向量切片不能为空", 422)
    expected_safety = _document_safety_metadata(document)
    for chunk in chunks:
        try:
            supplied_safety = KnowledgeSafetyMetadata.model_validate(chunk.metadata.get("knowledge_safety"))
        except (TypeError, ValueError) as exc:
            raise AppError(ErrorCode.VALIDATION_ERROR, "向量切片缺少有效知识审批元数据", 422) from exc
        if supplied_safety != expected_safety:
            raise AppError(ErrorCode.VALIDATION_ERROR, "向量切片知识审批元数据与文档不一致", 422)
    await session.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
    session.add_all(
        [
            KnowledgeChunk(
                store_id=store_id,
                document_id=document.id,
                document_version=document_version,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                token_count=chunk.token_count,
                embedding=chunk.embedding,
                metadata_json=chunk.metadata,
            )
            for chunk in chunks
        ]
    )
    document.vectorization_status = "ready"
    await session.commit()
    return True


async def mark_vectorization_failed(
    session: AsyncSession, store_id: uuid.UUID, document_id: uuid.UUID, document_version: int
) -> bool:
    """只更新当前版本状态，不允许旧任务覆盖新版本。"""
    document = await session.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.store_id == store_id,
            KnowledgeDocument.document_version == document_version,
            KnowledgeDocument.vectorization_status == "processing",
        )
    )
    if document is not None:
        document.vectorization_status = "failed"
        await session.commit()
        return True
    return False


async def ready_chunks(session: AsyncSession, store_id: uuid.UUID) -> list[KnowledgeChunk]:
    """仅返回发布、ready 且版本一致的切片，作为 RAG 的强制数据门禁。"""
    return list(
        (
            await session.scalars(
                select(KnowledgeChunk)
                .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
                .where(
                    KnowledgeChunk.store_id == store_id,
                    KnowledgeDocument.status == "published",
                    KnowledgeDocument.vectorization_status == "ready",
                    KnowledgeDocument.statement_type != KnowledgeStatementType.UNKNOWN,
                    KnowledgeDocument.publication_approval.in_(
                        [
                            KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
                            KnowledgePublicationApproval.APPROVED_FOR_PUBLIC_REPLY,
                        ]
                    ),
                    KnowledgeDocument.deleted_at.is_(None),
                    KnowledgeChunk.document_version == KnowledgeDocument.document_version,
                )
            )
        ).all()
    )


def _document_safety_metadata(document: KnowledgeDocument) -> KnowledgeSafetyMetadata:
    """从数据库权威字段生成当前知识版本的安全元数据。"""
    return KnowledgeSafetyMetadata.model_validate(
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


def _row_safety_metadata(row: Mapping[str, Any]) -> KnowledgeSafetyMetadata:
    """比较切片副本与文档权威值；损坏或伪造时返回不可使用元数据。"""
    store_id = row["store_id"]
    document_version = row["document_version"]
    try:
        authoritative = KnowledgeSafetyMetadata.model_validate(
            {
                "statement_type": row["statement_type"],
                "customer_scope": row["customer_scope"],
                "publication_approval": row["publication_approval"],
                "semantic_schema_version": row["semantic_schema_version"],
                "approved_by": row["approved_by"],
                "approved_at": row["approved_at"],
                "store_id": store_id,
                "document_version": document_version,
                "approved_document_version": document_version,
            }
        )
    except (TypeError, ValueError):
        return KnowledgeSafetyMetadata.unapproved(store_id=store_id, document_version=document_version)
    try:
        metadata_json = row["metadata_json"]
        copied = KnowledgeSafetyMetadata.model_validate(metadata_json.get("knowledge_safety"))
    except (AttributeError, TypeError, ValueError):
        return KnowledgeSafetyMetadata.unapproved(store_id=store_id, document_version=document_version)
    if copied != authoritative:
        return KnowledgeSafetyMetadata.unapproved(store_id=store_id, document_version=document_version)
    return authoritative


async def similarity_search(
    session: AsyncSession,
    store_id: uuid.UUID,
    query_embedding: list[float],
    *,
    top_k: int = 5,
    min_score: float = 0.70,
) -> list[KnowledgeRetrievalHit]:
    """使用 pgvector cosine 索引执行店铺隔离 Top-K 检索。

    查询同时校验发布状态、向量化门禁和文档版本。普通请求参数不能扩大
    store_id 范围，因此跨店铺 chunk 即使向量更相似也不会进入结果。
    """
    if len(query_embedding) != 1024:
        raise AppError(ErrorCode.VALIDATION_ERROR, "查询向量必须为 1024 维", 422)
    if not 1 <= top_k <= 10 or not 0 <= min_score <= 1:
        raise AppError(ErrorCode.VALIDATION_ERROR, "RAG 检索参数超出允许范围", 422)
    distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)
    score = (1 - distance).label("score")
    rows = (
        (
            await session.execute(
                select(
                    KnowledgeChunk.id.label("chunk_id"),
                    KnowledgeChunk.document_id,
                    KnowledgeChunk.document_version,
                    KnowledgeChunk.chunk_index,
                    KnowledgeChunk.content,
                    KnowledgeChunk.token_count,
                    KnowledgeChunk.metadata_json,
                    KnowledgeDocument.store_id,
                    KnowledgeDocument.category_id,
                    KnowledgeDocument.title,
                    KnowledgeDocument.source,
                    KnowledgeDocument.statement_type,
                    KnowledgeDocument.customer_scope,
                    KnowledgeDocument.publication_approval,
                    KnowledgeDocument.semantic_schema_version,
                    KnowledgeDocument.approved_by,
                    KnowledgeDocument.approved_at,
                    score,
                )
                .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
                .where(
                    KnowledgeChunk.store_id == store_id,
                    KnowledgeDocument.store_id == store_id,
                    KnowledgeDocument.status == "published",
                    KnowledgeDocument.vectorization_status == "ready",
                    KnowledgeDocument.statement_type != KnowledgeStatementType.UNKNOWN,
                    KnowledgeDocument.publication_approval.in_(
                        [
                            KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
                            KnowledgePublicationApproval.APPROVED_FOR_PUBLIC_REPLY,
                        ]
                    ),
                    KnowledgeDocument.deleted_at.is_(None),
                    KnowledgeChunk.document_version == KnowledgeDocument.document_version,
                    distance <= 1 - min_score,
                )
                .order_by(distance, KnowledgeChunk.id)
                .limit(top_k)
            )
        )
        .mappings()
        .all()
    )
    return [
        KnowledgeRetrievalHit(
            document_id=row["document_id"],
            chunk_id=row["chunk_id"],
            category_id=row["category_id"],
            document_version=row["document_version"],
            chunk_index=row["chunk_index"],
            content=row["content"],
            token_count=row["token_count"],
            score=max(0.0, min(1.0, float(row["score"]))),
            dense_score=max(0.0, min(1.0, float(row["score"]))),
            source_label=str(row["source"] or row["title"]),
            safety_metadata=_row_safety_metadata(cast(Mapping[str, Any], row)),
        )
        for row in rows
    ]


async def hybrid_search(
    session: AsyncSession,
    store_id: uuid.UUID,
    query_text: str,
    query_embedding: list[float],
    *,
    dense_top_k: int = 20,
    lexical_top_k: int = 20,
    candidate_top_k: int = 20,
    rrf_k: int = 60,
) -> list[KnowledgeRetrievalHit]:
    """执行 BGE-M3 Dense 与 pg_trgm 词法双路召回，并用 RRF 融合。

    两路查询都重复执行店铺、发布状态、ready 状态和当前版本门禁。
    RRF 只依据名次融合，避免直接混合 cosine 与 trigram 的不同分数分布；
    Cross-Encoder 在 Agent 层对这里返回的有限候选集合做最终排序。
    """
    if len(query_embedding) != 1024:
        raise AppError(ErrorCode.VALIDATION_ERROR, "查询向量必须为 1024 维", 422)
    if not query_text.strip() or len(query_text) > 4000:
        raise AppError(ErrorCode.VALIDATION_ERROR, "混合检索查询文本无效", 422)
    if not all(1 <= value <= 100 for value in (dense_top_k, lexical_top_k, candidate_top_k)):
        raise AppError(ErrorCode.VALIDATION_ERROR, "混合检索候选参数超出允许范围", 422)
    if not 1 <= rrf_k <= 1000:
        raise AppError(ErrorCode.VALIDATION_ERROR, "RRF K 超出允许范围", 422)

    distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)
    dense_score = (1 - distance).label("dense_score")
    lexical_score = func.similarity(KnowledgeChunk.content, query_text).label("lexical_score")
    columns = (
        KnowledgeChunk.id.label("chunk_id"),
        KnowledgeChunk.document_id,
        KnowledgeChunk.document_version,
        KnowledgeChunk.chunk_index,
        KnowledgeChunk.content,
        KnowledgeChunk.token_count,
        KnowledgeChunk.metadata_json,
        KnowledgeDocument.store_id,
        KnowledgeDocument.category_id,
        KnowledgeDocument.title,
        KnowledgeDocument.source,
        KnowledgeDocument.statement_type,
        KnowledgeDocument.customer_scope,
        KnowledgeDocument.publication_approval,
        KnowledgeDocument.semantic_schema_version,
        KnowledgeDocument.approved_by,
        KnowledgeDocument.approved_at,
        dense_score,
        lexical_score,
    )
    gates = (
        KnowledgeChunk.store_id == store_id,
        KnowledgeDocument.store_id == store_id,
        KnowledgeDocument.status == "published",
        KnowledgeDocument.vectorization_status == "ready",
        KnowledgeDocument.statement_type != KnowledgeStatementType.UNKNOWN,
        KnowledgeDocument.publication_approval.in_(
            [
                KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
                KnowledgePublicationApproval.APPROVED_FOR_PUBLIC_REPLY,
            ]
        ),
        KnowledgeDocument.deleted_at.is_(None),
        KnowledgeChunk.document_version == KnowledgeDocument.document_version,
    )
    dense_rows = (
        (
            await session.execute(
                select(*columns)
                .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
                .where(*gates)
                .order_by(distance, KnowledgeChunk.id)
                .limit(dense_top_k)
            )
        )
        .mappings()
        .all()
    )
    lexical_rows = (
        (
            await session.execute(
                select(*columns)
                .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
                # ``%`` 由 pg_trgm 提供，可使用迁移 014 创建的 GIN 索引先筛选
                # 候选；随后仍按 similarity 原始分数稳定排序，避免全表计算。
                .where(*gates, KnowledgeChunk.content.op("%")(query_text))
                .order_by(lexical_score.desc(), KnowledgeChunk.id)
                .limit(lexical_top_k)
            )
        )
        .mappings()
        .all()
    )

    dense_ranks = {row["chunk_id"]: rank for rank, row in enumerate(dense_rows, start=1)}
    lexical_ranks = {row["chunk_id"]: rank for rank, row in enumerate(lexical_rows, start=1)}
    rows_by_id = {row["chunk_id"]: row for row in [*dense_rows, *lexical_rows]}
    max_rrf_score = 2 / (rrf_k + 1)

    def normalized_rrf(chunk_id: uuid.UUID) -> float:
        """把两路倒数排名分数归一化到 0-1，仅供可观测性和稳定排序。"""
        raw_score = 0.0
        if chunk_id in dense_ranks:
            raw_score += 1 / (rrf_k + dense_ranks[chunk_id])
        if chunk_id in lexical_ranks:
            raw_score += 1 / (rrf_k + lexical_ranks[chunk_id])
        return max(0.0, min(1.0, raw_score / max_rrf_score))

    ordered_ids = sorted(
        rows_by_id,
        key=lambda chunk_id: (
            -normalized_rrf(chunk_id),
            dense_ranks.get(chunk_id, 101),
            lexical_ranks.get(chunk_id, 101),
            str(chunk_id),
        ),
    )[:candidate_top_k]
    hits: list[KnowledgeRetrievalHit] = []
    for chunk_id in ordered_ids:
        row = rows_by_id[chunk_id]
        normalized_dense = max(0.0, min(1.0, float(row["dense_score"])))
        normalized_lexical = max(0.0, min(1.0, float(row["lexical_score"])))
        hits.append(
            KnowledgeRetrievalHit(
                document_id=row["document_id"],
                chunk_id=row["chunk_id"],
                category_id=row["category_id"],
                document_version=row["document_version"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                token_count=row["token_count"],
                score=normalized_dense,
                dense_score=normalized_dense,
                lexical_score=normalized_lexical,
                fusion_score=normalized_rrf(chunk_id),
                source_label=str(row["source"] or row["title"]),
                safety_metadata=_row_safety_metadata(cast(Mapping[str, Any], row)),
            )
        )
    return hits


class KnowledgeVectorPort(Protocol):
    """AI 向量化服务可使用的最小知识库写入边界。"""

    async def claim_pending_documents(self, session: AsyncSession, limit: int) -> list[KnowledgeDocument]:
        """原子认领待处理 FAQ。"""
        ...

    async def replace_document_chunks(
        self,
        session: AsyncSession,
        store_id: uuid.UUID,
        document_id: uuid.UUID,
        document_version: int,
        chunks: list[VectorChunkInput],
    ) -> bool:
        """仅在文档版本仍有效时替换向量。"""
        ...

    async def mark_vectorization_failed(
        self,
        session: AsyncSession,
        store_id: uuid.UUID,
        document_id: uuid.UUID,
        document_version: int,
    ) -> bool:
        """仅把本次认领的当前版本标记失败。"""
        ...


class KnowledgeSearchPort(Protocol):
    """Agent 查询侧可使用的租户安全知识端口。"""

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
        """返回当前店铺经 Dense、词法和 RRF 融合的安全候选。"""
        ...


class SqlAlchemyKnowledgeVectorPort:
    """把 AI 服务限制在全栈层批准的知识库函数内。"""

    async def claim_pending_documents(self, session: AsyncSession, limit: int) -> list[KnowledgeDocument]:
        return await claim_pending_documents(session, limit)

    async def replace_document_chunks(
        self,
        session: AsyncSession,
        store_id: uuid.UUID,
        document_id: uuid.UUID,
        document_version: int,
        chunks: list[VectorChunkInput],
    ) -> bool:
        return await replace_document_chunks(session, store_id, document_id, document_version, chunks)

    async def mark_vectorization_failed(
        self,
        session: AsyncSession,
        store_id: uuid.UUID,
        document_id: uuid.UUID,
        document_version: int,
    ) -> bool:
        return await mark_vectorization_failed(session, store_id, document_id, document_version)


class SqlAlchemyKnowledgeSearchPort:
    """将 RAG 查询限制在知识库批准的 pgvector 检索函数内。"""

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
        return await hybrid_search(
            session,
            store_id,
            query_text,
            query_embedding,
            dense_top_k=dense_top_k,
            lexical_top_k=lexical_top_k,
            candidate_top_k=candidate_top_k,
            rrf_k=rrf_k,
        )
