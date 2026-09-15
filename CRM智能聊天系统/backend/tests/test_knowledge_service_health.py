"""独立知识服务健康契约测试。"""

from fastapi.testclient import TestClient

from app.knowledge_service.main import create_app


def test_liveness_is_independent_from_crm_router() -> None:
    """独立进程只暴露内部健康入口，不挂载 CRM 公共路由。"""
    with TestClient(create_app()) as client:
        response = client.get("/internal/health/live")
        crm_response = client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "company-knowledge-service"}
    assert crm_response.status_code == 404


def test_readiness_reports_configuration_boundary() -> None:
    """K2 就绪检查返回独立服务与数据库标识。"""
    with TestClient(create_app()) as client:
        response = client.get("/internal/health/ready")

    assert response.status_code == 200
    assert response.json()["service"] == "company-knowledge-service"
    assert response.json()["database"] == "company_knowledge"


def test_readiness_fails_closed_when_dependency_probe_fails() -> None:
    class FailingProbe:
        async def check(self) -> None:
            raise RuntimeError("database unavailable")

    with TestClient(create_app(readiness_probe=FailingProbe())) as client:
        response = client.get("/internal/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
