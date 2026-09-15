"""工具调用幂等记录持久化。"""

import hashlib
import json
import time
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.exceptions.errors import AppError, ErrorCode
from app.tools.models import ToolCall

TERMINAL_STATUSES = {"succeeded", "failed", "timeout", "unknown"}


def request_hash(tool_name: str, arguments: dict[str, object]) -> str:
    """对标准化参数计算摘要，正文不写入日志。"""
    encoded = json.dumps({"tool": tool_name, "arguments": arguments}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


async def begin_tool_call(
    session: AsyncSession,
    store_id: uuid.UUID,
    actor_type: str,
    actor_id: uuid.UUID | None,
    tool_name: str,
    idempotency_key: str,
    arguments: dict[str, object],
    input_summary: dict[str, object],
    agent_run_id: uuid.UUID | None = None,
    trace_id: str | None = None,
) -> tuple[ToolCall, bool, float]:
    """原子建立幂等记录；同键不同请求和在途重复均默认拒绝。"""
    digest = request_hash(tool_name, arguments)
    existing = await session.scalar(
        select(ToolCall).where(ToolCall.store_id == store_id, ToolCall.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_hash != digest:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "幂等键已用于不同请求", 409)
        if existing.status not in TERMINAL_STATUSES:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "相同请求正在处理中", 409)
        return existing, True, time.perf_counter()
    call = ToolCall(
        store_id=store_id,
        agent_run_id=agent_run_id,
        actor_type=actor_type,
        actor_id=actor_id,
        tool_name=tool_name,
        idempotency_key=idempotency_key,
        request_hash=digest,
        status="running",
        input_summary=input_summary,
        trace_id=trace_id,
    )
    session.add(call)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(ErrorCode.RESOURCE_CONFLICT, "相同请求正在处理中", 409) from exc
    return call, False, time.perf_counter()


async def finish_tool_call(
    session: AsyncSession,
    call: ToolCall,
    started_at: float,
    status: str,
    output_summary: dict[str, object] | None,
    mocked: bool,
    error_code: str | None = None,
) -> None:
    """保存明确终态；未知外部结果使用 unknown，不能伪装为失败后安全可重试。"""
    call.status = status
    call.output_summary = output_summary
    call.error_code = error_code
    call.mocked = mocked
    call.latency_ms = int((time.perf_counter() - started_at) * 1000)
    await session.commit()
