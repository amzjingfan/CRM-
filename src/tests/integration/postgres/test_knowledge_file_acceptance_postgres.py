"""通用文件受理的同店替换、幂等和配置快照。"""

import os
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.knowledge_base import document_service
from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileVersion
from app.knowledge_base.document_schemas import DocumentIndexConfig
from app.knowledge_base.models import KnowledgeCategory
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_same_name_requires_explicit_replacement_and_keeps_old_active(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="文档受理店铺", code=f"rag-accept-{uuid.uuid4().hex}")
    other = Store(id=uuid.uuid4(), name="其他店铺", code=f"rag-other-{uuid.uuid4().hex}")
    user = User(
        id=uuid.uuid4(), email=f"rag-accept-{uuid.uuid4().hex}@example.invalid", password_hash="test", name="管理员"
    )
    store_ids = [store.id, other.id]
    user_id = user.id
    category = KnowledgeCategory(id=uuid.uuid4(), store_id=store.id, name="资料", code="docs")
    other_category = KnowledgeCategory(id=uuid.uuid4(), store_id=store.id, name="其他资料", code="other-docs")
    storage = AsyncMock()
    monkeypatch.setattr(document_service, "put_import_file", storage)
    monkeypatch.setattr(document_service, "ensure_store_access", AsyncMock())
    first_bytes = b"%PDF-1.7\nfirst"
    changed_bytes = b"%PDF-1.7\nchanged"
    try:
        async with sessions() as session:
            session.add_all([store, other, user])
            await session.flush()
            session.add_all([category, other_category])
            await session.commit()

            first = await document_service.accept_document_import(
                session,
                user,
                store.id,
                category.id,
                "Guide.PDF",
                "application/pdf",
                first_bytes,
                DocumentIndexConfig(chunk_size=320, overlap=24),
                None,
                "key-first",
            )
            assert first.version_number == 1
            assert first.config_json["chunk_size"] == 320
            same = await document_service.accept_document_import(
                session,
                user,
                store.id,
                category.id,
                "guide.pdf",
                "application/pdf",
                first_bytes,
                DocumentIndexConfig(chunk_size=320, overlap=24),
                None,
                "key-repeat",
            )
            assert same.id == first.id
            assert storage.await_count == 1
            with pytest.raises(AppError) as category_mismatch:
                await document_service.accept_document_import(
                    session,
                    user,
                    store.id,
                    other_category.id,
                    "guide.pdf",
                    "application/pdf",
                    first_bytes,
                    DocumentIndexConfig(chunk_size=320, overlap=24),
                    None,
                    "key-category",
                )
            assert category_mismatch.value.code == ErrorCode.VALIDATION_ERROR
            with pytest.raises(AppError) as duplicate_key_reuse:
                await document_service.accept_document_import(
                    session,
                    user,
                    store.id,
                    category.id,
                    "guide.pdf",
                    "application/pdf",
                    changed_bytes,
                    DocumentIndexConfig(),
                    first.file_id,
                    "key-repeat",
                )
            assert duplicate_key_reuse.value.code == ErrorCode.RESOURCE_CONFLICT

            with pytest.raises(AppError) as conflict:
                await document_service.accept_document_import(
                    session,
                    user,
                    store.id,
                    category.id,
                    "guide.pdf",
                    "application/pdf",
                    changed_bytes,
                    DocumentIndexConfig(),
                    None,
                    "key-second",
                )
            assert conflict.value.code == ErrorCode.RESOURCE_CONFLICT
            with pytest.raises(AppError) as reused_key:
                await document_service.accept_document_import(
                    session,
                    user,
                    store.id,
                    category.id,
                    "guide.pdf",
                    "application/pdf",
                    changed_bytes,
                    DocumentIndexConfig(),
                    first.file_id,
                    "key-first",
                )
            assert reused_key.value.code == ErrorCode.RESOURCE_CONFLICT

            document_file = await session.get(KnowledgeFile, first.file_id)
            assert document_file is not None
            document_file.active_version_number = 1
            await session.commit()
            second = await document_service.accept_document_import(
                session,
                user,
                store.id,
                category.id,
                "guide.pdf",
                "application/pdf",
                changed_bytes,
                DocumentIndexConfig(),
                first.file_id,
                "key-replace",
            )
            assert second.version_number == 2
            assert (await session.get(KnowledgeFile, first.file_id)).active_version_number == 1
            assert (
                len(
                    (
                        await session.scalars(
                            select(KnowledgeFileVersion).where(KnowledgeFileVersion.file_id == first.file_id)
                        )
                    ).all()
                )
                == 2
            )

            with pytest.raises(AppError) as cross_store:
                await document_service.accept_document_import(
                    session,
                    user,
                    other.id,
                    None,
                    "guide.pdf",
                    "application/pdf",
                    changed_bytes,
                    DocumentIndexConfig(),
                    first.file_id,
                    "key-cross",
                )
            assert cross_store.value.code == ErrorCode.RESOURCE_NOT_FOUND
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id.in_(store_ids)))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_saved_store_defaults_do_not_change_existing_version_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="配置店铺", code=f"rag-settings-{uuid.uuid4().hex}")
    user = User(
        id=uuid.uuid4(), email=f"rag-settings-{uuid.uuid4().hex}@example.invalid", password_hash="test", name="管理员"
    )
    store_id, user_id = store.id, user.id
    monkeypatch.setattr(document_service, "put_import_file", AsyncMock())
    monkeypatch.setattr(document_service, "ensure_store_access", AsyncMock())
    try:
        async with sessions() as session:
            session.add_all([store, user])
            await session.commit()
            before = await document_service.get_document_settings(session, user, store_id)
            assert (before.chunk_size, before.overlap) == (500, 50)
            version = await document_service.accept_document_import(
                session,
                user,
                store_id,
                None,
                "before.pdf",
                "application/pdf",
                b"%PDF-1.7\ntext",
                before,
                None,
                "settings-before",
            )
            await document_service.save_document_settings(
                session,
                user,
                store_id,
                DocumentIndexConfig(strategy="fixed_char", chunk_size=700, overlap=70),
                idempotency_key="settings-update-1",
            )
            after = await document_service.get_document_settings(session, user, store_id)
            assert (after.strategy, after.chunk_size, after.overlap) == ("fixed_char", 700, 70)
            repeated = await document_service.save_document_settings(
                session, user, store_id, after, idempotency_key="settings-update-1"
            )
            assert repeated == after
            with pytest.raises(AppError) as reused:
                await document_service.save_document_settings(
                    session, user, store_id, DocumentIndexConfig(), idempotency_key="settings-update-1"
                )
            assert reused.value.status_code == 409
            await session.refresh(version)
            assert version.config_json["strategy"] == "recursive"
            assert version.config_json["chunk_size"] == 500
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()
