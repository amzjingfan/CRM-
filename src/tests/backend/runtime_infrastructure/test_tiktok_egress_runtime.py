"""TikTok 固定公网出口运行时验证器测试。"""

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

import scripts.verify_tiktok_egress as verifier
from scripts.verify_tiktok_egress import main, parse_observed_egress


@pytest.mark.parametrize("payload", ["", "not-an-ip", "38.55.145.52 extra"])
def test_parse_observed_egress_rejects_invalid_payload(payload: str) -> None:
    with pytest.raises(ValueError):
        parse_observed_egress("38.55.145.52", payload)


def test_parse_observed_egress_rejects_mismatch() -> None:
    with pytest.raises(ValueError, match="does not match"):
        parse_observed_egress("38.55.145.52", "122.234.23.242\n")


def test_parse_observed_egress_accepts_exact_ip() -> None:
    assert parse_observed_egress("38.55.145.52", "38.55.145.52\n") == "38.55.145.52"


class FakeResponse:
    def __init__(self, text: str, error: httpx.HTTPError | None = None) -> None:
        self.text = text
        self.error = error

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error


def fake_client_type(
    captured: dict[str, Any],
    response: FakeResponse,
) -> type:
    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured["kwargs"] = kwargs

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            captured["url"] = url
            return response

    return FakeClient


def configure_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIKTOK_EGRESS_IP", "38.55.145.52")
    monkeypatch.setenv("TIKTOK_EGRESS_PROXY_URL", "socks5h://tiktok-egress:1080")
    monkeypatch.setenv("TIKTOK_APP_SECRET", "must-not-appear")
    monkeypatch.setenv("DATABASE_URL", "must-not-appear")


def test_main_uses_only_fixed_proxy_and_emits_low_sensitive_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, Any] = {}
    configure_environment(monkeypatch)
    monkeypatch.setattr(
        verifier.httpx,
        "Client",
        fake_client_type(captured, FakeResponse("38.55.145.52\n")),
    )

    assert main() == 0

    output = capsys.readouterr().out
    assert json.loads(output) == {
        "configured_ip": "38.55.145.52",
        "observed_ip": "38.55.145.52",
        "schema_version": 1,
        "status": "ok",
    }
    assert "must-not-appear" not in output
    assert captured == {
        "kwargs": {
            "proxy": "socks5h://tiktok-egress:1080",
            "trust_env": False,
            "timeout": 10,
        },
        "url": "https://checkip.amazonaws.com",
    }


@pytest.mark.parametrize(
    "response_factory",
    [
        lambda: FakeResponse("not-an-ip"),
        lambda: FakeResponse("122.234.23.242\n"),
        lambda: FakeResponse(
            "",
            httpx.ConnectError(
                "fixed egress unavailable",
                request=httpx.Request("GET", "https://checkip.amazonaws.com"),
            ),
        ),
    ],
)
def test_main_fails_closed_without_direct_retry(
    response_factory: Callable[[], FakeResponse],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, Any] = {}
    configure_environment(monkeypatch)
    client_type = fake_client_type(captured, response_factory())
    constructions = 0

    def create_client(**kwargs: Any) -> object:
        nonlocal constructions
        constructions += 1
        return client_type(**kwargs)

    monkeypatch.setattr(verifier.httpx, "Client", create_client)

    assert main() == 1
    assert constructions == 1
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("missing_name", ["TIKTOK_EGRESS_IP", "TIKTOK_EGRESS_PROXY_URL"])
def test_main_rejects_missing_required_environment(
    missing_name: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_environment(monkeypatch)
    monkeypatch.delenv(missing_name)
    monkeypatch.setattr(
        verifier.httpx,
        "Client",
        lambda **_kwargs: pytest.fail("HTTP client must not be constructed without required configuration"),
    )

    assert main() == 1
    assert capsys.readouterr().out == ""
