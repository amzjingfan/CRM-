"""应用就绪探针，检查请求链路依赖但不泄露底层连接信息。"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal
from urllib.parse import urlsplit

import httpx
from minio import Minio
from pydantic import BaseModel
from sqlalchemy import text

from app.shared.config.settings import (
    REAL_DEPLOYMENT_ENVIRONMENTS,
    Settings,
    get_settings,
    has_non_blank_secret,
)
from app.shared.database.redis import redis_client
from app.shared.database.session import engine

ComponentStatus = Literal["ok", "disabled", "error"]


class ReadinessComponents(BaseModel):
    """依赖级低敏状态；不包含 URL、路径、凭证和异常正文。"""

    database: ComponentStatus
    redis: ComponentStatus
    object_storage: ComponentStatus
    retrieval_model: ComponentStatus
    llm_provider: ComponentStatus


class ReadinessReport(BaseModel):
    """就绪探针响应。"""

    status: Literal["ready", "not_ready"]
    components: ReadinessComponents


async def check_database() -> bool:
    """执行轻量查询验证 PostgreSQL 连接。"""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    return True


async def check_redis() -> bool:
    """验证 Redis 可以响应命令。"""
    return bool(await redis_client.ping())


async def check_object_storage() -> bool:
    """在线程中验证 MinIO 目标桶可访问，避免阻塞事件循环。"""
    settings = get_settings()
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    return await asyncio.to_thread(client.bucket_exists, settings.minio_bucket)


async def check_retrieval_model(settings: Settings) -> bool:
    """验证模型服务版本契约，不携带推理 Token 或模型本机路径。"""
    url = f"{settings.retrieval_model_service_url.rstrip('/')}/internal/health"
    async with httpx.AsyncClient(timeout=settings.readiness_timeout_seconds) as client:
        response = await client.get(url)
        response.raise_for_status()
        payload = response.json()
    return bool(
        isinstance(payload, dict)
        and payload.get("status") == "ok"
        and str(payload.get("embedding_model", "")).lower() in {"baai/bge-m3", "bge-m3"}
        and payload.get("dimensions") == 1024
    )


def check_llm_provider_configuration(settings: Settings) -> bool:
    """检查 LLM 运行配置是否完整，不调用收费接口也不展开任何密钥。"""
    provider = settings.llm_primary_provider.strip().lower()
    if not settings.llm_primary_model or not settings.llm_primary_model.strip():
        return False
    if provider == "deepseek":
        parsed = urlsplit(settings.deepseek_base_url)
        allowed_schemes = {"https"} if settings.app_env in REAL_DEPLOYMENT_ENVIRONMENTS else {"http", "https"}
        return (
            has_non_blank_secret(settings.deepseek_api_key)
            and parsed.scheme in allowed_schemes
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )
    if provider == "openai":
        return has_non_blank_secret(settings.openai_api_key)
    if provider == "anthropic":
        return has_non_blank_secret(settings.anthropic_api_key)
    return False


async def _safe_check(check: Callable[[], Awaitable[bool]], timeout_seconds: float) -> bool:
    """把依赖异常和超时收敛为不可用，响应中不回显底层细节。"""
    try:
        return bool(await asyncio.wait_for(check(), timeout=timeout_seconds))
    except Exception:  # noqa: BLE001 - 就绪探针必须稳定收敛所有基础设施异常
        return False


async def collect_readiness(settings: Settings | None = None) -> ReadinessReport:
    """并发检查必需依赖；AI 关闭时模型服务不作为启动门禁。"""
    current = settings or get_settings()
    database_ok, redis_ok, storage_ok = await asyncio.gather(
        _safe_check(check_database, current.readiness_timeout_seconds),
        _safe_check(check_redis, current.readiness_timeout_seconds),
        _safe_check(check_object_storage, current.readiness_timeout_seconds),
    )
    model_status: ComponentStatus = "disabled"
    if current.embedding_enabled:
        model_ok = await _safe_check(lambda: check_retrieval_model(current), current.readiness_timeout_seconds)
        model_status = "ok" if model_ok else "error"
    llm_status: ComponentStatus = "disabled"
    if current.llm_enabled:
        llm_status = "ok" if check_llm_provider_configuration(current) else "error"
    components = ReadinessComponents(
        database="ok" if database_ok else "error",
        redis="ok" if redis_ok else "error",
        object_storage="ok" if storage_ok else "error",
        retrieval_model=model_status,
        llm_provider=llm_status,
    )
    ready = all(value in {"ok", "disabled"} for value in components.model_dump().values())
    return ReadinessReport(status="ready" if ready else "not_ready", components=components)
