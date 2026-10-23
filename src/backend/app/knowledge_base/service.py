"""知识库分类、FAQ、发布与导入受理业务规则。"""

import hashlib
import re
import uuid
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids, ensure_store_access
from app.knowledge_base.document_models import KnowledgeFile
from app.knowledge_base.models import KnowledgeCategory, KnowledgeDocument, KnowledgeImportJob
from app.knowledge_base.repository import (
    count_vectorization_statuses,
    find_category,
    find_document,
    find_import_job,
    list_categories,
    list_documents,
)
from app.knowledge_base.schemas import (
    CategoryCreate,
    CategoryUpdate,
    KnowledgeEntryCreate,
    KnowledgeEntryUpdate,
    KnowledgeEntryView,
    KnowledgePage,
    KnowledgePublicationApproval,
    KnowledgeSafetyMetadata,
    KnowledgeStatementType,
    KnowledgeVectorizationStatus,
    VectorizationCounts,
)
from app.knowledge_base.storage import put_import_file
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode

ALLOWED_IMPORT_TYPES = {
    "text/csv": ".csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


def content_hash(question: str, answer: str) -> str:
    """为内容版本生成不含正文的稳定摘要。"""
    return hashlib.sha256(f"{question}\n{answer}".encode()).hexdigest()


async def validate_category_parent(
    session: AsyncSession,
    store_id: uuid.UUID,
    category_id: uuid.UUID | None,
    parent_id: uuid.UUID | None,
) -> None:
    """校验父分类存在且不会形成任意深度的循环引用。

    分类只有一个父节点，因此从候选父节点持续向上追溯即可判断环路。
    除直接把自身设为父级外，也必须拒绝把任一后代设为父级；否则分类树
    无法稳定遍历，前端层级展示和删除约束都会失效。
    """
    current_id = parent_id
    visited: set[uuid.UUID] = set()
    while current_id is not None:
        if current_id == category_id or current_id in visited:
            raise AppError(ErrorCode.VALIDATION_ERROR, "父分类不能形成循环关系", 422)
        visited.add(current_id)
        current = await find_category(session, current_id, {store_id})
        if current is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "父分类不存在", 404)
        current_id = current.parent_id


async def get_categories(session: AsyncSession, user: User, store_id: uuid.UUID | None) -> list[KnowledgeCategory]:
    """获取授权店铺分类。"""
    stores = await allowed_store_ids(session, user)
    if store_id and store_id not in stores:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    return await list_categories(session, stores, store_id)


async def create_category(session: AsyncSession, user: User, payload: CategoryCreate) -> KnowledgeCategory:
    """创建 C 层 FAQ 分类并校验父分类属于同一店铺。"""
    await ensure_store_access(session, user, payload.store_id)
    await validate_category_parent(session, payload.store_id, None, payload.parent_id)
    category = KnowledgeCategory(**payload.model_dump(), layer="C")
    session.add(category)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "分类编码已存在", 409) from exc
    await session.refresh(category)
    return category


async def update_category(
    session: AsyncSession, user: User, category_id: uuid.UUID, payload: CategoryUpdate
) -> KnowledgeCategory:
    """更新分类，并拒绝直接或间接的父子循环。"""
    category = await find_category(session, category_id, await allowed_store_ids(session, user))
    if category is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "分类不存在", 404)
    if "parent_id" in payload.model_fields_set:
        await validate_category_parent(session, category.store_id, category.id, payload.parent_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, key, value)
    await session.commit()
    await session.refresh(category)
    return category


async def delete_category(session: AsyncSession, user: User, category_id: uuid.UUID) -> None:
    """仅允许删除空分类，避免 FAQ 或文件被意外脱离运营分类。"""
    category = await find_category(session, category_id, await allowed_store_ids(session, user))
    if category is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "分类不存在", 404)
    usage = await session.scalar(
        select(func.count())
        .select_from(KnowledgeDocument)
        .where(KnowledgeDocument.category_id == category.id, KnowledgeDocument.deleted_at.is_(None))
    )
    file_usage = await session.scalar(
        select(func.count())
        .select_from(KnowledgeFile)
        .where(KnowledgeFile.category_id == category.id, KnowledgeFile.deleted_at.is_(None))
    )
    children = await session.scalar(
        select(func.count()).select_from(KnowledgeCategory).where(KnowledgeCategory.parent_id == category.id)
    )
    if usage or file_usage or children:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "分类下仍有子分类或知识", 409)
    await session.delete(category)
    await session.commit()


async def get_entries(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    layer: str | None,
    status: str | None,
    search: str | None,
    page: int,
    page_size: int,
) -> KnowledgePage:
    """返回店铺隔离 FAQ 分页。"""
    stores = await allowed_store_ids(session, user)
    if store_id and store_id not in stores:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在", 404)
    items, total = await list_documents(session, stores, store_id, category_id, layer, status, search, page, page_size)
    return KnowledgePage(
        items=[KnowledgeEntryView.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


async def get_entry(session: AsyncSession, user: User, entry_id: uuid.UUID) -> KnowledgeDocument:
    """按资源 ID 和授权店铺联合获取 FAQ。"""
    document = await find_document(session, entry_id, await allowed_store_ids(session, user))
    if document is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "FAQ 不存在", 404)
    return document


async def get_vectorization_status(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
) -> KnowledgeVectorizationStatus:
    """返回经过店铺权限校验的 BGE 向量化队列汇总。"""
    await ensure_store_access(session, user, store_id)
    counts = await count_vectorization_statuses(session, store_id)
    settings = get_settings()
    return KnowledgeVectorizationStatus(
        store_id=store_id,
        worker_enabled=settings.embedding_enabled,
        provider="local_bge",
        model="BAAI/bge-m3",
        dimensions=1024,
        counts=VectorizationCounts(**counts),
    )


async def retry_entry_vectorization(
    session: AsyncSession,
    user: User,
    entry_id: uuid.UUID,
) -> KnowledgeDocument:
    """把已发布且向量化失败的 FAQ 安全放回 pending 队列。"""
    document = await find_document(session, entry_id, await allowed_store_ids(session, user))
    if document is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "FAQ 不存在", 404)
    if not get_settings().embedding_enabled:
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "本地向量化 Worker 未启用", 409)
    if (
        document.status != "published"
        or document.vectorization_status != "failed"
        or document.publication_approval == KnowledgePublicationApproval.DRAFT
        or document.statement_type == KnowledgeStatementType.UNKNOWN
    ):
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "仅可重试已发布且向量化失败的 FAQ", 409)
    document.vectorization_status = "pending"
    session.add(
        AuditLog(
            store_id=document.store_id,
            actor_type="user",
            actor_id=user.id,
            action="knowledge.vectorization_retry",
            resource_type="knowledge_document",
            resource_id=document.id,
            before_data={"vectorization_status": "failed", "version": document.document_version},
            after_data={"vectorization_status": "pending", "version": document.document_version},
            result="succeeded",
        )
    )
    await session.commit()
    await session.refresh(document)
    return document


async def create_entry(
    session: AsyncSession, user: User, payload: KnowledgeEntryCreate, *, commit: bool = True
) -> KnowledgeDocument:
    """创建草稿 FAQ；草稿不参与正式检索。"""
    await ensure_store_access(session, user, payload.store_id)
    if payload.category_id and await find_category(session, payload.category_id, {payload.store_id}) is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "分类不存在", 404)
    document_id = uuid.uuid4()
    document = KnowledgeDocument(
        id=document_id,
        **payload.model_dump(),
        title=payload.question[:500],
        content_hash=content_hash(payload.question, payload.answer),
    )
    session.add(document)
    session.add(
        AuditLog(
            store_id=payload.store_id,
            actor_type="user",
            actor_id=user.id,
            action="knowledge.create",
            resource_type="knowledge_document",
            resource_id=document_id,
            after_data={
                "statement_type": payload.statement_type.value,
                "customer_scope": payload.customer_scope.value,
                "publication_approval": KnowledgePublicationApproval.DRAFT.value,
                "version": 1,
            },
            result="succeeded",
        )
    )
    if commit:
        await session.commit()
        await session.refresh(document)
    else:
        await session.flush()
    return document


async def update_entry(
    session: AsyncSession, user: User, entry_id: uuid.UUID, payload: KnowledgeEntryUpdate
) -> KnowledgeDocument:
    """正文变化时递增版本并使旧向量立即失效。"""
    document = await find_document(session, entry_id, await allowed_store_ids(session, user))
    if document is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "FAQ 不存在", 404)
    updates = payload.model_dump(exclude_unset=True)
    if payload.category_id and await find_category(session, payload.category_id, {document.store_id}) is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "分类不存在", 404)
    old_hash = document.content_hash
    before_safety = {
        "statement_type": document.statement_type,
        "customer_scope": document.customer_scope,
        "publication_approval": document.publication_approval,
        "version": document.document_version,
    }
    try:
        KnowledgeSafetyMetadata.model_validate(
            {
                "statement_type": updates.get("statement_type", document.statement_type),
                "customer_scope": updates.get("customer_scope", document.customer_scope),
                "publication_approval": KnowledgePublicationApproval.DRAFT,
                "semantic_schema_version": document.semantic_schema_version,
                "store_id": document.store_id,
                "document_version": document.document_version,
                "approved_document_version": document.document_version,
            }
        )
    except ValidationError as exc:
        raise AppError(ErrorCode.VALIDATION_ERROR, "知识语义类型与客户范围不一致", 422) from exc
    for key, value in updates.items():
        setattr(document, key, value)
    new_hash = content_hash(document.question, document.answer)
    semantic_changed = str(document.statement_type) != str(before_safety["statement_type"]) or str(
        document.customer_scope
    ) != str(before_safety["customer_scope"])
    if new_hash != old_hash or semantic_changed:
        document.content_hash = new_hash
        document.document_version += 1
        document.vectorization_status = "pending"
        document.title = document.question[:500]
        document.status = "draft"
        document.publication_approval = KnowledgePublicationApproval.DRAFT
        document.approved_by = None
        document.approved_at = None
        document.published_at = None
    session.add(
        AuditLog(
            store_id=document.store_id,
            actor_type="user",
            actor_id=user.id,
            action="knowledge.update",
            resource_type="knowledge_document",
            resource_id=document.id,
            before_data=before_safety,
            after_data={
                "statement_type": str(document.statement_type),
                "customer_scope": str(document.customer_scope),
                "publication_approval": str(document.publication_approval),
                "version": document.document_version,
            },
            result="succeeded",
        )
    )
    await session.commit()
    await session.refresh(document)
    return document


async def set_entry_status(
    session: AsyncSession, user: User, entry_id: uuid.UUID, status: str, *, commit: bool = True
) -> KnowledgeDocument:
    """发布进入待向量化，归档则立即退出正式检索。"""
    document = await find_document(session, entry_id, await allowed_store_ids(session, user))
    if document is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "FAQ 不存在", 404)
    if status == "published":
        approved_at = datetime.now(UTC)
        try:
            KnowledgeSafetyMetadata.model_validate(
                {
                    "statement_type": document.statement_type,
                    "customer_scope": document.customer_scope,
                    "publication_approval": KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW,
                    "semantic_schema_version": document.semantic_schema_version,
                    "approved_by": user.id,
                    "approved_at": approved_at,
                    "store_id": document.store_id,
                    "document_version": document.document_version,
                    "approved_document_version": document.document_version,
                }
            )
        except ValidationError as exc:
            raise AppError(
                ErrorCode.RESOURCE_CONFLICT,
                "发布前必须设置有效的知识语义类型和客户范围",
                409,
            ) from exc
        document.status = status
        document.vectorization_status = "pending"
        document.publication_approval = KnowledgePublicationApproval.APPROVED_FOR_INTERNAL_REVIEW
        document.approved_by = user.id
        document.approved_at = approved_at
        document.published_at = approved_at
    else:
        document.status = status
    session.add(
        AuditLog(
            store_id=document.store_id,
            actor_type="user",
            actor_id=user.id,
            action=f"knowledge.{status}",
            resource_type="knowledge_document",
            resource_id=document.id,
            after_data={
                "status": status,
                "version": document.document_version,
                "statement_type": str(document.statement_type),
                "customer_scope": str(document.customer_scope),
                "publication_approval": str(document.publication_approval),
                "approved_by": str(document.approved_by) if document.approved_by else None,
                "approved_at": document.approved_at.isoformat() if document.approved_at else None,
            },
            result="succeeded",
        )
    )
    if commit:
        await session.commit()
        await session.refresh(document)
    else:
        await session.flush()
    return document


async def delete_entry(session: AsyncSession, user: User, entry_id: uuid.UUID) -> None:
    """软删除 FAQ，保留审计与历史工具链引用。"""
    document = await find_document(session, entry_id, await allowed_store_ids(session, user))
    if document is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "FAQ 不存在", 404)
    document.deleted_at = datetime.now(UTC)
    document.status = "archived"
    await session.commit()


async def accept_import(
    session: AsyncSession,
    user: User,
    store_id: uuid.UUID,
    filename: str,
    content_type: str,
    content: bytes,
) -> KnowledgeImportJob:
    """校验文件边界后存入 MinIO，并创建异步任务。"""
    await ensure_store_access(session, user, store_id)
    settings = get_settings()
    suffix = ALLOWED_IMPORT_TYPES.get(content_type)
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:255]
    if suffix is None or not safe_name.lower().endswith(suffix):
        raise AppError(ErrorCode.VALIDATION_ERROR, "仅支持 CSV 或 XLSX 文件", 422)
    if not content or len(content) > settings.knowledge_import_max_bytes:
        raise AppError(ErrorCode.VALIDATION_ERROR, "导入文件必须小于等于 10 MiB", 422)
    object_key = f"knowledge-imports/{store_id}/{uuid.uuid4()}{suffix}"
    await put_import_file(object_key, content, content_type)
    job = KnowledgeImportJob(
        store_id=store_id,
        created_by=user.id,
        object_key=object_key,
        original_filename=safe_name,
        content_type=content_type,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def get_import_job(session: AsyncSession, user: User, job_id: uuid.UUID) -> KnowledgeImportJob:
    """读取授权店铺的导入任务。"""
    job = await find_import_job(session, job_id, await allowed_store_ids(session, user))
    if job is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "导入任务不存在", 404)
    return job
