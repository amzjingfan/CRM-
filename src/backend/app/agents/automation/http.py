"""自动化操作沿用 Cookie/CSRF 和服务端店铺授权。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.agents.automation.policy import (
    AutomationPolicyUpdate,
    AutomationPolicyView,
    ConversationAutomationUpdate,
    ConversationAutomationView,
    conversation_policy,
    get_policy,
    set_policy,
)
from app.auth.dependencies import get_current_user, require_csrf, require_permission
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse

router = APIRouter()


@router.get("/agents/automation", dependencies=[Depends(require_permission("agent.view"))])
async def read_policy(
    store_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[AutomationPolicyView]:
    return ApiResponse(data=await get_policy(session, user, store_id, get_settings()))


@router.put("/agents/automation", dependencies=[Depends(require_csrf), Depends(require_permission("agent.manage"))])
async def update_policy(
    store_id: uuid.UUID,
    payload: AutomationPolicyUpdate,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[AutomationPolicyView]:
    return ApiResponse(data=await set_policy(session, user, store_id, payload, get_settings()))


@router.get(
    "/workspace/sessions/{conversation_id}/automation", dependencies=[Depends(require_permission("workspace.view"))]
)
async def read_conversation(
    conversation_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[ConversationAutomationView]:
    return ApiResponse(data=await conversation_policy(session, user, conversation_id))


@router.put(
    "/workspace/sessions/{conversation_id}/automation",
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.reply"))],
)
async def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationAutomationUpdate,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[ConversationAutomationView]:
    return ApiResponse(data=await conversation_policy(session, user, conversation_id, payload))
