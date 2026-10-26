"""Agent 从当前店铺绑定且已审批的文件版本检索向量块。"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileChunk, KnowledgeFileVersion
from app.knowledge_base.schemas import KnowledgeRetrievalHit, KnowledgeSafetyMetadata
from app.shared.config.settings import get_settings
from app.shared.exceptions.errors import AppError, ErrorCode


async def hybrid_search_files(
    session: AsyncSession,
    store_id: uuid.UUID,
    file_ids: tuple[uuid.UUID, ...],
    query_text: str,
    query_embedding: list[float],
    *,
    dense_top_k: int,
    lexical_top_k: int,
    candidate_top_k: int,
    rrf_k: int,
) -> list[KnowledgeRetrievalHit]:
    """Dense 与词法两路只读取当前有效、人工批准且属于绑定范围的版本。"""
    if not file_ids:
        return []
    if len(file_ids) > 100 or len(query_embedding) != 1024 or not query_text.strip() or len(query_text) > 4000:
        raise AppError(ErrorCode.VALIDATION_ERROR, "文件检索参数无效", 422)
    if not all(1 <= value <= 100 for value in (dense_top_k, lexical_top_k, candidate_top_k)) or not 1 <= rrf_k <= 1000:
        raise AppError(ErrorCode.VALIDATION_ERROR, "文件检索候选参数无效", 422)
    distance = KnowledgeFileChunk.embedding.cosine_distance(query_embedding)
    lexical_score = func.similarity(KnowledgeFileChunk.content, query_text)
    columns = (
        KnowledgeFileChunk.id.label("chunk_id"),
        KnowledgeFileChunk.content,
        KnowledgeFileChunk.token_count,
        KnowledgeFileChunk.chunk_index,
        KnowledgeFile.id.label("file_id"),
        KnowledgeFile.category_id,
        KnowledgeFile.original_filename,
        KnowledgeFileVersion.version_number,
        KnowledgeFileVersion.statement_type,
        KnowledgeFileVersion.customer_scope,
        KnowledgeFileVersion.publication_approval,
        KnowledgeFileVersion.approved_by,
        KnowledgeFileVersion.approved_at,
        (1 - distance).label("dense_score"),
        lexical_score.label("lexical_score"),
    )
    gates = (
        KnowledgeFileChunk.store_id == store_id,
        KnowledgeFile.store_id == store_id,
        KnowledgeFileVersion.store_id == store_id,
        KnowledgeFile.id.in_(file_ids),
        KnowledgeFileVersion.file_id == KnowledgeFile.id,
        KnowledgeFile.deleted_at.is_(None),
        KnowledgeFile.archived_at.is_(None),
        KnowledgeFile.active_version_number == KnowledgeFileVersion.version_number,
        KnowledgeFileVersion.status == "ready",
        KnowledgeFileVersion.publication_approval == "approved_for_internal_review",
        KnowledgeFileChunk.embedding_model == get_settings().embedding_model,
        KnowledgeFileVersion.approved_by.is_not(None),
        KnowledgeFileVersion.approved_at.is_not(None),
    )
    base = (
        select(*columns)
        .join(KnowledgeFile, KnowledgeFile.id == KnowledgeFileChunk.file_id)
        .join(KnowledgeFileVersion, KnowledgeFileVersion.id == KnowledgeFileChunk.version_id)
        .where(*gates)
    )
    dense_rows = (
        (await session.execute(base.order_by(distance, KnowledgeFileChunk.id).limit(dense_top_k))).mappings().all()
    )
    lexical_rows = (
        (
            await session.execute(
                base.where(KnowledgeFileChunk.content.op("%")(query_text))
                .order_by(lexical_score.desc(), KnowledgeFileChunk.id)
                .limit(lexical_top_k)
            )
        )
        .mappings()
        .all()
    )
    dense_ranks = {row["chunk_id"]: rank for rank, row in enumerate(dense_rows, 1)}
    lexical_ranks = {row["chunk_id"]: rank for rank, row in enumerate(lexical_rows, 1)}
    by_id = {row["chunk_id"]: row for row in [*dense_rows, *lexical_rows]}

    def fusion(chunk_id: uuid.UUID) -> float:
        score = 1 / (rrf_k + dense_ranks[chunk_id]) if chunk_id in dense_ranks else 0
        score += 1 / (rrf_k + lexical_ranks[chunk_id]) if chunk_id in lexical_ranks else 0
        return min(1.0, score / (2 / (rrf_k + 1)))

    ordered = sorted(by_id, key=lambda chunk_id: (-fusion(chunk_id), str(chunk_id)))[:candidate_top_k]
    hits: list[KnowledgeRetrievalHit] = []
    for chunk_id in ordered:
        row = by_id[chunk_id]
        dense = max(0.0, min(1.0, float(row["dense_score"])))
        lexical = max(0.0, min(1.0, float(row["lexical_score"])))
        metadata = KnowledgeSafetyMetadata(
            store_id=store_id,
            document_version=row["version_number"],
            approved_document_version=row["version_number"],
            statement_type=row["statement_type"],
            customer_scope=row["customer_scope"],
            publication_approval=row["publication_approval"],
            approved_by=row["approved_by"],
            approved_at=row["approved_at"],
        )
        hits.append(
            KnowledgeRetrievalHit(
                document_id=row["file_id"],
                chunk_id=chunk_id,
                category_id=row["category_id"],
                document_version=row["version_number"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                token_count=row["token_count"],
                score=dense,
                dense_score=dense,
                lexical_score=lexical,
                fusion_score=fusion(chunk_id),
                source_label=row["original_filename"],
                source_type="file",
                safety_metadata=metadata,
            )
        )
    return hits
