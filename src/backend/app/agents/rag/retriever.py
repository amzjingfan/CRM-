"""显式文件范围适配；空绑定绝不落到旧 FAQ 搜索。"""

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.repository import PublishedAgent
from app.agents.rag.search import RagRetrievalResult
from app.agents.runtime.snapshot import RunSnapshot
from app.agents.safety.input import prepare_untrusted_text
from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileVersion
from app.knowledge_base.schemas import KnowledgeRetrievalHit
from app.shared.exceptions.errors import AppError, ErrorCode


class FileRagPort(Protocol):
    async def retrieve(
        self, session: AsyncSession, store_id: uuid.UUID, query: str, file_ids: tuple[uuid.UUID, ...]
    ) -> RagRetrievalResult: ...


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    hits: tuple[KnowledgeRetrievalHit, ...]
    excluded_file_count: int


async def retrieve_bound_files(
    *,
    session: AsyncSession,
    snapshot: RunSnapshot,
    agent: PublishedAgent,
    query: str,
    deadline: float,
    rag_service: FileRagPort,
) -> EvidenceBundle:
    """仅向底层传入非空文件 tuple，版本变化或撤权后的命中不展示。"""
    if agent.store_id != snapshot.store_id:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Agent 不在当前店铺", 404)
    if not agent.file_ids:
        return EvidenceBundle(hits=(), excluded_file_count=0)
    bound = {uuid.UUID(item) for item in agent.file_ids}
    approved_versions = {item.file_id: item.version_number for item in snapshot.file_versions if item.file_id in bound}
    eligible = tuple(sorted(approved_versions, key=str))
    excluded_count = len(bound) - len(eligible)
    if not eligible:
        return EvidenceBundle(hits=(), excluded_file_count=excluded_count)
    async with asyncio.timeout(max(0.0, deadline - time.monotonic())):
        result = await rag_service.retrieve(session, snapshot.store_id, query, file_ids=eligible)
    hits = tuple(
        item
        for item in result.hits
        if item.document_id in approved_versions
        and item.document_version == approved_versions[item.document_id]
        and item.safety_metadata.store_id == snapshot.store_id
    )
    return EvidenceBundle(hits=hits, excluded_file_count=excluded_count)


async def revalidate_evidence(
    *,
    session: AsyncSession,
    snapshot: RunSnapshot,
    agent: PublishedAgent,
    bundle: EvidenceBundle,
) -> EvidenceBundle:
    """展示前重查当前有效与审批；撤权或换版立即剔除引用。"""
    if agent.store_id != snapshot.store_id:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Agent 不在当前店铺", 404)
    if not bundle.hits:
        return bundle
    frozen = {item.file_id: item.version_number for item in snapshot.file_versions}
    bound = {uuid.UUID(item) for item in agent.file_ids}
    wanted = {item.document_id for item in bundle.hits if item.document_id in frozen and item.document_id in bound}
    if not wanted:
        return EvidenceBundle(hits=(), excluded_file_count=bundle.excluded_file_count)
    records = await session.execute(
        select(KnowledgeFile.id, KnowledgeFileVersion.version_number)
        .join(
            KnowledgeFileVersion,
            and_(
                KnowledgeFileVersion.file_id == KnowledgeFile.id,
                KnowledgeFileVersion.store_id == KnowledgeFile.store_id,
                KnowledgeFileVersion.version_number == KnowledgeFile.active_version_number,
            ),
        )
        .where(
            KnowledgeFile.store_id == snapshot.store_id,
            KnowledgeFile.id.in_(wanted),
            KnowledgeFile.archived_at.is_(None),
            KnowledgeFile.deleted_at.is_(None),
            KnowledgeFileVersion.status == "ready",
            KnowledgeFileVersion.publication_approval.in_(
                ("approved_for_internal_review", "approved_for_public_reply")
            ),
            KnowledgeFileVersion.approved_by.is_not(None),
            KnowledgeFileVersion.approved_at.is_not(None),
        )
    )
    still_valid = {(item[0], item[1]) for item in records.all()}
    hits = tuple(
        item
        for item in bundle.hits
        if (item.document_id, item.document_version) in still_valid
        and item.document_version == frozen.get(item.document_id)
    )
    return EvidenceBundle(hits=hits, excluded_file_count=bundle.excluded_file_count)


def project_evidence_for_model(bundle: EvidenceBundle) -> dict[str, object]:
    """只交付已复核的低敏片段和引用键，文档内容始终标为不可信。"""
    projected: list[dict[str, object]] = []
    for hit in bundle.hits:
        try:
            content = prepare_untrusted_text(hit.content, source="knowledge_chunk").text
        except AppError:
            continue
        projected.append(
            {
                "chunk_id": str(hit.chunk_id),
                "document_version": hit.document_version,
                "untrusted_source": "knowledge_chunk",
                "content": content,
            }
        )
    result: dict[str, object] = {
        "status": "retrieved" if projected else "no_hits",
        "hits": projected,
        "excluded_file_count": bundle.excluded_file_count,
    }
    if not projected:
        result["query_guidance"] = (
            "本轮未命中不等于文件不存在或未审批。请结合当前问题，用完整自然语言描述主题和所需信息重新检索，"
            "不要只搜索编号或脱敏占位符；仍无依据时明确说明本轮未检索到相关片段，不能编造政策。"
        )
    return result
