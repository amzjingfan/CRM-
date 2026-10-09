"""G2 staging 事件观测只读及低敏输出契约。"""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from scripts import inspect_tiktok_webhook_events as observer
from scripts.inspect_tiktok_webhook_events import summarize_events


def test_event_summary_exposes_only_fixed_aggregate_fields() -> None:
    """现场对账只保留数量，不回显动态状态、正文或店铺标识。"""
    result = summarize_events(
        [
            ("succeeded", True, 0, 2),
            ("failed", True, 2, 1),
            ("received", True, 0, 1),
            ("unexpected-sensitive-value", False, 0, 1),
        ],
        inbound_messages=3,
        unbound_events=0,
    )

    assert result == {
        "new_message_events": 5,
        "signature_valid_events": 4,
        "succeeded_events": 2,
        "failed_events": 1,
        "pending_events": 1,
        "ignored_events": 0,
        "other_status_events": 1,
        "retried_events": 1,
        "inbound_messages": 3,
        "unbound_tiktok_events": 0,
    }
    assert "unexpected-sensitive-value" not in str(result)


@pytest.mark.parametrize("invalid_count", [-1, True, "1"])
def test_event_summary_rejects_invalid_aggregate_count(invalid_count: object) -> None:
    with pytest.raises(ValueError, match="Invalid aggregate count"):
        summarize_events([("succeeded", True, 0, invalid_count)], 0, 0)


def test_event_observer_workflow_is_read_only_and_main_staging_only() -> None:
    root = Path(__file__).resolve().parents[4]
    workflow = yaml.safe_load((root / ".github/workflows/inspect-staging-tiktok-webhook-events.yml").read_text("utf-8"))
    assert set(workflow["jobs"]) == {"inspect"}
    job = workflow["jobs"]["inspect"]
    assert job["environment"] == "staging"
    assert job["runs-on"] == ["self-hosted", "linux", "x64", "crm-staging"]
    assert "refs/heads/main" in job["if"]
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    assert "inspect_tiktok_webhook_events.py" in commands
    assert "docker exec -i" in commands or "docker --host $dockerHost exec -i" in commands
    assert "docker compose up" not in commands
    assert "docker build" not in commands
    assert "PUT /event" not in commands


def test_inspection_starts_readonly_transaction_before_select(monkeypatch: pytest.MonkeyPatch) -> None:
    statements: list[str] = []

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def execute(self, statement: object) -> SimpleNamespace:
            statements.append(str(statement))
            return SimpleNamespace(all=lambda: [])

        async def scalars(self, statement: object) -> SimpleNamespace:
            statements.append(str(statement))
            return SimpleNamespace(all=lambda: [SimpleNamespace(id="channel", store_id="store")])

        async def scalar(self, statement: object) -> int:
            statements.append(str(statement))
            return 0

    monkeypatch.setattr(
        observer, "get_settings", lambda: SimpleNamespace(app_env="staging", real_tiktok_webhook_enabled=True)
    )
    monkeypatch.setattr(observer, "session_factory", FakeSession)

    result = asyncio.run(observer.inspect())

    assert statements[0] == "SET TRANSACTION READ ONLY"
    assert len(statements) == 5
    assert result["new_message_events"] == 0
