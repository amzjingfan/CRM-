"""Phase 4 本地运行验收；创建低敏临时数据并在结束时清理。"""

import asyncio
import uuid

import httpx
from sqlalchemy import delete, insert, select

import app.shared.database.models  # noqa: F401
from app.audit.models import AuditLog
from app.auth.security import create_access_token, hash_password
from app.shared.database.base import Role, User, user_roles
from app.shared.database.session import session_factory
from app.stores.models import Store


async def create_runtime_admin() -> tuple[uuid.UUID, str]:
    """创建本次验收专用系统管理员，不打印令牌或密码。"""
    async with session_factory() as session:
        role = (await session.execute(select(Role).where(Role.code == "admin"))).scalar_one()
        user = User(
            email=f"phase4-{uuid.uuid4().hex[:12]}@example.invalid",
            password_hash=hash_password(uuid.uuid4().hex),
            name="Phase 4 Runtime Test",
        )
        session.add(user)
        await session.flush()
        await session.execute(
            insert(user_roles).values(id=uuid.uuid4(), user_id=user.id, role_id=role.id, store_id=None)
        )
        await session.commit()
        return user.id, create_access_token(user.id)


async def cleanup(user_id: uuid.UUID, store_id: uuid.UUID | None) -> None:
    """只删除脚本创建的精确用户和店铺，不触碰已有开发数据。"""
    async with session_factory() as session:
        await session.execute(delete(AuditLog).where(AuditLog.actor_id == user_id))
        if store_id is not None:
            await session.execute(delete(Store).where(Store.id == store_id))
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


async def main() -> None:
    user_id, token = await create_runtime_admin()
    store_id: uuid.UUID | None = None
    headers = {"Authorization": f"Bearer {token}"}
    suffix = uuid.uuid4().hex[:10]
    results: dict[str, bool] = {}
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000/v1", headers=headers, timeout=30) as client:
            store_response = await client.post(
                "/settings/stores",
                json={
                    "name": "Phase 4 Runtime",
                    "code": f"phase4-{suffix}",
                    "timezone": "Asia/Shanghai",
                    "currency": "CNY",
                },
            )
            store_response.raise_for_status()
            store_id = uuid.UUID(store_response.json()["data"]["id"])
            results["store"] = True
            agent_response = await client.post(
                "/agents",
                json={
                    "store_id": str(store_id),
                    "name": "Runtime Agent",
                    "code": "runtime_agent",
                    "description": "Phase 4 runtime verification",
                    "enabled_tools": ["query_order", "query_logistics"],
                },
            )
            agent_response.raise_for_status()
            agent_id = agent_response.json()["data"]["id"]
            results["agent"] = (await client.get(f"/agents/{agent_id}/logs")).status_code == 200
            results["dashboard"] = (
                await client.get(f"/dashboard/metrics?store_id={store_id}&period=7d")
            ).status_code == 200
            results["team"] = (await client.get("/settings/team")).status_code == 200
            async with client.stream("POST", "/chat/query", json={"session_id": str(uuid.uuid4())}) as stream:
                event_names = [
                    line.removeprefix("event:").strip()
                    async for line in stream.aiter_lines()
                    if line.startswith("event:")
                ]
            results["sse_error_contract"] = event_names == ["accepted", "status", "status", "error", "done"]
        if not all(results.values()):
            raise SystemExit(f"Phase 4 运行验收失败：{results}")
        print(f"Phase 4 运行验收通过：{results}")
    finally:
        await cleanup(user_id, store_id)


if __name__ == "__main__":
    asyncio.run(main())
