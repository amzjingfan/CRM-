"""在真实 PostgreSQL 上验证 BGE 1024 维与混合检索门禁。"""

import asyncio
import uuid

from sqlalchemy import delete

from app.knowledge_base.models import KnowledgeChunk, KnowledgeDocument
from app.knowledge_base.vector_port import claim_pending_documents, hybrid_search
from app.shared.database.session import session_factory
from app.stores.models import Store


def vector(first: float, second: float = 0.0) -> list[float]:
    """构造只用于数据库契约验证的 1024 维有限向量。"""
    return [first, second, *([0.0] * 1022)]


async def cleanup(store_ids: set[uuid.UUID]) -> None:
    """只删除本次随机 UUID 店铺，关联测试数据由外键级联清理。"""
    async with session_factory() as session:
        await session.execute(delete(Store).where(Store.id.in_(store_ids)))
        await session.commit()


async def verify_hybrid_gates() -> None:
    """验证店铺、发布、ready 和当前版本门禁不会被双路召回绕过。"""
    store_a = Store(id=uuid.uuid4(), name="BGE Runtime A", code=f"bge-runtime-a-{uuid.uuid4().hex}")
    store_b = Store(id=uuid.uuid4(), name="BGE Runtime B", code=f"bge-runtime-b-{uuid.uuid4().hex}")
    try:
        async with session_factory() as session:
            session.add_all([store_a, store_b])
            await session.flush()
            ready = KnowledgeDocument(
                id=uuid.uuid4(),
                store_id=store_a.id,
                title="退货政策",
                question="如何退货",
                answer="签收后七天内申请",
                status="published",
                vectorization_status="ready",
                document_version=2,
                content_hash="a" * 64,
            )
            cross_store = KnowledgeDocument(
                id=uuid.uuid4(),
                store_id=store_b.id,
                title="跨店铺政策",
                question="如何退货",
                answer="跨店铺内容",
                status="published",
                vectorization_status="ready",
                document_version=1,
                content_hash="b" * 64,
            )
            archived = KnowledgeDocument(
                id=uuid.uuid4(),
                store_id=store_a.id,
                title="归档政策",
                question="如何退货",
                answer="已归档",
                status="archived",
                vectorization_status="ready",
                document_version=1,
                content_hash="c" * 64,
            )
            session.add_all([ready, cross_store, archived])
            await session.flush()
            session.add_all(
                [
                    KnowledgeChunk(
                        store_id=store_a.id,
                        document_id=ready.id,
                        document_version=2,
                        chunk_index=0,
                        content="问题：如何退货\n答案：签收后七天内申请。",
                        token_count=20,
                        embedding=vector(1.0),
                        metadata_json={},
                    ),
                    KnowledgeChunk(
                        store_id=store_a.id,
                        document_id=ready.id,
                        document_version=1,
                        chunk_index=0,
                        content="旧版本退货内容",
                        token_count=10,
                        embedding=vector(1.0),
                        metadata_json={},
                    ),
                    KnowledgeChunk(
                        store_id=store_b.id,
                        document_id=cross_store.id,
                        document_version=1,
                        chunk_index=0,
                        content="跨店铺退货内容",
                        token_count=10,
                        embedding=vector(1.0),
                        metadata_json={},
                    ),
                    KnowledgeChunk(
                        store_id=store_a.id,
                        document_id=archived.id,
                        document_version=1,
                        chunk_index=0,
                        content="归档退货内容",
                        token_count=10,
                        embedding=vector(1.0),
                        metadata_json={},
                    ),
                ]
            )
            await session.commit()
            hits = await hybrid_search(
                session,
                store_a.id,
                "如何退货",
                vector(1.0),
                dense_top_k=20,
                lexical_top_k=20,
                candidate_top_k=20,
                rrf_k=60,
            )
            if len(hits) != 1 or hits[0].document_id != ready.id or hits[0].document_version != 2:
                raise RuntimeError("HYBRID_RETRIEVAL_GATE_FAILED")
            if hits[0].dense_score != 1.0 or hits[0].fusion_score <= 0:
                raise RuntimeError("HYBRID_RETRIEVAL_SCORE_FAILED")
    finally:
        await cleanup({store_a.id, store_b.id})


async def verify_concurrent_claim() -> None:
    """验证两个 Worker 的 SKIP LOCKED 认领不会重复处理同一文档。"""
    store = Store(id=uuid.uuid4(), name="BGE Claim", code=f"bge-runtime-claim-{uuid.uuid4().hex}")
    try:
        async with session_factory() as session:
            session.add(store)
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
                    )
                    for index in (1, 2)
                ]
            )
            await session.commit()

        async def claim_one() -> list[KnowledgeDocument]:
            async with session_factory() as session:
                return await claim_pending_documents(session, limit=1)

        first, second = await asyncio.gather(claim_one(), claim_one())
        if len(first) != 1 or len(second) != 1 or first[0].id == second[0].id:
            raise RuntimeError("VECTOR_WORKER_CLAIM_FAILED")
    finally:
        await cleanup({store.id})


async def main() -> None:
    """顺序执行真实数据库验收并只输出不含业务数据的结论。"""
    await verify_hybrid_gates()
    await verify_concurrent_claim()
    print("BGE hybrid runtime verification passed")


if __name__ == "__main__":
    asyncio.run(main())
