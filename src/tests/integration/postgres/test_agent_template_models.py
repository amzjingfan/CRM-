"""只在显式隔离测试库验证模板迁移与数据库约束。"""

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.management.config_models import AgentConfig
from app.agents.management.templates.models import (
    AgentTemplate,
    AgentTemplateBatch,
    AgentTemplateBatchItem,
    AgentTemplateVersion,
)
from app.shared.database.base import User
from app.stores.models import Store

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="未提供隔离的 PostgreSQL 测试数据库")


@pytest.mark.asyncio
async def test_migration_upgrade_downgrade_roundtrip_preserves_independent_agent() -> None:
    # 降级只能显式选择本任务隔离库，普通回归环境不运行结构破坏性往返。
    if os.getenv("AGENT_TEMPLATE_MIGRATION_ROUNDTRIP") != "1":
        pytest.skip("未开启模板迁移往返")
    assert (
        TEST_DATABASE_URL
        == "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:56874/crm_template_batch_migration_test_20261030"
    )
    backend = Path(__file__).resolve().parents[3] / "backend"
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id, config_id = uuid.uuid4(), uuid.uuid4()
    try:
        async with sessions() as session:
            session.add(Store(id=store_id, name="迁移独立店铺", code=store_id.hex))
            await session.flush()
            # Core INSERT 只使用044已有列，真实验证新增模板列不会自动关联历史配置。
            await session.execute(
                AgentConfig.__table__.insert().values(
                    id=config_id,
                    store_id=store_id,
                    name="原有独立Agent",
                    code="legacy",
                )
            )
            await session.commit()
        for target in ("046_merge_templates_dispatch", "044_reception_assignment", "046_merge_templates_dispatch"):
            action = "downgrade" if target == "044_reception_assignment" else "upgrade"
            result = subprocess.run(
                [sys.executable, "-m", "alembic", action, target],
                cwd=backend,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            assert result.returncode == 0, result.stdout + result.stderr
            if action == "downgrade":
                async with sessions() as session:
                    # 044 是两条 045 的共同父节点；退出两分支，保留原有独立 Agent。
                    assert await session.scalar(text("SELECT to_regclass('user_login_sessions')")) is None
                    assert await session.scalar(text("SELECT to_regclass('agent_templates')")) is None
                    assert (
                        await session.scalar(
                            text("SELECT count(*) FROM agent_configs WHERE id = :id"), {"id": config_id}
                        )
                        == 1
                    )
        async with sessions() as session:
            assert await session.scalar(text("SELECT to_regclass('user_login_sessions')")) is not None
            independent = await session.get(AgentConfig, config_id)
            assert independent is not None and independent.name == "原有独立Agent"
            assert independent.template_id is None and independent.template_state_json is None
            assert independent.draft_revision == 1 and independent.status == "disabled"
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_store_template_active_uniqueness_and_independent_agents() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    store_id, other_store_id, template_id = (uuid.uuid4() for _ in range(3))
    try:
        async with sessions() as session:
            session.add_all(
                [
                    Store(id=store_id, name="模板测试", code=store_id.hex),
                    Store(id=other_store_id, name="模板另店", code=other_store_id.hex),
                    AgentTemplate(id=template_id, name="模板"),
                ]
            )
            await session.flush()
            independent = AgentConfig(store_id=store_id, name="独立", code="independent")
            session.add_all(
                [
                    independent,
                    AgentConfig(store_id=store_id, name="独立二", code="independent2"),
                    AgentConfig(
                        store_id=store_id,
                        name="已删",
                        code="deleted",
                        template_id=template_id,
                        deleted_at=datetime.now(UTC),
                    ),
                    AgentConfig(store_id=store_id, name="关联", code="linked", template_id=template_id),
                    AgentConfig(store_id=other_store_id, name="另店关联", code="linked", template_id=template_id),
                ]
            )
            await session.commit()
            assert independent.template_id is None and independent.template_state_json is None
            assert independent.status == "disabled"
            session.add(AgentConfig(store_id=store_id, name="重复", code="duplicate", template_id=template_id))
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
            assert (
                await session.scalar(select(AgentTemplate.draft_revision).where(AgentTemplate.id == template_id)) == 1
            )
    finally:
        async with sessions() as session:
            await session.execute(delete(Store).where(Store.id.in_([store_id, other_store_id])))
            await session.execute(delete(AgentTemplate).where(AgentTemplate.id == template_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_populated_template_prevents_destructive_downgrade() -> None:
    if os.getenv("AGENT_TEMPLATE_MIGRATION_ROUNDTRIP") != "1":
        pytest.skip("未开启模板迁移往返")
    assert (
        TEST_DATABASE_URL
        == "postgresql+asyncpg://crm_test:crm_test@127.0.0.1:56874/crm_template_batch_migration_test_20261030"
    )
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    template_id = uuid.uuid4()
    try:
        async with sessions() as session:
            session.add(AgentTemplate(id=template_id, name="保留模板事实"))
            await session.commit()
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "044_reception_assignment"],
            cwd=Path(__file__).resolve().parents[3] / "backend",
            env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode != 0
        assert "不能无损降级" in result.stdout + result.stderr
        async with sessions() as session:
            assert (
                await session.scalar(text("SELECT version_num FROM alembic_version")) == "046_merge_templates_dispatch"
            )
            assert await session.get(AgentTemplate, template_id) is not None
            assert await session.scalar(text("SELECT to_regclass('user_login_sessions')")) is not None
    finally:
        async with sessions() as session:
            await session.execute(delete(AgentTemplate).where(AgentTemplate.id == template_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_version_number_and_creator_idempotency_constraints_and_batch_defaults() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    template_id, store_id, user_id, other_user_id = (uuid.uuid4() for _ in range(4))
    try:
        async with sessions() as session:
            session.add_all(
                [
                    AgentTemplate(id=template_id, name="版本模板"),
                    Store(id=store_id, name="批次店铺", code=store_id.hex),
                    User(id=user_id, login_name=f"tp{user_id.hex[:12]}", name="操作者", password_hash="test"),
                    User(
                        id=other_user_id,
                        login_name=f"tp{other_user_id.hex[:12]}",
                        name="其他操作者",
                        password_hash="test",
                    ),
                ]
            )
            await session.flush()
            session.add(
                AgentTemplateVersion(template_id=template_id, version=1, config_json={}, content_sha256="a" * 64)
            )
            await session.flush()
            batch = AgentTemplateBatch(template_id=template_id, template_version=1, created_by=user_id)
            session.add(batch)
            await session.flush()
            item = AgentTemplateBatchItem(batch_id=batch.id, store_id=store_id, target_config_json={})
            session.add(item)
            await session.commit()
            assert batch.status == "preview" and batch.idempotency_key is None
            assert item.status == "pending" and item.attempt_count == 0
            assert item.attempt_token is None and item.lease_expires_at is None
            assert item.requested_by is None
            item.requested_by = user_id
            await session.commit()
            await session.refresh(item)
            assert item.requested_by == user_id
            batch_id = item.batch_id
            session.add(AgentTemplateBatchItem(batch_id=batch_id, store_id=store_id))
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
            session.add(
                AgentTemplateVersion(template_id=template_id, version=1, config_json={}, content_sha256="b" * 64)
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
            with pytest.raises(IntegrityError):
                await session.execute(
                    update(AgentTemplateVersion)
                    .where(AgentTemplateVersion.template_id == template_id)
                    .values(config_json={"changed": True})
                )
            await session.rollback()
            assert (
                await session.scalar(
                    select(AgentTemplateVersion.config_json).where(AgentTemplateVersion.template_id == template_id)
                )
                == {}
            )
            session.add_all(
                [
                    AgentTemplateBatch(
                        template_id=template_id, template_version=1, created_by=user_id, idempotency_key="key"
                    ),
                    AgentTemplateBatch(
                        template_id=template_id, template_version=1, created_by=other_user_id, idempotency_key="key"
                    ),
                    AgentTemplateBatch(template_id=template_id, template_version=1, created_by=user_id),
                ]
            )
            await session.commit()
            session.add(
                AgentTemplateBatch(
                    template_id=template_id, template_version=1, created_by=user_id, idempotency_key="key"
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
            # 数据库本身拒绝非正版本号，避免手工写入绕过接口。
            session.add(
                AgentTemplateVersion(template_id=template_id, version=0, config_json={}, content_sha256="a" * 64)
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
            session.add(AgentTemplateBatch(template_id=template_id, template_version=999, created_by=user_id))
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()
            assert (
                await session.scalar(text("SELECT version_num FROM alembic_version")) == "046_merge_templates_dispatch"
            )
    finally:
        async with sessions() as session:
            await session.execute(delete(AgentTemplateBatch).where(AgentTemplateBatch.template_id == template_id))
            await session.execute(delete(AgentTemplate).where(AgentTemplate.id == template_id))
            await session.execute(delete(Store).where(Store.id == store_id))
            await session.execute(delete(User).where(User.id.in_([user_id, other_user_id])))
            await session.commit()
        await engine.dispose()
