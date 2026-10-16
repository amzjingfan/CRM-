"""现有 G5 凭证的单令牌只读诊断。"""

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt
import pytest

from scripts import diagnose_sse_staging_auth


def credentials_file(tmp_path: Path, token: str) -> Path:
    path = tmp_path / "pool.json"
    path.write_text(
        json.dumps(
            {
                "clients": [
                    {
                        "access_token": token if index == 0 else f"other-{index}",
                        "csrf_token": f"csrf-{index}",
                        "session_id": str(uuid.uuid4()),
                    }
                    for index in range(50)
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def token(secret: str, *, expires_at: datetime) -> str:
    return jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "iat": datetime.now(UTC) - timedelta(minutes=1),
            "exp": expires_at,
            "jti": str(uuid.uuid4()),
        },
        secret,
        algorithm="HS256",
    )


@pytest.mark.asyncio
async def test_diagnostic_uses_one_get_and_only_fixed_categories(tmp_path: Path) -> None:
    secret = "staging-test-secret-with-more-than-32-bytes"
    signed = token(secret, expires_at=datetime.now(UTC) + timedelta(minutes=30))
    path = credentials_file(tmp_path, signed)
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(401, json={"detail": "secret-response-marker"})

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(respond)) as client:
        report = await diagnose_sse_staging_auth.diagnose(
            path, client, secret, "HS256", hashlib.sha256(secret.encode()).hexdigest(), "HS256"
        )

    assert report == {
        "mode": "diagnose_auth",
        "token_state": "valid",
        "runtime_key_match": True,
        "runtime_algorithm_match": True,
        "auth_http_status": "401",
        "requests_sent": 1,
        "provider_calls": 0,
    }
    assert [(request.method, request.url.path) for request in requests] == [("GET", "/v1/auth/me")]
    assert signed not in json.dumps(report)
    assert "secret-response-marker" not in json.dumps(report)


@pytest.mark.asyncio
async def test_diagnostic_reports_runtime_key_mismatch_without_exposing_digest(tmp_path: Path) -> None:
    secret = "staging-test-secret-with-more-than-32-bytes"
    signed = token(secret, expires_at=datetime.now(UTC) + timedelta(minutes=30))
    path = credentials_file(tmp_path, signed)
    runtime_digest = hashlib.sha256(b"different-runtime-secret").hexdigest()

    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000",
        transport=httpx.MockTransport(lambda _request: httpx.Response(401)),
    ) as client:
        report = await diagnose_sse_staging_auth.diagnose(path, client, secret, "HS256", runtime_digest, "HS256")

    assert report["token_state"] == "valid"
    assert report["runtime_key_match"] is False
    assert report["runtime_algorithm_match"] is True
    assert report["auth_http_status"] == "401"
    assert runtime_digest not in json.dumps(report)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("expired", "key_matches", "expected_state"),
    [(True, True, "expired"), (False, False, "signature_mismatch")],
)
async def test_diagnostic_separates_expiry_from_signing_key(
    tmp_path: Path, expired: bool, key_matches: bool, expected_state: str
) -> None:
    secret = "staging-test-secret-with-more-than-32-bytes"
    signer = secret if key_matches else "another-staging-test-secret-32-bytes"
    signed = token(signer, expires_at=datetime.now(UTC) + timedelta(minutes=-1 if expired else 30))
    path = credentials_file(tmp_path, signed)
    requests = 0

    def respond(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(401)

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(respond)) as client:
        report = await diagnose_sse_staging_auth.diagnose(
            path, client, secret, "HS256", hashlib.sha256(secret.encode()).hexdigest(), "HS256"
        )

    assert report["token_state"] == expected_state
    assert report["auth_http_status"] == "401"
    assert requests == 1


@pytest.mark.asyncio
async def test_diagnostic_rejects_invalid_pool_without_network(tmp_path: Path) -> None:
    path = tmp_path / "pool.json"
    path.write_text("secret-marker-{", encoding="utf-8")

    def fail(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("network must not be used")

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", transport=httpx.MockTransport(fail)) as client:
        report = await diagnose_sse_staging_auth.diagnose(
            path, client, "staging-test-secret-with-more-than-32-bytes", "HS256", "0" * 64, "HS256"
        )
    assert report["token_state"] == "credentials_invalid"
    assert report["requests_sent"] == 0
    assert "secret-marker" not in json.dumps(report)


@pytest.mark.asyncio
async def test_diagnostic_classifies_runtime_algorithm_mismatch(tmp_path: Path) -> None:
    secret = "staging-test-secret-with-more-than-48-bytes-length-okay"
    signed = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(UTC) + timedelta(minutes=30),
        },
        secret,
        algorithm="HS384",
    )
    path = credentials_file(tmp_path, signed)
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000",
        transport=httpx.MockTransport(lambda _request: httpx.Response(401)),
    ) as client:
        report = await diagnose_sse_staging_auth.diagnose(
            path, client, secret, "HS384", hashlib.sha256(secret.encode()).hexdigest(), "HS256"
        )
    assert report["token_state"] == "algorithm_mismatch"
    assert report["runtime_key_match"] is True
    assert report["runtime_algorithm_match"] is False
    assert report["auth_http_status"] == "401"


@pytest.mark.asyncio
async def test_diagnostic_requires_backend_jwt_claims(tmp_path: Path) -> None:
    secret = "staging-test-secret-with-more-than-32-bytes"
    signed = jwt.encode({"type": "access", "exp": datetime.now(UTC) + timedelta(minutes=30)}, secret, algorithm="HS256")
    path = credentials_file(tmp_path, signed)
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000",
        transport=httpx.MockTransport(lambda _request: httpx.Response(401)),
    ) as client:
        report = await diagnose_sse_staging_auth.diagnose(
            path, client, secret, "HS256", hashlib.sha256(secret.encode()).hexdigest(), "HS256"
        )
    assert report["token_state"] == "claims_invalid"


@pytest.mark.asyncio
async def test_diagnostic_client_ignores_environment_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    options: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            options.update(kwargs)

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

    async def fake_diagnose(*_args: object) -> dict[str, object]:
        return {"mode": "diagnose_auth"}

    monkeypatch.setattr(diagnose_sse_staging_auth.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(diagnose_sse_staging_auth, "diagnose", fake_diagnose)
    report = await diagnose_sse_staging_auth.run(Path("unused"), "secret", "HS256", "0" * 64, "HS256")
    assert report == {"mode": "diagnose_auth"}
    assert options["trust_env"] is False
