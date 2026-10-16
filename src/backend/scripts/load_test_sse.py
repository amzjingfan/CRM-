"""对授权测试客户端执行 SSE 并发工程压测，不输出凭证、消息或模型正文。"""

import argparse
import asyncio
import json
import os
import statistics
import subprocess
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Any

import httpx

# 生产门禁来自 ADR：首个安全输出小于 3 秒，50 客户端总耗时 P99 小于 5 秒。
# 使用严格小于而不是小于等于，避免边界值被错误包装成合格证据。
FIRST_DELTA_P99_ARCHITECTURE_LIMIT_MS = 3000.0
TOTAL_P99_ARCHITECTURE_LIMIT_MS = 5000.0


@dataclass(frozen=True)
class Credential:
    """单个授权测试客户端的 Cookie 凭证和可访问会话。"""

    access_token: str
    csrf_token: str
    session_id: str


@dataclass(frozen=True)
class Assignment:
    """压测请求与授权客户端的低敏关联。"""

    client_index: int
    credential: Credential


@dataclass(frozen=True)
class Sample:
    """单次 SSE 请求的低敏工程指标。"""

    client_index: int
    ok: bool
    status_code: int
    outcome: str
    accepted_ms: float | None
    first_delta_ms: float | None
    total_ms: float
    error_code: int | None


def _required_string(value: Any, field: str, index: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"clients[{index}].{field} must be a non-empty string")
    return value.strip()


def load_credentials(path: Path | None, fallback_session_id: str | None) -> list[Credential]:
    """加载凭证池；文件只接受 clients 数组，避免宽松解析掩盖配置错误。"""

    if path is None:
        access_token = os.getenv("CRM_ACCESS_TOKEN")
        csrf_token = os.getenv("CRM_CSRF_TOKEN")
        if not access_token or not csrf_token or not fallback_session_id:
            raise ValueError("single-client mode requires CRM_ACCESS_TOKEN, CRM_CSRF_TOKEN and --session-id")
        return [Credential(access_token, csrf_token, fallback_session_id)]

    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read credentials file: {exc}") from exc
    rows = payload.get("clients") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("credentials file must contain a non-empty 'clients' array")

    credentials: list[Credential] = []
    exact_tokens: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"clients[{index}] must be an object")
        access_token = _required_string(row.get("access_token"), "access_token", index)
        csrf_token = _required_string(row.get("csrf_token"), "csrf_token", index)
        session_id = _required_string(row.get("session_id", fallback_session_id), "session_id", index)
        if access_token in exact_tokens:
            raise ValueError("credentials file contains a duplicate access token")
        exact_tokens.add(access_token)
        credentials.append(Credential(access_token, csrf_token, session_id))
    return credentials


def build_assignments(
    credentials: list[Credential], concurrency: int, requests_per_credential: int
) -> list[Assignment]:
    """按轮询分配客户端，并在发请求前阻止超出声明容量的压测。"""

    capacity = len(credentials) * requests_per_credential
    if concurrency > capacity:
        raise ValueError(
            f"concurrency {concurrency} exceeds credential capacity {capacity}; "
            "add distinct authorized clients or explicitly increase --requests-per-credential"
        )
    return [
        Assignment(client_index=index % len(credentials), credential=credentials[index % len(credentials)])
        for index in range(concurrency)
    ]


def validate_single_source_ip_capacity(concurrency: int, server_ip_rate_limit: int) -> None:
    """在发请求前确认单机压测不会被服务端 IP 限流截断。"""
    if concurrency > server_ip_rate_limit:
        raise ValueError(
            f"concurrency {concurrency} exceeds declared server IP rate limit {server_ip_rate_limit}; "
            "apply the isolated SSE load-test overlay or use an approved distributed load source"
        )


def prepare_paths_are_safe(credentials_file: Path, output: Path | None) -> bool:
    """准备模式只在可识别的仓库 checkout 中使用仓库外文件，且不覆盖已有证据。"""

    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(Path(__file__).resolve().parent),
                "rev-parse",
                "--path-format=absolute",
                "--show-toplevel",
                "--git-common-dir",
            ],
            capture_output=True,
            encoding="utf-8",
            check=True,
            timeout=5,
        )
        roots = result.stdout.splitlines()
        if len(roots) != 2:
            return False
        checkout_root, common_dir = (Path(value).resolve() for value in roots)
        if common_dir.name != ".git":
            return False
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    if output is not None and output.exists():
        return False
    return all(
        not path.resolve().is_relative_to(root)
        for path in (credentials_file, output)
        if path is not None
        for root in (checkout_root, common_dir.parent)
    )


async def prepare_clients(
    client: httpx.AsyncClient, credentials: list[Credential], *, required_clients: int
) -> dict[str, Any]:
    """只读核对独立身份和会话访问；不发起 AI 请求，也不保留响应正文。"""

    failures: Counter[str] = Counter()
    user_ids: set[uuid.UUID] = set()
    if len(credentials) < required_clients:
        failures["insufficient_clients"] = required_clients - len(credentials)
    else:
        for credential in credentials[:required_clients]:
            client.cookies.clear()
            client.cookies.set("crm_access_token", credential.access_token)
            try:
                response = await client.get("/v1/auth/me")
            except httpx.HTTPError:
                failures["transport_error"] += 1
                continue
            if response.status_code != 200:
                failures["auth_rejected"] += 1
                continue
            try:
                payload = response.json()
                data = payload["data"] if isinstance(payload, dict) and payload.get("code") == 0 else None
                if not isinstance(data, dict) or not isinstance(data.get("id"), str):
                    raise ValueError("invalid identity")
                user_id = uuid.UUID(data["id"])
                permissions = data.get("permissions")
                if not isinstance(permissions, list) or not all(isinstance(item, str) for item in permissions):
                    raise ValueError("invalid permissions")
            except (TypeError, ValueError):
                failures["identity_invalid"] += 1
                continue
            if "workspace.view" not in permissions:
                failures["permission_missing"] += 1
                continue
            if user_id in user_ids:
                failures["duplicate_identity"] += 1
                continue
            try:
                session_id = uuid.UUID(credential.session_id)
                response = await client.get(f"/v1/workspace/sessions/{session_id}/messages", params={"page_size": 1})
            except (ValueError, httpx.HTTPError):
                failures["session_inaccessible"] += 1
                continue
            if response.status_code != 200:
                failures["session_inaccessible"] += 1
                continue
            try:
                payload = response.json()
                data = payload["data"] if isinstance(payload, dict) and payload.get("code") == 0 else None
                if not isinstance(data, dict):
                    raise ValueError("invalid session response")
                session = data.get("session")
                if (
                    not isinstance(session, dict)
                    or not isinstance(session.get("id"), str)
                    or uuid.UUID(session["id"]) != session_id
                    or not isinstance(data.get("messages"), list)
                ):
                    raise ValueError("invalid session response")
            except (TypeError, ValueError):
                failures["session_inaccessible"] += 1
                continue
            user_ids.add(user_id)
    return {
        "mode": "prepare",
        "required_clients": required_clients,
        "distinct_authorized_users": len(user_ids),
        "ready": len(user_ids) == required_clients and not failures,
        "failures": dict(sorted(failures.items())),
        "provider_calls": 0,
    }


def classify_status(status_code: int) -> str:
    """将限流与认证、服务端等失败分开，避免把 429 误报为并发成功。"""

    if status_code == 429:
        return "rate_limited"
    if status_code in {401, 403}:
        return "authentication_rejected"
    if status_code == 0:
        return "transport_error"
    return "http_error"


def classify_sse_terminal(reason: str, error_code: int | None) -> tuple[bool, str]:
    """只有 completed 才算成功，避免把 error + done 误报为压测通过。"""
    if reason == "completed":
        return True, "succeeded"
    if reason == "timeout":
        return False, "sse_timeout"
    if reason == "disconnected":
        return False, "sse_disconnected"
    if error_code == 42901:
        return False, "sse_rate_limited"
    if error_code in {40101, 40102, 40301}:
        return False, "sse_authentication_rejected"
    return False, "sse_failed"


async def run_one(base_url: str, origin: str, assignment: Assignment) -> Sample:
    started = time.perf_counter()
    accepted: float | None = None
    first_delta: float | None = None
    terminal = False
    terminal_ok = False
    outcome = "stream_incomplete"
    error_code: int | None = None
    credential = assignment.credential
    headers = {"Origin": origin, "X-CSRF-Token": credential.csrf_token}
    cookies = {
        "crm_access_token": credential.access_token,
        "crm_csrf_token": credential.csrf_token,
    }
    timeout = httpx.Timeout(connect=10, read=120, write=10, pool=10)
    try:
        # 每个虚拟客户端使用独立连接和 Cookie 容器，避免单连接池掩盖真实并发。
        async with httpx.AsyncClient(base_url=base_url, headers=headers, cookies=cookies, timeout=timeout) as client:
            async with client.stream("POST", "/v1/chat/query", json={"session_id": credential.session_id}) as response:
                if response.status_code != 200:
                    return Sample(
                        assignment.client_index,
                        False,
                        response.status_code,
                        classify_status(response.status_code),
                        None,
                        None,
                        (time.perf_counter() - started) * 1000,
                        None,
                    )
                event_name = ""
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        event_name = line.removeprefix("event:").strip()
                    elif line.startswith("data:"):
                        try:
                            data = json.loads(line.removeprefix("data:").strip())
                        except json.JSONDecodeError:
                            outcome = "invalid_sse_data"
                            continue
                        if event_name == "accepted" and accepted is None:
                            accepted = (time.perf_counter() - started) * 1000
                        elif event_name == "delta" and first_delta is None:
                            first_delta = (time.perf_counter() - started) * 1000
                        elif event_name == "error" and isinstance(data, dict) and isinstance(data.get("code"), int):
                            error_code = data["code"]
                        elif event_name == "done" and isinstance(data, dict):
                            terminal = True
                            terminal_ok, outcome = classify_sse_terminal(str(data.get("reason", "")), error_code)
        return Sample(
            assignment.client_index,
            terminal and terminal_ok,
            200,
            outcome if terminal else "stream_incomplete",
            accepted,
            first_delta,
            (time.perf_counter() - started) * 1000,
            error_code,
        )
    except httpx.HTTPError:
        return Sample(
            assignment.client_index,
            False,
            0,
            "transport_error",
            accepted,
            first_delta,
            (time.perf_counter() - started) * 1000,
            error_code,
        )


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * fraction))]


def _bounded_sla_limit(raw_value: str, architecture_limit_ms: float) -> float:
    """解析只能收紧、不能放宽的毫秒级性能门禁。"""

    try:
        value = float(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("SLA limit must be a number in milliseconds") from exc
    if not 0 < value <= architecture_limit_ms:
        raise argparse.ArgumentTypeError(
            f"SLA limit must be greater than 0 and no greater than {architecture_limit_ms:g}ms"
        )
    return value


def performance_gate_passed(
    samples: list[Sample],
    expected_samples: int,
    *,
    first_delta_p99_limit_ms: float = FIRST_DELTA_P99_ARCHITECTURE_LIMIT_MS,
    total_p99_limit_ms: float = TOTAL_P99_ARCHITECTURE_LIMIT_MS,
) -> bool:
    """同时校验样本完整性、首输出 P99 和总耗时 P99 的严格 SLA。"""

    limits_are_safe = (
        0 < first_delta_p99_limit_ms <= FIRST_DELTA_P99_ARCHITECTURE_LIMIT_MS
        and 0 < total_p99_limit_ms <= TOTAL_P99_ARCHITECTURE_LIMIT_MS
    )
    if not limits_are_safe:
        return False

    samples_complete = len(samples) == expected_samples and all(
        sample.ok
        and sample.accepted_ms is not None
        and sample.first_delta_ms is not None
        and all(
            isfinite(value) and value >= 0 for value in (sample.accepted_ms, sample.first_delta_ms, sample.total_ms)
        )
        for sample in samples
    )
    if not samples_complete:
        return False

    first_delta_p99_ms = percentile(
        [sample.first_delta_ms for sample in samples if sample.first_delta_ms is not None],
        0.99,
    )
    total_p99_ms = percentile([sample.total_ms for sample in samples], 0.99)
    return (
        first_delta_p99_ms is not None
        and first_delta_p99_ms < first_delta_p99_limit_ms
        and total_p99_ms is not None
        and total_p99_ms < total_p99_limit_ms
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Authorized multi-client SSE engineering load test")
    parser.add_argument(
        "--prepare", action="store_true", help="Read-only identity and session preflight; never starts SSE"
    )
    parser.add_argument("--session-id", help="Fallback session UUID for clients without session_id")
    parser.add_argument("--credentials-file", type=Path, help="Path to a JSON credential pool outside the repository")
    parser.add_argument("--concurrency", type=int, default=50, choices=range(1, 101))
    parser.add_argument(
        "--requests-per-credential",
        type=int,
        default=1,
        choices=range(1, 21),
        help="Explicit per-user reuse ceiling; keep 1 for production-like evidence",
    )
    parser.add_argument(
        "--server-ip-rate-limit",
        type=int,
        default=10,
        choices=range(1, 1001),
        help="Declared CHAT_QUERY_LIMIT for this single-source load window; must cover concurrency",
    )
    parser.add_argument(
        "--first-delta-p99-limit-ms",
        type=lambda value: _bounded_sla_limit(value, FIRST_DELTA_P99_ARCHITECTURE_LIMIT_MS),
        default=FIRST_DELTA_P99_ARCHITECTURE_LIMIT_MS,
        metavar="MS",
        help="Strict P99 first-safe-delta limit; may only tighten the architecture limit of 3000ms",
    )
    parser.add_argument(
        "--total-p99-limit-ms",
        type=lambda value: _bounded_sla_limit(value, TOTAL_P99_ARCHITECTURE_LIMIT_MS),
        default=TOTAL_P99_ARCHITECTURE_LIMIT_MS,
        metavar="MS",
        help="Strict P99 total-duration limit; may only tighten the architecture limit of 5000ms",
    )
    parser.add_argument("--base-url", default=os.getenv("CRM_API_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--output", type=Path, help="Optional low-sensitivity JSON evidence output path")
    args = parser.parse_args()
    if args.prepare:
        failures: dict[str, int] = {}
        credentials: list[Credential] = []
        if args.credentials_file is None:
            failures["credentials_invalid"] = 1
        elif not prepare_paths_are_safe(args.credentials_file, args.output):
            failures["unsafe_path"] = 1
        else:
            try:
                credentials = load_credentials(args.credentials_file, args.session_id)
            except ValueError:
                failures["credentials_invalid"] = 1
        if args.requests_per_credential != 1:
            failures["credential_reuse_forbidden"] = 1
        if args.server_ip_rate_limit < args.concurrency:
            failures["declared_rate_limit_low"] = 1
        if failures:
            report: dict[str, Any] = {
                "mode": "prepare",
                "required_clients": args.concurrency,
                "distinct_authorized_users": 0,
                "ready": False,
                "failures": failures,
                "provider_calls": 0,
            }
        else:
            async with httpx.AsyncClient(base_url=args.base_url, timeout=10.0, follow_redirects=False) as client:
                report = await prepare_clients(client, credentials, required_clients=args.concurrency)
        report["declared_server_ip_rate_limit"] = args.server_ip_rate_limit
        rendered = json.dumps(report, ensure_ascii=True)
        if args.output is not None and "unsafe_path" not in report["failures"]:
            try:
                with args.output.open("x", encoding="utf-8") as stream:
                    stream.write(f"{rendered}\n")
            except OSError:
                report["ready"] = False
                report["failures"]["output_unavailable"] = 1
                rendered = json.dumps(report, ensure_ascii=True)
        print(rendered)
        if not report["ready"]:
            raise SystemExit(1)
        return
    try:
        credentials = load_credentials(args.credentials_file, args.session_id)
        assignments = build_assignments(credentials, args.concurrency, args.requests_per_credential)
        validate_single_source_ip_capacity(args.concurrency, args.server_ip_rate_limit)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    origin = os.getenv("CRM_ORIGIN", "http://localhost:3000")
    samples = await asyncio.gather(*(run_one(args.base_url, origin, assignment) for assignment in assignments))
    accepted = [item.accepted_ms for item in samples if item.accepted_ms is not None]
    first_delta = [item.first_delta_ms for item in samples if item.ok and item.first_delta_ms is not None]
    totals = [item.total_ms for item in samples]
    outcomes = {
        outcome: sum(item.outcome == outcome for item in samples)
        for outcome in sorted({item.outcome for item in samples})
    }
    status_codes = {
        str(code): sum(item.status_code == code for item in samples)
        for code in sorted({item.status_code for item in samples})
    }
    first_delta_p99_ms = percentile(first_delta, 0.99)
    total_p99_ms = percentile(totals, 0.99)
    gate_passed = performance_gate_passed(
        samples,
        args.concurrency,
        first_delta_p99_limit_ms=args.first_delta_p99_limit_ms,
        total_p99_limit_ms=args.total_p99_limit_ms,
    )
    result = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "concurrency": args.concurrency,
        "authorized_clients": len(credentials),
        "requests_per_credential": args.requests_per_credential,
        "declared_server_ip_rate_limit": args.server_ip_rate_limit,
        "succeeded": sum(item.ok for item in samples),
        "failed": sum(not item.ok for item in samples),
        "outcomes": outcomes,
        "status_codes": status_codes,
        "accepted_p50_ms": percentile(accepted, 0.50),
        "accepted_p99_ms": percentile(accepted, 0.99),
        "first_delta_p50_ms": percentile(first_delta, 0.50),
        "first_delta_p99_ms": first_delta_p99_ms,
        "total_p50_ms": statistics.median(totals),
        "total_p99_ms": total_p99_ms,
        "first_delta_p99_limit_ms": args.first_delta_p99_limit_ms,
        "total_p99_limit_ms": args.total_p99_limit_ms,
        "sla_comparison": "strictly_less_than",
        "samples": [asdict(item) for item in samples],
        "performance_gate_passed": gate_passed,
        "scope": "Authorized SSE runtime evidence; model quality and public release require separate gates",
    }
    rendered = json.dumps(result, ensure_ascii=True)
    if args.output is not None:
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    if not result["performance_gate_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
