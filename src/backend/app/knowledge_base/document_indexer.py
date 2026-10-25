"""通用文件版本的租约认领、整版复核和原子向量切换。"""

import hashlib
import math
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Protocol

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_base.document_chunking import (
    DocumentChunkDraft,
    DocumentChunkError,
    DocumentTokenizer,
    _sentences,
    chunk_document,
)
from app.knowledge_base.document_cleaning import CleanedUnit, clean_document, version_requires_review
from app.knowledge_base.document_models import (
    KnowledgeFile,
    KnowledgeFileChunk,
    KnowledgeFileUnit,
    KnowledgeFileVersion,
)
from app.knowledge_base.document_parser import DocumentParseError, ParsedUnit
from app.knowledge_base.document_schemas import DocumentIndexConfig
from app.shared.config.settings import get_settings

LEASE_DURATION = timedelta(minutes=30)
MAX_RETRIES = 3
EMBEDDING_DIMENSIONS = 1024


class DocumentParserPort(Protocol):
    async def parse(self, object_key: str, suffix: str, mode: str) -> list[ParsedUnit]: ...


class EmbeddingResponse(Protocol):
    model: str
    revision: str
    dimensions: int
    vectors: list[list[float]]


class DocumentEmbedderPort(Protocol):
    async def embed(self, texts: list[str]) -> EmbeddingResponse: ...


class DocumentIndexError(ValueError):
    def __init__(self, code: str, *, retriable: bool) -> None:
        self.code = code
        self.retriable = retriable
        super().__init__(code)


async def _claim(session: AsyncSession, worker_id: str) -> KnowledgeFileVersion | None:
    now = datetime.now(UTC)
    lease_due = or_(KnowledgeFileVersion.lease_until.is_(None), KnowledgeFileVersion.lease_until <= now)
    version = await session.scalar(
        select(KnowledgeFileVersion)
        .join(KnowledgeFile, KnowledgeFile.id == KnowledgeFileVersion.file_id)
        .where(
            KnowledgeFile.deleted_at.is_(None),
            KnowledgeFile.archived_at.is_(None),
            or_(
                and_(KnowledgeFileVersion.status.in_(["queued", "failed_retryable"]), lease_due),
                and_(KnowledgeFileVersion.status.in_(["parsing", "indexing"]), KnowledgeFileVersion.lease_until < now),
            ),
        )
        .order_by(KnowledgeFileVersion.created_at, KnowledgeFileVersion.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if version is None:
        await session.commit()
        return None
    version.status = "parsing"
    version.lease_owner = worker_id
    version.lease_until = now + LEASE_DURATION
    version.error_code = None
    await session.commit()
    return version


async def _owned_version(session: AsyncSession, version_id: uuid.UUID, worker_id: str) -> KnowledgeFileVersion | None:
    version = await session.scalar(
        select(KnowledgeFileVersion)
        .where(KnowledgeFileVersion.id == version_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return version if version is not None and version.lease_owner == worker_id else None


async def _renew_lease(session: AsyncSession, version_id: uuid.UUID, worker_id: str) -> None:
    version = await _owned_version(session, version_id, worker_id)
    if version is None or version.status != "indexing":
        await session.rollback()
        raise DocumentIndexError("DOCUMENT_LEASE_LOST", retriable=True)
    version.lease_until = datetime.now(UTC) + LEASE_DURATION
    await session.commit()


def _stored_unit(row: KnowledgeFileUnit, parser_version: str) -> CleanedUnit:
    if any(not isinstance(value, int) or isinstance(value, bool) for value in row.source_locator.values()):
        raise DocumentIndexError("SOURCE_LOCATOR_INVALID", retriable=False)
    return CleanedUnit(
        index=row.unit_index,
        kind=row.unit_kind,
        locator={key: value for key, value in row.source_locator.items() if isinstance(value, int)},
        raw_text=row.raw_text,
        cleaned_text=row.cleaned_text,
        blocks=row.blocks_json,
        issue_codes=row.issue_codes,
        needs_review=row.needs_review,
        parse_mode=row.parse_mode,
        ocr_derived=row.parse_mode not in {"txt", "native_text"},
        parser_version=parser_version,
    )


async def _save_units(session: AsyncSession, version_id: uuid.UUID, worker_id: str, cleaned: list[CleanedUnit]) -> bool:
    version = await _owned_version(session, version_id, worker_id)
    if version is None:
        await session.rollback()
        return False
    if len({unit.parser_version for unit in cleaned}) != 1:
        raise DocumentIndexError("PARSER_VERSION_MISMATCH", retriable=False)
    version.parser_version = cleaned[0].parser_version
    for unit in cleaned:
        session.add(
            KnowledgeFileUnit(
                store_id=version.store_id,
                version_id=version.id,
                unit_index=unit.index,
                unit_kind=unit.kind,
                source_locator=unit.locator,
                blocks_json=unit.blocks,
                raw_text=unit.raw_text,
                cleaned_text=unit.cleaned_text,
                issue_codes=unit.issue_codes,
                parse_mode=unit.parse_mode,
                needs_review=unit.needs_review,
            )
        )
    if version_requires_review(cleaned):
        version.status = "review_required"
        version.lease_owner = None
        version.lease_until = None
        version.completed_at = datetime.now(UTC)
    else:
        version.status = "indexing"
        version.lease_until = datetime.now(UTC) + LEASE_DURATION
    await session.commit()
    return True


async def _mark_error(
    session: AsyncSession, version_id: uuid.UUID, worker_id: str, code: str, *, retriable: bool
) -> None:
    await session.rollback()
    version = await _owned_version(session, version_id, worker_id)
    if version is None:
        await session.rollback()
        return
    version.retry_count += 1
    version.status = "failed_retryable" if retriable and version.retry_count < MAX_RETRIES else "failed_final"
    version.error_code = code[:100]
    version.lease_owner = None
    version.lease_until = None
    if version.status == "failed_final":
        version.completed_at = datetime.now(UTC)
    await session.commit()


async def _mark_unit_review(
    session: AsyncSession, version_id: uuid.UUID, worker_id: str, unit_index: int, code: str
) -> None:
    await session.rollback()
    version = await _owned_version(session, version_id, worker_id)
    if version is None:
        await session.rollback()
        return
    unit = await session.scalar(
        select(KnowledgeFileUnit)
        .where(KnowledgeFileUnit.version_id == version_id, KnowledgeFileUnit.unit_index == unit_index)
        .with_for_update()
    )
    if unit is None:
        raise DocumentIndexError("REVIEW_UNIT_NOT_FOUND", retriable=False)
    unit.issue_codes = list(dict.fromkeys([*unit.issue_codes, code]))
    unit.needs_review = True
    version.status = "review_required"
    version.error_code = code
    version.lease_owner = None
    version.lease_until = None
    version.completed_at = datetime.now(UTC)
    await session.commit()


def _validated_vectors(response: EmbeddingResponse, count: int, revision: str | None) -> str:
    if response.model.lower() not in {"baai/bge-m3", "bge-m3"}:
        raise DocumentIndexError("EMBEDDING_MODEL_INVALID", retriable=False)
    if response.dimensions != EMBEDDING_DIMENSIONS or len(response.vectors) != count:
        raise DocumentIndexError("EMBEDDING_OUTPUT_INVALID", retriable=True)
    if any(len(vector) != EMBEDDING_DIMENSIONS for vector in response.vectors):
        raise DocumentIndexError("EMBEDDING_OUTPUT_INVALID", retriable=True)
    if any(not math.isfinite(value) for vector in response.vectors for value in vector):
        raise DocumentIndexError("EMBEDDING_OUTPUT_INVALID", retriable=True)
    if not response.revision or (revision is not None and response.revision != revision):
        raise DocumentIndexError("EMBEDDING_REVISION_MISMATCH", retriable=True)
    return response.revision


async def _embed_texts(
    embedder: DocumentEmbedderPort,
    texts: list[str],
    *,
    expected_revision: str | None = None,
    renew_lease: Callable[[], Awaitable[None]] | None = None,
) -> tuple[list[list[float]], str]:
    if not texts:
        return [], ""
    size = get_settings().embedding_batch_size
    vectors: list[list[float]] = []
    revision = expected_revision
    for start in range(0, len(texts), size):
        batch = texts[start : start + size]
        response = await embedder.embed(batch)
        revision = _validated_vectors(response, len(batch), revision)
        vectors.extend(response.vectors)
        if renew_lease is not None:
            await renew_lease()
    assert revision is not None
    return vectors, revision


async def _semantic_vectors(
    units: list[CleanedUnit],
    embedder: DocumentEmbedderPort,
    tokenizer: DocumentTokenizer,
    renew_lease: Callable[[], Awaitable[None]],
) -> tuple[dict[int, list[list[float]]], str]:
    result: dict[int, list[list[float]]] = {}
    revision: str | None = None
    for unit in units:
        sentences = _sentences(unit.cleaned_text)
        _check_embedding_lengths(sentences, tokenizer)
        vectors, revision = await _embed_texts(embedder, sentences, expected_revision=revision, renew_lease=renew_lease)
        result[unit.index] = vectors
    return result, revision or ""


def _check_embedding_lengths(texts: list[str], tokenizer: DocumentTokenizer) -> None:
    # 模型服务默认会截断超长输入；索引前拒绝，避免向量只代表被截断的内容。
    max_content_tokens = get_settings().embedding_max_length - 2
    if any(len(value) > 20_000 or len(tokenizer.encode(value)) > max_content_tokens for value in texts):
        raise DocumentIndexError("EMBEDDING_INPUT_TOO_LONG", retriable=False)


async def _commit_ready(
    session: AsyncSession,
    version_id: uuid.UUID,
    worker_id: str,
    drafts: list[DocumentChunkDraft],
    vectors: list[list[float]],
    revision: str,
) -> None:
    version = await _owned_version(session, version_id, worker_id)
    if version is None:
        await session.rollback()
        return
    file = await session.scalar(select(KnowledgeFile).where(KnowledgeFile.id == version.file_id).with_for_update())
    if file is None or file.store_id != version.store_id:
        raise DocumentIndexError("FILE_SCOPE_INVALID", retriable=False)
    if file.deleted_at is not None or file.archived_at is not None:
        raise DocumentIndexError("FILE_INACTIVE", retriable=False)
    existing_chunk = await session.scalar(
        select(KnowledgeFileChunk.id).where(KnowledgeFileChunk.version_id == version.id).limit(1)
    )
    if existing_chunk is not None:
        raise DocumentIndexError("INDEX_STATE_CONFLICT", retriable=False)
    if not version.parser_version:
        raise DocumentIndexError("PARSER_VERSION_MISSING", retriable=False)
    if file.active_version_number is not None and file.active_version_number > version.version_number:
        version.status = "failed_final"
        version.error_code = "VERSION_SUPERSEDED"
    else:
        config = DocumentIndexConfig.model_validate(version.config_json)
        for draft, vector in zip(drafts, vectors, strict=True):
            session.add(
                KnowledgeFileChunk(
                    store_id=version.store_id,
                    file_id=file.id,
                    version_id=version.id,
                    unit_index=draft.unit_index,
                    chunk_index=draft.index,
                    content=draft.content,
                    token_count=draft.token_count,
                    content_hash=hashlib.sha256(draft.content.encode("utf-8")).hexdigest(),
                    strategy=draft.strategy,
                    heading_path=draft.heading_path,
                    source_locator=draft.locator,
                    parser_version=version.parser_version,
                    cleaning_version=version.cleaning_version,
                    embedding_model=config.embedding_model,
                    embedding_revision=revision,
                    embedding=vector,
                )
            )
        version.status = "ready"
        file.active_version_number = version.version_number
    version.completed_at = datetime.now(UTC)
    version.lease_owner = None
    version.lease_until = None
    await session.commit()


async def process_document_version(
    session: AsyncSession,
    parser: DocumentParserPort,
    embedder: DocumentEmbedderPort,
    tokenizer: DocumentTokenizer,
    *,
    worker_id: str,
) -> bool:
    """处理一个已认领版本；只在所有单元可靠且全部向量完成后切换有效版本。"""
    version = await _claim(session, worker_id)
    if version is None:
        return False
    try:
        file = await session.get(KnowledgeFile, version.file_id)
        if file is None or file.store_id != version.store_id:
            raise DocumentIndexError("FILE_SCOPE_INVALID", retriable=False)
        suffix = PurePosixPath(file.original_filename).suffix.lower()
        config = DocumentIndexConfig.model_validate(version.config_json)
        rows = (
            await session.scalars(
                select(KnowledgeFileUnit)
                .where(KnowledgeFileUnit.version_id == version.id)
                .order_by(KnowledgeFileUnit.unit_index)
            )
        ).all()
        if rows:
            if not version.parser_version:
                raise DocumentIndexError("PARSER_VERSION_MISSING", retriable=False)
            cleaned = [_stored_unit(row, version.parser_version) for row in rows]
            if version_requires_review(cleaned):
                owned = await _owned_version(session, version.id, worker_id)
                if owned is not None:
                    owned.status = "review_required"
                    owned.lease_owner = None
                    owned.lease_until = None
                    await session.commit()
                return True
            owned = await _owned_version(session, version.id, worker_id)
            if owned is None:
                await session.rollback()
                return True
            owned.status = "indexing"
            await session.commit()
        else:
            parsed = await parser.parse(version.source_object_key, suffix, config.parser_mode)
            if not parsed:
                raise DocumentIndexError("PARSER_RESULT_EMPTY", retriable=False)
            cleaned = clean_document(parsed)
            if not await _save_units(session, version.id, worker_id, cleaned):
                return True
            if version_requires_review(cleaned):
                return True

        async def renew_lease() -> None:
            await _renew_lease(session, version.id, worker_id)

        semantic = None
        semantic_revision = None
        if config.strategy == "semantic_similarity":
            semantic, semantic_revision = await _semantic_vectors(cleaned, embedder, tokenizer, renew_lease)
        drafts = chunk_document(cleaned, config, tokenizer, suffix=suffix, semantic_vectors=semantic)
        _check_embedding_lengths([draft.content for draft in drafts], tokenizer)
        vectors, revision = await _embed_texts(
            embedder,
            [draft.content for draft in drafts],
            expected_revision=semantic_revision,
            renew_lease=renew_lease,
        )
        await _commit_ready(session, version.id, worker_id, drafts, vectors, revision)
    except DocumentParseError as exc:
        await _mark_error(
            session,
            version.id,
            worker_id,
            exc.code,
            retriable=exc.code
            in {"PARSER_EXECUTION_FAILED", "PARSER_UNAVAILABLE", "PARSER_TIMEOUT", "PARSER_SOURCE_UNAVAILABLE"},
        )
    except DocumentChunkError as exc:
        if exc.unit_index is not None and exc.code in {"ROW_TOO_LARGE_REVIEW_REQUIRED", "TABLE_STRUCTURE_REQUIRED"}:
            await _mark_unit_review(session, version.id, worker_id, exc.unit_index, exc.code)
        else:
            await _mark_error(session, version.id, worker_id, exc.code, retriable=False)
    except DocumentIndexError as exc:
        await _mark_error(session, version.id, worker_id, exc.code, retriable=exc.retriable)
    except Exception:
        await _mark_error(session, version.id, worker_id, "DOCUMENT_PROCESSING_FAILED", retriable=True)
    return True
