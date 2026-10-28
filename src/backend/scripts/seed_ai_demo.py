"""幂等创建不依赖真实店铺的 AI 手动演示数据。"""

import asyncio
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.agents.core.security import SYNTHETIC_DEMO_SCENARIOS
from app.agents.management.config_models import AgentConfig
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.orders.models import Order
from app.shared.database.session import session_factory
from app.stores.models import Store


async def seed() -> None:
    """创建固定合成会话；重复执行会恢复场景正文而不会产生重复数据。"""
    async with session_factory() as session:
        store = await session.scalar(select(Store).where(Store.code == "ai-demo-store"))
        if store is None:
            store = Store(
                id=uuid.uuid4(),
                name="AI 合成数据演示店铺",
                code="ai-demo-store",
                currency="USD",
                timezone="Asia/Shanghai",
                metadata_json={"synthetic_demo": True},
            )
            session.add(store)
            await session.flush()
        else:
            store.status = "active"
            store.metadata_json = {**store.metadata_json, "synthetic_demo": True}

        agent_config = await session.scalar(
            select(AgentConfig).where(AgentConfig.store_id == store.id, AgentConfig.code == "synthetic_demo_agent")
        )
        if agent_config is None:
            agent_config = AgentConfig(
                id=uuid.uuid4(),
                store_id=store.id,
                name="AI 合成演示 Agent",
                code="synthetic_demo_agent",
                description="仅处理服务端固定的虚构测试场景，不执行平台写操作",
                status="enabled",
                enabled_tools=[],
                knowledge_scope={"mode": "synthetic_demo"},
            )
            session.add(agent_config)
        else:
            agent_config.status = "enabled"
            agent_config.deleted_at = None

        now = datetime.now(UTC)
        conversation_ids: list[str] = []
        for scenario_id, scenario in SYNTHETIC_DEMO_SCENARIOS.items():
            external_customer_id = f"ai-demo-customer-{scenario_id}"
            customer = await session.scalar(
                select(Customer).where(
                    Customer.store_id == store.id,
                    Customer.platform == "tiktok",
                    Customer.external_customer_id == external_customer_id,
                )
            )
            if customer is None:
                customer = Customer(
                    id=uuid.uuid4(),
                    store_id=store.id,
                    platform="tiktok",
                    external_customer_id=external_customer_id,
                    name=f"演示客户·{scenario_id}",
                    tags=["AI合成演示"],
                    metadata_json={"synthetic_demo": True},
                )
                session.add(customer)
                await session.flush()

            external_conversation_id = f"ai-demo-{scenario_id}"
            conversation = await session.scalar(
                select(Conversation).where(
                    Conversation.store_id == store.id,
                    Conversation.external_conversation_id == external_conversation_id,
                )
            )
            if conversation is None:
                conversation = Conversation(
                    id=uuid.uuid4(),
                    store_id=store.id,
                    customer_id=customer.id,
                    platform="tiktok",
                    external_conversation_id=external_conversation_id,
                    status="active",
                    unread_count=1,
                    metadata_json={"synthetic_demo": True, "scenario_id": scenario_id},
                )
                session.add(conversation)
                await session.flush()

            external_message_id = f"ai-demo-message-{scenario_id}"
            message = await session.scalar(
                select(Message).where(Message.platform == "tiktok", Message.external_message_id == external_message_id)
            )
            if message is None:
                message = Message(
                    id=uuid.uuid4(),
                    store_id=store.id,
                    conversation_id=conversation.id,
                    customer_id=customer.id,
                    platform="tiktok",
                    external_message_id=external_message_id,
                    role="user",
                    direction="inbound",
                    content=scenario["customer_message"],
                    language="zh-CN",
                    status="received",
                    raw_payload={"synthetic_demo": True},
                )
                session.add(message)
                await session.flush()
            else:
                message.content = scenario["customer_message"]
                message.language = "zh-CN"
                message.status = "received"

            conversation.last_message_id = message.id
            conversation.last_message_at = now
            conversation.unread_count = 1
            conversation_ids.append(str(conversation.id))

            if scenario_id == "logistics":
                order = await session.scalar(
                    select(Order).where(
                        Order.store_id == store.id,
                        Order.platform == "tiktok",
                        Order.external_order_id == "DEMO-1001",
                    )
                )
                if order is None:
                    session.add(
                        Order(
                            id=uuid.uuid4(),
                            store_id=store.id,
                            customer_id=customer.id,
                            platform="tiktok",
                            external_order_id="DEMO-1001",
                            status="shipped",
                            payment_status="paid",
                            fulfillment_status="shipped",
                            currency="USD",
                            total_amount=Decimal("49.90"),
                            tracking_number="DEMO-TRACK-1001",
                            tracking_status="广州转运中心",
                            raw_payload={"synthetic_demo": True},
                        )
                    )

        await session.commit()
        print(f"AI synthetic demo ready: store={store.id}, conversations={len(conversation_ids)}")


if __name__ == "__main__":
    asyncio.run(seed())
