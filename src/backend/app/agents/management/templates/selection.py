"""选择项按数据库同店授权分页，不加载 Prompt 或知识正文。"""

import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.management.config_models import AgentConfig
from app.agents.management.templates.batch_schemas import BatchPagination
from app.agents.management.templates.knowledge import knowledge_version_publishable
from app.agents.management.templates.selection_schemas import (
    ApplicationAgentOption,
    ApplicationStoreOption,
    ApplicationStorePage,
    KnowledgeFileOption,
    KnowledgeFileOptionPage,
)
from app.auth.store_access import allowed_store_ids_for_permission
from app.knowledge_base.document_models import KnowledgeFile, KnowledgeFileVersion
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import Store


def pagination(page: int, page_size: int, total: int) -> BatchPagination:
    return BatchPagination(
        page=page, page_size=page_size, total=total, total_pages=(total + page_size - 1) // page_size
    )


async def application_stores(
    session: AsyncSession, user: User, page: int, page_size: int, search: str
) -> ApplicationStorePage:
    allowed = await allowed_store_ids_for_permission(session, user, "agent.manage")
    knowledge = await allowed_store_ids_for_permission(session, user, "knowledge.view")
    statement = select(Store.id, Store.name, Store.code).where(
        Store.id.in_(allowed), Store.status == "active", Store.deleted_at.is_(None)
    )
    if search:
        statement = statement.where(
            or_(Store.name.icontains(search, autoescape=True), Store.code.icontains(search, autoescape=True))
        )
    total = await session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    stores = (
        await session.execute(statement.order_by(Store.name, Store.id).offset((page - 1) * page_size).limit(page_size))
    ).all()
    agents = (
        (
            await session.execute(
                select(
                    AgentConfig.store_id,
                    AgentConfig.id,
                    AgentConfig.name,
                    AgentConfig.code,
                    AgentConfig.template_id,
                    AgentConfig.draft_revision,
                    AgentConfig.published_version,
                    AgentConfig.status,
                )
                .where(AgentConfig.store_id.in_([s.id for s in stores]), AgentConfig.deleted_at.is_(None))
                .order_by(AgentConfig.name, AgentConfig.id)
            )
        ).all()
        if stores
        else []
    )
    return ApplicationStorePage(
        items=[
            ApplicationStoreOption(
                id=s.id,
                name=s.name,
                code=s.code,
                can_view_knowledge=s.id in knowledge,
                agents=[ApplicationAgentOption.model_validate(dict(a._mapping)) for a in agents if a.store_id == s.id],
            )
            for s in stores
        ],
        pagination=pagination(page, page_size, total),
    )


async def knowledge_files(
    session: AsyncSession, user: User, store_id: uuid.UUID, page: int, page_size: int, search: str
) -> KnowledgeFileOptionPage:
    manageable = await allowed_store_ids_for_permission(session, user, "agent.manage")
    readable = await allowed_store_ids_for_permission(session, user, "knowledge.view")
    store = await session.scalar(
        select(Store.id).where(Store.id == store_id, Store.status == "active", Store.deleted_at.is_(None))
    )
    if store is None or store_id not in manageable & readable:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "资源不存在或无权访问", 404)
    statement = (
        select(KnowledgeFile, KnowledgeFileVersion)
        .outerjoin(
            KnowledgeFileVersion,
            and_(
                KnowledgeFileVersion.file_id == KnowledgeFile.id,
                KnowledgeFileVersion.store_id == KnowledgeFile.store_id,
                KnowledgeFileVersion.version_number == KnowledgeFile.active_version_number,
            ),
        )
        .where(
            KnowledgeFile.store_id == store_id, KnowledgeFile.archived_at.is_(None), KnowledgeFile.deleted_at.is_(None)
        )
    )
    if search:
        statement = statement.where(KnowledgeFile.original_filename.icontains(search, autoescape=True))
    total = await session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = (
        await session.execute(
            statement.order_by(KnowledgeFile.original_filename, KnowledgeFile.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return KnowledgeFileOptionPage(
        items=[
            KnowledgeFileOption(
                id=file.id,
                name=file.original_filename,
                active_version_number=version.version_number if version else None,
                status=version.status if version else None,
                publication_approval=version.publication_approval if version else None,
                can_publish=knowledge_version_publishable(version),
            )
            for file, version in rows
        ],
        pagination=pagination(page, page_size, total),
    )
