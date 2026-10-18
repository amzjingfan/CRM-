"""G5 主动断连探针只记录固定类别并在 accepted 后关闭客户端。"""

import sys
import uuid
from pathlib import Path

import httpx
import pytest

from scripts import probe_sse_disconnect
from scripts.load_test_sse import Credential


class _EventStream(httpx.AsyncByteStream):
    def __init__(self, trace_id: uuid.UUID) -> None:
        self.trace_id = trace_id
        self.closed = False
        self.delta_read = False

    async def __aiter__(self):  # type: ignore[no-untyped-def]
        yield f'event: accepted\ndata: {{"trace_id":"{self.trace_id}"}}\n\n'.encode()
        self.delta_read = True
        yield b'event: delta\ndata: {"text":"private model output"}\n\n'

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_probe_closes_after_accepted_without_reading_model_output() -> None:
    user_id = uuid.uuid4()
    trace_id = uuid.uuid4()
    stream = _EventStream(trace_id)
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path == "/v1/auth/me":
            return httpx.Response(200, json={"code": 0, "data": {"id": str(user_id)}})
        assert request.url.path == "/v1/chat/query"
        assert request.headers["origin"] == "https://staging.overselfx.com"
        return httpx.Response(200, stream=stream)

    result, correlation = await probe_sse_disconnect.probe_once(
        Credential("synthetic-access", "synthetic-csrf", str(uuid.uuid4())),
        base_url="http://127.0.0.1:8000",
        origin="https://staging.overselfx.com",
        transport=httpx.MockTransport(handler),
    )

    assert result["http_status"] == 200
    assert result["accepted"] is True
    assert result["client_closed_after_accepted"] is True
    assert result["delta_seen_before_close"] is False
    assert stream.closed is True
    assert stream.delta_read is False
    assert requests == ["/v1/auth/me", "/v1/chat/query"]
    assert correlation == {"user_id": str(user_id), "trace_id": str(trace_id)}
    assert "synthetic-access" not in str(result)
    assert "private model output" not in str(result)


@pytest.mark.asyncio
async def test_probe_rejects_http_failure_without_response_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/auth/me":
            return httpx.Response(200, json={"code": 0, "data": {"id": str(uuid.uuid4())}})
        return httpx.Response(403, text="sensitive response body")

    with pytest.raises(probe_sse_disconnect.ProbeFailure, match="http_rejected") as error:
        await probe_sse_disconnect.probe_once(
            Credential("synthetic-access", "synthetic-csrf", str(uuid.uuid4())),
            base_url="http://127.0.0.1:8000",
            origin="https://staging.overselfx.com",
            transport=httpx.MockTransport(handler),
        )

    assert "sensitive response body" not in str(error.value)


@pytest.mark.asyncio
async def test_cli_refuses_non_loopback_target_before_loading_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "probe_sse_disconnect",
            "--credentials-file",
            str(tmp_path / "not-present.json"),
            "--base-url",
            "https://example.com",
            "--origin",
            "https://staging.overselfx.com",
            "--output-directory",
            str(tmp_path),
        ],
    )

    assert await probe_sse_disconnect.main() == 1
    assert '"probe_status":"target_invalid"' in capsys.readouterr().out


@pytest.mark.asyncio
async def test_cli_refuses_arbitrary_output_directory_before_loading_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "probe_sse_disconnect",
            "--credentials-file",
            str(tmp_path / "not-present.json"),
            "--base-url",
            "http://127.0.0.1:8000",
            "--origin",
            "https://staging.overselfx.com",
            "--output-directory",
            str(tmp_path),
        ],
    )

    assert await probe_sse_disconnect.main() == 1
    assert '"probe_status":"output_target_invalid"' in capsys.readouterr().out
