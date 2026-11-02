"""文件对外回复授权必须显式确认，不能从内部建议审批推导。"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.knowledge_base import document_service
from app.knowledge_base.document_api_schemas import DocumentVersionApproval
from app.shared.exceptions.errors import AppError


def approval_context(monkeypatch: pytest.MonkeyPatch):
    store_id, file_id, version_id, actor_id = (uuid.uuid4() for _ in range(4))
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
    session = SimpleNamespace(scalar=AsyncMock(return_value=None), add=Mock(), commit=AsyncMock(), rollback=AsyncMock())
    return session, file, version, SimpleNamespace(id=actor_id)


@pytest.mark.asyncio
async def test_explicit_customer_purpose_records_public_approval_and_audit(monkeypatch: pytest.MonkeyPatch):
    session, file, version, actor = approval_context(monkeypatch)
    payload = DocumentVersionApproval(statement_type="policy", customer_scope="generic", purpose="public_reply")
    await document_service.approve_document_version(session, actor, file.id, 1, payload, "customer-approve")
    assert version.publication_approval == "approved_for_public_reply"
    assert version.approved_by == actor.id and version.approved_at
    assert session.add.call_args.args[0].after_data["purpose"] == "public_reply"


@pytest.mark.asyncio
async def test_customer_purpose_cannot_reuse_internal_approval_idempotency_key(monkeypatch: pytest.MonkeyPatch):
    session, file, version, actor = approval_context(monkeypatch)
    session.scalar.return_value = SimpleNamespace(
        after_data={
            "statement_type": "policy",
            "customer_scope": "generic",
            "publication_approval": "approved_for_internal_review",
        },
    )
    payload = DocumentVersionApproval(statement_type="policy", customer_scope="generic", purpose="public_reply")
    with pytest.raises(AppError) as error:
        await document_service.approve_document_version(session, actor, file.id, 1, payload, "used-key")
    assert error.value.status_code == 409
    session.commit.assert_not_awaited()
    assert version.publication_approval == "draft"


@pytest.mark.asyncio
async def test_customer_purpose_rejects_technical_internal_material(monkeypatch: pytest.MonkeyPatch):
    session, file, _, actor = approval_context(monkeypatch)
    payload = DocumentVersionApproval(
        statement_type="technical_artifact", customer_scope="none", purpose="public_reply"
    )
    with pytest.raises(AppError) as error:
        await document_service.approve_document_version(session, actor, file.id, 1, payload, "technical-key")
    assert error.value.status_code == 422
    session.commit.assert_not_awaited()
