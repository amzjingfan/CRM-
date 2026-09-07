"""通过公开建议接口验证一条真实 DeepSeek 合成演示请求。"""

import asyncio

import httpx
from sqlalchemy import select

from app.auth.security import create_access_token
from app.conversations.models import Conversation
from app.shared.database.base import Role, User
from app.shared.database.session import session_factory
from app.stores.models import Store


async def main() -> None:
    """使用现有系统管理员生成短期内存 Token，不读取或打印密码。"""
    async with session_factory() as session:
        admin = await session.scalar(
            select(User).where(User.status == "active", User.roles.any(Role.code == "admin")).limit(1)
        )
        store = await session.scalar(select(Store).where(Store.code == "ai-demo-store"))
        if admin is None or store is None:
            raise SystemExit("缺少系统管理员或 AI 演示店铺，请先执行 seed_ai_demo")
        conversation = await session.scalar(
            select(Conversation).where(
                Conversation.store_id == store.id,
                Conversation.external_conversation_id == "ai-demo-general",
            )
        )
        if conversation is None:
            raise SystemExit("缺少 AI 演示会话，请先执行 seed_ai_demo")
        token = create_access_token(admin.id)

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000/v1", timeout=60) as client:
        response = await client.post(
            f"/workspace/sessions/{conversation.id}/suggest",
            headers={"Authorization": f"Bearer {token}"},
            json={"trigger_message_id": None},
        )
        if not response.is_success:
            body = response.json()
            raise SystemExit(
                "AI 合成演示请求失败："
                f"status={response.status_code}, code={body.get('code')}, message={body.get('message')}"
            )
        result = response.json()["data"]
        if not result["demo_mode"] or not result["content"]:
            raise SystemExit("AI 合成演示未返回可人工使用的建议")
        sse_result: dict[str, object] | None = None
        async with client.stream(
            "POST",
            "/chat/query",
            headers={"Authorization": f"Bearer {token}"},
            json={"session_id": str(conversation.id), "trigger_message_id": None},
        ) as stream_response:
            if not stream_response.is_success:
                raise SystemExit(f"AI 合成演示 SSE 请求失败：status={stream_response.status_code}")
            event_name: str | None = None
            async for line in stream_response.aiter_lines():
                if line.startswith("event:"):
                    event_name = line.removeprefix("event:").strip()
                elif event_name == "result" and line.startswith("data:"):
                    import json

                    sse_result = json.loads(line.removeprefix("data:").strip())
        if sse_result is None or sse_result.get("demo_mode") is not True:
            raise SystemExit("AI 合成演示 SSE 未携带 demo_mode 标识")
        print(
            "AI synthetic demo passed: "
            f"intent={result['intent']}, confidence={result['confidence']:.2f}, "
            f"action={result['action']}, scenario={result['demo_scenario']}"
        )


if __name__ == "__main__":
    asyncio.run(main())
