"""真实 PostgreSQL 证明整版本向量事务、待复核与可恢复失败。"""

import asyncio
import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.knowledge_base import document_service
from app.knowledge_base.document_api_schemas import DocumentUnitReview
from app.knowledge_base.document_indexer import process_document_version
from app.knowledge_base.document_models import (
    KnowledgeFile,
    KnowledgeFileChunk,
    KnowledgeFileUnit,
    KnowledgeFileVersion,
)
from app.knowledge_base.document_parser import ParsedUnit
from app.knowledge_base.document_schemas import DocumentIndexConfig
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


class CharacterTokenizer:
    def encode(self, text: str) -> list[int]:
        return [ord(char) for char in text]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(token) for token in tokens)


def _parsed(index: int, text: str, *, ocr: bool = False) -> ParsedUnit:
    return ParsedUnit(
        index=index,
        kind="page",
        locator={"page": index + 1},
        blocks=[{"type": "text", "content": [{"type": "text", "content": text}]}],
        parse_mode="ocr" if ocr else "txt",
        ocr_derived=ocr,
        parser_version="4.0.12",
    )


class FakeParser:
    def __init__(self, units: list[ParsedUnit]) -> None:
        self.units = units
        self.calls = 0

    async def parse(self, _object_key: str, _suffix: str, _mode: str) -> list[ParsedUnit]:
        self.calls += 1
        return self.units


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    async def embed(self, texts: list[str]) -> SimpleNamespace:
        self.calls += 1
        if self.fail:
            raise ConnectionError("synthetic model outage")
        return SimpleNamespace(
            model="BAAI/bge-m3",
            revision="synthetic-revision",
            dimensions=1024,
            vectors=[[0.1] * 1024 for _ in texts],
        )


@pytest.mark.asyncio
async def test_complete_version_is_written_and_activated_atomically(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="索引店铺", code=f"index-{uuid.uuid4().hex}")
    user = User(id=uuid.uuid4(), email=f"index-{uuid.uuid4().hex}@example.invalid", password_hash="test", name="管理员")
    monkeypatch.setattr(document_service, "ensure_store_access", AsyncMock())
    monkeypatch.setattr(document_service, "put_import_file", AsyncMock())
    try:
        async with sessions() as session:
            session.add_all([store, user])
            await session.commit()
            version = await document_service.accept_document_import(
                session,
                user,
                store.id,
                None,
                "guide.pdf",
                "application/pdf",
                b"%PDF-1.7\nsynthetic",
                DocumentIndexConfig(strategy="fixed_token", chunk_size=32, overlap=4),
                None,
                "index-first",
            )
            parser = FakeParser([_parsed(0, "SKU-1 ¥20 不得退款。" * 5)])
            embedder = FakeEmbedder()
            assert await process_document_version(
                session, parser, embedder, CharacterTokenizer(), worker_id="worker-one"
            )
            await session.refresh(version)
            file = await session.get(KnowledgeFile, version.file_id)
            assert file is not None
            assert version.status == "ready"
            assert file.active_version_number == 1
            chunks = (
                await session.scalars(
                    select(KnowledgeFileChunk)
                    .where(KnowledgeFileChunk.version_id == version.id)
                    .order_by(KnowledgeFileChunk.chunk_index)
                )
            ).all()
            assert len(chunks) > 1
            assert all(chunk.store_id == store.id and len(chunk.embedding) == 1024 for chunk in chunks)
            assert all(chunk.embedding_model == "BAAI/bge-m3" for chunk in chunks)
            assert parser.calls == 1 and embedder.calls >= 1
            assert not await process_document_version(
                session, parser, embedder, CharacterTokenizer(), worker_id="worker-one"
            )
            assert await session.scalar(
                select(func.count(KnowledgeFileChunk.id)).where(KnowledgeFileChunk.version_id == version.id)
            ) == len(chunks)
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_one_unreliable_page_holds_entire_replacement_with_zero_new_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="复核店铺", code=f"review-{uuid.uuid4().hex}")
    user = User(
        id=uuid.uuid4(), email=f"review-{uuid.uuid4().hex}@example.invalid", password_hash="test", name="管理员"
    )
    monkeypatch.setattr(document_service, "ensure_store_access", AsyncMock())
    monkeypatch.setattr(document_service, "put_import_file", AsyncMock())
    try:
        async with sessions() as session:
            session.add_all([store, user])
            await session.commit()
            first = await document_service.accept_document_import(
                session,
                user,
                store.id,
                None,
                "policy.pdf",
                "application/pdf",
                b"%PDF-1.7\nold",
                DocumentIndexConfig(),
                None,
                "review-first",
            )
            embedder = FakeEmbedder()
            assert await process_document_version(
                session,
                FakeParser([_parsed(0, "旧版本政策。")]),
                embedder,
                CharacterTokenizer(),
                worker_id="worker-old",
            )
            replacement = await document_service.accept_document_import(
                session,
                user,
                store.id,
                None,
                "policy.pdf",
                "application/pdf",
                b"%PDF-1.7\nnew",
                DocumentIndexConfig(),
                first.file_id,
                "review-second",
            )
            before_calls = embedder.calls
            assert await process_document_version(
                session,
                FakeParser([_parsed(0, "新版本第 1 页。"), _parsed(1, "金额 ¥90，图片识别。", ocr=True)]),
                embedder,
                CharacterTokenizer(),
                worker_id="worker-new",
            )
            await session.refresh(replacement)
            file = await session.get(KnowledgeFile, first.file_id)
            assert file is not None
            assert replacement.status == "review_required"
            assert file.active_version_number == 1
            assert embedder.calls == before_calls
            assert (
                await session.scalar(
                    select(func.count(KnowledgeFileChunk.id)).where(KnowledgeFileChunk.version_id == replacement.id)
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count(KnowledgeFileChunk.id)).where(KnowledgeFileChunk.version_id == first.id)
                )
                > 0
            )
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_model_failure_is_retryable_without_reparse_or_duplicate_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="重试店铺", code=f"retry-{uuid.uuid4().hex}")
    user = User(id=uuid.uuid4(), email=f"retry-{uuid.uuid4().hex}@example.invalid", password_hash="test", name="管理员")
    monkeypatch.setattr(document_service, "ensure_store_access", AsyncMock())
    monkeypatch.setattr(document_service, "put_import_file", AsyncMock())
    try:
        async with sessions() as session:
            session.add_all([store, user])
            await session.commit()
            version = await document_service.accept_document_import(
                session,
                user,
                store.id,
                None,
                "retry.pdf",
                "application/pdf",
                b"%PDF-1.7\nretry",
                DocumentIndexConfig(),
                None,
                "retry-key",
            )
            parser = FakeParser([_parsed(0, "可恢复模型故障。")])
            embedder = FakeEmbedder()
            embedder.fail = True
            assert await process_document_version(
                session, parser, embedder, CharacterTokenizer(), worker_id="worker-fail"
            )
            await session.refresh(version)
            assert version.status == "failed_retryable"
            assert (
                await session.scalar(
                    select(func.count(KnowledgeFileChunk.id)).where(KnowledgeFileChunk.version_id == version.id)
                )
                == 0
            )
            embedder.fail = False
            assert await process_document_version(
                session, parser, embedder, CharacterTokenizer(), worker_id="worker-retry"
            )
            await session.refresh(version)
            assert version.status == "ready"
            assert parser.calls == 1
            assert (
                await session.scalar(
                    select(func.count(KnowledgeFileChunk.id)).where(KnowledgeFileChunk.version_id == version.id)
                )
                == 1
            )
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store.id))
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_two_workers_claim_same_version_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="并发店铺", code=f"parallel-{uuid.uuid4().hex}")
    user = User(
        id=uuid.uuid4(), email=f"parallel-{uuid.uuid4().hex}@example.invalid", password_hash="test", name="管理员"
    )
    store_id, user_id = store.id, user.id
    monkeypatch.setattr(document_service, "ensure_store_access", AsyncMock())
    monkeypatch.setattr(document_service, "put_import_file", AsyncMock())
    entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingParser(FakeParser):
        async def parse(self, _object_key: str, _suffix: str, _mode: str) -> list[ParsedUnit]:
            self.calls += 1
            entered.set()
            await release.wait()
            return self.units

    parser = BlockingParser([_parsed(0, "并发安全内容。")])
    embedder = FakeEmbedder()
    try:
        async with sessions() as setup:
            setup.add_all([store, user])
            await setup.commit()
            version = await document_service.accept_document_import(
                setup,
                user,
                store_id,
                None,
                "parallel.pdf",
                "application/pdf",
                b"%PDF-1.7\nparallel",
                DocumentIndexConfig(),
                None,
                "parallel-key",
            )
            version_id = version.id
        async with sessions() as first_session, sessions() as second_session:
            first_task = asyncio.create_task(
                process_document_version(first_session, parser, embedder, CharacterTokenizer(), worker_id="worker-a")
            )
            await asyncio.wait_for(entered.wait(), timeout=5)
            second_result = await process_document_version(
                second_session, parser, embedder, CharacterTokenizer(), worker_id="worker-b"
            )
            release.set()
            assert await asyncio.wait_for(first_task, timeout=5)
            assert not second_result
        async with sessions() as inspect:
            assert (
                await inspect.scalar(
                    select(func.count(KnowledgeFileChunk.id)).where(KnowledgeFileChunk.version_id == version_id)
                )
                == 1
            )
            assert (await inspect.get(KnowledgeFileVersion, version_id)).status == "ready"
            assert parser.calls == 1
    finally:
        release.set()
        async with sessions() as cleanup:
            await cleanup.execute(delete(Store).where(Store.id == store_id))
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_oversized_table_row_requires_review_with_source_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="表格店铺", code=f"table-{uuid.uuid4().hex}")
    user = User(id=uuid.uuid4(), email=f"table-{uuid.uuid4().hex}@example.invalid", password_hash="test", name="管理员")
    store_id, user_id = store.id, user.id
    monkeypatch.setattr(document_service, "ensure_store_access", AsyncMock())
    monkeypatch.setattr(document_service, "put_import_file", AsyncMock())
    html = "<table><tr><th>SKU</th></tr><tr><td>" + "X" * 100 + "</td></tr></table>"
    parsed = ParsedUnit(
        index=0,
        kind="page",
        locator={"page": 1},
        blocks=[{"type": "table", "content": html}],
        parse_mode="txt",
        ocr_derived=False,
        parser_version="4.0.12",
    )
    try:
        async with sessions() as session:
            session.add_all([store, user])
            await session.commit()
            version = await document_service.accept_document_import(
                session,
                user,
                store_id,
                None,
                "prices.pdf",
                "application/pdf",
                b"%PDF-1.7\nsynthetic",
                DocumentIndexConfig(strategy="table_rows", chunk_size=32),
                None,
                "table-key",
            )
            embedder = FakeEmbedder()
            assert await process_document_version(
                session, FakeParser([parsed]), embedder, CharacterTokenizer(), worker_id="worker-table"
            )
            await session.refresh(version)
            unit = await session.scalar(select(KnowledgeFileUnit).where(KnowledgeFileUnit.version_id == version.id))
            assert unit is not None
            assert version.status == "review_required"
            assert unit.needs_review
            assert "ROW_TOO_LARGE_REVIEW_REQUIRED" in unit.issue_codes
            assert embedder.calls == 0
            assert (
                await session.scalar(
                    select(func.count(KnowledgeFileChunk.id)).where(KnowledgeFileChunk.version_id == version.id)
                )
                == 0
            )
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_manual_review_requeues_whole_version_and_preserves_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store = Store(id=uuid.uuid4(), name="人工复核店铺", code=f"manual-{uuid.uuid4().hex}")
    user = User(
        id=uuid.uuid4(), email=f"manual-{uuid.uuid4().hex}@example.invalid", password_hash="test", name="管理员"
    )
    store_id, user_id = store.id, user.id
    monkeypatch.setattr(document_service, "ensure_store_access", AsyncMock())
    monkeypatch.setattr(document_service, "allowed_store_ids", AsyncMock(return_value={store_id}))
    monkeypatch.setattr(document_service, "put_import_file", AsyncMock())
    try:
        async with sessions() as session:
            session.add_all([store, user])
            await session.commit()
            version = await document_service.accept_document_import(
                session,
                user,
                store_id,
                None,
                "ocr.pdf",
                "application/pdf",
                b"%PDF-1.7\nreview",
                DocumentIndexConfig(),
                None,
                "manual-upload",
            )
            parser = FakeParser([_parsed(0, "SKU A1 ¥20 不退款。"), _parsed(1, "金额 ¥90。", ocr=True)])
            embedder = FakeEmbedder()
            assert await process_document_version(
                session, parser, embedder, CharacterTokenizer(), worker_id="worker-review"
            )
            await session.refresh(version)
            assert version.status == "review_required"
            assert embedder.calls == 0
            detail = await document_service.get_document_version(session, user, version.file_id, 1)
            assert len(detail.units) == 2 and detail.units[1].needs_review
            payload = DocumentUnitReview(corrected_text="金额 ¥90，不退款。", confirmed=True)
            reviewed = await document_service.review_document_unit(
                session, user, version.file_id, 1, 1, payload, "manual-review-one"
            )
            assert reviewed.status == "queued"
            assert all(not unit.needs_review for unit in reviewed.units)
            assert await process_document_version(
                session, parser, embedder, CharacterTokenizer(), worker_id="worker-after-review"
            )
            assert parser.calls == 1
            replay = await document_service.review_document_unit(
                session, user, version.file_id, 1, 1, payload, "manual-review-one"
            )
            assert replay.status == "ready" and replay.chunk_count >= 2
            with pytest.raises(AppError):
                await document_service.review_document_unit(
                    session,
                    user,
                    version.file_id,
                    1,
                    1,
                    DocumentUnitReview(corrected_text="不同内容", confirmed=True),
                    "manual-review-one",
                )
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_file_queries_hide_other_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    own = Store(id=uuid.uuid4(), name="可见店铺", code=f"own-{uuid.uuid4().hex}")
    other = Store(id=uuid.uuid4(), name="其他店铺", code=f"other-{uuid.uuid4().hex}")
    user = User(id=uuid.uuid4(), email=f"scope-{uuid.uuid4().hex}@example.invalid", password_hash="test", name="管理员")
    monkeypatch.setattr(document_service, "ensure_store_access", AsyncMock())
    monkeypatch.setattr(document_service, "put_import_file", AsyncMock())
    try:
        async with sessions() as session:
            session.add_all([own, other, user])
            await session.commit()
            own_version = await document_service.accept_document_import(
                session, user, own.id, None, "same.txt", "text/plain", b"own", DocumentIndexConfig(), None, "own-key-1"
            )
            other_version = await document_service.accept_document_import(
                session,
                user,
                other.id,
                None,
                "same.txt",
                "text/plain",
                b"other",
                DocumentIndexConfig(),
                None,
                "other-key-1",
            )
            monkeypatch.setattr(document_service, "allowed_store_ids", AsyncMock(return_value={own.id}))
            page = await document_service.list_document_files(session, user, own.id, None, None, 1, 20)
            assert page.total == 1 and page.items[0].id == own_version.file_id
            with pytest.raises(AppError) as hidden:
                await document_service.get_document_version(session, user, other_version.file_id, 1)
            assert hidden.value.status_code == 404
            with pytest.raises(AppError) as hidden_source:
                await document_service.get_document_source(session, user, other_version.file_id, 1)
            assert hidden_source.value.status_code == 404
            monkeypatch.setattr(document_service, "get_import_file", lambda _key, *, max_bytes: b"own")
            content, media_type, filename = await document_service.get_document_source(
                session, user, own_version.file_id, 1
            )
            assert (content, media_type, filename) == (b"own", "text/plain", "same.txt")
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id.in_([own.id, other.id])))
            await session.execute(delete(User).where(User.id == user.id))
            await session.commit()
        await engine.dispose()
