"""隔离 PostgreSQL 验证文件元数据操作不改写版本及向量。"""

import os
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audit.models import AuditLog
from app.knowledge_base import document_service
from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileVersion
from app.knowledge_base.models import KnowledgeCategory
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_file_category_archive_restore_delete_preserve_versions_and_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="文件管理测试", code=f"file-management-{uuid.uuid4().hex}")
    other_store = Store(id=uuid.uuid4(), name="其他店铺测试", code=f"file-other-{uuid.uuid4().hex}")
    user = User(id=uuid.uuid4(), email=f"file-{uuid.uuid4().hex}@example.invalid", password_hash="test", name="测试员")
    first = KnowledgeCategory(id=uuid.uuid4(), store_id=store.id, name="商品", code="goods")
    second = KnowledgeCategory(id=uuid.uuid4(), store_id=store.id, name="物流", code="logistics")
    foreign = KnowledgeCategory(id=uuid.uuid4(), store_id=other_store.id, name="其他", code="other")
    file = KnowledgeFile(
        id=uuid.uuid4(),
        store_id=store.id,
        category_id=first.id,
        original_filename="policy.pdf",
        filename_key="policy.pdf",
        active_version_number=1,
    )
    version = KnowledgeFileVersion(
        id=uuid.uuid4(),
        store_id=store.id,
        file_id=file.id,
        version_number=1,
        source_object_key="tests/policy.pdf",
        file_sha256="a" * 64,
        media_type="application/pdf",
        config_json={"strategy": "recursive", "chunk_size": 500, "overlap": 50},
        status="ready",
        created_by=user.id,
    )
    file_id = file.id
    store_id = store.id
    other_store_id = other_store.id
    user_id = user.id
    second_category_id = second.id
    foreign_category_id = foreign.id
    monkeypatch.setattr(document_service, "allowed_store_ids", AsyncMock(return_value={store.id}))
    monkeypatch.setattr(document_service, "ensure_store_access", AsyncMock())
    try:
        async with sessions() as session:
            session.add_all([store, other_store, user])
            await session.flush()
            session.add_all([first, second, foreign])
            await session.flush()
            session.add(file)
            await session.flush()
            session.add(version)
            await session.commit()

            with pytest.raises(AppError) as foreign_error:
                await document_service.change_document_file(
                    session, user, file_id, "category_update", "foreign-key", foreign_category_id
                )
            assert foreign_error.value.status_code == 404
            await session.rollback()
            await session.refresh(user)

            changed = await document_service.change_document_file(
                session, user, file_id, "category_update", "category-key", second_category_id
            )
            assert changed is not None and changed.category_id == second_category_id
            repeated = await document_service.change_document_file(
                session, user, file_id, "category_update", "category-key", second_category_id
            )
            assert repeated is not None and repeated.category_id == second_category_id
            archived = await document_service.change_document_file(session, user, file_id, "archive", "archive-key")
            assert archived is not None and archived.archived_at is not None
            assert (await document_service.list_document_files(session, user, store_id, None, None, 1, 20)).total == 1
            restored = await document_service.change_document_file(session, user, file_id, "restore", "restore-key")
            assert restored is not None and restored.archived_at is None
            assert await document_service.change_document_file(session, user, file_id, "delete", "delete-key") is None
            assert await document_service.change_document_file(session, user, file_id, "delete", "delete-key") is None
            assert (await document_service.list_document_files(session, user, store_id, None, None, 1, 20)).total == 0
            assert (
                await session.scalar(
                    select(func.count(KnowledgeFileVersion.id)).where(KnowledgeFileVersion.file_id == file_id)
                )
                == 1
            )
            assert await session.scalar(select(func.count(AuditLog.id)).where(AuditLog.resource_id == file_id)) == 4
    finally:
        async with sessions() as session:
            await session.execute(delete(AuditLog).where(AuditLog.resource_id == file_id))
            await session.execute(delete(KnowledgeFileVersion).where(KnowledgeFileVersion.file_id == file_id))
            await session.execute(delete(KnowledgeFile).where(KnowledgeFile.id == file_id))
            await session.execute(
                delete(KnowledgeCategory).where(KnowledgeCategory.store_id.in_([store_id, other_store_id]))
            )
            await session.execute(delete(Store).where(Store.id.in_([store_id, other_store_id])))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()
