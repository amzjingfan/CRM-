"""公司级独立知识服务 FastAPI 入口。"""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.knowledge_service.api import install_evidence_api
from app.knowledge_service.auth import TokenVerifier
from app.knowledge_service.authorization import KnowledgeAuthorizer
from app.knowledge_service.config import KnowledgeServiceSettings
from app.knowledge_service.database import create_knowledge_engine, create_session_factory
from app.knowledge_service.repository import SqlAlchemyAuditSink, SqlAlchemyAuthorityRepository
from app.knowledge_service.service import (
    AuditSink,
    DatabaseReadinessProbe,
    EvidenceSearcher,
    IndexUnavailableSearcher,
    ReadinessProbe,
)


def create_app(
    settings: KnowledgeServiceSettings | None = None,
    *,
    verifier: TokenVerifier | None = None,
    authorizer: KnowledgeAuthorizer | None = None,
    searcher: EvidenceSearcher | None = None,
    audit_sink: AuditSink | None = None,
    readiness_probe: ReadinessProbe | None = None,
) -> FastAPI:
    """创建不挂载 CRM 路由和状态的独立 ASGI 应用。"""
    configured = settings or KnowledgeServiceSettings()
    application = FastAPI(title="Company Knowledge Service", version="0.1.0")
    if authorizer is None or audit_sink is None:
        engine = create_knowledge_engine(configured)
        session_factory = create_session_factory(engine)
        authority_repository = SqlAlchemyAuthorityRepository(session_factory)
        authorizer = authorizer or KnowledgeAuthorizer(authority_repository)
        audit_sink = audit_sink or SqlAlchemyAuditSink(session_factory)

    install_evidence_api(
        application,
        settings=configured,
        verifier=verifier or TokenVerifier(configured),
        authorizer=authorizer,
        searcher=searcher or IndexUnavailableSearcher(),
        audit_sink=audit_sink,
    )

    @application.get("/internal/health/live", include_in_schema=False)
    async def liveness() -> dict[str, str]:
        return {"status": "ok", "service": configured.service_name}

    @application.get("/internal/health/ready", include_in_schema=False, response_model=None)
    async def readiness() -> dict[str, str] | JSONResponse:
        if readiness_probe is not None:
            try:
                await asyncio.wait_for(readiness_probe.check(), timeout=configured.authority_timeout_seconds)
            except Exception:
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "unavailable",
                        "service": configured.service_name,
                        "database": configured.database_name,
                    },
                )
        return {
            "status": "ok",
            "service": configured.service_name,
            "database": configured.database_name,
        }

    return application


def create_configured_app() -> FastAPI:
    """部署入口：强制使用 SQL 授权、SQL 审计和真实数据库就绪检查。"""
    settings = KnowledgeServiceSettings()
    engine = create_knowledge_engine(settings)
    session_factory = create_session_factory(engine)
    authority_repository = SqlAlchemyAuthorityRepository(session_factory)
    application = create_app(
        settings,
        verifier=TokenVerifier(settings),
        authorizer=KnowledgeAuthorizer(authority_repository),
        searcher=IndexUnavailableSearcher(),
        audit_sink=SqlAlchemyAuditSink(session_factory),
        readiness_probe=DatabaseReadinessProbe(session_factory),
    )
    application.state.knowledge_engine = engine
    return application


app = create_app()
