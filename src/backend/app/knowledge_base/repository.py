"""知识库店铺隔离数据访问。"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.knowledge_base.models import KnowledgeCategory, KnowledgeDocument, KnowledgeImportJob


async def list_categories(
    session: AsyncSession, store_ids: set[uuid.UUID], store_id: uuid.UUID | None
) -> list[KnowledgeCategory]:
    """只返回认证用户可访问店铺的分类。"""
    if not store_ids:
        return []
    query = select(KnowledgeCategory).where(KnowledgeCategory.store_id.in_(store_ids))
    if store_id:
        query = query.where(KnowledgeCategory.store_id == store_id)
    return list((await session.scalars(query.order_by(KnowledgeCategory.sort_order, KnowledgeCategory.id))).all())


async def find_category(
    session: AsyncSession, category_id: uuid.UUID, store_ids: set[uuid.UUID]
) -> KnowledgeCategory | None:
    """联合资源 ID 和授权店铺查询分类。"""
    if not store_ids:
        return None
    result: KnowledgeCategory | None = await session.scalar(
        select(KnowledgeCategory).where(KnowledgeCategory.id == category_id, KnowledgeCategory.store_id.in_(store_ids))
    )
    return result


async def find_document(
    session: AsyncSession, document_id: uuid.UUID, store_ids: set[uuid.UUID]
) -> KnowledgeDocument | None:
    """联合资源 ID 和授权店铺查询未删除 FAQ。"""
    if not store_ids:
        return None
    result: KnowledgeDocument | None = await session.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.store_id.in_(store_ids),
            KnowledgeDocument.deleted_at.is_(None),
        )
    )
    return result


async def list_documents(
    session: AsyncSession,
    store_ids: set[uuid.UUID],
    store_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    layer: str | None,
    status: str | None,
    search: str | None,
    page: int,
    page_size: int,
) -> tuple[list[KnowledgeDocument], int]:
    """按更新时间和 UUID 稳定排序 FAQ。"""
    if not store_ids:
        return [], 0
    conditions: list[ColumnElement[bool]] = [
        KnowledgeDocument.store_id.in_(store_ids),
        KnowledgeDocument.deleted_at.is_(None),
    ]
    if store_id:
        conditions.append(KnowledgeDocument.store_id == store_id)
    if category_id:
        conditions.append(KnowledgeDocument.category_id == category_id)
    if layer:
        # 层级筛选必须在数据库分页前完成，否则前端只能过滤当前页，条目总数和翻页都会失真。
        layer_category_ids = select(KnowledgeCategory.id).where(
            KnowledgeCategory.store_id.in_(store_ids),
            KnowledgeCategory.layer == layer,
        )
        if store_id:
            layer_category_ids = layer_category_ids.where(KnowledgeCategory.store_id == store_id)
        conditions.append(KnowledgeDocument.category_id.in_(layer_category_ids))
    if status:
        conditions.append(KnowledgeDocument.status == status)
    if search:
        escaped = search.replace("%", "\\%").replace("_", "\\_")
        conditions.append(KnowledgeDocument.question.ilike(f"%{escaped}%", escape="\\"))
    total = await session.scalar(select(func.count()).select_from(KnowledgeDocument).where(*conditions)) or 0
    items = list(
        (
            await session.scalars(
                select(KnowledgeDocument)
                .where(*conditions)
                .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    return items, int(total)


async def find_import_job(
    session: AsyncSession, job_id: uuid.UUID, store_ids: set[uuid.UUID]
) -> KnowledgeImportJob | None:
    """按授权店铺读取导入进度。"""
    if not store_ids:
        return None
    result: KnowledgeImportJob | None = await session.scalar(
        select(KnowledgeImportJob).where(KnowledgeImportJob.id == job_id, KnowledgeImportJob.store_id.in_(store_ids))
    )
    return result


async def count_vectorization_statuses(session: AsyncSession, store_id: uuid.UUID) -> dict[str, int]:
    """统计指定店铺已发布 FAQ 的当前向量化状态。"""
    rows = (
        await session.execute(
            select(KnowledgeDocument.vectorization_status, func.count())
            .where(
                KnowledgeDocument.store_id == store_id,
                KnowledgeDocument.status == "published",
                KnowledgeDocument.deleted_at.is_(None),
            )
            .group_by(KnowledgeDocument.vectorization_status)
        )
    ).all()
    counts = {status: 0 for status in ("pending", "processing", "ready", "failed")}
    for vectorization_status, count in rows:
        if vectorization_status in counts:
            counts[vectorization_status] = int(count)
    return counts
