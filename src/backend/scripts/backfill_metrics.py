"""按日期范围幂等回填店铺每日指标。"""

import argparse
import asyncio
import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.dashboard.aggregation import aggregate_store_day
from app.shared.database.session import session_factory
from app.stores.models import Store


async def run(store_id: uuid.UUID, start: date, end: date) -> None:
    async with session_factory() as session:
        store = await session.scalar(select(Store).where(Store.id == store_id, Store.deleted_at.is_(None)))
        if store is None:
            raise SystemExit("店铺不存在")
        current = start
        while current <= end:
            await aggregate_store_day(session, store, current)
            current += timedelta(days=1)
        await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="幂等回填 CRM 每日指标")
    parser.add_argument("--store-id", type=uuid.UUID, required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    if args.end < args.start:
        raise SystemExit("结束日期不能早于开始日期")
    asyncio.run(run(args.store_id, args.start, args.end))


if __name__ == "__main__":
    main()
