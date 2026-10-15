"""staging DeepSeek 传输探针只能执行无凭据、无模型调用的只读检查。"""

import ast
import http.client
import importlib
import json
import socket
import ssl
from pathlib import Path
from types import SimpleNamespace

import pytest
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
    assert "DEEPSEEK_API_KEY" not in source
    assert "Authorization" not in source
    assert "docker --host $dockerHost exec -i" in source
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


def test_request_path_probe_requires_explicit_mode_and_has_no_credentials() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "probe_mode:" in source
    assert "default: transport" in source
    assert "request_path" in source
    assert "https://api.deepseek.com/chat/completions" in source
    assert 'body=b"{}"' in source
    assert "DEEPSEEK_API_KEY" not in source
    assert "Authorization" not in source
    assert "response.read(" not in source
    assert "curl -q" in source
    assert "if ($requestHttpClass -eq '2xx' -or $backendRequestHttpClass -eq '2xx')" in source


def test_request_path_evidence_is_fixed_and_bucketed() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "$requestProbeCode = @'" in source
    assert "request_to_first_byte" in source
    assert "total_duration" in source
    assert "dns_duration" in source
    assert "tcp_duration" in source
    assert "tls_duration" in source
    assert "0-100ms" in source
    assert "101-500ms" in source
    assert "501-2000ms" in source
    assert "2001-7000ms" in source
    assert ">7000ms" in source
    assert "not_reached" in source
    assert "http_status_class" in source
    assert "status_code =" not in source
    assert "response_body" not in source
    assert "proxy_address" not in source
    workflow = yaml.safe_load(source)
    run = workflow["jobs"]["diagnose"]["steps"][0]["run"]
    request_script = run.split("$requestProbeCode = @'\n", 1)[1].split("\n'@", 1)[0]
    ast.parse(request_script)


def test_request_path_probe_sends_only_empty_unauthenticated_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    run = workflow["jobs"]["diagnose"]["steps"][0]["run"]
    script = run.split("$requestProbeCode = @'\n", 1)[1].split("\n'@", 1)[0]
    sent: list[tuple[str, str, bytes, dict[str, str]]] = []
    monkeypatch.syspath_prepend(str(WORKFLOW.parents[2] / "src/backend"))
    settings_module = importlib.import_module("app.shared.config.settings")

    class FakeSocket:
        def settimeout(self, _timeout: float) -> None:
            pass

        def connect(self, _address: object) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeConnection:
        sock: FakeSocket | None = None

        def request(self, method: str, path: str, *, body: bytes, headers: dict[str, str]) -> None:
            sent.append((method, path, body, headers))

        def getresponse(self) -> SimpleNamespace:
            return SimpleNamespace(status=401)

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        settings_module, "get_settings", lambda: SimpleNamespace(deepseek_base_url="https://api.deepseek.com")
    )
    for name in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [(2, 1, 0, "", ("127.0.0.1", 443))])
    monkeypatch.setattr(socket, "socket", lambda *_args: FakeSocket())
    monkeypatch.setattr(ssl, "create_default_context", lambda: SimpleNamespace(wrap_socket=lambda raw, **_kwargs: raw))
    monkeypatch.setattr(http.client, "HTTPSConnection", lambda *_args, **_kwargs: FakeConnection())

    exec(script, {"__name__": "__main__"})
    result = json.loads(capsys.readouterr().out)
    assert sent == [("POST", "/chat/completions", b"{}", {"Content-Type": "application/json"})]
    assert result["category"] == "http_response"
    assert result["http_status_class"] == "4xx"
    assert set(result) == {
        "category",
        "http_status_class",
        "dns_duration",
        "tcp_duration",
        "tls_duration",
        "request_to_first_byte",
        "total_duration",
    }
