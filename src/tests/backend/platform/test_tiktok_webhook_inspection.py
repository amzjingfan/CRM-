"""G2 staging 订阅读取只输出低敏摘要。"""

import json
from pathlib import Path

import yaml

from app.integrations.tiktok_read import TikTokWebhookSubscription
from scripts.inspect_tiktok_webhooks import summarize_subscriptions


def test_subscription_summary_reports_topics_without_address_or_query() -> None:
    """诊断证据可辨认错误地址，但不得泄漏订阅 URL 或其中的参数。"""
    subscriptions = [
        TikTokWebhookSubscription(
            event_type="NEW_MESSAGE",
            address="https://staging.overselfx.com/v1/webhooks/tiktok",
        ),
        TikTokWebhookSubscription(
            event_type="ORDER_STATUS_CHANGE",
            address="https://example.invalid/callback?token=private-value",
        ),
    ]

    summary = summarize_subscriptions(subscriptions)

    assert summary == {
        "subscription_count": 2,
        "event_types": ["NEW_MESSAGE", "ORDER_STATUS_CHANGE"],
        "matching_address_count": 1,
        "unexpected_address_count": 1,
    }
    serialized = json.dumps(summary)
    assert "example.invalid" not in serialized
    assert "private-value" not in serialized
    assert "staging.overselfx.com" not in serialized


def test_inspection_workflow_is_main_scoped_and_does_not_publish_or_deploy() -> None:
    """临时平台订阅诊断仅在 staging Runner 上做只读查询。"""
    root = Path(__file__).resolve().parents[4]
    workflow = yaml.safe_load((root / ".github/workflows/inspect-staging-tiktok-webhooks.yml").read_text("utf-8"))
    assert set(workflow["jobs"]) == {"inspect"}
    job = workflow["jobs"]["inspect"]
    assert job["environment"] == "staging"
    assert job["runs-on"] == ["self-hosted", "linux", "x64", "crm-staging"]
    assert "refs/heads/main" in job["if"]
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    assert "inspect_tiktok_webhooks.py" in commands
    assert "REAL_TIKTOK_READ_ENABLED=true" in commands
    assert "docker" in commands
    assert "docker compose up" not in commands
    assert "docker build" not in commands
    assert "PUT /event/202309/webhooks" not in commands
