"""在真实 PostgreSQL + pgvector 上验证 RAG 门禁和并发认领。"""

import asyncio
import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.knowledge_base.models import KnowledgeChunk, KnowledgeDocument
from app.knowledge_base.schemas import (
    KnowledgeCustomerScope,
    KnowledgePublicationApproval,
    KnowledgeSafetyMetadata,
    KnowledgeStatementType,
)
from app.knowledge_base.vector_port import claim_pending_documents, hybrid_search
from app.shared.database.base import User
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


def vector(first: float, second: float = 0.0) -> list[float]:
    """构造适合 cosine 排序断言的 BGE-M3 1024 维合成向量。"""
    return [first, second, *([0.0] * 1022)]


async def cleanup_records(
    session: AsyncSession,
    store_ids: set[uuid.UUID],
    user_ids: set[uuid.UUID],
) -> None:
    """只删除本测试创建的随机店铺和审批人，外键数据由 CASCADE 清理。"""
    await session.execute(delete(Store).where(Store.id.in_(store_ids)))
    await session.execute(delete(User).where(User.id.in_(user_ids)))
    await session.commit()


def approved_document_fields(approver_id: uuid.UUID, approved_at: datetime) -> dict[str, object]:
    """构造当前文档版本通过人工内部复核的权威字段。"""
    return {
        "statement_type": KnowledgeStatementType.POLICY,
        "customer_scope": KnowledgeCustomerScope.GENERIC,
        "publication_approval": KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
        "semantic_schema_version": 1,
        "approved_by": approver_id,
        "approved_at": approved_at,
        "published_at": approved_at,
    }


def approved_chunk_metadata(
    *,
    store_id: uuid.UUID,
    document_version: int,
    approver_id: uuid.UUID,
    approved_at: datetime,
) -> dict[str, object]:
    """构造与文档权威字段完全一致的切片安全元数据。"""
    safety = KnowledgeSafetyMetadata(
        statement_type=KnowledgeStatementType.POLICY,
        customer_scope=KnowledgeCustomerScope.GENERIC,
        publication_approval=KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
        approved_by=approver_id,
        approved_at=approved_at,
        store_id=store_id,
        document_version=document_version,
        approved_document_version=document_version,
    )
    return {"knowledge_safety": safety.model_dump(mode="json")}


@pytest.mark.asyncio
async def test_pgvector_search_enforces_store_publish_ready_and_current_version() -> None:
    """相似度再高也不能绕过店铺、发布、ready 和当前版本过滤。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_a = Store(id=uuid.uuid4(), name="RAG A", code=f"rag-a-{uuid.uuid4().hex}")
    store_b = Store(id=uuid.uuid4(), name="RAG B", code=f"rag-b-{uuid.uuid4().hex}")
    approver = User(
        id=uuid.uuid4(),
        email=f"rag-approver-{uuid.uuid4().hex}@example.com",
        password_hash="test-only",
        name="RAG Approver",
    )
    approved_at = datetime.now(UTC)
    try:
        async with sessions() as session:
            session.add_all([store_a, store_b, approver])
            await session.flush()
            ready = KnowledgeDocument(
                id=uuid.uuid4(),
                store_id=store_a.id,
                title="可检索",
                question="Q",
                answer="A",
                status="published",
                vectorization_status="ready",
                document_version=2,
                content_hash="a" * 64,
                **approved_document_fields(approver.id, approved_at),
            )
            cross_store = KnowledgeDocument(
                id=uuid.uuid4(),
                store_id=store_b.id,
                title="跨店铺",
                question="Q",
                answer="B",
                status="published",
                vectorization_status="ready",
                document_version=1,
                content_hash="b" * 64,
                **approved_document_fields(approver.id, approved_at),
            )
            archived = KnowledgeDocument(
                id=uuid.uuid4(),
                store_id=store_a.id,
                title="已归档",
                question="Q",
                answer="C",
                status="archived",
                vectorization_status="ready",
                document_version=1,
                content_hash="c" * 64,
                **approved_document_fields(approver.id, approved_at),
            )
            pending = KnowledgeDocument(
                id=uuid.uuid4(),
                store_id=store_a.id,
                title="未向量化",
                question="Q",
                answer="D",
                status="published",
                vectorization_status="pending",
                document_version=1,
                content_hash="d" * 64,
                **approved_document_fields(approver.id, approved_at),
            )
            legacy_untyped = KnowledgeDocument(
                id=uuid.uuid4(),
                store_id=store_a.id,
                title="迁移前未分类知识",
                question="Q",
                answer="E",
                status="published",
                vectorization_status="ready",
                document_version=1,
                content_hash="e" * 64,
            )
            session.add_all([ready, cross_store, archived, pending, legacy_untyped])
            await session.flush()
            session.add_all(
                [
                    KnowledgeChunk(
                        store_id=store_a.id,
                        document_id=ready.id,
                        document_version=2,
                        chunk_index=0,
                        content="问题：Q\n答案：A",
                        token_count=10,
                        embedding=vector(1.0),
                        metadata_json=approved_chunk_metadata(
                            store_id=store_a.id,
                            document_version=2,
                            approver_id=approver.id,
                            approved_at=approved_at,
                        ),
                    ),
                    KnowledgeChunk(
                        store_id=store_a.id,
                        document_id=ready.id,
                        document_version=1,
                        chunk_index=0,
                        content="旧版本",
                        token_count=5,
                        embedding=vector(1.0),
                        metadata_json={},
                    ),
                    KnowledgeChunk(
                        store_id=store_b.id,
                        document_id=cross_store.id,
                        document_version=1,
                        chunk_index=0,
                        content="跨店铺",
                        token_count=5,
                        embedding=vector(1.0),
                        metadata_json=approved_chunk_metadata(
                            store_id=store_b.id,
                            document_version=1,
                            approver_id=approver.id,
                            approved_at=approved_at,
                        ),
                    ),
                    KnowledgeChunk(
                        store_id=store_a.id,
                        document_id=archived.id,
                        document_version=1,
                        chunk_index=0,
                        content="已归档",
                        token_count=5,
                        embedding=vector(1.0),
                        metadata_json=approved_chunk_metadata(
                            store_id=store_a.id,
                            document_version=1,
                            approver_id=approver.id,
                            approved_at=approved_at,
                        ),
                    ),
                    KnowledgeChunk(
                        store_id=store_a.id,
                        document_id=pending.id,
                        document_version=1,
                        chunk_index=0,
                        content="未 ready",
                        token_count=5,
                        embedding=vector(1.0),
                        metadata_json=approved_chunk_metadata(
                            store_id=store_a.id,
                            document_version=1,
                            approver_id=approver.id,
                            approved_at=approved_at,
                        ),
                    ),
                    KnowledgeChunk(
                        store_id=store_a.id,
                        document_id=legacy_untyped.id,
                        document_version=1,
                        chunk_index=0,
                        content="迁移前未分类知识",
                        token_count=5,
                        embedding=vector(1.0),
                        metadata_json={},
                    ),
                ]
            )
            await session.commit()

            hits = await hybrid_search(
                session,
                store_a.id,
                "问题 Q",
                vector(1.0),
                dense_top_k=20,
                lexical_top_k=20,
                candidate_top_k=20,
                rrf_k=60,
            )

            assert len(hits) == 1
            assert hits[0].document_id == ready.id
            assert hits[0].document_version == 2
            assert hits[0].score == pytest.approx(1.0)
    finally:
        async with sessions() as session:
            await cleanup_records(session, {store_a.id, store_b.id}, {approver.id})
        await engine.dispose()


@pytest.mark.asyncio
async def test_pending_documents_are_claimed_once_across_workers() -> None:
    """两个 Worker 并发认领时必须得到不同文档。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="Claim", code=f"claim-{uuid.uuid4().hex}")
    approver = User(
        id=uuid.uuid4(),
        email=f"claim-approver-{uuid.uuid4().hex}@example.com",
        password_hash="test-only",
        name="Claim Approver",
    )
    approved_at = datetime.now(UTC)
    try:
        async with sessions() as session:
            session.add_all([store, approver])
            await session.flush()
            session.add_all(
                [
                    KnowledgeDocument(
                        store_id=store.id,
                        title=f"FAQ {index}",
                        question="Q",
                        answer="A",
                        status="published",
                        vectorization_status="pending",
                        document_version=1,
                        content_hash=str(index) * 64,
                        **approved_document_fields(approver.id, approved_at),
                    )
                    for index in (1, 2)
                ]
            )
            await session.commit()

        async def claim_one() -> list[KnowledgeDocument]:
            async with sessions() as session:
                return await claim_pending_documents(session, limit=1)

        first, second = await asyncio.gather(claim_one(), claim_one())

        assert len(first) == len(second) == 1
        assert first[0].id != second[0].id
        async with sessions() as session:
            statuses = list(
                (
                    await session.scalars(
                        select(KnowledgeDocument.vectorization_status).where(KnowledgeDocument.store_id == store.id)
                    )
                ).all()
            )
            assert statuses == ["processing", "processing"]
    finally:
        async with sessions() as session:
            await cleanup_records(session, {store.id}, {approver.id})
        await engine.dispose()
