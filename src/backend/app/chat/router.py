"""AI 建议 JSON 和 SSE 传输接口。"""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.agent.factory import SharedAgentRuntime
from app.agent.workflow import AgentWorkflowExecutionError
from app.auth.dependencies import get_current_user, require_csrf, require_permission
from app.chat.schemas import ChatQueryRequest, SuggestionRequest, SuggestionView
from app.chat.service import mark_suggestion_delivery_interrupted, record_first_output_latency, suggest_for_user
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


def _agent_runtime(request: Request) -> SharedAgentRuntime | None:
    """从当前进程获取共享连接池；独立测试请求可继续走请求级路径。"""
    state = getattr(getattr(request, "app", None), "state", None)
    return cast(SharedAgentRuntime | None, getattr(state, "agent_runtime", None))


def _event(name: str, sequence: int, data: dict[str, object]) -> str:
    return f"id: {sequence}\nevent: {name}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _agent_error_payload(error_code: str) -> dict[str, object]:
    """把 AI 内部稳定错误收敛为不含供应商细节的 SSE 公开错误。"""
    if error_code in {"LLM_RATE_LIMITED", "EMBEDDING_RATE_LIMITED"}:
        return {"code": 42901, "message": "AI 服务请求受限，请稍后重试", "retryable": True}
    if error_code in {"LLM_TIMEOUT", "EMBEDDING_TIMEOUT", "RERANK_TIMEOUT"}:
        return {"code": 50003, "message": "AI 服务响应超时，请稍后重试", "retryable": True}
    if error_code in {
        "LLM_AUTHENTICATION_ERROR",
        "LLM_PERMISSION_DENIED",
        "LLM_INVALID_REQUEST",
        "LLM_CONFIGURATION_ERROR",
        "EMBEDDING_AUTHENTICATION_ERROR",
        "EMBEDDING_PERMISSION_DENIED",
        "EMBEDDING_INVALID_REQUEST",
        "EMBEDDING_CONFIGURATION_ERROR",
        "RERANK_AUTHENTICATION_ERROR",
        "RERANK_INVALID_REQUEST",
        "RERANK_CONFIGURATION_ERROR",
    }:
        return {"code": 50003, "message": "AI 服务配置不可用", "retryable": False}
    if error_code in {
        "LLM_CONNECTION_ERROR",
        "LLM_PROVIDER_ERROR",
        "LLM_OUTPUT_INVALID",
        "EMBEDDING_CONNECTION_ERROR",
        "EMBEDDING_PROVIDER_ERROR",
        "EMBEDDING_OUTPUT_INVALID",
        "RERANK_CONNECTION_ERROR",
        "RERANK_PROVIDER_ERROR",
        "RERANK_OUTPUT_INVALID",
    }:
        return {"code": 50003, "message": "AI 依赖暂时不可用，请稍后重试", "retryable": True}
    return {"code": 50001, "message": "AI 建议生成失败", "retryable": False}


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
        first_output_latency_ms: int | None = None

        async def mark_interrupted(error_code: str) -> None:
            if result is not None and not result_handed_to_transport:
                await mark_suggestion_delivery_interrupted(session, result.agent_run_id, error_code)

        try:
            yield _event("accepted", sequence, {"request_id": request_id, "trace_id": trace_id})
            sequence += 1
            yield _event("status", sequence, {"stage": "context_loading"})
            sequence += 1
            yield _event("status", sequence, {"stage": "agent_running"})
            sequence += 1
            agent_started_at = time.perf_counter()
            workflow_task = asyncio.create_task(
                suggest_for_user(
                    session,
                    user,
                    payload.session_id,
                    payload.trigger_message_id,
                    trace_id,
                    _agent_runtime(request),
                )
            )
            # 允许无 I/O 的工作流测试替身先完成；真实工作流一旦等待外部依赖，
            # 后续循环便可及时感知浏览器断线并取消模型调用。
            await asyncio.sleep(0)
            deadline = agent_started_at + settings.chat_stream_timeout_seconds
            next_heartbeat = agent_started_at + settings.chat_sse_heartbeat_seconds
            while not workflow_task.done():
                if await request.is_disconnected():
                    await _cancel_task(workflow_task)
                    logger.info(
                        "chat_stream_disconnected",
                        extra={
                            "event": "chat_stream_disconnected",
                            "trace_id": trace_id,
                            "total_latency_ms": int((time.perf_counter() - stream_started_at) * 1000),
                        },
                    )
                    return
                now = time.perf_counter()
                if now >= deadline:
                    await _cancel_task(workflow_task)
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
                yield _event("done", sequence, {"reason": "disconnected"})
                return
            first_output_latency_ms = int((time.perf_counter() - agent_started_at) * 1000)
            await record_first_output_latency(session, result.agent_run_id, first_output_latency_ms)
            yield _event("status", sequence, {"stage": "finalizing"})
            sequence += 1
            content = result.content or ""
            for index in range(0, len(content), 24):
                if await request.is_disconnected():
                    await mark_interrupted("SSE_DELIVERY_INTERRUPTED")
                    yield _event("done", sequence, {"reason": "disconnected"})
                    return
                yield _event("delta", sequence, {"index": index // 24, "text": content[index : index + 24]})
                sequence += 1
                await asyncio.sleep(0)
            if await request.is_disconnected():
                await mark_interrupted("SSE_DELIVERY_INTERRUPTED")
                yield _event("done", sequence, {"reason": "disconnected"})
                return
            result_handed_to_transport = True
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
            if workflow_task is not None:
                await _cancel_task(workflow_task)
            await mark_interrupted("SSE_DELIVERY_CANCELLED")
            return
        except AgentWorkflowExecutionError as error:
            await mark_interrupted("SSE_DELIVERY_FAILED")
            failure = _agent_error_payload(error.error_code)
            logger.warning(
                "chat_stream_agent_failed",
                extra={
                    "event": "chat_stream_agent_failed",
                    "trace_id": trace_id,
                    "agent_run_id": str(error.agent_run_id),
                    "error_code": error.error_code,
                    "total_latency_ms": int((time.perf_counter() - stream_started_at) * 1000),
                },
            )
            yield _event("error", sequence, failure)
            yield _event("done", sequence + 1, {"reason": "failed"})
        except AppError as error:
            await mark_interrupted("SSE_DELIVERY_FAILED")
            yield _event(
                "error",
                sequence,
                {"code": error.numeric_code, "message": error.message, "retryable": error.status_code >= 500},
            )
            yield _event("done", sequence + 1, {"reason": "failed"})
        except Exception:
            await mark_interrupted("SSE_DELIVERY_FAILED")
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
