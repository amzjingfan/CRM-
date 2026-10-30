"""共享模板静态路由须在 Agent UUID 路由前注册。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.agents.management.templates.lifecycle_schemas import (
    TemplateCatalogView,
    TemplateCreate,
    TemplateFromAgent,
    TemplateListView,
    TemplateRevision,
    TemplateUpdate,
    TemplateVersionView,
    TemplateView,
)
from app.agents.management.templates.preview import create_application_preview
from app.agents.management.templates.schemas import ApplicationPreviewRequest, ApplicationPreviewView
from app.agents.management.templates.selection import application_stores, knowledge_files
from app.agents.management.templates.selection_schemas import ApplicationStorePage, KnowledgeFileOptionPage
from app.agents.management.templates.service import (
    create_template,
    get_template,
    list_template_versions,
    list_templates,
    publish_template,
    set_template_archived,
    template_catalog,
    template_from_agent,
    update_template,
)
from app.auth.dependencies import get_current_user, require_csrf, require_permission
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse

router = APIRouter(prefix="/templates", tags=["Agent 共享模板"])
ReadUser = Annotated[User, Depends(require_permission("agent.view"))]
Actor = Annotated[User, Depends(get_current_user)]


@router.post(
    "/{template_id}/application-previews",
    response_model=ApiResponse[ApplicationPreviewView],
    dependencies=[Depends(require_csrf), Depends(require_permission("agent.manage"))],
)
async def application_preview(
    template_id: uuid.UUID, payload: ApplicationPreviewRequest, session: DbSession, user: Actor
) -> ApiResponse[ApplicationPreviewView]:
    return ApiResponse(data=await create_application_preview(session, user, template_id, payload))


@router.get("", response_model=ApiResponse[TemplateListView])
async def templates(
    session: DbSession, user: ReadUser, include_archived: bool = False
) -> ApiResponse[TemplateListView]:
    return ApiResponse(data=await list_templates(session, user, include_archived=include_archived))


@router.post("", response_model=ApiResponse[TemplateView], dependencies=[Depends(require_csrf)])
async def add_template(payload: TemplateCreate, session: DbSession, user: Actor) -> ApiResponse[TemplateView]:
    return ApiResponse(data=await create_template(session, user, payload))


@router.post("/from-agent", response_model=ApiResponse[TemplateView], dependencies=[Depends(require_csrf)])
async def from_agent(payload: TemplateFromAgent, session: DbSession, user: Actor) -> ApiResponse[TemplateView]:
    return ApiResponse(data=await template_from_agent(session, user, payload))


@router.get("/catalog", response_model=ApiResponse[TemplateCatalogView])
async def catalog(user: ReadUser) -> ApiResponse[TemplateCatalogView]:
    return ApiResponse(data=template_catalog())


@router.get(
    "/application-stores",
    response_model=ApiResponse[ApplicationStorePage],
    dependencies=[Depends(require_permission("agent.manage"))],
)
async def application_store_options(
    session: DbSession,
    user: Actor,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str, Query(max_length=200)] = "",
) -> ApiResponse[ApplicationStorePage]:
    return ApiResponse(data=await application_stores(session, user, page, page_size, search))


@router.get(
    "/application-stores/{store_id}/knowledge-files",
    response_model=ApiResponse[KnowledgeFileOptionPage],
)
async def application_knowledge_options(
    store_id: uuid.UUID,
    session: DbSession,
    user: Actor,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str, Query(max_length=200)] = "",
) -> ApiResponse[KnowledgeFileOptionPage]:
    return ApiResponse(data=await knowledge_files(session, user, store_id, page, page_size, search))


@router.get("/{template_id}", response_model=ApiResponse[TemplateView])
async def template(template_id: uuid.UUID, session: DbSession, user: ReadUser) -> ApiResponse[TemplateView]:
    return ApiResponse(data=await get_template(session, user, template_id))


@router.patch("/{template_id}", response_model=ApiResponse[TemplateView], dependencies=[Depends(require_csrf)])
async def edit_template(
    template_id: uuid.UUID, payload: TemplateUpdate, session: DbSession, user: Actor
) -> ApiResponse[TemplateView]:
    return ApiResponse(data=await update_template(session, user, template_id, payload))


@router.get("/{template_id}/versions", response_model=ApiResponse[list[TemplateVersionView]])
async def versions(
    template_id: uuid.UUID, session: DbSession, user: ReadUser
) -> ApiResponse[list[TemplateVersionView]]:
    return ApiResponse(data=await list_template_versions(session, user, template_id))


@router.post("/{template_id}/publish", response_model=ApiResponse[TemplateView], dependencies=[Depends(require_csrf)])
async def publish(
    template_id: uuid.UUID, payload: TemplateRevision, session: DbSession, user: Actor
) -> ApiResponse[TemplateView]:
    return ApiResponse(data=await publish_template(session, user, template_id, payload.expected_revision))


@router.post("/{template_id}/archive", response_model=ApiResponse[TemplateView], dependencies=[Depends(require_csrf)])
async def archive(
    template_id: uuid.UUID, payload: TemplateRevision, session: DbSession, user: Actor
) -> ApiResponse[TemplateView]:
    return ApiResponse(
        data=await set_template_archived(session, user, template_id, payload.expected_revision, archived=True)
    )


@router.post("/{template_id}/restore", response_model=ApiResponse[TemplateView], dependencies=[Depends(require_csrf)])
async def restore(
    template_id: uuid.UUID, payload: TemplateRevision, session: DbSession, user: Actor
) -> ApiResponse[TemplateView]:
    return ApiResponse(
        data=await set_template_archived(session, user, template_id, payload.expected_revision, archived=False)
    )
