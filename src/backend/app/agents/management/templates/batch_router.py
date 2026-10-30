"""后台批次静态路由，优先于 Agent UUID。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.agents.management.templates import batch
from app.agents.management.templates.batch_schemas import BatchConfirmation, BatchListView, BatchView
from app.auth.dependencies import get_current_user, require_csrf
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse

router = APIRouter(prefix="/template-batches", tags=["Agent 模板批次"])
Actor = Annotated[User, Depends(get_current_user)]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.post("", response_model=ApiResponse[BatchView], dependencies=[Depends(require_csrf)])
async def confirm(
    payload: BatchConfirmation,
    session: DbSession,
    user: Actor,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=200)],
) -> ApiResponse[BatchView]:
    return ApiResponse(data=await batch.confirm_batch(session, user, payload, idempotency_key))


@router.get("", response_model=ApiResponse[BatchListView])
async def listing(
    session: DbSession, user: Actor, page: Page = 1, page_size: PageSize = 20
) -> ApiResponse[BatchListView]:
    return ApiResponse(data=await batch.list_batches(session, user, page=page, page_size=page_size))


@router.get("/{batch_id}", response_model=ApiResponse[BatchView])
async def detail(
    batch_id: uuid.UUID, session: DbSession, user: Actor, page: Page = 1, page_size: PageSize = 50
) -> ApiResponse[BatchView]:
    return ApiResponse(data=await batch.get_batch(session, user, batch_id, page=page, page_size=page_size))


@router.post("/{batch_id}/cancel", response_model=ApiResponse[BatchView], dependencies=[Depends(require_csrf)])
async def cancel(batch_id: uuid.UUID, session: DbSession, user: Actor) -> ApiResponse[BatchView]:
    return ApiResponse(data=await batch.cancel_batch(session, user, batch_id))


@router.post("/{batch_id}/retry-failed", response_model=ApiResponse[BatchView], dependencies=[Depends(require_csrf)])
async def retry(batch_id: uuid.UUID, session: DbSession, user: Actor) -> ApiResponse[BatchView]:
    return ApiResponse(data=await batch.retry_failed(session, user, batch_id))
