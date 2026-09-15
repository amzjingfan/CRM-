"""创建 Phase 2 本地契约测试店铺与三平台渠道，不创建固定密码。"""

import asyncio
import uuid

from sqlalchemy import select

from app.shared.database.session import session_factory
from app.stores.models import ChannelAccount, Store


async def seed() -> None:
    """幂等创建演示店铺和契约级 Mock 渠道。"""
    async with session_factory() as session:
        store = await session.scalar(select(Store).where(Store.code == "demo-store"))
        if store is None:
            store = Store(id=uuid.uuid4(), name="Phase 2 演示店铺", code="demo-store", currency="USD")
            session.add(store)
            await session.flush()
        for platform in ("tiktok", "shopee", "amazon"):
            external_store_id = f"demo-{platform}-store"
            channel = await session.scalar(
                select(ChannelAccount).where(
                    ChannelAccount.platform == platform,
                    ChannelAccount.external_store_id == external_store_id,
                )
            )
            if channel is None:
                session.add(
                    ChannelAccount(
                        id=uuid.uuid4(),
                        store_id=store.id,
                        platform=platform,
                        external_store_id=external_store_id,
                        display_name=f"{platform.title()} Demo",
                        access_token_ref=f"secret://development/{platform}",
                        scopes=["messages", "orders"],
                    )
                )
        await session.commit()
        print(f"Phase 2 demo store ready: {store.id}")


if __name__ == "__main__":
    asyncio.run(seed())
