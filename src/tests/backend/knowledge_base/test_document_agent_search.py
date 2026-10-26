"""文件 RAG 的租户、版本与审批门禁。"""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.knowledge_base.document_search import hybrid_search_files


@pytest.mark.asyncio
async def test_file_search_never_queries_without_binding() -> None:
    session = SimpleNamespace(execute=AsyncMock())
    hits = await hybrid_search_files(
        session,
        uuid.uuid4(),
        (),
        "退款",
        [0.1] * 1024,
        dense_top_k=5,
        lexical_top_k=5,
        candidate_top_k=5,
        rrf_k=60,
    )
    assert hits == []
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_both_file_search_routes_repeat_tenant_version_and_approval_gates() -> None:
    store_id, file_id = uuid.uuid4(), uuid.uuid4()
    result = SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: []))
    session = SimpleNamespace(execute=AsyncMock(return_value=result))
    hits = await hybrid_search_files(
        session,
        store_id,
        (file_id,),
        "退款政策",
        [0.1] * 1024,
        dense_top_k=5,
        lexical_top_k=5,
        candidate_top_k=5,
        rrf_k=60,
    )
    assert hits == []
    assert session.execute.await_count == 2
    for call in session.execute.await_args_list:
        statement = call.args[0]
        compiled = statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        assert "knowledge_file_chunks.store_id =" in sql
        assert "knowledge_files.store_id =" in sql
        assert "knowledge_file_versions.store_id =" in sql
        assert "knowledge_files.id IN" in sql
        assert "knowledge_file_versions.file_id = knowledge_files.id" in sql
        assert "knowledge_files.deleted_at IS NULL" in sql
        assert "knowledge_files.archived_at IS NULL" in sql
        assert "knowledge_files.active_version_number = knowledge_file_versions.version_number" in sql
        assert "knowledge_file_versions.status =" in sql
        assert "knowledge_file_versions.publication_approval =" in sql
        values = list(compiled.params.values())
        assert store_id in values
        assert [file_id] in values


@pytest.mark.asyncio
async def test_approved_file_hit_carries_real_version_approval_metadata() -> None:
    store_id, file_id, chunk_id, reviewer_id = (uuid.uuid4() for _ in range(4))
    row = {
        "chunk_id": chunk_id,
        "content": "退货政策以订单实际状态为准。",
        "token_count": 20,
        "chunk_index": 0,
        "file_id": file_id,
        "category_id": None,
        "original_filename": "售后政策.pdf",
        "version_number": 2,
        "statement_type": "policy",
        "customer_scope": "generic",
        "publication_approval": "approved_for_internal_review",
        "approved_by": reviewer_id,
        "approved_at": datetime.now(UTC),
        "dense_score": 0.91,
        "lexical_score": 0.55,
    }
    dense = SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: [row]))
    empty = SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: []))
    session = SimpleNamespace(execute=AsyncMock(side_effect=[dense, empty]))
    hits = await hybrid_search_files(
        session,
        store_id,
        (file_id,),
        "退货政策",
        [0.1] * 1024,
        dense_top_k=5,
        lexical_top_k=5,
        candidate_top_k=5,
        rrf_k=60,
    )
    assert len(hits) == 1
    hit = hits[0]
    assert hit.source_type == "file"
    assert hit.document_id == file_id
    assert hit.source_label == "售后政策.pdf"
    assert hit.safety_metadata.approved_by == reviewer_id
    assert hit.safety_metadata.document_version == 2
