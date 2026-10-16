"""仅对现有 G5 私有凭证池做身份与会话 GET 预检。"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from scripts.load_test_sse import load_credentials, prepare_clients


def failure_report(category: str) -> dict[str, Any]:
    """只保留固定类别，防止凭证路径或远端响应进入日志。"""
    return {
        "mode": "preflight",
        "required_clients": 50,
        "distinct_authorized_users": 0,
        "ready": False,
        "failures": {category: 1},
        "provider_calls": 0,
    }


async def preflight_clients(credentials_file: Path, client: httpx.AsyncClient) -> dict[str, Any]:
    try:
        credentials = load_credentials(credentials_file, fallback_session_id=None)
    except (OSError, ValueError):
        return failure_report("credentials_invalid")
    if len(credentials) != 50:
        return failure_report("credentials_invalid")
    try:
        report = await prepare_clients(client, credentials, required_clients=50)
    except Exception:
        return failure_report("internal_error")
    allowed_failures = {
        "transport_error",
        "auth_rejected",
        "identity_invalid",
        "permission_missing",
        "duplicate_identity",
        "session_inaccessible",
        "insufficient_clients",
    }
    failures = report.get("failures")
    if not isinstance(failures, dict) or any(
        key not in allowed_failures or not isinstance(value, int) or value < 0 for key, value in failures.items()
    ):
        return failure_report("internal_error")
    distinct = report.get("distinct_authorized_users")
    ready = report.get("ready")
    if not isinstance(distinct, int) or not 0 <= distinct <= 50 or not isinstance(ready, bool):
        return failure_report("internal_error")
    return {
        "mode": "preflight",
        "required_clients": 50,
        "distinct_authorized_users": distinct,
        "ready": ready and distinct == 50 and not failures,
        "failures": failures,
        "provider_calls": 0,
    }


async def run(credentials_file: Path) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=3.0, follow_redirects=False) as client:
        return await preflight_clients(credentials_file, client)


def main() -> None:
    parser = argparse.ArgumentParser(description="G5 existing fixture identity and session GET preflight")
    parser.add_argument("--credentials-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = asyncio.run(run(args.credentials_file))
    except Exception:
        report = failure_report("internal_error")
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    if not report["ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
