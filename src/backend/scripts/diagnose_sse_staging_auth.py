"""对既有 G5 测试凭证只检查一枚令牌和一次认证 GET。"""

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
import jwt

from app.shared.config.settings import get_settings
from scripts.load_test_sse import load_credentials


def fixed_report(
    token_state: str, key_match: bool, algorithm_match: bool, http_status: str, requests_sent: int
) -> dict[str, Any]:
    """禁止把令牌、密钥、用户和响应正文写入工作流输出。"""
    return {
        "mode": "diagnose_auth",
        "token_state": token_state,
        "runtime_key_match": key_match,
        "runtime_algorithm_match": algorithm_match,
        "auth_http_status": http_status,
        "requests_sent": requests_sent,
        "provider_calls": 0,
    }


async def diagnose(
    credentials_file: Path,
    client: httpx.AsyncClient,
    secret: str,
    algorithm: str,
    runtime_key_sha256: str,
    runtime_algorithm: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{64}", runtime_key_sha256) or runtime_algorithm not in {"HS256", "HS384", "HS512"}:
        return fixed_report("config_invalid", False, False, "not_sent", 0)
    key_match = hmac.compare_digest(hashlib.sha256(secret.encode()).hexdigest(), runtime_key_sha256)
    algorithm_match = algorithm == runtime_algorithm
    try:
        credentials = load_credentials(credentials_file, fallback_session_id=None)
    except (OSError, ValueError):
        return fixed_report("credentials_invalid", key_match, algorithm_match, "not_sent", 0)
    if len(credentials) != 50:
        return fixed_report("credentials_invalid", key_match, algorithm_match, "not_sent", 0)

    token = credentials[0].access_token
    if not algorithm_match:
        token_state = "algorithm_mismatch"
    else:
        try:
            claims = jwt.decode(token, secret, algorithms=[runtime_algorithm])
            token_state = (
                "valid"
                if claims.get("type") == "access" and claims.get("sub") and claims.get("jti")
                else "claims_invalid"
            )
        except jwt.ExpiredSignatureError:
            token_state = "expired"
        except jwt.InvalidSignatureError:
            token_state = "signature_mismatch"
        except jwt.InvalidTokenError:
            token_state = "claims_invalid"

    client.cookies.clear()
    client.cookies.set("crm_access_token", token)
    try:
        response = await client.get("/v1/auth/me")
    except httpx.HTTPError:
        return fixed_report(token_state, key_match, algorithm_match, "transport_error", 1)
    status = str(response.status_code) if response.status_code in {200, 401, 403, 429} else "other"
    return fixed_report(token_state, key_match, algorithm_match, status, 1)


async def run(
    credentials_file: Path, secret: str, algorithm: str, runtime_key_sha256: str, runtime_algorithm: str
) -> dict[str, Any]:
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000", timeout=3.0, follow_redirects=False, trust_env=False
    ) as client:
        return await diagnose(credentials_file, client, secret, algorithm, runtime_key_sha256, runtime_algorithm)


def main() -> None:
    parser = argparse.ArgumentParser(description="G5 existing fixture one-token read-only diagnosis")
    parser.add_argument("--credentials-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        settings = get_settings()
        report = asyncio.run(
            run(
                args.credentials_file,
                settings.jwt_secret_key,
                settings.jwt_algorithm,
                os.environ.get("EXPECTED_RUNTIME_JWT_SHA256", ""),
                os.environ.get("EXPECTED_RUNTIME_JWT_ALGORITHM", ""),
            )
        )
    except Exception:
        report = fixed_report("config_invalid", False, False, "not_sent", 0)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    if report["token_state"] in {"config_invalid", "credentials_invalid"} or report["requests_sent"] != 1:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
