"""文件列表批量查询与店铺隔离的生命周期操作。"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.audit.models import AuditLog
from app.knowledge_base import document_indexer, document_service
from app.knowledge_base.document_api_schemas import DocumentUnitReview, DocumentVersionApproval
from app.shared.exceptions.errors import AppError


@pytest.mark.asyncio
async def test_document_approval_requires_active_ready_version(monkeypatch: pytest.MonkeyPatch) -> None:
    store_id, file_id, version_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    file = SimpleNamespace(
        id=file_id,
        store_id=store_id,
        deleted_at=None,
        archived_at=None,
        active_version_number=1,
    )
    version = SimpleNamespace(id=version_id, version_number=2, status="ready", publication_approval="draft")
    monkeypatch.setattr(document_service, "_scoped_version", AsyncMock(return_value=(file, version)))
    session = SimpleNamespace(add=Mock(), commit=AsyncMock())
    payload = DocumentVersionApproval(statement_type="policy", customer_scope="generic")
    with pytest.raises(AppError) as error:
        await document_service.approve_document_version(
            session,
            SimpleNamespace(id=uuid.uuid4()),
            file_id,
            2,
            payload,
            "key",
        )
    assert error.value.status_code == 409
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_document_approval_records_user_version_and_semantics(monkeypatch: pytest.MonkeyPatch) -> None:
    store_id, file_id, version_id, user_id = (uuid.uuid4() for _ in range(4))
    file = SimpleNamespace(
        id=file_id,
        store_id=store_id,
        deleted_at=None,
        archived_at=None,
        active_version_number=1,
    )
    version = SimpleNamespace(id=version_id, version_number=1, status="ready", publication_approval="draft")
    monkeypatch.setattr(document_service, "_scoped_version", AsyncMock(return_value=(file, version)))
    monkeypatch.setattr(document_service, "get_document_version", AsyncMock(return_value="approved"))
    session = SimpleNamespace(scalar=AsyncMock(return_value=None), add=Mock(), commit=AsyncMock())
    payload = DocumentVersionApproval(statement_type="policy", customer_scope="generic")
    result = await document_service.approve_document_version(
        session,
        SimpleNamespace(id=user_id),
        file_id,
        1,
        payload,
        "approve-key",
    )
    assert result == "approved"
    assert version.publication_approval == "approved_for_internal_review"
    assert version.approved_by == user_id and version.approved_at is not None
    audit = session.add.call_args.args[0]
    assert audit.action == "knowledge.file_version_approve"
    assert audit.resource_id == version_id and audit.actor_id == user_id
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_revocation_clears_approval_and_audits(monkeypatch: pytest.MonkeyPatch) -> None:
    store_id, file_id, version_id, user_id = (uuid.uuid4() for _ in range(4))
    file = SimpleNamespace(id=file_id, store_id=store_id)
    version = SimpleNamespace(
        id=version_id,
        publication_approval="approved_for_internal_review",
        approved_by=user_id,
        approved_at=datetime.now(UTC),
    )
    monkeypatch.setattr(document_service, "_scoped_version", AsyncMock(return_value=(file, version)))
    monkeypatch.setattr(document_service, "get_document_version", AsyncMock(return_value="revoked"))
    session = SimpleNamespace(scalar=AsyncMock(return_value=None), add=Mock(), commit=AsyncMock())
    result = await document_service.revoke_document_version(
        session,
        SimpleNamespace(id=user_id),
        file_id,
        1,
        "revoke-key",
    )
    assert result == "revoked"
    assert version.publication_approval == "draft"
    assert version.approved_by is None and version.approved_at is None
    assert session.add.call_args.args[0].action == "knowledge.file_version_revoke"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_document_file_page_batches_latest_versions_and_chunk_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    store_id = uuid.uuid4()
    file_a, file_b = uuid.uuid4(), uuid.uuid4()
    version_a, version_b = uuid.uuid4(), uuid.uuid4()
    files = [
        SimpleNamespace(
            id=file_a,
            store_id=store_id,
            category_id=None,
            original_filename="a.pdf",
            active_version_number=1,
            archived_at=None,
        ),
        SimpleNamespace(
            id=file_b,
            store_id=store_id,
            category_id=None,
            original_filename="b.pdf",
            active_version_number=2,
            archived_at=None,
        ),
    ]
    now = datetime.now(UTC)
    versions = [
        SimpleNamespace(
            id=version_a,
            file_id=file_a,
            version_number=1,
            status="ready",
            error_code=None,
            retry_count=0,
            created_at=now,
            completed_at=now,
        ),
        SimpleNamespace(
            id=version_b,
            file_id=file_b,
            version_number=2,
            status="ready",
            error_code=None,
            retry_count=0,
            created_at=now,
            completed_at=now,
        ),
    ]
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=2),
        scalars=AsyncMock(side_effect=[SimpleNamespace(all=lambda: files), SimpleNamespace(all=lambda: versions)]),
        execute=AsyncMock(return_value=[(version_a, 3), (version_b, 5)]),
    )
    monkeypatch.setattr(document_service, "ensure_store_access", AsyncMock())
    result = await document_service.list_document_files(session, SimpleNamespace(), store_id, None, None, 1, 20)
    assert result.total == 2
    assert [item.latest_version.chunk_count for item in result.items] == [3, 5]
    assert session.scalar.await_count == 1
    assert session.scalars.await_count == 2
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_file_category_change_is_scoped_and_audited(monkeypatch: pytest.MonkeyPatch) -> None:
    store_id, file_id, category_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    file = SimpleNamespace(id=file_id, store_id=store_id, category_id=None, archived_at=None, deleted_at=None)
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[file, None, category_id]),
        add=Mock(),
        commit=AsyncMock(),
    )
    monkeypatch.setattr(document_service, "allowed_store_ids", AsyncMock(return_value={store_id}))
    monkeypatch.setattr(document_service, "get_document_file", AsyncMock(return_value="updated"))
    result = await document_service.change_document_file(
        session, user, file_id, "category_update", "category-key", category_id
    )
    assert result == "updated"
    assert file.category_id == category_id
    audit = session.add.call_args.args[0]
    assert isinstance(audit, AuditLog)
    assert audit.store_id == store_id and audit.action == "knowledge.file_category_update"
    assert audit.after_data == {"category_id": str(category_id)}
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_file_action_fails_closed_outside_authorized_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(scalar=AsyncMock(return_value=None), commit=AsyncMock())
    monkeypatch.setattr(document_service, "allowed_store_ids", AsyncMock(return_value=set()))
    with pytest.raises(AppError) as error:
        await document_service.change_document_file(
            session, SimpleNamespace(id=uuid.uuid4()), uuid.uuid4(), "delete", "delete-key"
        )
    assert error.value.status_code == 404
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_file_archive_rejects_processing_version(monkeypatch: pytest.MonkeyPatch) -> None:
    store_id, file_id = uuid.uuid4(), uuid.uuid4()
    file = SimpleNamespace(id=file_id, store_id=store_id, category_id=None, archived_at=None, deleted_at=None)
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[file, None, uuid.uuid4()]), commit=AsyncMock())
    monkeypatch.setattr(document_service, "allowed_store_ids", AsyncMock(return_value={store_id}))
    with pytest.raises(AppError) as error:
        await document_service.change_document_file(
            session, SimpleNamespace(id=uuid.uuid4()), file_id, "archive", "archive-key"
        )
    assert error.value.status_code == 409
    assert file.archived_at is None
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_file_archive_and_delete_are_soft_and_audited(monkeypatch: pytest.MonkeyPatch) -> None:
    store_id, file_id = uuid.uuid4(), uuid.uuid4()
    user = SimpleNamespace(id=uuid.uuid4())
    file = SimpleNamespace(id=file_id, store_id=store_id, category_id=None, archived_at=None, deleted_at=None)
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[file, None, None, file, None, None]),
        add=Mock(),
        commit=AsyncMock(),
    )
    monkeypatch.setattr(document_service, "allowed_store_ids", AsyncMock(return_value={store_id}))
    monkeypatch.setattr(document_service, "get_document_file", AsyncMock(return_value="archived"))
    assert await document_service.change_document_file(session, user, file_id, "archive", "archive-key") == "archived"
    assert file.archived_at is not None and file.deleted_at is None
    assert await document_service.change_document_file(session, user, file_id, "delete", "delete-key") is None
    assert file.deleted_at is not None
    assert [call.args[0].action for call in session.add.call_args_list] == [
        "knowledge.file_archive",
        "knowledge.file_delete",
    ]
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_document_worker_skips_inactive_files(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(scalar=AsyncMock(return_value=None), commit=AsyncMock())
    assert await document_indexer._claim(session, "test-worker") is None
    query = str(session.scalar.await_args.args[0])
    assert "knowledge_files.archived_at IS NULL" in query
    assert "knowledge_files.deleted_at IS NULL" in query
    version = SimpleNamespace(file_id=uuid.uuid4(), store_id=uuid.uuid4(), id=uuid.uuid4())
    file = SimpleNamespace(
        id=version.file_id, store_id=version.store_id, archived_at=datetime.now(UTC), deleted_at=None
    )
    monkeypatch.setattr(document_indexer, "_owned_version", AsyncMock(return_value=version))
    session.scalar.return_value = file
    with pytest.raises(document_indexer.DocumentIndexError, match="FILE_INACTIVE"):
        await document_indexer._commit_ready(session, version.id, "test-worker", [], [], "test")


@pytest.mark.asyncio
async def test_archived_file_cannot_queue_review_or_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    file = SimpleNamespace(archived_at=datetime.now(UTC))
    version = SimpleNamespace()
    monkeypatch.setattr(document_service, "_scoped_version", AsyncMock(return_value=(file, version)))
    session = SimpleNamespace(scalar=AsyncMock(), commit=AsyncMock())
    user = SimpleNamespace(id=uuid.uuid4())
    file_id = uuid.uuid4()
    with pytest.raises(AppError) as review_error:
        await document_service.review_document_unit(
            session,
            user,
            file_id,
            1,
            0,
            DocumentUnitReview(corrected_text="可信内容", confirmed=True),
            "review-key",
        )
    assert review_error.value.status_code == 409
    with pytest.raises(AppError) as retry_error:
        await document_service.retry_document_version(session, user, file_id, 1, "retry-key")
    assert retry_error.value.status_code == 409
    session.commit.assert_not_awaited()
