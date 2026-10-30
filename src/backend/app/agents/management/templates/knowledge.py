"""知识槽只管理同店引用，多来源去重且不复活手工解绑。"""

import uuid
from collections.abc import Sequence
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.templates.schemas import ApplicationIssue
from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileVersion
from app.shared.exceptions.errors import AppError, ErrorCode


def knowledge_version_publishable(version: KnowledgeFileVersion | None) -> bool:
    """选择提示与应用发布共用当前有效版本的内部审批资格。"""
    return (
        version is not None
        and version.status == "ready"
        and version.publication_approval == "approved_for_internal_review"
        and version.approved_by is not None
        and version.approved_at is not None
    )


def resolve_mappings(
    slots: Sequence[dict[str, object]],
    previous: dict[str, object] | None,
    current: list[str],
    requested: dict[str, list[str]],
    unbind: list[str],
) -> tuple[list[str], dict[str, list[str]], list[str]]:
    keys = {str(slot["key"]) for slot in slots}
    if set(requested) - keys:
        raise AppError(ErrorCode.VALIDATION_ERROR, "知识映射包含未接受的槽", 422)
    state = previous or {}
    old = cast(dict[str, list[str]], state.get("knowledge_mappings", {}))
    current_set = set(current)
    mappings = {
        key: sorted(set(requested[key]) if key in requested else set(old.get(key, [])) & current_set)
        for key in sorted(keys)
    }
    retained = set().union(*(set(value) for value in mappings.values())) if mappings else set()
    old_references = set().union(*(set(value) for value in old.values())) if old else set()
    old_extras = set(cast(list[str], state.get("extra_file_ids", []))) & current_set
    manual_extras = current_set - old_references
    # 手工额外来源与槽来源独立；解绑槽引用不能删除仍存在的手工来源。
    extras = old_extras | manual_extras | ((current_set - retained) - set(unbind))
    return sorted(extras | retained), mappings, sorted(extras)


async def knowledge_dependencies(
    session: AsyncSession,
    store_id: uuid.UUID,
    file_ids: list[str],
    *,
    publish: bool,
    lock: bool = False,
) -> tuple[list[dict[str, object]], list[ApplicationIssue]]:
    dependencies: list[dict[str, object]] = []
    issues = []
    # 与归档/撤销审批共享真实行锁，按稳定 ID 顺序避免文件间死锁。
    for file_id in sorted(set(file_ids)):
        statement = (
            select(KnowledgeFile)
            .where(
                KnowledgeFile.id == uuid.UUID(file_id),
                KnowledgeFile.store_id == store_id,
                KnowledgeFile.archived_at.is_(None),
                KnowledgeFile.deleted_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        if lock:
            statement = statement.with_for_update(read=True)
        file = await session.scalar(statement)
        if file is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "所选知识文件不存在或不可绑定", 404)
        version_query = (
            select(KnowledgeFileVersion)
            .where(
                KnowledgeFileVersion.file_id == file.id,
                KnowledgeFileVersion.store_id == store_id,
                KnowledgeFileVersion.version_number == file.active_version_number,
            )
            .execution_options(populate_existing=True)
        )
        if lock:
            version_query = version_query.with_for_update(read=True)
        version = await session.scalar(version_query)
        ready = knowledge_version_publishable(version)
        if publish and not ready:
            issues.append(
                ApplicationIssue(
                    code="knowledge_not_ready", message="知识文件尚未完成索引或内部审批", field="knowledge_slots"
                )
            )
        dependencies.append(
            {
                "file_id": file_id,
                "active_version_number": file.active_version_number,
                "version_id": str(version.id) if version else None,
                "file_sha256": version.file_sha256 if version else None,
                "status": version.status if version else None,
                "publication_approval": version.publication_approval if version else None,
                "approved_by": str(version.approved_by) if version and version.approved_by else None,
                "approved_at": version.approved_at.isoformat() if version and version.approved_at else None,
            }
        )
    return dependencies, issues
