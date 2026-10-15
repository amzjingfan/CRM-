"""staging DeepSeek 传输探针只能执行无凭据、无模型调用的只读检查。"""

import ast
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parents[4] / ".github/workflows/diagnose-staging-deepseek-transport.yml"


def test_transport_probe_is_read_only_and_staging_only() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in source
    assert "environment: staging" in source
    assert "runs-on: [self-hosted, linux, x64, crm-staging]" in source
    assert "contents: read" in source
    assert "refs/heads/main" in source
    assert "EXPECTED_BACKEND_IMAGE" in source
    assert "chat/completions" not in source
    assert "DEEPSEEK_API_KEY" not in source
    assert "Authorization" not in source
    assert "docker --host $dockerHost exec -i" in source
    assert "-X POST" not in source
    assert "docker restart" not in source
    assert "docker compose" not in source


def test_transport_probe_limits_evidence_to_fixed_categories() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "api.deepseek.com" in source
    assert 'method="HEAD"' in source
    assert "socket.getaddrinfo" in source
    assert "socket.create_connection" in source
    assert "ssl.create_default_context" in source
    assert "https_proxy_present" in source
    assert "dns_status" in source
    assert "tcp_status" in source
    assert "tls_status" in source
    assert "http_status_class" in source
    assert "response.body" not in source
    assert "response.text" not in source
    assert "Write-Output $probe" not in source


def test_in_container_probe_is_valid_python() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    run = workflow["jobs"]["diagnose"]["steps"][0]["run"]
    script = run.split("$probeCode = @'\n", 1)[1].split("\n'@", 1)[0]
    ast.parse(script)
