"""知识服务专属 SQLAlchemy metadata 和会话工厂。"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.knowledge_service.config import KnowledgeServiceSettings


class KnowledgeBase(DeclarativeBase):
    """不包含任何 CRM model 的独立声明式基类。"""


def create_knowledge_engine(settings: KnowledgeServiceSettings) -> AsyncEngine:
    """按知识服务专属 URL 创建连接池。"""
    return create_async_engine(settings.database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """创建不跨服务共享的异步会话工厂。"""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# 在 metadata 定义后导入 models，使 Alembic 和边界测试看到全部专属表。
from app.knowledge_service import models as _models  # noqa: E402,F401
