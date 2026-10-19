"""G2 真实重投探针：只用合成通知验证安全边界。"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

import app.integrations.service as service
from app.audit.models import AuditLog
from app.integrations.models import WebhookEvent
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
        assert nx is True and 0 < ex <= 86400
        if key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.values.get(key)


class FakeSession:
    def __init__(self, channel: SimpleNamespace) -> None:
        self.channel = channel
        self.event: WebhookEvent | None = None
        self.pending: list[object] = []
        self.audits: list[AuditLog] = []

    async def scalar(self, statement: object) -> object:
        entity = statement.column_descriptions[0]["entity"]  # type: ignore[attr-defined]
        return self.event if entity is WebhookEvent else self.channel if entity is ChannelAccount else None

    def add(self, item: object) -> None:
        self.pending.append(item)

    async def commit(self) -> None:
        for item in self.pending:
            if isinstance(item, WebhookEvent):
                item.id = uuid.uuid4()
                self.event = item
            if isinstance(item, AuditLog):
                self.audits.append(item)
        self.pending.clear()


def setup_probe(monkeypatch: pytest.MonkeyPatch, mode: str) -> tuple[FakeSession, FakeRedis, dict[str, object], bytes]:
    store_id = uuid.uuid4()
    channel = SimpleNamespace(id=uuid.uuid4(), store_id=store_id)
    session = FakeSession(channel)
    redis = FakeRedis()
    monkeypatch.setattr(service, "redis_client", redis, raising=False)
    settings = SimpleNamespace(
        app_env="staging",
        real_tiktok_webhook_enabled=True,
        g2_webhook_probe_mode=mode,
        g2_webhook_probe_run_id=uuid.uuid4(),
        g2_webhook_probe_store_id=store_id,
        g2_webhook_probe_conversation_id="710688832392260838",
        g2_webhook_probe_expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    monkeypatch.setattr(service, "get_settings", lambda: settings)

    class SignedAdapter:
        def verify_webhook(self, _raw_body: bytes, headers: dict[str, str]) -> bool:
            return headers.get("authorization") == "signed"

    monkeypatch.setattr(service, "get_platform_adapter", lambda _platform: SignedAdapter())
    payload: dict[str, object] = {
        "type": 14,
        "tts_notification_id": "7327112393057371910",
        "shop_id": "7494049642642441621",
        "data": {
            "conversation_id": "710688832392260838",
            "message_id": "722323407926368819",
            "create_time": 1718305585,
            "is_visible": True,
            "sender": {"role": "BUYER", "im_user_id": "707885565181165594"},
            "content": "synthetic private message",
        },
    }
    return session, redis, payload, b"synthetic raw signed body"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,first_persisted,second_duplicate",
    [
        ("before_commit_503", False, False),
        ("after_commit_503", True, True),
    ],
)
async def test_one_503_then_same_signed_event_is_accepted_and_audited(
    monkeypatch: pytest.MonkeyPatch, mode: str, first_persisted: bool, second_duplicate: bool
) -> None:
    session, _, payload, raw = setup_probe(monkeypatch, mode)
    with pytest.raises(AppError) as caught:
        await service.receive_webhook(session, "tiktok", raw, payload, {"authorization": "signed"})  # type: ignore[arg-type]
    assert caught.value.status_code == 503
    assert (session.event is not None) is first_persisted
    receipt = await service.receive_webhook(session, "tiktok", raw, payload, {"authorization": "signed"})  # type: ignore[arg-type]
    assert receipt.duplicate is second_duplicate
    assert len(session.audits) == 2
    assert {a.result for a in session.audits} == {"forced_503", "redelivered"}
    assert all(a.store_id == session.channel.store_id for a in session.audits)
    assert all("synthetic private message" not in str(a.after_data) for a in session.audits)
    assert all(
        a.after_data and a.after_data["payload_sha256"] == hashlib.sha256(raw).hexdigest() for a in session.audits
    )


@pytest.mark.asyncio
async def test_invalid_signature_and_other_conversation_cannot_consume_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    session, redis, payload, raw = setup_probe(monkeypatch, "before_commit_503")
    with pytest.raises(AppError) as caught:
        await service.receive_webhook(session, "tiktok", raw, payload, {"authorization": "invalid"})  # type: ignore[arg-type]
    assert caught.value.code == ErrorCode.TOKEN_INVALID
    assert not redis.values and not session.audits
    payload["data"] = {"conversation_id": "different", "sender": {"role": "BUYER"}, "is_visible": True}
    receipt = await service.receive_webhook(session, "tiktok", raw, payload, {"authorization": "signed"})  # type: ignore[arg-type]
    assert receipt.accepted and not redis.values and not session.audits


@pytest.mark.asyncio
async def test_expired_probe_cannot_rearm(monkeypatch: pytest.MonkeyPatch) -> None:
    session, redis, payload, raw = setup_probe(monkeypatch, "before_commit_503")
    settings = service.get_settings()
    settings.g2_webhook_probe_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    receipt = await service.receive_webhook(session, "tiktok", raw, payload, {"authorization": "signed"})  # type: ignore[arg-type]
    assert receipt.accepted and not redis.values and not session.audits


@pytest.mark.asyncio
async def test_other_store_and_non_buyer_do_not_consume_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    session, redis, payload, raw = setup_probe(monkeypatch, "before_commit_503")
    session.channel.store_id = uuid.uuid4()
    receipt = await service.receive_webhook(session, "tiktok", raw, payload, {"authorization": "signed"})  # type: ignore[arg-type]
    assert receipt.accepted and not redis.values and not session.audits

    other_session, other_redis, other_payload, other_raw = setup_probe(monkeypatch, "before_commit_503")
    other_payload["data"] = {
        "conversation_id": "710688832392260838",
        "message_id": "722323407926368819",
        "create_time": 1718305585,
        "sender": {"role": "CUSTOMER_SERVICE", "im_user_id": "707885565181165594"},
    }
    other = await service.receive_webhook(  # type: ignore[arg-type]
        other_session, "tiktok", other_raw, other_payload, {"authorization": "signed"}
    )
    assert other.accepted and not other_redis.values and not other_session.audits
