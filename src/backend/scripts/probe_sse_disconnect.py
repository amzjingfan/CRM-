"""G5 单连接主动断开探针；只输出固定类别与延迟。"""

import argparse
import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from scripts.load_test_sse import Credential, load_credentials


class ProbeFailure(Exception):
    """仅允许固定类别进入低敏报告。"""


async def probe_once(
    credential: Credential,
    *,
    base_url: str,
    origin: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """收到 accepted 后主动关闭客户端；服务端结果由独立日志与租约核对。"""

    started = time.perf_counter()
    headers = {"Origin": origin, "X-CSRF-Token": credential.csrf_token}
    cookies = {
        "crm_access_token": credential.access_token,
        "crm_csrf_token": credential.csrf_token,
    }
    timeout = httpx.Timeout(connect=5, read=10, write=5, pool=5)
    try:
        async with httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            trust_env=False,
            transport=transport,
        ) as client:
            auth = await client.get("/v1/auth/me")
            if auth.status_code != 200:
                raise ProbeFailure("auth_rejected")
            try:
                auth_data = auth.json()
                user_id = str(uuid.UUID(auth_data["data"]["id"]))
            except (KeyError, TypeError, ValueError) as exc:
                raise ProbeFailure("auth_invalid") from exc

            trace_id: str | None = None
            accepted_ms: float | None = None
            async with client.stream("POST", "/v1/chat/query", json={"session_id": credential.session_id}) as response:
                if response.status_code != 200:
                    raise ProbeFailure("http_rejected")
                event_name = ""
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        event_name = line.removeprefix("event:").strip()
                    elif line.startswith("data:"):
                        if event_name == "delta":
                            raise ProbeFailure("delta_before_accepted")
                        if event_name != "accepted":
                            continue
                        try:
                            data = json.loads(line.removeprefix("data:").strip())
                            trace_id = str(uuid.UUID(data["trace_id"]))
                            accepted_ms = round((time.perf_counter() - started) * 1000, 2)
                        except (KeyError, TypeError, ValueError) as exc:
                            raise ProbeFailure("accepted_invalid") from exc
                        break
                if trace_id is None or accepted_ms is None:
                    raise ProbeFailure("accepted_missing")
            # 离开流上下文后底层连接已关闭；不消费模型正文或后续事件。
            return (
                {
                    "http_status": 200,
                    "accepted": True,
                    "client_closed_after_accepted": True,
                    "delta_seen_before_close": False,
                    "accepted_ms": accepted_ms,
                },
                {"user_id": user_id, "trace_id": trace_id},
            )
    except httpx.HTTPError as exc:
        raise ProbeFailure("transport_error") from exc


def _write_exclusive(path: Path, payload: dict[str, Any]) -> None:
    """报告和私有关联文件独占创建，避免覆盖先前窗口。"""

    import os

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(payload, output, separators=(",", ":"))
        output.write("\n")


async def main() -> int:
    parser = argparse.ArgumentParser(description="G5 one-client SSE disconnect probe")
    parser.add_argument("--credentials-file", required=True, type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--output-directory", required=True, type=Path)
    args = parser.parse_args()
    if args.base_url != "http://127.0.0.1:8000" or args.origin != "https://staging.overselfx.com":
        print('{"probe_status":"target_invalid"}')
        return 1
    if args.output_directory.as_posix() != "/opt/g5-evidence":
        print('{"probe_status":"output_target_invalid"}')
        return 1
    if not args.output_directory.is_dir():
        print('{"probe_status":"output_directory_missing"}')
        return 1
    try:
        credentials = load_credentials(args.credentials_file, None)
        if len(credentials) != 50:
            raise ProbeFailure("credential_count_invalid")
        result, correlation = await probe_once(credentials[0], base_url=args.base_url, origin=args.origin)
        _write_exclusive(args.output_directory / "private-correlation.json", correlation)
        summary = {"probe_status": "client_closed", **result}
        _write_exclusive(args.output_directory / "disconnect-client.json", summary)
        print(json.dumps(summary, separators=(",", ":")))
        return 0
    except ValueError:
        category = "credential_invalid"
    except ProbeFailure as exc:
        category = str(exc)
    except OSError:
        category = "output_write_failed"
    except Exception:
        category = "probe_internal_error"
    summary = {"probe_status": category}
    print(json.dumps(summary, separators=(",", ":")))
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
