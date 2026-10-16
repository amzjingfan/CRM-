"""现有 staging 私有凭证池的只读身份与会话预检。"""

import json
import uuid
from pathlib import Path

import httpx
import pytest

from scripts import preflight_sse_staging_fixture


@pytest.mark.asyncio
async def test_preflight_checks_fifty_distinct_users_and_sessions_with_get_only(tmp_path: Path) -> None:
    rows = [
        {
            "access_token": f"secret-access-{index}",
            "csrf_token": f"secret-csrf-{index}",
            "session_id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
        }
        for index in range(50)
    ]
    credential_file = tmp_path / "pool.json"
    credential_file.write_text(json.dumps({"clients": rows}), encoding="utf-8")
    requests: list[tuple[str, str]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        token = request.headers["cookie"].split("crm_access_token=")[1].split(";")[0]
        row = rows[int(token.removeprefix("secret-access-"))]
        if request.url.path == "/v1/auth/me":
            return httpx.Response(
                200, json={"code": 0, "data": {"id": row["user_id"], "permissions": ["workspace.view"]}}
            )
        assert request.url.path == f"/v1/workspace/sessions/{row['session_id']}/messages"
        return httpx.Response(200, json={"code": 0, "data": {"session": {"id": row["session_id"]}, "messages": []}})

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(respond)) as client:
        report = await preflight_sse_staging_fixture.preflight_clients(credential_file, client)

    assert report == {
        "mode": "preflight",
        "required_clients": 50,
        "distinct_authorized_users": 50,
        "ready": True,
        "failures": {},
        "provider_calls": 0,
    }
    assert len(requests) == 100
    assert all(method == "GET" for method, _ in requests)
    assert "secret-" not in json.dumps(report)


@pytest.mark.asyncio
async def test_preflight_redacts_invalid_credentials_and_unexpected_transport_error(tmp_path: Path) -> None:
    credential_file = tmp_path / "pool.json"
    credential_file.write_text("secret-marker-{", encoding="utf-8")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        invalid = await preflight_sse_staging_fixture.preflight_clients(credential_file, client)
    assert invalid["failures"] == {"credentials_invalid": 1}
    assert "secret-marker" not in json.dumps(invalid)

    rows = [
        {"access_token": f"secret-{index}", "csrf_token": f"csrf-{index}", "session_id": str(uuid.uuid4())}
        for index in range(50)
    ]
    credential_file.write_text(json.dumps({"clients": rows}), encoding="utf-8")

    def fail(_request: httpx.Request) -> httpx.Response:
        raise RuntimeError("secret-marker-provider-detail")

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(fail)) as client:
        report = await preflight_sse_staging_fixture.preflight_clients(credential_file, client)
    assert report["failures"] == {"internal_error": 1}
    assert "secret-marker" not in json.dumps(report)
