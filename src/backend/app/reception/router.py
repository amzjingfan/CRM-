"""基础接待配置 HTTP 接口，仅管理本地文本配置。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.auth.dependencies import get_current_user, require_csrf, require_idempotency_key
from app.reception import service
from app.reception.schemas import (
    GroupCreate,
    GroupPage,
    GroupUpdate,
    GroupView,
    PolicyCreate,
    PolicyKind,
    PolicyPage,
    PolicyUpdate,
    PolicyView,
    ReplyCreate,
    ReplyPage,
    ReplyUpdate,
    ReplyView,
    Scope,
)
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse

router = APIRouter(prefix="/marketing/reception", tags=["基础接待配置"])
Actor = Annotated[User, Depends(get_current_user)]
WriteKey = Annotated[str, Depends(require_idempotency_key)]
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/groups", response_model=ApiResponse[GroupPage])
async def get_groups(
    session: DbSession,
    user: Actor,
    store_id: uuid.UUID,
    scope: Scope,
    page: Page = 1,
    page_size: PageSize = 20,
) -> ApiResponse[GroupPage]:
    return ApiResponse(data=await service.list_groups(session, user, store_id, scope, page, page_size))


@router.post("/groups", response_model=ApiResponse[GroupView], dependencies=[Depends(require_csrf)])
async def post_group(payload: GroupCreate, session: DbSession, user: Actor, key: WriteKey) -> ApiResponse[GroupView]:
    return ApiResponse(data=await service.create_group(session, user, payload, key))


@router.patch("/groups/{item_id}", response_model=ApiResponse[GroupView], dependencies=[Depends(require_csrf)])
async def patch_group(
    item_id: uuid.UUID,
    payload: GroupUpdate,
    session: DbSession,
    user: Actor,
    key: WriteKey,
) -> ApiResponse[GroupView]:
    return ApiResponse(data=await service.update_group(session, user, item_id, payload, key))


@router.delete("/groups/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
async def remove_group(item_id: uuid.UUID, session: DbSession, user: Actor, key: WriteKey) -> Response:
    await service.delete_group(session, user, item_id, key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/replies", response_model=ApiResponse[ReplyPage])
async def get_replies(
    session: DbSession,
    user: Actor,
    store_id: uuid.UUID,
    scope: Scope,
    group_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    shortcut: Annotated[str | None, Query(pattern=r"^[A-Za-z0-9]{1,8}$")] = None,
    include_disabled: bool = False,
    page: Page = 1,
    page_size: PageSize = 20,
) -> ApiResponse[ReplyPage]:
    return ApiResponse(
        data=await service.list_replies(
            session,
            user,
            store_id,
            scope,
            group_id,
            q,
            page,
            page_size,
            shortcut=shortcut,
            include_disabled=include_disabled,
        )
    )


@router.post("/replies", response_model=ApiResponse[ReplyView], dependencies=[Depends(require_csrf)])
async def post_reply(payload: ReplyCreate, session: DbSession, user: Actor, key: WriteKey) -> ApiResponse[ReplyView]:
    return ApiResponse(data=await service.create_reply(session, user, payload, key))


@router.patch("/replies/{item_id}", response_model=ApiResponse[ReplyView], dependencies=[Depends(require_csrf)])
async def patch_reply(
    item_id: uuid.UUID,
    payload: ReplyUpdate,
    session: DbSession,
    user: Actor,
    key: WriteKey,
) -> ApiResponse[ReplyView]:
    return ApiResponse(data=await service.update_reply(session, user, item_id, payload, key))


@router.delete("/replies/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
async def remove_reply(item_id: uuid.UUID, session: DbSession, user: Actor, key: WriteKey) -> Response:
    await service.delete_reply(session, user, item_id, key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/policies", response_model=ApiResponse[PolicyPage])
async def get_policies(
    session: DbSession,
    user: Actor,
    kind: PolicyKind,
    store_id: uuid.UUID | None = None,
    page: Page = 1,
    page_size: PageSize = 20,
) -> ApiResponse[PolicyPage]:
    return ApiResponse(data=await service.list_policies(session, user, store_id, kind, page, page_size))


@router.post("/policies", response_model=ApiResponse[PolicyView], dependencies=[Depends(require_csrf)])
async def post_policy(payload: PolicyCreate, session: DbSession, user: Actor, key: WriteKey) -> ApiResponse[PolicyView]:
    return ApiResponse(data=await service.create_policy(session, user, payload, key))


@router.patch("/policies/{item_id}", response_model=ApiResponse[PolicyView], dependencies=[Depends(require_csrf)])
async def patch_policy(
    item_id: uuid.UUID,
    payload: PolicyUpdate,
    session: DbSession,
    user: Actor,
    key: WriteKey,
) -> ApiResponse[PolicyView]:
    return ApiResponse(data=await service.update_policy(session, user, item_id, payload, key))


@router.delete("/policies/{item_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
async def remove_policy(item_id: uuid.UUID, session: DbSession, user: Actor, key: WriteKey) -> Response:
    await service.delete_policy(session, user, item_id, key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
