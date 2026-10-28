"""FastAPI 应用入口和 Phase 1 基础健康检查。"""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.core.factory import build_shared_agent_runtime
from app.api.v1.router import router as v1_router
from app.integrations.tiktok_read import close_tiktok_read_http_pool, read_timing
from app.shared.config.settings import get_settings
from app.shared.exceptions.errors import AppError
from app.shared.health import ReadinessReport, collect_readiness
from app.shared.logging.setup import configure_logging
from app.shared.schemas.responses import ApiResponse

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """管理应用生命周期内的模型连接池。"""
    lifecycle_trace_id = str(uuid.uuid4())
    # 生产配置在 Settings 构建阶段统一失败关闭。这里不再因为 Mock 被禁用而
    # 阻止只读管理能力启动；平台调用仍由适配器和独立真实能力开关双重保护。
    logger.info(
        "应用启动 app_name=%s version=%s",
        settings.app_name,
        settings.app_version,
        extra={"trace_id": lifecycle_trace_id, "event": "application_started"},
    )
    runtime = build_shared_agent_runtime(settings)
    application.state.agent_runtime = runtime
    try:
        yield
    finally:
        try:
            if runtime is not None:
                await runtime.aclose()
        finally:
            await close_tiktok_read_http_pool()
            application.state.agent_runtime = None
            logger.info("应用关闭", extra={"trace_id": lifecycle_trace_id, "event": "application_stopped"})


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    description=(
        "CRM 智能聊天系统 Phase 4 API。所有业务资源按 store_id 做服务端隔离，跨店铺资源统一返回 40401；"
        "写操作使用 Idempotency-Key，重复请求返回原结果或 40901 冲突。外部平台写操作在 Mock 模式下会返回 mocked 标识，"
        "异步知识库导入和主动营销任务返回任务/事件状态。接口统一返回 {code, message, data}，常见错误码包括 "
        "40001、40101、40102、40301、40401、40901、42901、50001 和 50003。"
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(v1_router, prefix="/v1")


@app.middleware("http")
async def add_trace_id(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """为每个请求生成追踪 ID；仅沿用格式合法的客户端 UUID。"""
    raw_trace_id = request.headers.get("X-Trace-Id")
    try:
        # 客户端 Header 属于不可信输入。只接受标准 UUID，避免任意正文进入
        # Agent 运行记录、响应 Header 和生产日志的低敏追踪字段。
        trace_id = str(uuid.UUID(raw_trace_id)) if raw_trace_id else str(uuid.uuid4())
        if raw_trace_id and raw_trace_id != trace_id:
            raise ValueError("Trace ID 不是规范 UUID")
    except (ValueError, AttributeError):
        trace_id = str(uuid.uuid4())
    request.state.trace_id = trace_id
    started = time.perf_counter()
    timing = {"count": 0, "ms": 0}
    token = read_timing.set(timing)
    timeout_exempt = (
        request.url.path == "/v1/chat/query"
        or request.url.path.startswith("/v1/webhooks/")
        or request.url.path == "/v1/knowledge/imports"
    )
    try:
        try:
            if timeout_exempt:
                response = await call_next(request)
            else:
                response = await asyncio.wait_for(call_next(request), timeout=settings.request_timeout_seconds)
        except TimeoutError:
            logger.warning("请求超时", extra={"trace_id": trace_id, "event": "request_timeout"})
            response = JSONResponse(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                content=ApiResponse(code=50003, message="请求处理超时", data=None).model_dump(),
            )
    finally:
        read_timing.reset(token)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    route = request.scope.get("route")
    route_template = getattr(route, "path", "unmatched")
    logger.info(
        "api_request_timing route=%s method=%s status=%s app_ms=%s tiktok_ms=%s tiktok_calls=%s",
        route_template,
        request.method,
        response.status_code,
        elapsed_ms,
        timing["ms"],
        timing["count"],
        extra={"trace_id": trace_id, "event": "api_request_timing"},
    )
    response.headers["Server-Timing"] = f"app;dur={elapsed_ms}, tiktok;dur={timing['ms']}"
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.exception_handler(AppError)
async def handle_app_error(_: Request, error: AppError) -> JSONResponse:
    """将业务异常转换为稳定的 JSON 错误结构。"""
    return JSONResponse(
        status_code=error.status_code,
        content=ApiResponse(code=error.numeric_code, message=error.message, data=None).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
    """将 Pydantic 参数错误转换为不泄露内部堆栈的统一响应。"""
    logger.warning(
        "请求参数校验失败 count=%s",
        len(error.errors()),
        extra={"trace_id": getattr(request.state, "trace_id", str(uuid.uuid4())), "event": "validation_failed"},
    )
    return JSONResponse(
        status_code=422,
        content=ApiResponse(code=40001, message="请求参数校验失败", data=None).model_dump(),
    )


@app.exception_handler(Exception)
async def handle_internal_error(request: Request, error: Exception) -> JSONResponse:
    """隐藏未处理异常细节，同时保留 trace_id 供服务端定位。"""
    logger.exception(
        "未处理异常 error_type=%s",
        type(error).__name__,
        extra={"trace_id": getattr(request.state, "trace_id", str(uuid.uuid4())), "event": "internal_error"},
    )
    return JSONResponse(
        status_code=500,
        content=ApiResponse(code=50001, message="系统内部错误", data=None).model_dump(),
    )


@app.get("/v1/health", response_model=ApiResponse[dict[str, str]])
async def health_check() -> ApiResponse[dict[str, str]]:
    """返回应用存活状态。"""
    return ApiResponse(data={"status": "ok", "version": settings.app_version})


@app.get("/v1/health/ready", response_model=ApiResponse[ReadinessReport])
async def readiness_check(response: Response) -> ApiResponse[ReadinessReport]:
    """返回数据库、缓存、对象存储和可选本地模型服务的真实就绪状态。"""
    report = await collect_readiness(settings)
    if report.status == "not_ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ApiResponse(code=50003, message="服务依赖尚未就绪", data=report)
    return ApiResponse(data=report)
