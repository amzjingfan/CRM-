"""隔离 PostgreSQL 中验证文件分类保护与 pgvector 表结构。"""

import os
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.knowledge_base import document_service, repository
from app.knowledge_base import service as knowledge_service
from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileChunk, KnowledgeFileVersion
from app.knowledge_base.models import KnowledgeCategory, KnowledgeDocument
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_file_vector_is_separate_and_category_with_file_cannot_be_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """新文件计入分类占用；向量只写新表，不改变 FAQ 表。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="文档导入测试", code=f"rag-file-{uuid.uuid4().hex}")
    user = User(id=uuid.uuid4(), email=f"rag-{uuid.uuid4().hex}@example.invalid", password_hash="test", name="测试员")
    category = KnowledgeCategory(id=uuid.uuid4(), store_id=store.id, name="资料", code="docs")
    document_file = KnowledgeFile(
        id=uuid.uuid4(),
        store_id=store.id,
        category_id=category.id,
        original_filename="guide.pdf",
        filename_key="guide.pdf",
    )
    version = KnowledgeFileVersion(
        id=uuid.uuid4(),
        store_id=store.id,
        file_id=document_file.id,
        version_number=1,
        source_object_key="tests/guide.pdf",
        file_sha256="a" * 64,
        media_type="application/pdf",
        config_json={"strategy": "recursive", "chunk_size": 500, "overlap": 50},
        status="ready",
        created_by=user.id,
    )
    chunk = KnowledgeFileChunk(
        store_id=store.id,
        file_id=document_file.id,
        version_id=version.id,
        unit_index=0,
        chunk_index=0,
        content="测试内容",
        token_count=2,
        content_hash="b" * 64,
        strategy="recursive",
        source_locator={"page": 1},
        parser_version="4.0.0",
        cleaning_version="clean-v1",
        embedding_model="BAAI/bge-m3",
        embedding_revision="test",
        embedding=[1.0, *([0.0] * 1023)],
    )
    monkeypatch.setattr(knowledge_service, "allowed_store_ids", AsyncMock(return_value={store.id}))
    try:
        async with sessions() as session:
            session.add_all([store, user])
            await session.flush()
            session.add(category)
            await session.flush()
            session.add(document_file)
            await session.flush()
            session.add(version)
            await session.flush()
            session.add(chunk)
            await session.commit()
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(KnowledgeFileChunk)
                    .where(KnowledgeFileChunk.version_id == version.id)
                )
                == 1
            )
            with pytest.raises(AppError) as error:
                await knowledge_service.delete_category(session, user, category.id)
            assert error.value.code == ErrorCode.RESOURCE_CONFLICT
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_all_knowledge_lists_only_classified_records_before_count_and_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """历史未分类数据保留在旧 API，但分类汇总从数据库层排除。"""
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="分类汇总测试", code=f"rag-list-{uuid.uuid4().hex}")
    user = User(
        id=uuid.uuid4(), email=f"rag-list-{uuid.uuid4().hex}@example.invalid", password_hash="test", name="测试员"
    )
    category = KnowledgeCategory(id=uuid.uuid4(), store_id=store.id, name="商品与目录", code="goods")
    files = [
        KnowledgeFile(
            id=uuid.uuid4(), store_id=store.id, category_id=category_id, original_filename=name, filename_key=name
        )
        for name, category_id in (("uncategorized.txt", None), ("categorized.txt", category.id))
    ]
    versions = [
        KnowledgeFileVersion(
            id=uuid.uuid4(),
            store_id=store.id,
            file_id=file.id,
            version_number=1,
            source_object_key=f"tests/{file.filename_key}",
            file_sha256="a" * 64,
            media_type="text/plain",
            config_json={"strategy": "recursive", "chunk_size": 500, "overlap": 50},
            status="ready",
            created_by=user.id,
        )
        for file in files
    ]
    faqs = [
        KnowledgeDocument(
            id=uuid.uuid4(),
            store_id=store.id,
            category_id=category_id,
            title=title,
            question=title,
            answer="测试正文",
            content_hash="b" * 64,
        )
        for title, category_id in (("未分类 FAQ", None), ("已分类 FAQ", category.id))
    ]
    monkeypatch.setattr(document_service, "ensure_store_access", AsyncMock())
    try:
        async with sessions() as session:
            session.add_all([store, user])
            await session.flush()
            session.add(category)
            await session.flush()
            session.add_all([*files, *faqs])
            await session.flush()
            session.add_all(versions)
            await session.commit()

            legacy_files = await document_service.list_document_files(session, user, store.id, None, None, 1, 20)
            visible_files = await document_service.list_document_files(
                session, user, store.id, None, None, 1, 1, categorized_only=True
            )
            category_files = await document_service.list_document_files(
                session, user, store.id, category.id, None, 1, 20, categorized_only=True
            )
            assert legacy_files.total == 2
            assert visible_files.total == 1 and [item.id for item in visible_files.items] == [files[1].id]
            assert category_files.total == 1

            _, legacy_faq_count = await repository.list_documents(
                session, {store.id}, store.id, None, None, None, None, 1, 20
            )
            visible_faqs, visible_faq_count = await repository.list_documents(
                session, {store.id}, store.id, None, None, None, None, 1, 1, categorized_only=True
            )
            assert legacy_faq_count == 2
            assert visible_faq_count == 1 and [item.id for item in visible_faqs] == [faqs[1].id]
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()
        await engine.dispose()
