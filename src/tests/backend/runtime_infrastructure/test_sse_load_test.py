"""SSE 多客户端压测工具的凭证容量与结果分类测试。"""

import asyncio
import json
import sys
import uuid
from pathlib import Path

import httpx
import pytest

from scripts import load_test_sse
from scripts.load_test_sse import (
    FIRST_DELTA_P99_ARCHITECTURE_LIMIT_MS,
    TOTAL_P99_ARCHITECTURE_LIMIT_MS,
    Credential,
    Sample,
    build_assignments,
    classify_sse_terminal,
    classify_status,
    load_credentials,
    performance_gate_passed,
    validate_single_source_ip_capacity,
)


def make_credential(index: int) -> Credential:
    return Credential(f"access-{index}", f"csrf-{index}", f"session-{index}")


def test_default_production_like_assignments_use_distinct_clients() -> None:
    credentials = [make_credential(index) for index in range(50)]

    assignments = build_assignments(credentials, concurrency=50, requests_per_credential=1)

    assert len(assignments) == 50
    assert {item.client_index for item in assignments} == set(range(50))


def test_assignment_rejects_single_user_for_fifty_concurrent_requests() -> None:
    with pytest.raises(ValueError, match="credential capacity"):
        build_assignments([make_credential(0)], concurrency=50, requests_per_credential=1)


def test_single_source_load_rejects_concurrency_above_declared_ip_limit() -> None:
    with pytest.raises(ValueError, match="server IP rate limit 10"):
        validate_single_source_ip_capacity(concurrency=50, server_ip_rate_limit=10)


def test_single_source_load_accepts_isolated_sixty_request_limit() -> None:
    validate_single_source_ip_capacity(concurrency=50, server_ip_rate_limit=60)


def test_credentials_file_supports_per_client_sessions(tmp_path: Path) -> None:
    path = tmp_path / "clients.json"
    path.write_text(
        json.dumps(
            {
                "clients": [
                    {
                        "access_token": "access-a",
                        "csrf_token": "csrf-a",
                        "session_id": "session-a",
                    },
                    {
                        "access_token": "access-b",
                        "csrf_token": "csrf-b",
                        "session_id": "session-b",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    credentials = load_credentials(path, fallback_session_id=None)

    assert [item.session_id for item in credentials] == ["session-a", "session-b"]


def test_credentials_file_rejects_duplicate_access_tokens(tmp_path: Path) -> None:
    path = tmp_path / "clients.json"
    path.write_text(
        json.dumps(
            {
                "clients": [
                    {"access_token": "same", "csrf_token": "csrf-a", "session_id": "a"},
                    {"access_token": "same", "csrf_token": "csrf-b", "session_id": "b"},
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate access token"):
        load_credentials(path, fallback_session_id=None)


@pytest.mark.asyncio
async def test_prepare_rejects_different_tokens_for_same_user_without_model_call() -> None:
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    requests: list[tuple[str, str]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path))
        if request.url.path == "/v1/auth/me":
            return httpx.Response(200, json={"code": 0, "data": {"id": user_id, "permissions": ["workspace.view"]}})
        return httpx.Response(200, json={"code": 0, "data": {"session": {"id": session_id}, "messages": []}})

    async with httpx.AsyncClient(
        base_url="https://staging.example.test", transport=httpx.MockTransport(respond)
    ) as client:
        report = await load_test_sse.prepare_clients(
            client,
            [
                Credential("secret-token-one", "secret-csrf-one", session_id),
                Credential("secret-token-two", "secret-csrf-two", session_id),
            ],
            required_clients=2,
        )

    assert report["ready"] is False
    assert report["distinct_authorized_users"] == 1
    assert report["failures"] == {"duplicate_identity": 1}
    assert all(method == "GET" for method, _ in requests)
    assert "secret-token" not in json.dumps(report)
    assert user_id not in json.dumps(report)


@pytest.mark.asyncio
async def test_prepare_requires_session_access_without_model_call() -> None:
    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/auth/me":
            return httpx.Response(200, json={"code": 0, "data": {"id": user_id, "permissions": ["workspace.view"]}})
        return httpx.Response(404, json={"code": 40401})

    async with httpx.AsyncClient(
        base_url="https://staging.example.test", transport=httpx.MockTransport(respond)
    ) as client:
        report = await load_test_sse.prepare_clients(
            client,
            [Credential("secret-token", "secret-csrf", session_id)],
            required_clients=1,
        )

    assert report["ready"] is False
    assert report["failures"] == {"session_inaccessible": 1}
    assert report["provider_calls"] == 0


@pytest.mark.asyncio
async def test_prepare_accepts_distinct_authorized_users_with_visible_sessions() -> None:
    first_id, second_id, session_id = (str(uuid.uuid4()) for _ in range(3))

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/auth/me":
            user_id = first_id if "token-one" in request.headers["cookie"] else second_id
            return httpx.Response(200, json={"code": 0, "data": {"id": user_id, "permissions": ["workspace.view"]}})
        assert request.url.path == f"/v1/workspace/sessions/{session_id}/messages"
        return httpx.Response(200, json={"code": 0, "data": {"session": {"id": session_id}, "messages": []}})

    async with httpx.AsyncClient(
        base_url="https://staging.example.test", transport=httpx.MockTransport(respond)
    ) as client:
        report = await load_test_sse.prepare_clients(
            client,
            [Credential("token-one", "csrf-one", session_id), Credential("token-two", "csrf-two", session_id)],
            required_clients=2,
        )

    assert report["ready"] is True
    assert report["distinct_authorized_users"] == 2
    assert report["failures"] == {}


@pytest.mark.asyncio
async def test_prepare_classifies_malformed_auth_identity_without_traceback() -> None:
    session_id = str(uuid.uuid4())

    def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 0, "data": {"id": 123, "permissions": ["workspace.view"]}})

    async with httpx.AsyncClient(
        base_url="https://staging.example.test", transport=httpx.MockTransport(respond)
    ) as client:
        report = await load_test_sse.prepare_clients(
            client, [Credential("secret-token", "secret-csrf", session_id)], required_clients=1
        )

    assert report["failures"] == {"identity_invalid": 1}


@pytest.mark.asyncio
@pytest.mark.parametrize("session_reply", ["html", "business_error", "wrong_session"])
async def test_prepare_rejects_http_200_without_matching_session(session_reply: str) -> None:
    user_id, session_id = (str(uuid.uuid4()) for _ in range(2))

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/auth/me":
            return httpx.Response(200, json={"code": 0, "data": {"id": user_id, "permissions": ["workspace.view"]}})
        if session_reply == "html":
            return httpx.Response(200, text="<html>login</html>")
        if session_reply == "business_error":
            return httpx.Response(200, json={"code": 40401, "data": None})
        return httpx.Response(
            200,
            json={"code": 0, "data": {"session": {"id": str(uuid.uuid4())}, "messages": []}},
        )

    async with httpx.AsyncClient(
        base_url="https://staging.example.test", transport=httpx.MockTransport(respond)
    ) as client:
        report = await load_test_sse.prepare_clients(
            client, [Credential("secret-token", "secret-csrf", session_id)], required_clients=1
        )

    assert report["ready"] is False
    assert report["failures"] == {"session_inaccessible": 1}


def test_prepare_cli_never_dispatches_live_sse(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    async def fake_prepare(
        _client: httpx.AsyncClient, _credentials: list[Credential], *, required_clients: int
    ) -> dict:
        return {"mode": "prepare", "required_clients": required_clients, "ready": True, "provider_calls": 0}

    async def forbid_live(*_args: object) -> Sample:
        raise AssertionError("live SSE must not run in prepare mode")

    monkeypatch.setattr(load_test_sse, "load_credentials", lambda *_args: [make_credential(0)])
    monkeypatch.setattr(load_test_sse, "prepare_clients", fake_prepare)
    monkeypatch.setattr(load_test_sse, "run_one", forbid_live)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "load_test_sse",
            "--prepare",
            "--credentials-file",
            str(tmp_path / "clients.json"),
            "--concurrency",
            "1",
            "--server-ip-rate-limit",
            "1",
            "--base-url",
            "https://staging.example.test",
        ],
    )

    asyncio.run(load_test_sse.main())

    assert json.loads(capsys.readouterr().out)["provider_calls"] == 0


def test_prepare_paths_reject_repository_files_and_existing_output(tmp_path: Path) -> None:
    assert load_test_sse.prepare_paths_are_safe(Path(__file__), None) is False
    assert (
        load_test_sse.prepare_paths_are_safe(tmp_path / "clients.json", Path(__file__).parent / "report.json") is False
    )
    worktree_root = next(parent for parent in Path(__file__).resolve().parents if (parent / ".git").exists())
    primary_root = worktree_root.parent.parent if worktree_root.parent.name == ".worktrees" else worktree_root
    assert load_test_sse.prepare_paths_are_safe(primary_root / "secrets.json", None) is False
    assert load_test_sse.prepare_paths_are_safe(tmp_path / "clients.json", primary_root / "report.json") is False
    existing = tmp_path / "existing.json"
    existing.write_text("keep", encoding="utf-8")
    assert load_test_sse.prepare_paths_are_safe(tmp_path / "clients.json", existing) is False
    assert load_test_sse.prepare_paths_are_safe(tmp_path / "clients.json", tmp_path / "new.json") is True


def test_prepare_cli_does_not_overwrite_existing_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    existing = tmp_path / "report.json"
    existing.write_text("keep", encoding="utf-8")

    async def forbid_prepare(*_args: object, **_kwargs: object) -> dict:
        raise AssertionError("unsafe output path must stop before network")

    monkeypatch.setattr(load_test_sse, "load_credentials", lambda *_args: [make_credential(0)])
    monkeypatch.setattr(load_test_sse, "prepare_clients", forbid_prepare)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "load_test_sse",
            "--prepare",
            "--credentials-file",
            str(tmp_path / "clients.json"),
            "--output",
            str(existing),
            "--concurrency",
            "1",
            "--server-ip-rate-limit",
            "1",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        asyncio.run(load_test_sse.main())

    report = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 1
    assert report["failures"] == {"unsafe_path": 1}
    assert report["provider_calls"] == 0
    assert existing.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize(
    ("status_code", "outcome"),
    [
        (429, "rate_limited"),
        (401, "authentication_rejected"),
        (503, "http_error"),
        (0, "transport_error"),
    ],
)
def test_http_failures_are_classified(status_code: int, outcome: str) -> None:
    assert classify_status(status_code) == outcome


@pytest.mark.parametrize(
    ("reason", "error_code", "ok", "outcome"),
    [
        ("completed", None, True, "succeeded"),
        ("failed", 42901, False, "sse_rate_limited"),
        ("failed", 50003, False, "sse_failed"),
        ("timeout", 50003, False, "sse_timeout"),
        ("disconnected", None, False, "sse_disconnected"),
    ],
)
def test_sse_terminal_reason_controls_success(
    reason: str,
    error_code: int | None,
    ok: bool,
    outcome: str,
) -> None:
    """error 后的 done 只能表示协议完整结束，不能被统计为业务成功。"""
    assert classify_sse_terminal(reason, error_code) == (ok, outcome)


def test_performance_gate_requires_every_client_to_reach_first_safe_delta() -> None:
    complete = Sample(0, True, 200, "succeeded", 5.0, 120.0, 180.0, None)
    missing_delta = Sample(1, True, 200, "succeeded", 6.0, None, 181.0, None)

    assert performance_gate_passed([complete], expected_samples=1) is True
    assert performance_gate_passed([complete, missing_delta], expected_samples=2) is False


@pytest.mark.parametrize(
    ("first_delta_ms", "total_ms", "expected"),
    [
        (2999.0, 4999.0, True),
        (3000.0, 4999.0, False),
        (2999.0, 5000.0, False),
        (3001.0, 5001.0, False),
    ],
)
def test_performance_gate_uses_strict_p99_sla_boundaries(
    first_delta_ms: float,
    total_ms: float,
    expected: bool,
) -> None:
    """ADR 使用“小于”，因此等于 3 秒或 5 秒也不能通过生产门禁。"""

    sample = Sample(0, True, 200, "succeeded", 5.0, first_delta_ms, total_ms, None)

    assert performance_gate_passed([sample], expected_samples=1) is expected


def test_performance_gate_rejects_one_slow_tail_request_in_fifty_samples() -> None:
    samples = [Sample(index, True, 200, "succeeded", 5.0, 100.0, 200.0, None) for index in range(49)]
    samples.append(Sample(49, True, 200, "succeeded", 5.0, 10_000.0, 20_000.0, None))

    assert performance_gate_passed(samples, expected_samples=50) is False


def test_performance_gate_rejects_non_finite_latency() -> None:
    sample = Sample(0, True, 200, "succeeded", 5.0, float("nan"), 100.0, None)

    assert performance_gate_passed([sample], expected_samples=1) is False


def test_performance_gate_api_cannot_relax_architecture_sla() -> None:
    sample = Sample(0, True, 200, "succeeded", 5.0, 10_000.0, 20_000.0, None)

    assert (
        performance_gate_passed(
            [sample],
            expected_samples=1,
            first_delta_p99_limit_ms=10_001.0,
            total_p99_limit_ms=20_001.0,
        )
        is False
    )


@pytest.mark.parametrize(
    ("argument", "value"),
    [
        ("--first-delta-p99-limit-ms", "3001"),
        ("--total-p99-limit-ms", "5001"),
    ],
)
def test_cli_cannot_relax_architecture_sla(
    monkeypatch: pytest.MonkeyPatch,
    argument: str,
    value: str,
) -> None:
    monkeypatch.setattr(sys, "argv", ["load_test_sse", argument, value])

    with pytest.raises(SystemExit) as exc_info:
        asyncio.run(load_test_sse.main())

    assert exc_info.value.code == 2


def test_cli_exits_nonzero_and_records_sla_when_complete_samples_are_slow(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def run_slow_sample(
        _base_url: str,
        _origin: str,
        assignment: load_test_sse.Assignment,
    ) -> Sample:
        return Sample(assignment.client_index, True, 200, "succeeded", 5.0, 10_000.0, 20_000.0, None)

    monkeypatch.setattr(load_test_sse, "run_one", run_slow_sample)
    monkeypatch.setenv("CRM_ACCESS_TOKEN", "test-access")
    monkeypatch.setenv("CRM_CSRF_TOKEN", "test-csrf")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "load_test_sse",
            "--session-id",
            "test-session",
            "--concurrency",
            "1",
            "--server-ip-rate-limit",
            "1",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        asyncio.run(load_test_sse.main())

    assert exc_info.value.code == 1
    evidence = json.loads(capsys.readouterr().out)
    assert evidence["first_delta_p99_ms"] == 10_000.0
    assert evidence["total_p99_ms"] == 20_000.0
    assert evidence["first_delta_p99_limit_ms"] == FIRST_DELTA_P99_ARCHITECTURE_LIMIT_MS
    assert evidence["total_p99_limit_ms"] == TOTAL_P99_ARCHITECTURE_LIMIT_MS
    assert evidence["sla_comparison"] == "strictly_less_than"
    assert evidence["performance_gate_passed"] is False
