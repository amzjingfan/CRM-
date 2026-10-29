"""物流观察、复核和受控投递；任何模型参数都不能授予发送权限。"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from langchain_core.tools import BaseTool, tool

from .contracts import (
    AuthorizationSnapshot,
    BoundLogisticsEvent,
    DeliveryMode,
    LogisticsObservation,
    LogisticsRepository,
    LogisticsUpdateResult,
    NotificationArguments,
    NotificationDeliveryPort,
    NotificationRecord,
    PreparedLogisticsNotification,
    ReviewDecision,
)

logger = logging.getLogger(__name__)
Authorize = Callable[[BoundLogisticsEvent], Awaitable[AuthorizationSnapshot]]
Review = Callable[[BoundLogisticsEvent, str], Awaitable[ReviewDecision]]
Generate = Callable[[BoundLogisticsEvent], Awaitable[str]]


class LogisticsUpdateService:
    def __init__(
        self,
        *,
        repository: LogisticsRepository,
        authorize: Authorize,
        review: Review,
        generate: Generate,
        delivery: NotificationDeliveryPort,
        mode: DeliveryMode = "preview",
    ) -> None:
        if mode not in {"preview", "external"}:
            raise ValueError("未知物流通知交付模式")
        self.repository = repository
        self.authorize = authorize
        self.review = review
        self.generate = generate
        self.delivery = delivery
        self.mode = mode

    async def observe(self, observation: LogisticsObservation) -> LogisticsUpdateResult:
        return await self.repository.record(observation)

    async def observe_and_notify(self, observation: LogisticsObservation) -> LogisticsUpdateResult:
        result = await self.observe(observation)
        if result.context is None:
            return result
        return await self._execute(result.context, None)

    async def _denial(self, context: BoundLogisticsEvent) -> str | None:
        try:
            return (await self.authorize(context)).blocking_reason
        except asyncio.CancelledError:
            raise
        except Exception:
            return "authorization_unavailable"

    async def notify(self, context: BoundLogisticsEvent | None, candidate_text: str) -> LogisticsUpdateResult:
        if context is None:
            return LogisticsUpdateResult(status="context_unavailable")
        return await self._execute(context, candidate_text)

    async def resume(self, context: BoundLogisticsEvent) -> LogisticsUpdateResult:
        """可信 worker 恢复已持久观察，重新授权和生成，不重复读取或提交观察。"""
        return await self._execute(context, None)

    async def _execute(self, context: BoundLogisticsEvent, candidate_text: str | None) -> LogisticsUpdateResult:
        row = await self.repository.get(context)
        if row is None:
            return LogisticsUpdateResult(status="context_unavailable")
        claim_token = await self.repository.claim(context)
        if claim_token is None:
            return await self._result(context)
        try:
            reason = await self._denial(context)
            if reason:
                await self.repository.finish(context, "blocked", reason, claim_token=claim_token)
                return await self._result(context)
            if candidate_text is None:
                try:
                    candidate_text = await self.generate(context)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    await self.repository.finish(context, "failed", "generation_failed", claim_token=claim_token)
                    return await self._result(context)
            arguments = NotificationArguments(candidate_text=candidate_text)
            decision = await self.review(context, arguments.candidate_text)
            if decision.status != "approved" or decision.text is None:
                await self.repository.finish(context, "rejected", decision.reason, claim_token=claim_token)
                return await self._result(context)
            reason = await self._denial(context)
            if reason:
                await self.repository.finish(context, "blocked", reason, claim_token=claim_token)
                return await self._result(context)
            if not await self.repository.prepare(context, decision.text, self.mode, claim_token=claim_token):
                await self.repository.finish(context, "superseded", "newer_event", claim_token=claim_token)
                return await self._result(context)
        except asyncio.CancelledError:
            await asyncio.shield(self.repository.finish(context, "failed", "review_cancelled", claim_token=claim_token))
            raise
        except Exception:
            await self.repository.finish(context, "failed", "review_failed", claim_token=claim_token)
            return await self._result(context)
        prepared = self._prepared(context, decision.text)
        try:
            operation = self.delivery.preview if self.mode == "preview" else self.delivery.deliver
            receipt = await operation(prepared)
        except asyncio.CancelledError:
            # prepare 已把潜在写入记为 unknown，取消也不得回退成可重试状态。
            raise
        except Exception:
            logger.warning("logistics_notification_delivery_unknown", extra={"event_key": context.idempotency_key})
            await self.repository.finish(context, "unknown", "delivery_unknown", claim_token=claim_token)
            return await self._result(context)
        state = "previewed" if self.mode == "preview" and receipt.status == "succeeded" else receipt.status
        await self.repository.finish(context, state, reference=receipt.reference, claim_token=claim_token)
        return await self._result(context)

    async def reconcile(self, context: BoundLogisticsEvent) -> LogisticsUpdateResult:
        row = await self.repository.get(context)
        if row is None:
            return LogisticsUpdateResult(status="context_unavailable")
        if row.state != "unknown" or row.reviewed_text is None or row.mode != "external":
            return await self._result(context)
        # 对账只读取原稳定交付键，不生成新计划或再次调用 deliver。
        try:
            receipt = await self.delivery.reconcile(self._prepared(context, row.reviewed_text))
        except asyncio.CancelledError:
            raise
        except Exception:
            return await self._result(context)
        await self.repository.finish(context, receipt.status, reference=receipt.reference)
        return await self._result(context)

    @staticmethod
    def _prepared(context: BoundLogisticsEvent, text: str) -> PreparedLogisticsNotification:
        return PreparedLogisticsNotification(
            scope=context.scope,
            event=context.event,
            buyer_language=context.buyer_language,
            idempotency_key=context.idempotency_key,
            text=text,
        )

    async def _result(self, context: BoundLogisticsEvent) -> LogisticsUpdateResult:
        row: NotificationRecord | None = await self.repository.get(context)
        if row is None:
            return LogisticsUpdateResult(status="context_unavailable")
        return LogisticsUpdateResult(
            status=row.state, reason=row.reason, context=context, idempotency_key=context.idempotency_key
        )


def build_notify_logistics_update_tool(
    service: LogisticsUpdateService | None,
    *,
    context: BoundLogisticsEvent | None,
) -> BaseTool:
    @tool(
        "notify_logistics_update",
        args_schema=NotificationArguments,
        description="为当前已核验的新物流节点提出一条买家语言通知；必须复核及重新授权，默认只预览。普通问答没有事件上下文时不可发送。",
    )
    async def notify_logistics_update(candidate_text: str) -> dict[str, object]:
        """可信服务闭包绑定店铺、买家、会话、订单和事件，模型不能选目标或确认。"""
        if service is None:
            return {"status": "context_unavailable", "reason": None}
        result = await service.notify(context, candidate_text)
        # 只回传低敏状态；正文、真实目标和内部上下文不送回模型。
        return {"status": result.status, "reason": result.reason}

    return notify_logistics_update
