"""G5 一次性向量化只允许原隔离店铺的唯一已审批合成 FAQ。"""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from scripts import prepare_sse_staging_content as content


def target() -> tuple[object, object]:
    store_id = uuid.uuid4()
    document_id = uuid.uuid4()
    manifest = SimpleNamespace(store_id=store_id)
    snapshot = SimpleNamespace(
        state="prepared",
        document=SimpleNamespace(
            id=document_id,
            store_id=store_id,
            source="g5-synthetic-only",
            status="published",
            vectorization_status="pending",
            document_version=1,
            deleted_at=None,
        ),
    )
    return manifest, snapshot


def test_exact_prepared_faq_is_eligible_for_one_local_vectorization() -> None:
    manifest, snapshot = target()

    assert content.assert_single_vector_target(manifest, snapshot) == (
        snapshot.document.id,
        manifest.store_id,
        1,
    )


@pytest.mark.parametrize(
    "change", ["other_store", "ready", "failed", "wrong_source", "missing"]
)
def test_vectorization_rejects_any_other_faq_or_prior_outcome(change: str) -> None:
    manifest, snapshot = target()
    if change == "other_store":
        snapshot.document.store_id = uuid.uuid4()
    elif change in {"ready", "failed"}:
        snapshot.document.vectorization_status = change
    elif change == "wrong_source":
        snapshot.document.source = "customer-faq"
    else:
        snapshot.document = None

    with pytest.raises(ValueError, match="G5 vector target"):
        content.assert_single_vector_target(manifest, snapshot)


@pytest.mark.asyncio
async def test_claim_locks_only_the_exact_store_document_and_version() -> None:
    manifest, snapshot = target()
    document = snapshot.document

    class Session:
        statement: object | None = None
        commits = 0

        async def scalars(self, statement: object) -> object:
            self.statement = statement
            return SimpleNamespace(all=lambda: [document])

        async def commit(self) -> None:
            self.commits += 1

    session = Session()
    port = content.ScopedG5VectorPort(manifest.store_id, document.id, 1)

    assert await port.claim_pending_documents(session, 1) == [document]
    assert document.vectorization_status == "processing"
    assert session.commits == 1
    sql = str(
        session.statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert str(manifest.store_id) in sql
    assert str(document.id) in sql
    assert "document_version = 1" in sql
    assert "FOR UPDATE SKIP LOCKED" in sql


@pytest.mark.asyncio
async def test_claim_refuses_any_batch_larger_than_one() -> None:
    manifest, snapshot = target()
    port = content.ScopedG5VectorPort(manifest.store_id, snapshot.document.id, 1)

    with pytest.raises(ValueError, match="G5 vector claim"):
        await port.claim_pending_documents(None, 2)


@pytest.mark.parametrize(
    "change",
    [None, "environment", "embedding", "provider", "model_url", "llm", "write"],
)
def test_one_faq_vector_mode_rejects_external_or_real_message_capabilities(
    change: str | None,
) -> None:
    settings = SimpleNamespace(
        app_env="staging",
        embedding_enabled=True,
        embedding_provider="local_bge",
        embedding_model="BAAI/bge-m3",
        embedding_dimensions=1024,
        retrieval_model_service_url="http://retrieval-model-service:8010",
        llm_enabled=False,
        real_tiktok_message_write_enabled=False,
    )
    if change == "environment":
        settings.app_env = "production"
    elif change == "embedding":
        settings.embedding_enabled = False
    elif change == "provider":
        settings.embedding_provider = "openai"
    elif change == "model_url":
        settings.retrieval_model_service_url = "https://external.example.com"
    elif change == "llm":
        settings.llm_enabled = True
    elif change == "write":
        settings.real_tiktok_message_write_enabled = True

    if change is None:
        content.assert_vector_runtime(settings)
    else:
        with pytest.raises(ValueError, match="G5 vector runtime"):
            content.assert_vector_runtime(settings)
