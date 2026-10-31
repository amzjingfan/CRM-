"""AI 建议 JSON 和 SSE 传输接口。"""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime
from typing import Annotated, cast

import anyio
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.agents.core.factory import SharedAgentRuntime
from app.agents.orchestration.service import RunProgress
from app.auth.dependencies import get_current_user, require_csrf, require_permission
from app.chat.auto_preview import AutoPreviewView, get_auto_preview
from app.chat.schemas import ChatQueryRequest, SuggestionRequest, SuggestionView
from app.chat.service import (
    mark_suggestion_delivery_interrupted,
    reconcile_cancelled_sse_agent_run,
    record_first_output_latency,
    suggest_for_user,
)
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.database.redis import (
    acquire_chat_stream,
    consume_chat_query,
    release_chat_stream,
)
from app.shared.database.session import DbSession
from app.shared.exceptions.errors import AppError, ErrorCode
from app.shared.schemas.responses import ApiResponse

router = APIRouter(tags=["AI 建议与 SSE"])
logger = logging.getLogger(__name__)
SUGGEST_DESCRIPTION = "权限：workspace.view；按会话的 store_id 服务端隔离。仅读取可信上下文，不执行写工具或自动发送。"
SSE_DESCRIPTION = (
    "权限：workspace.view；Cookie 认证写请求需 Origin 和 CSRF。POST SSE 返回 "
    "accepted/status/delta/result/error/done，等待期间使用无业务数据的注释心跳，总超时后以 "
    "error + done(timeout) 结束；delta 为安全草稿完成后的传输层分块。"
)


@router.get(
    "/workspace/sessions/{session_id}/auto-preview",
    response_model=ApiResponse[AutoPreviewView | None],
    dependencies=[Depends(require_permission("workspace.view"))],
)
async def auto_preview(
    session_id: uuid.UUID, session: DbSession, user: Annotated[User, Depends(get_current_user)]
) -> ApiResponse[AutoPreviewView | None]:
    return ApiResponse(data=await get_auto_preview(session, user, session_id))


def _agent_runtime(request: Request) -> SharedAgentRuntime | None:
    """从当前进程获取共享连接池；独立测试请求可继续走请求级路径。"""
    state = getattr(getattr(request, "app", None), "state", None)
    return cast(SharedAgentRuntime | None, getattr(state, "agent_runtime", None))


def _event(name: str, sequence: int, data: dict[str, object]) -> str:
    return f"id: {sequence}\nevent: {name}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def _cancel_task(task: asyncio.Task[SuggestionView]) -> None:
    """取消仍在运行的工作流并等待清理完成，避免断线后继续消耗模型配额。"""
    if task.done():
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


async def _enforce_chat_limits(request: Request, user: User) -> None:
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    if not await consume_chat_query(user.id, client_ip, settings.chat_query_limit, settings.chat_query_window_seconds):
        raise AppError(ErrorCode.RATE_LIMITED, "AI 建议请求过于频繁", 429)


@router.post(
    "/workspace/sessions/{session_id}/suggest",
    response_model=ApiResponse[SuggestionView],
    description=SUGGEST_DESCRIPTION,
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.view"))],
)
async def suggest(
    session_id: uuid.UUID,
    payload: SuggestionRequest,
    request: Request,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[SuggestionView]:
    await _enforce_chat_limits(request, user)
    trace_id = str(getattr(request.state, "trace_id", uuid.uuid4()))
    return ApiResponse(
        data=await suggest_for_user(
            session, user, session_id, payload.trigger_message_id, trace_id, _agent_runtime(request)
        )
    )


@router.post(
    "/chat/query",
    dependencies=[Depends(require_csrf), Depends(require_permission("workspace.view"))],
    response_class=StreamingResponse,
    description=SSE_DESCRIPTION,
)
async def chat_query(
    payload: ChatQueryRequest,
    request: Request,
    session: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """先输出阶段事件，Agent 返回安全草稿后再做传输层分块。"""
    settings = get_settings()
    g5_timing_enabled = getattr(settings, "sse_load_test_enabled", False)
    limit_started_at = time.perf_counter_ns()
    await _enforce_chat_limits(request, user)
    if g5_timing_enabled:
        logger.info(
            "g5_chat_limit_timing",
            extra={
                "event": "g5_chat_limit_timing",
                "trace_id": str(getattr(request.state, "trace_id", "")),
                "latency_ms": max(0, (time.perf_counter_ns() - limit_started_at) // 1_000_000),
            },
        )
    lease_started_at = time.perf_counter_ns()
    stream_lease_token = await acquire_chat_stream(
        user.id,
        settings.chat_user_concurrency,
        settings.chat_stream_lease_seconds,
    )
    if g5_timing_enabled:
        logger.info(
            "g5_chat_lease_timing",
            extra={
                "event": "g5_chat_lease_timing",
                "trace_id": str(getattr(request.state, "trace_id", "")),
                "latency_ms": max(0, (time.perf_counter_ns() - lease_started_at) // 1_000_000),
            },
        )
    if stream_lease_token is None:
        raise AppError(ErrorCode.RATE_LIMITED, "同时进行的 AI 建议过多", 429)
    request_id = str(uuid.uuid4())
    trace_id = str(getattr(request.state, "trace_id", request_id))

    async def stream() -> AsyncIterator[str]:
        sequence = 1
        result: SuggestionView | None = None
        result_handed_to_transport = False
        workflow_task: asyncio.Task[SuggestionView] | None = None
        stream_started_at = time.perf_counter()
        stream_started_at_utc = datetime.now(UTC)
        first_output_latency_ms: int | None = None
        terminal_event_emitted = False
        cancellation_reconcile_needed = False
        drafts: asyncio.Queue[tuple[int, str]] = asyncio.Queue(maxsize=64)

        async def on_draft(index: int, text: str) -> None:
            # 快照可合并，避免慢客户端积压逐Token副本；最终答复仍完整交付。
            if drafts.full():
                drafts.get_nowait()
            drafts.put_nowait((index, text))

        async def run_suggestion() -> SuggestionView:
            if payload.reply_mode == "review_plan":
                return await suggest_for_user(
                    session,
                    user,
                    payload.session_id,
                    payload.trigger_message_id,
                    trace_id,
                    _agent_runtime(request),
                    reply_progress=RunProgress(reply_plan=True, on_draft=on_draft),
                )
            return await suggest_for_user(
                session,
                user,
                payload.session_id,
                payload.trigger_message_id,
                trace_id,
                _agent_runtime(request),
            )

        async def mark_interrupted(error_code: str) -> None:
            if result is not None and not result_handed_to_transport:
                await mark_suggestion_delivery_interrupted(session, result.agent_run_id, error_code)

        def log_disconnected() -> None:
            logger.info(
                "chat_stream_disconnected",
                extra={
                    "event": "chat_stream_disconnected",
                    "trace_id": trace_id,
                    "total_latency_ms": int((time.perf_counter() - stream_started_at) * 1000),
                },
            )

        try:
            yield _event("accepted", sequence, {"request_id": request_id, "trace_id": trace_id})
            sequence += 1
            yield _event("status", sequence, {"stage": "context_loading"})
            sequence += 1
            yield _event("status", sequence, {"stage": "agent_running"})
            sequence += 1
            agent_started_at = time.perf_counter()
            workflow_task = asyncio.create_task(run_suggestion())
            # 允许无 I/O 的工作流测试替身先完成；真实工作流一旦等待外部依赖，
            # 后续循环便可及时感知浏览器断线并取消模型调用。
            await asyncio.sleep(0)
            deadline = agent_started_at + settings.chat_stream_timeout_seconds
            next_heartbeat = agent_started_at + settings.chat_sse_heartbeat_seconds
            while not workflow_task.done():
                if await request.is_disconnected():
                    cancellation_reconcile_needed = True
                    await _cancel_task(workflow_task)
                    terminal_event_emitted = True
                    log_disconnected()
                    return
                while not drafts.empty():
                    part_index, text = drafts.get_nowait()
                    yield _event(
                        "draft",
                        sequence,
                        {
                            "part_index": part_index,
                            "text": text,
                            "replace": True,
                            "unverified": True,
                            "sendable": False,
                            "trigger_message_id": str(payload.trigger_message_id)
                            if payload.trigger_message_id
                            else None,
                        },
                    )
                    sequence += 1
                now = time.perf_counter()
                if now >= deadline:
                    cancellation_reconcile_needed = True
                    await _cancel_task(workflow_task)
                    terminal_event_emitted = True
                    logger.warning(
                        "chat_stream_timeout",
                        extra={
                            "event": "chat_stream_timeout",
                            "trace_id": trace_id,
                            "error_code": "CHAT_STREAM_TIMEOUT",
                            "total_latency_ms": int((time.perf_counter() - stream_started_at) * 1000),
                        },
                    )
                    yield _event(
                        "error",
                        sequence,
                        {"code": 50003, "message": "AI 建议生成超时，请稍后重试", "retryable": True},
                    )
                    yield _event("done", sequence + 1, {"reason": "timeout"})
                    return
                wait_seconds = min(1.0, deadline - now, max(0.01, next_heartbeat - now))
                await asyncio.wait({workflow_task}, timeout=wait_seconds)
                now = time.perf_counter()
                if not workflow_task.done() and now >= next_heartbeat:
                    # SSE 注释行不会改变现有事件契约，只用于让代理和浏览器确认连接仍存活。
                    yield ": keep-alive\n\n"
                    next_heartbeat = now + settings.chat_sse_heartbeat_seconds
            result = await workflow_task
            if await request.is_disconnected():
                await mark_interrupted("SSE_DELIVERY_INTERRUPTED")
                terminal_event_emitted = True
                log_disconnected()
                yield _event("done", sequence, {"reason": "disconnected"})
                return
            first_output_latency_ms = int((time.perf_counter() - agent_started_at) * 1000)
            metric_started_at = time.perf_counter_ns()
            await record_first_output_latency(session, result.agent_run_id, first_output_latency_ms)
            if g5_timing_enabled:
                logger.info(
                    "g5_chat_first_output_persist_timing",
                    extra={
                        "event": "g5_chat_first_output_persist_timing",
                        "trace_id": trace_id,
                        "latency_ms": max(0, (time.perf_counter_ns() - metric_started_at) // 1_000_000),
                    },
                )
            yield _event("status", sequence, {"stage": "finalizing"})
            sequence += 1
            content = result.content or ""
            for index in range(0, len(content), 24):
                if await request.is_disconnected():
                    await mark_interrupted("SSE_DELIVERY_INTERRUPTED")
                    terminal_event_emitted = True
                    log_disconnected()
                    yield _event("done", sequence, {"reason": "disconnected"})
                    return
                yield _event("delta", sequence, {"index": index // 24, "text": content[index : index + 24]})
                sequence += 1
                await asyncio.sleep(0)
            if await request.is_disconnected():
                await mark_interrupted("SSE_DELIVERY_INTERRUPTED")
                terminal_event_emitted = True
                log_disconnected()
                yield _event("done", sequence, {"reason": "disconnected"})
                return
            result_handed_to_transport = True
            terminal_event_emitted = True
            yield _event("result", sequence, result.model_dump(mode="json"))
            sequence += 1
            yield _event("done", sequence, {"reason": "completed"})
            logger.info(
                "chat_stream_completed",
                extra={
                    "event": "chat_stream_completed",
                    "trace_id": trace_id,
                    "agent_run_id": str(result.agent_run_id),
                    "first_output_latency_ms": first_output_latency_ms,
                    "total_latency_ms": int((time.perf_counter() - stream_started_at) * 1000),
                },
            )
        except asyncio.CancelledError:
            cancellation_reconcile_needed = True
            if workflow_task is not None:
                await _cancel_task(workflow_task)
            await mark_interrupted("SSE_DELIVERY_CANCELLED")
            return
        except AppError as error:
            await mark_interrupted("SSE_DELIVERY_FAILED")
            terminal_event_emitted = True
            yield _event(
                "error",
                sequence,
                {"code": error.numeric_code, "message": error.message, "retryable": error.status_code >= 500},
            )
            yield _event("done", sequence + 1, {"reason": "failed"})
        except Exception:
            await mark_interrupted("SSE_DELIVERY_FAILED")
            terminal_event_emitted = True
            logger.exception(
                "chat_stream_failed",
                extra={
                    "event": "chat_stream_failed",
                    "trace_id": trace_id,
                    "error_code": "CHAT_STREAM_ERROR",
                    "total_latency_ms": int((time.perf_counter() - stream_started_at) * 1000),
                },
            )
            yield _event("error", sequence, {"code": 50001, "message": "AI 建议生成失败", "retryable": True})
            yield _event("done", sequence + 1, {"reason": "failed"})
        finally:
            if not terminal_event_emitted:
                # ASGI 传输层可能直接关闭生成器；异步清理可被取消，须先记录固定终态。
                logger.info(
                    "chat_stream_closed_early",
                    extra={
                        "event": "chat_stream_closed_early",
                        "trace_id": trace_id,
                        "total_latency_ms": int((time.perf_counter() - stream_started_at) * 1000),
                    },
                )
                cancellation_reconcile_needed = workflow_task is not None
            # Starlette/AnyIO 的断连取消作用域会取消其中每一次 await；
            # 清理必须屏蔽该作用域，才能完成独立审计事务并释放租约。
            with anyio.CancelScope(shield=True):
                try:
                    if workflow_task is not None and not workflow_task.done():
                        await _cancel_task(workflow_task)
                finally:
                    try:
                        if cancellation_reconcile_needed and not result_handed_to_transport:
                            try:
                                updated = await reconcile_cancelled_sse_agent_run(
                                    user, payload.session_id, trace_id, stream_started_at_utc
                                )
                            except Exception as error:
                                logger.error(
                                    "chat_stream_agent_cancel_reconcile_failed",
                                    extra={
                                        "event": "chat_stream_agent_cancel_reconcile_failed",
                                        "trace_id": trace_id,
                                        "error_type": type(error).__name__,
                                    },
                                )
                                raise
                            logger.info(
                                "chat_stream_agent_cancel_reconciled",
                                extra={
                                    "event": "chat_stream_agent_cancel_reconciled",
                                    "trace_id": trace_id,
                                    "updated": updated,
                                },
                            )
                    finally:
                        await release_chat_stream(user.id, stream_lease_token)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
