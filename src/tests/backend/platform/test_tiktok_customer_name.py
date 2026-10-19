"""TikTok 消息通知缺少画像字段时的客户名称回归。"""

import uuid

import pytest

from app.customers.models import Customer
from app.integrations.adapters import TikTokAdapter
from app.integrations.service import _upsert_customer


@pytest.mark.asyncio
async def test_message_without_nickname_keeps_known_buyer_name() -> None:
    """通知只含买家 IM ID 时，工作台不能把已知昵称降级为匿名。"""
    store_id = uuid.uuid4()
    customer = Customer(
        id=uuid.uuid4(),
        store_id=store_id,
        platform="tiktok",
        external_customer_id="700000000000000001",
        name="Known buyer",
    )

    class ExistingCustomerSession:
        async def scalar(self, _statement: object) -> Customer:
            return customer

        async def flush(self) -> None:
            pass

    event = TikTokAdapter._resolve_message_event(
        "event-1",
        "shop-1",
        {
            "sender": {"role": "BUYER", "im_user_id": "700000000000000001"},
            "conversation_id": "710000000000000001",
            "message_id": "720000000000000001",
            "type": "TEXT",
            "content": '{"content":"hello"}',
            "create_time": 1792371400,
        },
    )
    assert event is not None
    assert event.customer.name is None

    await _upsert_customer(ExistingCustomerSession(), store_id, "tiktok", event.customer)  # type: ignore[arg-type]

    assert customer.name == "Known buyer"


@pytest.mark.asyncio
async def test_message_with_nickname_updates_known_buyer_name() -> None:
    store_id = uuid.uuid4()
    customer = Customer(
        id=uuid.uuid4(),
        store_id=store_id,
        platform="tiktok",
        external_customer_id="700000000000000001",
        name="Old buyer",
    )

    class ExistingCustomerSession:
        async def scalar(self, _statement: object) -> Customer:
            return customer

        async def flush(self) -> None:
            pass

    event = TikTokAdapter._resolve_message_event(
        "event-2",
        "shop-1",
        {
            "sender": {"role": "BUYER", "im_user_id": "700000000000000001", "nickname": "New buyer"},
            "conversation_id": "710000000000000001",
            "message_id": "720000000000000002",
            "type": "TEXT",
            "content": '{"content":"hello"}',
            "create_time": 1792371401,
        },
    )
    assert event is not None

    await _upsert_customer(ExistingCustomerSession(), store_id, "tiktok", event.customer)  # type: ignore[arg-type]

    assert customer.name == "New buyer"
