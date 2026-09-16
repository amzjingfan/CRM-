"""异步数据库会话工厂。"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.shared.config.settings import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """为每个请求提供独立数据库会话，并在结束时释放资源。"""
    async with session_factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
