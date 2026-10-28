"""新版 Agent 只检索绑定、冻结且当前审批有效的文件。"""

import time
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_empty_binding_never_calls_legacy_faq_search() -> None:
    from app.agents.rag.retriever import retrieve_bound_files

    store_id = uuid.uuid4()
    agent = SimpleNamespace(store_id=store_id, file_ids=())
    snapshot = SimpleNamespace(store_id=store_id, file_versions=())
    rag = SimpleNamespace(retrieve=AsyncMock())
    result = await retrieve_bound_files(
        session=AsyncMock(),
        snapshot=snapshot,
        agent=agent,
        query="退货政策",
        deadline=time.monotonic() + 10,
        rag_service=rag,
    )
    assert result.hits == ()
    rag.retrieve.assert_not_awaited()


@pytest.mark.asyncio
async def test_bound_search_passes_only_approved_snapshot_files_and_rejects_new_version() -> None:
    from app.agents.rag.retriever import retrieve_bound_files
    from app.agents.runtime.snapshot import FileVersionRef

    store_id = uuid.uuid4()
    approved_file = uuid.uuid4()
    unapproved_file = uuid.uuid4()
    snapshot = SimpleNamespace(
        store_id=store_id,
        file_versions=(FileVersionRef(file_id=approved_file, version_id=uuid.uuid4(), version_number=2),),
    )
    agent = SimpleNamespace(store_id=store_id, file_ids=(str(approved_file), str(unapproved_file)))
    hit_v2 = SimpleNamespace(
        document_id=approved_file,
        document_version=2,
        safety_metadata=SimpleNamespace(store_id=store_id),
    )
    hit_v3 = SimpleNamespace(
        document_id=approved_file,
        document_version=3,
        safety_metadata=SimpleNamespace(store_id=store_id),
    )
    rag = SimpleNamespace(retrieve=AsyncMock(return_value=SimpleNamespace(hits=[hit_v2, hit_v3])))
    result = await retrieve_bound_files(
        session=AsyncMock(),
        snapshot=snapshot,
        agent=agent,
        query="物流",
        deadline=time.monotonic() + 10,
        rag_service=rag,
    )
    assert result.hits == (hit_v2,)
    assert result.excluded_file_count == 1
    assert rag.retrieve.await_args.kwargs["file_ids"] == (approved_file,)


@pytest.mark.asyncio
async def test_approval_revocation_before_display_removes_frozen_hit() -> None:
    from app.agents.rag.retriever import EvidenceBundle, revalidate_evidence
    from app.agents.runtime.snapshot import FileVersionRef

    store_id = uuid.uuid4()
    file_id = uuid.uuid4()
    version = FileVersionRef(file_id=file_id, version_id=uuid.uuid4(), version_number=1)
    snapshot = SimpleNamespace(store_id=store_id, file_versions=(version,))
    agent = SimpleNamespace(store_id=store_id, file_ids=(str(file_id),))
    hit = SimpleNamespace(document_id=file_id, document_version=1)
    session = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))
    result = await revalidate_evidence(
        session=session,
        snapshot=snapshot,
        agent=agent,
        bundle=EvidenceBundle(hits=(hit,), excluded_file_count=0),
    )
    assert result.hits == ()


def test_model_projection_labels_chunks_and_drops_address_content() -> None:
    from app.agents.rag.retriever import EvidenceBundle, project_evidence_for_model

    safe = SimpleNamespace(chunk_id=uuid.uuid4(), document_version=2, content="退货需平台审核")
    sensitive = SimpleNamespace(
        chunk_id=uuid.uuid4(),
        document_version=2,
        content="Ship to 123 Main Street, New York, NY 10001",
    )
    projection = project_evidence_for_model(EvidenceBundle(hits=(safe, sensitive), excluded_file_count=0))
    assert len(projection["hits"]) == 1
    assert projection["hits"][0]["chunk_id"] == str(safe.chunk_id)
    assert "Main Street" not in str(projection)
