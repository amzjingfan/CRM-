"""Phase 3 本地运行验收脚本。

脚本只在显式提供临时测试密码时运行，结束后清理用户和业务测试数据，
不会打印密码、Token、原始导入文件或客户隐私。
"""

import asyncio
import os
import uuid

import httpx
from sqlalchemy import delete, insert, select

import app.shared.database.models  # noqa: F401  # 注册全部外键目标，脚本直接使用 ORM 写入夹具。
from app.audit.models import AuditLog
from app.auth.security import hash_password
from app.customers.models import Customer
from app.knowledge_base.models import KnowledgeCategory, KnowledgeDocument, KnowledgeImportJob
from app.marketing.models import MarketingCampaign
from app.orders.models import Order
from app.shared.database.base import Role, User, user_roles
from app.shared.database.session import session_factory
from app.tools.models import CouponIssuance, ToolCall


def phase3_write_headers(auth_headers: dict[str, str], suffix: str, operation: str) -> dict[str, str]:
    """为运行验收中的每个写动作生成稳定且互不冲突的幂等键。"""
    return auth_headers | {"Idempotency-Key": f"phase3-runtime:{suffix}:{operation}"}


async def _ensure_admin(email: str, password: str) -> uuid.UUID:
    """创建仅用于本次验收的系统管理员。"""
    async with session_factory() as session:
        role = (await session.execute(select(Role).where(Role.code == "admin"))).scalar_one()
        user = User(email=email, password_hash=hash_password(password), name="Phase 3 Runtime Test")
        session.add(user)
        await session.flush()
        await session.execute(
            insert(user_roles).values(id=uuid.uuid4(), user_id=user.id, role_id=role.id, store_id=None)
        )
        await session.commit()
        return user.id


async def _create_tool_fixtures(store_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """创建仅供工具接口验收的客户和订单。"""
    async with session_factory() as session:
        customer = Customer(store_id=store_id, platform="shopee", external_customer_id=f"runtime-{uuid.uuid4()}")
        session.add(customer)
        await session.flush()
        order = Order(
            store_id=store_id,
            customer_id=customer.id,
            platform="shopee",
            external_order_id=f"runtime-{uuid.uuid4()}",
            status="pending",
            payment_status="unpaid",
            currency="USD",
            tracking_number="MOCK-TRACKING",
            tracking_status="in_transit",
        )
        session.add(order)
        await session.commit()
        return customer.id, order.id


async def _cleanup(
    email: str,
    user_id: uuid.UUID,
    import_job_ids: list[uuid.UUID],
    tool_call_ids: list[uuid.UUID],
    entry_ids: list[str],
    category_id: str | None,
    campaign_id: str | None,
    customer_id: uuid.UUID | None,
    order_id: uuid.UUID | None,
) -> None:
    """清理验收脚本创建的任务和临时用户。"""
    async with session_factory() as session:
        # 接口在返回前可能已经成功落库，因此同时按 actor 清理未被脚本记录 ID 的调用。
        actor_tool_call_ids = list(
            (await session.scalars(select(ToolCall.id).where(ToolCall.actor_id == user_id))).all()
        )
        all_tool_call_ids = list(set(tool_call_ids + actor_tool_call_ids))
        if import_job_ids:
            await session.execute(delete(KnowledgeImportJob).where(KnowledgeImportJob.id.in_(import_job_ids)))
        if campaign_id:
            await session.execute(delete(MarketingCampaign).where(MarketingCampaign.id == uuid.UUID(campaign_id)))
        if entry_ids:
            await session.execute(
                delete(KnowledgeDocument).where(
                    KnowledgeDocument.id.in_([uuid.UUID(entry_id) for entry_id in entry_ids])
                )
            )
        if category_id:
            await session.execute(delete(KnowledgeCategory).where(KnowledgeCategory.id == uuid.UUID(category_id)))
        if all_tool_call_ids:
            await session.execute(delete(CouponIssuance).where(CouponIssuance.tool_call_id.in_(all_tool_call_ids)))
            await session.execute(delete(ToolCall).where(ToolCall.id.in_(all_tool_call_ids)))
        await session.execute(delete(AuditLog).where(AuditLog.actor_id == user_id))
        if order_id:
            await session.execute(delete(Order).where(Order.id == order_id))
        if customer_id:
            await session.execute(delete(Customer).where(Customer.id == customer_id))
        user = await session.scalar(select(User).where(User.email == email))
        if user is not None:
            await session.delete(user)
        await session.commit()


async def verify() -> None:
    """通过真实 FastAPI、PostgreSQL、MinIO 和 jobs Worker 验证主链路。"""
    password = os.environ.get("PHASE3_TEST_PASSWORD")
    if not password or len(password) < 12:
        raise RuntimeError("PHASE3_TEST_PASSWORD 必须是至少 12 位临时密码")
    email = f"phase3-{uuid.uuid4().hex}@example.com"
    category_id: str | None = None
    entry_ids: list[str] = []
    campaign_id: str | None = None
    import_jobs: list[uuid.UUID] = []
    tool_calls: list[uuid.UUID] = []
    customer_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    user_id = await _ensure_admin(email, password)
    try:
        async with httpx.AsyncClient(base_url="http://localhost:8000/v1", timeout=15) as client:
            login: httpx.Response | None = None
            for _ in range(20):
                try:
                    login = await client.post("/auth/login", json={"email": email, "password": password})
                    break
                except httpx.ConnectError:
                    # Compose 刚重建时等待 Uvicorn 完成应用启动，避免把启动竞态误判为接口失败。
                    await asyncio.sleep(0.5)
            if login is None:
                raise RuntimeError("后端服务未在 10 秒内就绪")
            login.raise_for_status()
            token = login.json()["data"]["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            stores = await client.get("/settings/stores", headers=headers)
            stores.raise_for_status()
            store_id = stores.json()["data"][0]["id"]
            customer_id, order_id = await _create_tool_fixtures(uuid.UUID(store_id))
            suffix = uuid.uuid4().hex[:8]

            logistics = await client.get(f"/workspace/actions/order/{order_id}/logistics", headers=headers)
            logistics.raise_for_status()
            assert logistics.json()["data"]["tracking_status"] == "in_transit"
            address_key = f"runtime-address-{suffix}"
            address_payload = {
                "recipient_name": "Runtime User",
                "address_line1": "Test address",
                "city": "Test City",
                "postal_code": "000000",
                "country_code": "CN",
            }
            address = await client.patch(
                f"/workspace/actions/order/{order_id}/shipping-address",
                headers=headers | {"Idempotency-Key": address_key},
                json=address_payload,
            )
            address.raise_for_status()
            tool_calls.append(uuid.UUID(address.json()["data"]["tool_call_id"]))
            replay = await client.patch(
                f"/workspace/actions/order/{order_id}/shipping-address",
                headers=headers | {"Idempotency-Key": address_key},
                json=address_payload,
            )
            replay.raise_for_status()
            assert replay.json()["data"]["replayed"] is True
            conflict = await client.patch(
                f"/workspace/actions/order/{order_id}/shipping-address",
                headers=headers | {"Idempotency-Key": address_key},
                json=address_payload | {"city": "Changed City"},
            )
            assert conflict.status_code == 409

            coupon_key = f"runtime-coupon-{suffix}"
            coupon = await client.post(
                f"/workspace/actions/customer/{customer_id}/coupon",
                headers=headers | {"Idempotency-Key": coupon_key},
                json={"coupon_code": "RUNTIME10"},
            )
            coupon.raise_for_status()
            tool_calls.append(uuid.UUID(coupon.json()["data"]["tool_call_id"]))
            coupon_replay = await client.post(
                f"/workspace/actions/customer/{customer_id}/coupon",
                headers=headers | {"Idempotency-Key": coupon_key},
                json={"coupon_code": "RUNTIME10"},
            )
            coupon_replay.raise_for_status()
            assert coupon_replay.json()["data"]["replayed"] is True

            category = await client.post(
                "/knowledge/categories",
                headers=phase3_write_headers(headers, suffix, "category-create"),
                json={"store_id": store_id, "name": "运行验收", "code": f"runtime-{suffix}"},
            )
            category.raise_for_status()
            category_id = category.json()["data"]["id"]
            entry = await client.post(
                "/knowledge/entries",
                headers=phase3_write_headers(headers, suffix, "entry-create"),
                json={
                    "store_id": store_id,
                    "category_id": category_id,
                    "question": f"Phase3 runtime {suffix}",
                    "answer": "运行验收答案",
                    "tags": ["runtime"],
                },
            )
            entry.raise_for_status()
            entry_id = entry.json()["data"]["id"]
            entry_ids.append(entry_id)
            published = await client.post(
                f"/knowledge/entries/{entry_id}/publish",
                headers=phase3_write_headers(headers, suffix, "entry-publish"),
            )
            published.raise_for_status()
            assert published.json()["data"]["vectorization_status"] == "pending"

            imported_question = f"Imported runtime {suffix}"
            upload = await client.post(
                "/knowledge/imports",
                headers=phase3_write_headers(headers, suffix, "knowledge-import"),
                data={"store_id": store_id},
                files={
                    "file": (
                        "runtime.csv",
                        (
                            "question,answer,category_code,status\n"
                            f"{imported_question},Imported answer,runtime-{suffix},draft\n"
                        ),
                        "text/csv",
                    )
                },
            )
            upload.raise_for_status()
            job_id = uuid.UUID(upload.json()["data"]["job_id"])
            import_jobs.append(job_id)
            job_status = "pending"
            for _ in range(20):
                await asyncio.sleep(0.5)
                progress = await client.get(f"/knowledge/imports/{job_id}", headers=headers)
                progress.raise_for_status()
                job_status = progress.json()["data"]["status"]
                if job_status in {"succeeded", "partially_succeeded", "failed"}:
                    break
            assert job_status == "succeeded"
            imported = await client.get(
                "/knowledge/entries",
                headers=headers,
                params={"store_id": store_id, "search": imported_question, "page": 1, "page_size": 20},
            )
            imported.raise_for_status()
            imported_items = imported.json()["data"]["items"]
            assert len(imported_items) == 1
            entry_ids.append(imported_items[0]["id"])

            campaign = await client.post(
                "/marketing/campaigns",
                headers=phase3_write_headers(headers, suffix, "campaign-create"),
                json={
                    "store_id": store_id,
                    "name": f"Runtime {suffix}",
                    "trigger_type": "bad_review",
                    "action_type": "send_message",
                    "content_mode": "ai",
                    "trigger_delay_minutes": 5,
                },
            )
            campaign.raise_for_status()
            campaign_id = campaign.json()["data"]["id"]
            enabled = await client.post(
                f"/marketing/campaigns/{campaign_id}/enable",
                headers=phase3_write_headers(headers, suffix, "campaign-enable"),
            )
            enabled.raise_for_status()
            assert enabled.json()["data"]["status"] == "active"
            disabled = await client.post(
                f"/marketing/campaigns/{campaign_id}/disable",
                headers=phase3_write_headers(headers, suffix, "campaign-disable"),
            )
            disabled.raise_for_status()

            for index, target_id in enumerate(entry_ids):
                response = await client.delete(
                    f"/knowledge/entries/{target_id}",
                    headers=phase3_write_headers(headers, suffix, f"entry-delete-{index}"),
                )
                response.raise_for_status()
            response = await client.delete(
                f"/knowledge/categories/{category_id}",
                headers=phase3_write_headers(headers, suffix, "category-delete"),
            )
            response.raise_for_status()
            category_id = None
            response = await client.delete(
                f"/marketing/campaigns/{campaign_id}",
                headers=phase3_write_headers(headers, suffix, "campaign-delete"),
            )
            response.raise_for_status()
            campaign_id = None
        print("Phase 3 runtime verification passed: knowledge/import/tools/marketing")
    finally:
        await _cleanup(
            email,
            user_id,
            import_jobs,
            tool_calls,
            entry_ids,
            category_id,
            campaign_id,
            customer_id,
            order_id,
        )


if __name__ == "__main__":
    asyncio.run(verify())
