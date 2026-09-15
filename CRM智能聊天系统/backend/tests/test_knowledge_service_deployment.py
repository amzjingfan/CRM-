"""K2 独立部署、数据库与对象存储边界测试。"""

import json
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_compose_overlay_runs_independent_service_and_one_shot_initializers() -> None:
    compose_path = PROJECT_ROOT / "docker-compose.knowledge.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = compose["services"]

    assert {"knowledge-db-bootstrap", "knowledge-migrations", "knowledge-minio-init", "knowledge-service"} <= set(
        services
    )
    knowledge_service = services["knowledge-service"]
    assert "env_file" not in knowledge_service
    assert "app.knowledge_service.main:create_configured_app" in " ".join(knowledge_service["command"])
    assert knowledge_service["environment"]["KNOWLEDGE_DATABASE_URL"].endswith("/company_knowledge")
    assert knowledge_service["environment"]["KNOWLEDGE_OBJECT_STORE_BUCKET"] == "company-knowledge"
    assert services["knowledge-migrations"]["command"][-2:] == ["upgrade", "head"]
    assert services["postgres"]["healthcheck"]["start_period"] == "120s"
    assert services["postgres"]["healthcheck"]["retries"] >= 30
    assert all(volume.endswith(":ro") for volume in knowledge_service["volumes"])
    assert all(volume.endswith(":ro") for volume in services["knowledge-migrations"]["volumes"])
    assert "KNOWLEDGE_APPLICATION_VERIFICATION_KEYS_JSON" in knowledge_service["environment"]
    assert "KNOWLEDGE_DELEGATION_VERIFICATION_KEYS_JSON" in knowledge_service["environment"]


def test_database_bootstrap_uses_separate_database_and_least_privilege_roles() -> None:
    sql = (PROJECT_ROOT / "deploy/postgres/bootstrap-company-knowledge.sql").read_text(encoding="utf-8")

    assert "company_knowledge" in sql
    assert "knowledge_migration" in sql
    assert "knowledge_runtime" in sql
    assert "ALTER DEFAULT PRIVILEGES" in sql
    assert "GRANT SELECT ON TABLES TO knowledge_runtime" in sql
    assert "GRANT SELECT ON ALL TABLES IN SCHEMA public TO knowledge_runtime" in sql
    assert "GRANT INSERT ON TABLE kb_audit_events TO knowledge_runtime" in sql
    assert "GRANT SELECT, INSERT, UPDATE, DELETE" not in sql
    assert "REVOKE INSERT, UPDATE, DELETE ON TABLES FROM knowledge_runtime" in sql
    assert "REVOKE ALL ON ALL TABLES" in sql
    assert "CREATE TABLE" not in sql
    assert "crm.users" not in sql
    assert "crm.stores" not in sql


def test_minio_policy_is_limited_to_company_knowledge_bucket() -> None:
    policy = json.loads(
        (PROJECT_ROOT / "deploy/minio/company-knowledge-policy.json").read_text(encoding="utf-8")
    )
    resources = [resource for statement in policy["Statement"] for resource in statement["Resource"]]

    assert resources
    assert all(resource.startswith("arn:aws:s3:::company-knowledge") for resource in resources)
    assert not any("crm-files" in resource or resource == "arn:aws:s3:::*" for resource in resources)


def test_example_environment_uses_only_dedicated_knowledge_names() -> None:
    example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    assert "KNOWLEDGE_DATABASE_URL=" in example
    assert "/company_knowledge" in example
    assert "KNOWLEDGE_OBJECT_STORE_BUCKET=company-knowledge" in example
    assert "KNOWLEDGE_APPLICATION_VERIFICATION_KEYS_JSON=" in example
    assert "KNOWLEDGE_DELEGATION_VERIFICATION_KEYS_JSON=" in example
