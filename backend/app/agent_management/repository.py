"""Agent 运营配置和运行日志租户安全查询。"""

import uuid
from datetime import datetime
from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.models import AgentRun
from app.agent_management.models import AgentConfig
from app.tools.models import ToolCall


async def list_configs(session: AsyncSession, store_ids: set[uuid.UUID]) -> list[AgentConfig]:
    if not store_ids:
        return []
    return list(
        (
            await session.scalars(
                select(AgentConfig)
                .where(AgentConfig.store_id.in_(store_ids), AgentConfig.deleted_at.is_(None))
                .order_by(AgentConfig.created_at, AgentConfig.id)
            )
        ).all()
    )


async def find_config(
    session: AsyncSession,
    config_id: uuid.UUID,
    store_ids: set[uuid.UUID],
) -> AgentConfig | None:
    if not store_ids:
        return None
    return cast(
        AgentConfig | None,
        await session.scalar(
            select(AgentConfig).where(
                AgentConfig.id == config_id,
                AgentConfig.store_id.in_(store_ids),
                AgentConfig.deleted_at.is_(None),
            )
        ),
    )


async def find_enabled_config(session: AsyncSession, store_id: uuid.UUID) -> AgentConfig | None:
    return cast(
        AgentConfig | None,
        await session.scalar(
            select(AgentConfig).where(
                AgentConfig.store_id == store_id,
                AgentConfig.status == "enabled",
                AgentConfig.deleted_at.is_(None),
            )
        ),
    )


async def list_run_logs(
    session: AsyncSession,
    config: AgentConfig,
    page: int,
    page_size: int,
    start: datetime | None,
    end: datetime | None,
) -> tuple[list[tuple[AgentRun, list[ToolCall]]], int]:
    conditions = [
        AgentRun.store_id == config.store_id,
        or_(AgentRun.agent_config_id == config.id, AgentRun.agent_config_id.is_(None)),
    ]
    if start is not None:
        conditions.append(AgentRun.created_at >= start)
    if end is not None:
        conditions.append(AgentRun.created_at <= end)
    total = await session.scalar(select(func.count()).select_from(AgentRun).where(*conditions)) or 0
    runs = list(
        (
            await session.scalars(
                select(AgentRun)
                .where(*conditions)
                .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    if not runs:
        return [], int(total)
    calls = list(
        (
            await session.scalars(
                select(ToolCall)
                .where(ToolCall.agent_run_id.in_([item.id for item in runs]))
                .order_by(ToolCall.created_at, ToolCall.id)
            )
        ).all()
    )
    grouped: dict[uuid.UUID, list[ToolCall]] = {}
    for call in calls:
        if call.agent_run_id is not None:
            grouped.setdefault(call.agent_run_id, []).append(call)
    return [(run, grouped.get(run.id, [])) for run in runs], int(total)
