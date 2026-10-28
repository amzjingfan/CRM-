"""Agent 运营管理 HTTP API。"""

import uuid
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.agents.core.factory import SharedAgentRuntime
from app.agents.management.config_service import (
    config_view,
    create_config,
    delete_config,
    get_config,
    get_configs,
    get_logs,
    set_config_status,
    update_config,
)
from app.agents.management.debug import run_agent_debug_v2
from app.agents.management.schemas import (
    AgentConfigCreate,
    AgentConfigUpdate,
    AgentConfigView,
    AgentDebugRequest,
    AgentDebugView,
    AgentPublishRequest,
    AgentRunLogPage,
)
from app.agents.management.service import publish_agent
from app.agents.tools.access import tool_catalog
from app.agents.tools.collaboration import CollaborationView, list_collaboration
from app.agents.tools.metadata import ToolCatalogView
from app.auth.dependencies import get_current_user, require_csrf, require_permission
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.database.redis import consume_chat_query
from app.shared.database.session import DbSession
from app.shared.exceptions.errors import AppError, ErrorCode
from app.shared.schemas.responses import ApiResponse

router = APIRouter(prefix="/agents", tags=["Agent 运营管理"])
READ_DESCRIPTION = "权限：agent.view；只返回当前用户可访问 store_id 的运营配置和脱敏日志。"
WRITE_DESCRIPTION = (
    "权限：agent.manage；需 CSRF 并校验 store_id。可编辑模型和七段式 Prompt 草稿，发布后生成不可变版本。"
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
    "/tool-catalog",
    response_model=ApiResponse[ToolCatalogView],
    dependencies=[Depends(require_permission("agent.view"))],
)
async def agent_tool_catalog(
    store_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[ToolCatalogView]:
    return ApiResponse(data=await tool_catalog(session, user, store_id))


@router.get(
    "/collaboration",
    response_model=ApiResponse[list[CollaborationView]],
    dependencies=[Depends(require_permission("workspace.view"))],
)
async def agent_collaboration(
    conversation_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[list[CollaborationView]]:
    return ApiResponse(data=await list_collaboration(session, user, conversation_id, offset))


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


@router.post(
    "/{agent_id}/publish",
    response_model=ApiResponse[AgentConfigView],
    dependencies=[Depends(require_csrf), Depends(require_permission("agent.manage"))],
    description="发布已保存的模型、七段式提示词、工具和文件绑定；拒绝过期草稿版本。",
)
async def publish_agent_config(
    agent_id: uuid.UUID,
    payload: AgentPublishRequest,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[AgentConfigView]:
    config = await get_config(session, user, agent_id)
    await publish_agent(
        session,
        store_id=config.store_id,
        config_id=agent_id,
        expected_revision=payload.expected_revision,
        publisher_id=user.id,
    )
    await session.refresh(config)
    return ApiResponse(data=config_view(config))


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


@router.post(
    "/{agent_id}/debug",
    response_model=ApiResponse[AgentDebugView],
    dependencies=[Depends(require_csrf), Depends(require_permission("agent.manage"))],
    description="真实模型调试已保存的服务类 Agent。可选授权会话供只读工具查询；不发送平台消息。",
)
async def debug_agent(
    agent_id: uuid.UUID,
    payload: AgentDebugRequest,
    request: Request,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[AgentDebugView]:
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    if not await consume_chat_query(user.id, client_ip, settings.chat_query_limit, settings.chat_query_window_seconds):
        raise AppError(ErrorCode.RATE_LIMITED, "Agent 调试请求过于频繁", 429)
    runtime = cast(SharedAgentRuntime | None, getattr(request.app.state, "agent_runtime", None))
    trace_id = str(getattr(request.state, "trace_id", uuid.uuid4()))
    if not settings.agent_v2_debug_enabled:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "动态 Agent 调试尚未启用", 503)
    return ApiResponse(data=await run_agent_debug_v2(session, user, agent_id, payload, trace_id, runtime))


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
