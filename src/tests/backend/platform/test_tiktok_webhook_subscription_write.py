"""一次性 staging Webhook 订阅工具的失败关闭契约。"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import yaml

from app.integrations.tiktok_oauth import generate_api_signature
from app.integrations.tiktok_read import TikTokWebhookSubscription
from scripts import subscribe_tiktok_new_message_webhook as subscription_script
from scripts.subscribe_tiktok_new_message_webhook import (
    ADDRESS,
    PATH,
    TOPIC,
    build_signed_request,
    preflight_decision,
)


def test_preflight_allows_only_empty_or_exact_existing_subscription() -> None:
    """平台有未知配置时不覆盖；重复执行精确目标时不再次写入。"""
    assert preflight_decision([]) == "write"
    target = TikTokWebhookSubscription(event_type=TOPIC, address=ADDRESS)
    assert preflight_decision([target]) == "already_present"

    with pytest.raises(RuntimeError, match="Unexpected existing webhook subscription"):
        preflight_decision([TikTokWebhookSubscription(event_type=TOPIC, address="https://example.invalid")])
    with pytest.raises(RuntimeError, match="Unexpected existing webhook subscription"):
        preflight_decision([target, target])


def test_signed_request_has_one_reviewed_topic_and_exact_body() -> None:
    """签名必须绑定唯一主题、固定回调地址和跨境店铺 shop_cipher。"""
    params, body = build_signed_request("app-key", "cipher", "secret", 1700000000)

    assert json.loads(body) == {"event_type": "NEW_MESSAGE", "address": ADDRESS}
    assert set(params) == {"app_key", "shop_cipher", "timestamp", "sign"}
    assert params["shop_cipher"] == "cipher"
    assert params["sign"] == generate_api_signature(
        PATH, {key: value for key, value in params.items() if key != "sign"}, "secret", body
    )


def test_subscription_workflow_is_staging_only_and_one_write() -> None:
    """部署工作流不允许动态主题、动态地址或重试写入。"""
    root = Path(__file__).resolve().parents[4]
    workflow = yaml.safe_load((root / ".github/workflows/subscribe-staging-tiktok-new-message.yml").read_text("utf-8"))
    assert set(workflow["jobs"]) == {"subscribe"}
    job = workflow["jobs"]["subscribe"]
    assert job["environment"] == "staging"
    assert job["runs-on"] == ["self-hosted", "linux", "x64", "crm-staging"]
    assert "refs/heads/main" in job["if"]
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    assert "subscribe_tiktok_new_message_webhook.py" in commands
    assert "NEW_MESSAGE@https://staging.overselfx.com/v1/webhooks/tiktok" in commands
    assert "docker compose up" not in commands
    assert "docker build" not in commands


@pytest.mark.parametrize(
    ("before", "after", "transport_failure", "expected_status", "expected_writes"),
    [
        ([], [TikTokWebhookSubscription(event_type=TOPIC, address=ADDRESS)], False, "confirmed", 1),
        ([], [], True, "unknown", 1),
        ([TikTokWebhookSubscription(event_type=TOPIC, address=ADDRESS)], [], False, "already_present", 0),
    ],
)
def test_live_subscription_writes_at_most_once_and_reconciles(
    monkeypatch: pytest.MonkeyPatch,
    before: list[TikTokWebhookSubscription],
    after: list[TikTokWebhookSubscription],
    transport_failure: bool,
    expected_status: str,
    expected_writes: int,
) -> None:
    """单次平台写入后用安全 GET 对账；网络失败也不盲目重发。"""
    calls: list[tuple[str, str, bytes]] = []
    reads = iter((before, after))

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def scalars(self, _query: object) -> SimpleNamespace:
            return SimpleNamespace(all=lambda: [SimpleNamespace()])

    class FakeReadClient:
        shop_cipher = "cipher"
        app_secret = "secret"
        access_token = "token"

        def __init__(self, _settings: object, _channel: object) -> None:
            pass

        async def get_webhooks(self) -> tuple[list[TikTokWebhookSubscription], None]:
            return next(reads), None

    class FakeHttpClient:
        async def __aenter__(self) -> "FakeHttpClient":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def request(self, method: str, url: str, *, content: bytes, **_kwargs: object) -> SimpleNamespace:
            calls.append((method, url, content))
            if transport_failure:
                raise httpx.ConnectError("connection reset")
            return SimpleNamespace(status_code=200)

    settings = SimpleNamespace(
        real_tiktok_read_enabled=True,
        real_tiktok_webhook_enabled=True,
        tiktok_app_key="app-key",
    )
    monkeypatch.setenv("CRM_G2_WEBHOOK_SUBSCRIPTION_CONFIRM", f"{TOPIC}@{ADDRESS}")
    monkeypatch.setattr(subscription_script, "get_settings", lambda: settings)
    monkeypatch.setattr(subscription_script, "session_factory", FakeSession)
    monkeypatch.setattr(subscription_script, "TikTokReadClient", FakeReadClient)
    monkeypatch.setattr(subscription_script, "create_tiktok_http_client", lambda _settings: FakeHttpClient())

    result = asyncio.run(subscription_script.subscribe())

    assert result["status"] == expected_status
    assert len(calls) == expected_writes
    if calls:
        assert calls[0][0] == "PUT"
        assert calls[0][1] == "https://open-api.tiktokglobalshop.com/event/202309/webhooks"
        assert json.loads(calls[0][2]) == {"event_type": TOPIC, "address": ADDRESS}
