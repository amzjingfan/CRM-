"""Agent 运营管理 HTTP API。"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.agent_management.schemas import AgentConfigCreate, AgentConfigUpdate, AgentConfigView, AgentRunLogPage
from app.agent_management.service import (
    config_view,
    create_config,
    delete_config,
    get_config,
    get_configs,
    get_logs,
    set_config_status,
    update_config,
)
from app.auth.dependencies import get_current_user, require_csrf, require_permission
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse

router = APIRouter(prefix="/agents", tags=["Agent 运营管理"])
READ_DESCRIPTION = "权限：agent.view；只返回当前用户可访问 store_id 的运营配置和脱敏日志。"
WRITE_DESCRIPTION = (
    "权限：agent.manage；需 CSRF 并校验 store_id。可配置固定枚举回复画像；模型、Prompt 和置信度阈值只读。"
)


@router.get(
    "",
    response_model=ApiResponse[list[AgentConfigView]],
    dependencies=[Depends(require_permission("agent.view"))],
    description=READ_DESCRIPTION,
)
async def agents(
    session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[list[AgentConfigView]]:
    return ApiResponse(data=await get_configs(session, user))


@router.post(
    "",
    response_model=ApiResponse[AgentConfigView],
    dependencies=[Depends(require_csrf), Depends(require_permission("agent.manage"))],
    description=WRITE_DESCRIPTION,
)
async def add_agent(
    payload: AgentConfigCreate, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[AgentConfigView]:
    return ApiResponse(data=await create_config(session, user, payload))


@router.get(
    "/{agent_id}",
    response_model=ApiResponse[AgentConfigView],
    dependencies=[Depends(require_permission("agent.view"))],
    description=READ_DESCRIPTION,
)
async def agent(
    agent_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[AgentConfigView]:
    return ApiResponse(data=config_view(await get_config(session, user, agent_id)))


@router.patch(
    "/{agent_id}",
    response_model=ApiResponse[AgentConfigView],
    dependencies=[Depends(require_csrf), Depends(require_permission("agent.manage"))],
    description=WRITE_DESCRIPTION,
)
async def edit_agent(
    agent_id: uuid.UUID,
    payload: AgentConfigUpdate,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[AgentConfigView]:
    return ApiResponse(data=await update_config(session, user, agent_id, payload))


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf), Depends(require_permission("agent.manage"))],
    description=WRITE_DESCRIPTION,
)
async def remove_agent(
    agent_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> Response:
    await delete_config(session, user, agent_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{agent_id}/enable",
    response_model=ApiResponse[AgentConfigView],
    dependencies=[Depends(require_csrf), Depends(require_permission("agent.manage"))],
    description=WRITE_DESCRIPTION,
)
async def enable_agent(
    agent_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[AgentConfigView]:
    return ApiResponse(data=await set_config_status(session, user, agent_id, "enabled"))


@router.post(
    "/{agent_id}/disable",
    response_model=ApiResponse[AgentConfigView],
    dependencies=[Depends(require_csrf), Depends(require_permission("agent.manage"))],
    description=WRITE_DESCRIPTION,
)
async def disable_agent(
    agent_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[AgentConfigView]:
    return ApiResponse(data=await set_config_status(session, user, agent_id, "disabled"))


@router.post(
    "/{agent_id}/toggle",
    response_model=ApiResponse[AgentConfigView],
    dependencies=[Depends(require_csrf), Depends(require_permission("agent.manage"))],
    description=WRITE_DESCRIPTION,
)
async def toggle_agent(
    agent_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[AgentConfigView]:
    current = await get_config(session, user, agent_id)
    return ApiResponse(
        data=await set_config_status(session, user, agent_id, "disabled" if current.status == "enabled" else "enabled")
    )


@router.get(
    "/{agent_id}/logs",
    response_model=ApiResponse[AgentRunLogPage],
    dependencies=[Depends(require_permission("agent.view"))],
    description=READ_DESCRIPTION,
)
async def agent_logs(
    agent_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    start: datetime | None = None,
    end: datetime | None = None,
) -> ApiResponse[AgentRunLogPage]:
    return ApiResponse(data=await get_logs(session, user, agent_id, page, page_size, start, end))
