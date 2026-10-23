"""v1 版本路由聚合。"""

from fastapi import APIRouter

from app.agent_management.router import router as agent_management_router
from app.auth.router import router as auth_router
from app.chat.router import router as chat_router
from app.dashboard.router import router as dashboard_router
from app.integrations.oauth_router import router as oauth_router
from app.integrations.router import router as integrations_router
from app.knowledge_base.document_router import router as knowledge_document_router
from app.knowledge_base.router import router as knowledge_router
from app.marketing.router import router as marketing_router
from app.reception.router import router as reception_router

# 应用启动时集中注册全部 ORM 表，确保跨模块外键（例如 tool_calls → agent_runs）
# 在任一模块首次 flush 前都能由 SQLAlchemy 正确解析。
from app.shared.database import models as _models  # noqa: F401
from app.stores.router import router as stores_router
from app.users.department_router import router as departments_router
from app.users.router import router as users_router
from app.workspace.alias_router import router as sessions_alias_router
from app.workspace.router import router as workspace_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(chat_router)
router.include_router(dashboard_router)
router.include_router(agent_management_router)
router.include_router(users_router)
router.include_router(departments_router)
router.include_router(stores_router)
router.include_router(integrations_router)
router.include_router(oauth_router)
router.include_router(knowledge_router)
router.include_router(knowledge_document_router)
router.include_router(marketing_router)
router.include_router(reception_router)
router.include_router(workspace_router)
router.include_router(sessions_alias_router)
