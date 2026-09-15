"""店铺级数据看板 HTTP API。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user, require_permission
from app.dashboard.schemas import (
    DashboardAlerts,
    DashboardChannels,
    DashboardMetrics,
    DashboardPeriod,
    DashboardTrend,
    TopQueryItem,
)
from app.dashboard.service import alerts, channels, metrics, top_queries, trend
from app.shared.database.base import User
from app.shared.database.session import DbSession
from app.shared.schemas.responses import ApiResponse

router = APIRouter(prefix="/dashboard", tags=["数据看板"], dependencies=[Depends(require_permission("dashboard.view"))])
READ_DESCRIPTION = "权限：dashboard.view；store_id 必须属于当前用户可访问店铺，跨店铺请求失败关闭。"


@router.get("/metrics", response_model=ApiResponse[DashboardMetrics], description=READ_DESCRIPTION)
async def dashboard_metrics(
    store_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    period: DashboardPeriod = "7d",
) -> ApiResponse[DashboardMetrics]:
    return ApiResponse(data=await metrics(session, user, store_id, period))


@router.get("/trend", response_model=ApiResponse[DashboardTrend], description=READ_DESCRIPTION)
async def dashboard_trend(
    store_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    days: Annotated[int, Query(ge=1, le=30)] = 7,
) -> ApiResponse[DashboardTrend]:
    return ApiResponse(data=await trend(session, user, store_id, days))


@router.get("/channels", response_model=ApiResponse[DashboardChannels], description=READ_DESCRIPTION)
async def dashboard_channels(
    store_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    period: DashboardPeriod = "7d",
) -> ApiResponse[DashboardChannels]:
    return ApiResponse(data=await channels(session, user, store_id, period))


@router.get("/alerts", response_model=ApiResponse[DashboardAlerts], description=READ_DESCRIPTION)
async def dashboard_alerts(
    store_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[DashboardAlerts]:
    return ApiResponse(data=await alerts(session, user, store_id))


@router.get("/top-queries", response_model=ApiResponse[list[TopQueryItem]], description=READ_DESCRIPTION)
async def dashboard_top_queries(
    store_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
    period: DashboardPeriod = "7d",
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> ApiResponse[list[TopQueryItem]]:
    return ApiResponse(data=await top_queries(session, user, store_id, period, limit))
