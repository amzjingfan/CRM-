"""SQLAlchemy 白名单工具执行器，为 Agent 提供唯一业务副作用边界。"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditLog
from app.auth.store_access import allowed_store_ids, supervised_store_ids
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.integrations.adapters import get_message_adapter
from app.integrations.schemas import SendMessageCommand
from app.integrations.tiktok_write import is_tiktok_send_target_allowed
from app.orders.models import Order
from app.shared.config.settings import get_settings
from app.shared.database.base import Permission, User, role_permissions, user_roles
from app.shared.exceptions.errors import AppError
from app.stores.models import ChannelAccount, Store
from app.tools.contracts import (
    READ_REPLAY_CONTRACT_VERSION,
    TOOL_DEFINITIONS,
    QueryCustomerProfileArguments,
    QueryLogisticsArguments,
    QueryOrderArguments,
    SendCouponArguments,
    SendPlatformMessageArguments,
    ToolInvocation,
    ToolName,
    ToolResult,
    ToolStatus,
    TransferToHumanArguments,
    UpdateShippingAddressArguments,
    validate_read_tool_replay_output,
    validate_tool_arguments,
    validate_tool_output,
)
from app.tools.models import CouponIssuance, ToolCall
from app.tools.repository import begin_tool_call, finish_tool_call
from app.workspace.media import verify_media_claim

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ToolDispatchOutcome:
    """执行器内部结果，区分返回数据和可持久化低敏摘要。"""

    status: ToolStatus
    data: dict[str, object] | None
    output_summary: dict[str, object] | None
    mocked: bool = False
    error_code: str | None = None


class ToolDispatchError(Exception):
    """工具资源或业务校验失败，不向 Agent 暴露数据库异常细节。"""

    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


class SqlAlchemyToolExecutor:
    """执行七个白名单工具并统一记录权限、幂等、终态和审计。"""

    def __init__(self, session: AsyncSession) -> None:
        """绑定当前 Agent 运行使用的数据库会话。"""
        self.session = session

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        """执行单个受控工具，任何失败都返回稳定状态而不伪装成功。"""
        definition = TOOL_DEFINITIONS[invocation.tool_name]
        arguments = validate_tool_arguments(invocation.tool_name, invocation.arguments)
        try:
            call, replayed, started_at = await begin_tool_call(
                self.session,
                invocation.context.store_id,
                invocation.context.actor_type,
                invocation.context.actor_id,
                invocation.tool_name,
                invocation.idempotency_key,
                arguments,
                self._input_summary(invocation.tool_name, arguments),
                invocation.context.agent_run_id,
                invocation.context.trace_id,
            )
        except AppError as error:
            # 冲突关联原工具记录返回，避免异常穿透工作流或伪造一条未持久化调用。
            existing = await self.session.scalar(
                select(ToolCall).where(
                    ToolCall.store_id == invocation.context.store_id,
                    ToolCall.idempotency_key == invocation.idempotency_key,
                )
            )
            if existing is None:
                raise ToolDispatchError("TOOL_IDEMPOTENCY_CONFLICT") from error
            return ToolResult(
                tool_call_id=existing.id,
                status="failed",
                error_code="TOOL_IDEMPOTENCY_CONFLICT",
                mocked=existing.mocked,
                replayed=True,
            )

        if definition.permission not in invocation.context.permissions:
            # 重放仍须按当前权限判定；权限已撤销时不能返回历史摘要。
            # 历史终态是原调用证据，拒绝重放时不得把它覆盖成失败。
            if not replayed:
                await finish_tool_call(
                    self.session,
                    call,
                    started_at,
                    "failed",
                    None,
                    False,
                    "TOOL_PERMISSION_DENIED",
                )
            return ToolResult(
                tool_call_id=call.id,
                status="failed",
                error_code="TOOL_PERMISSION_DENIED",
                replayed=replayed,
            )

        if replayed:
            replay_status = self._terminal_status(call.status)
            replay_data = call.output_summary
            replay_contract_version = None
            if replay_status == "succeeded":
                if replay_data is None:
                    # 历史成功记录若没有可恢复数据，写工具必须返回未知，避免
                    # 调用方把无法验证的摘要当成一次新的确定性成功。
                    return ToolResult(
                        tool_call_id=call.id,
                        status="unknown" if definition.idempotency_required else "failed",
                        error_code=(
                            "TOOL_RESULT_UNKNOWN" if definition.idempotency_required else "TOOL_OUTPUT_INVALID"
                        ),
                        mocked=call.mocked,
                        replayed=True,
                    )
                try:
                    if definition.idempotency_required:
                        replay_data = validate_tool_output(invocation.tool_name, replay_data)
                    else:
                        replay_data = validate_read_tool_replay_output(invocation.tool_name, replay_data)
                        replay_contract_version = READ_REPLAY_CONTRACT_VERSION
                except (ValidationError, ValueError):
                    # output_summary 是低敏审计字段，不天然等于业务返回 DTO。
                    # 历史摘要缺字段时禁止继续返回 succeeded；写操作使用 unknown
                    # 阻止自动重试，查询则明确返回输出无效。
                    return ToolResult(
                        tool_call_id=call.id,
                        status="unknown" if definition.idempotency_required else "failed",
                        error_code=(
                            "TOOL_RESULT_UNKNOWN" if definition.idempotency_required else "TOOL_OUTPUT_INVALID"
                        ),
                        mocked=call.mocked,
                        replayed=True,
                    )
            return ToolResult(
                tool_call_id=call.id,
                status=replay_status,
                data=replay_data,
                error_code=call.error_code,
                mocked=call.mocked,
                replayed=True,
                replay_contract_version=replay_contract_version,
            )

        try:
            outcome = await asyncio.wait_for(
                self._dispatch(invocation, call.id, arguments),
                timeout=definition.timeout_seconds,
            )
        except TimeoutError:
            # 平台发送超时无法判断对端是否已接收，必须标记 unknown 且禁止自动重试。
            status: ToolStatus = "unknown" if invocation.tool_name == "send_platform_message" else "timeout"
            error_code = "TOOL_RESULT_UNKNOWN" if status == "unknown" else "TOOL_TIMEOUT"
            await self._finish_after_error(call.id, started_at, status, error_code, invocation)
            return ToolResult(tool_call_id=call.id, status=status, error_code=error_code)
        except ToolDispatchError as error:
            await self._finish_after_error(call.id, started_at, "failed", error.error_code, invocation)
            return ToolResult(tool_call_id=call.id, status="failed", error_code=error.error_code)
        except Exception as error:
            status = "unknown" if invocation.tool_name == "send_platform_message" else "failed"
            error_code = "TOOL_RESULT_UNKNOWN" if status == "unknown" else "TOOL_EXECUTION_FAILED"
            await self._finish_after_error(call.id, started_at, status, error_code, invocation)
            logger.error(
                "agent_tool_execution_failed",
                extra={
                    "trace_id": invocation.context.trace_id,
                    "agent_run_id": str(invocation.context.agent_run_id) if invocation.context.agent_run_id else None,
                    "tool_call_id": str(call.id),
                    "tool_name": invocation.tool_name,
                    "error_type": type(error).__name__,
                },
            )
            return ToolResult(
                tool_call_id=call.id,
                status=status,
                error_code=error_code,
            )

        try:
            normalized_data = validate_tool_output(invocation.tool_name, outcome.data) if outcome.data else None
        except ValidationError:
            # 平台发送可能已被对端接收，输出异常时只能记录未知，禁止自动重试。
            status = "unknown" if invocation.tool_name == "send_platform_message" else "failed"
            error_code = "TOOL_RESULT_UNKNOWN" if status == "unknown" else "TOOL_OUTPUT_INVALID"
            await self._finish_after_error(call.id, started_at, status, error_code, invocation)
            return ToolResult(tool_call_id=call.id, status=status, error_code=error_code)

        if outcome.status == "succeeded" and definition.idempotency_required:
            replay_summary = outcome.output_summary
            replay_summary_valid = replay_summary is not None
            if replay_summary is not None:
                try:
                    validate_tool_output(invocation.tool_name, replay_summary)
                except ValidationError:
                    replay_summary_valid = False
            if not replay_summary_valid:
                # 写工具的成功摘要将成为后续幂等重放结果。落库前必须满足同一输出
                # 契约；否则当前请求虽然拿到了完整结果，后续重放却会失去事实证据。
                # 对此统一记录 unknown，避免制造可被误认成成功的不可恢复终态。
                await self._finish_after_error(
                    call.id,
                    started_at,
                    "unknown",
                    "TOOL_RESULT_UNKNOWN",
                    invocation,
                )
                return ToolResult(
                    tool_call_id=call.id,
                    status="unknown",
                    error_code="TOOL_RESULT_UNKNOWN",
                    mocked=outcome.mocked,
                )

        await finish_tool_call(
            self.session,
            call,
            started_at,
            outcome.status,
            outcome.output_summary,
            outcome.mocked,
            outcome.error_code,
        )
        return ToolResult(
            tool_call_id=call.id,
            status=outcome.status,
            data=normalized_data,
            error_code=outcome.error_code,
            mocked=outcome.mocked,
        )

    async def _dispatch(
        self,
        invocation: ToolInvocation,
        tool_call_id: uuid.UUID,
        arguments: dict[str, object],
    ) -> ToolDispatchOutcome:
        """按白名单名称分派到固定实现，禁止动态导入或模型指定函数。"""
        tool_name = invocation.tool_name
        if tool_name == "query_order":
            return await self._query_order(invocation, QueryOrderArguments.model_validate(arguments))
        if tool_name == "query_logistics":
            return await self._query_logistics(invocation, QueryLogisticsArguments.model_validate(arguments))
        if tool_name == "query_customer_profile":
            return await self._query_customer_profile(
                invocation,
                QueryCustomerProfileArguments.model_validate(arguments),
            )
        if tool_name == "update_shipping_address":
            return await self._update_shipping_address(
                invocation,
                UpdateShippingAddressArguments.model_validate(arguments),
            )
        if tool_name == "send_coupon":
            return await self._send_coupon(
                invocation,
                tool_call_id,
                SendCouponArguments.model_validate(arguments),
            )
        if tool_name == "transfer_to_human":
            return await self._transfer_to_human(
                invocation,
                TransferToHumanArguments.model_validate(arguments),
            )
        return await self._send_platform_message(
            invocation,
            tool_call_id,
            SendPlatformMessageArguments.model_validate(arguments),
        )

    async def _query_order(
        self,
        invocation: ToolInvocation,
        arguments: QueryOrderArguments,
    ) -> ToolDispatchOutcome:
        """返回当前店铺的最小订单事实，不返回原始平台载荷。"""
        order = await self._find_order(invocation.context.store_id, arguments.order_id)
        if order is None:
            raise ToolDispatchError("TOOL_RESOURCE_NOT_FOUND")
        data: dict[str, object] = {
            "order_id": str(order.id),
            "external_order_id": order.external_order_id,
            "status": order.status,
            "payment_status": order.payment_status,
            "fulfillment_status": order.fulfillment_status,
            "currency": order.currency,
            "total_amount": str(order.total_amount),
            "ordered_at": order.ordered_at.isoformat() if order.ordered_at else None,
        }
        return ToolDispatchOutcome(
            status="succeeded",
            data=data,
            output_summary={"order_id": str(order.id), "status": order.status},
        )

    async def _query_logistics(
        self,
        invocation: ToolInvocation,
        arguments: QueryLogisticsArguments,
    ) -> ToolDispatchOutcome:
        """返回当前店铺订单的标准化物流事实。"""
        order = await self._find_order(invocation.context.store_id, arguments.order_id)
        if order is None:
            raise ToolDispatchError("TOOL_RESOURCE_NOT_FOUND")
        data: dict[str, object] = {
            "order_id": str(order.id),
            "external_order_id": order.external_order_id,
            "tracking_number": order.tracking_number,
            "tracking_status": order.tracking_status,
            "shipped_at": order.shipped_at.isoformat() if order.shipped_at else None,
            "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        }
        return ToolDispatchOutcome(
            status="succeeded",
            data=data,
            # 物流号属于客户标识，只在内存结果中返回，不进入工具运行摘要。
            output_summary={"order_id": str(order.id), "tracking_status": order.tracking_status},
        )

    async def _query_customer_profile(
        self,
        invocation: ToolInvocation,
        arguments: QueryCustomerProfileArguments,
    ) -> ToolDispatchOutcome:
        """返回最小客户画像，排除邮箱、电话和平台原始数据。"""
        customer = await self.session.scalar(
            select(Customer).where(
                Customer.id == arguments.customer_id,
                Customer.store_id == invocation.context.store_id,
            )
        )
        if customer is None:
            raise ToolDispatchError("TOOL_RESOURCE_NOT_FOUND")
        data: dict[str, object] = {
            "customer_id": str(customer.id),
            "tags": customer.tags,
            "order_count": customer.order_count,
            "total_spend": str(customer.total_spend),
        }
        return ToolDispatchOutcome(
            status="succeeded",
            data=data,
            output_summary={"customer_id": str(customer.id), "order_count": customer.order_count},
        )

    async def _update_shipping_address(
        self,
        invocation: ToolInvocation,
        arguments: UpdateShippingAddressArguments,
    ) -> ToolDispatchOutcome:
        """创建地址变更审计，但 Phase 3 Mock 不覆盖订单权威地址。"""
        order = await self._find_order(invocation.context.store_id, arguments.order_id)
        if order is None:
            raise ToolDispatchError("TOOL_RESOURCE_NOT_FOUND")
        self.session.add(
            self._audit_log(
                invocation,
                action="order.address.update.requested",
                resource_type="order",
                resource_id=order.id,
                after_data={"status": "pending_confirmation", "mocked": True},
                result="succeeded",
            )
        )
        return ToolDispatchOutcome(
            status="succeeded",
            data={"order_id": str(order.id), "status": "pending_confirmation", "mocked": True},
            # 地址正文不持久化；对象、状态和 Mock 标识已足够安全重放。
            output_summary={"order_id": str(order.id), "status": "pending_confirmation", "mocked": True},
            mocked=True,
        )

    async def _send_coupon(
        self,
        invocation: ToolInvocation,
        tool_call_id: uuid.UUID,
        arguments: SendCouponArguments,
    ) -> ToolDispatchOutcome:
        """创建明确标记为 Mock 的优惠券记录和审计日志。"""
        customer = await self.session.scalar(
            select(Customer).where(
                Customer.id == arguments.customer_id,
                Customer.store_id == invocation.context.store_id,
            )
        )
        if customer is None:
            raise ToolDispatchError("TOOL_RESOURCE_NOT_FOUND")
        issuance = CouponIssuance(
            store_id=invocation.context.store_id,
            customer_id=customer.id,
            tool_call_id=tool_call_id,
            coupon_code=arguments.coupon_code,
            description=arguments.description,
            expires_at=arguments.expires_at,
            mocked=True,
        )
        self.session.add(issuance)
        await self.session.flush()
        self.session.add(
            self._audit_log(
                invocation,
                action="coupon.issue",
                resource_type="customer",
                resource_id=customer.id,
                after_data={"issuance_id": str(issuance.id), "mocked": True},
                result="succeeded",
            )
        )
        return ToolDispatchOutcome(
            status="succeeded",
            data={
                "issuance_id": str(issuance.id),
                "coupon_code": arguments.coupon_code,
                "status": issuance.status,
                "mocked": True,
            },
            # 优惠码已存在于受控输入摘要；补齐它和 Mock 标识即可满足强类型
            # 重放契约，无需保存客户信息或营销正文。
            output_summary={
                "issuance_id": str(issuance.id),
                "coupon_code": arguments.coupon_code,
                "status": issuance.status,
                "mocked": True,
            },
            mocked=True,
        )

    async def _transfer_to_human(
        self,
        invocation: ToolInvocation,
        arguments: TransferToHumanArguments,
    ) -> ToolDispatchOutcome:
        """更新会话接管状态并写入不可变审计记录。"""
        conversation = await self.session.scalar(
            select(Conversation)
            .where(
                Conversation.id == arguments.conversation_id,
                Conversation.store_id == invocation.context.store_id,
            )
            .with_for_update()
        )
        if conversation is None:
            raise ToolDispatchError("TOOL_RESOURCE_NOT_FOUND")
        if conversation.status == "closed":
            raise ToolDispatchError("TOOL_PLATFORM_DISABLED")
        await self._verify_user_owner(invocation, conversation, "workspace.transfer")
        if arguments.assign_to is not None:
            assignment = await self.session.scalar(
                select(user_roles.c.id)
                .join(User, User.id == user_roles.c.user_id)
                .join(role_permissions, role_permissions.c.role_id == user_roles.c.role_id)
                .join(Permission, Permission.id == role_permissions.c.permission_id)
                .where(
                    user_roles.c.user_id == arguments.assign_to,
                    user_roles.c.store_id == invocation.context.store_id,
                    User.status == "active",
                    Permission.code == "workspace.reply",
                )
            )
            if assignment is None:
                raise ToolDispatchError("TOOL_ASSIGNEE_NOT_AUTHORIZED")
        conversation.status = "transferred"
        conversation.transfer_reason = arguments.reason
        conversation.assigned_user_id = arguments.assign_to
        audit = self._audit_log(
            invocation,
            action="conversation.transfer",
            resource_type="conversation",
            resource_id=conversation.id,
            after_data={"assigned_user_id": str(arguments.assign_to) if arguments.assign_to else None},
            result="succeeded",
        )
        self.session.add(audit)
        await self.session.flush()
        return ToolDispatchOutcome(
            status="succeeded",
            data={"transfer_id": str(audit.id), "status": "transferred"},
            output_summary={"transfer_id": str(audit.id), "status": "transferred"},
        )

    async def _send_platform_message(
        self,
        invocation: ToolInvocation,
        tool_call_id: uuid.UUID,
        arguments: SendPlatformMessageArguments,
    ) -> ToolDispatchOutcome:
        """经平台适配器发送已批准消息，并保存 sent/failed/unknown 状态。"""
        conversation = await self.session.scalar(
            select(Conversation)
            .where(
                Conversation.id == arguments.conversation_id,
                Conversation.store_id == invocation.context.store_id,
            )
            .with_for_update()
        )
        if conversation is None:
            raise ToolDispatchError("TOOL_RESOURCE_NOT_FOUND")
        if conversation.status == "closed":
            raise ToolDispatchError("TOOL_PLATFORM_DISABLED")
        channel = await self.session.scalar(
            select(ChannelAccount).where(
                ChannelAccount.store_id == invocation.context.store_id,
                ChannelAccount.platform == conversation.platform,
                ChannelAccount.status == "connected",
            )
        )
        if channel is None:
            raise ToolDispatchError("TOOL_CHANNEL_NOT_AVAILABLE")
        automation = None
        if invocation.context.automation_delivery_id is not None:
            from app.agents.automation.authorization import authorize_persisted_send as authorize_automation

            automation = await authorize_automation(
                self.session, get_settings(), invocation, arguments, verify_remote=False
            )
            if automation is None:
                raise ToolDispatchError("TOOL_AUTOMATION_NOT_AUTHORIZED")
        notification_authorized = False
        if invocation.context.logistics_notification_key is not None:
            from app.agents.tools.logistics_updates.authorization import authorize_persisted_send

            notification_authorized = await authorize_persisted_send(
                self.session, get_settings(), invocation, arguments
            )
            if not notification_authorized:
                raise ToolDispatchError("TOOL_LOGISTICS_NOTIFICATION_NOT_AUTHORIZED")
        try:
            adapter = get_message_adapter(conversation.platform)
        except AppError as error:
            raise ToolDispatchError("TOOL_PLATFORM_DISABLED") from error
        if adapter.real_writes:
            if conversation.platform == "tiktok" and not is_tiktok_send_target_allowed(
                get_settings(), conversation.store_id, conversation.external_conversation_id
            ):
                raise ToolDispatchError("TOOL_PLATFORM_DISABLED")
            # 普通消息真实写开关只授权“当前人工用户已二次确认”的入口。
            # Agent/Job 即使伪造 human_confirmed，也必须在创建消息和调用平台前失败关闭。
            if (
                automation is None
                and not notification_authorized
                and (
                    invocation.context.actor_type != "user"
                    or invocation.context.actor_id is None
                    or not invocation.context.human_confirmed
                )
            ):
                raise ToolDispatchError("TOOL_HUMAN_CONFIRMATION_REQUIRED")
            # 同店铺发送在落下 processing 消息前串行化，避免两个并发请求
            # 都通过未结清检查。若进程在平台调用前后退出，已提交的
            # processing 必须继续阻断新发送，等待人工核对平台事实。
            locked_store = await self.session.scalar(
                select(Store.id)
                .where(
                    Store.id == invocation.context.store_id,
                    Store.status == "active",
                    Store.deleted_at.is_(None),
                )
                .with_for_update()
            )
            if locked_store is None:
                raise ToolDispatchError("TOOL_RESOURCE_NOT_FOUND")
            unresolved = await self.session.scalar(
                select(Message.id)
                .where(
                    Message.store_id == invocation.context.store_id,
                    Message.platform == "tiktok",
                    Message.direction == "outbound",
                    Message.status.in_(("processing", "unknown")),
                )
                .limit(1)
            )
            if unresolved is not None:
                raise ToolDispatchError("TOOL_RECONCILIATION_REQUIRED")
        if arguments.message_type in {"logistics_card", "order_card"} and (
            conversation.platform != "tiktok"
            or (
                automation is None
                and (invocation.context.actor_type != "user" or not invocation.context.human_confirmed)
            )
            or not arguments.card_order_id
        ):
            raise ToolDispatchError("TOOL_HUMAN_CONFIRMATION_REQUIRED")
        if automation is not None and not adapter.real_writes:
            raise ToolDispatchError("TOOL_AUTOMATION_MOCK_BLOCKED")
        media_claim = None
        if arguments.message_type in {"image", "video"}:
            if (
                conversation.platform != "tiktok"
                or invocation.context.actor_type != "user"
                or invocation.context.actor_id is None
                or not invocation.context.human_confirmed
                or not arguments.media_token
            ):
                raise ToolDispatchError("TOOL_HUMAN_CONFIRMATION_REQUIRED")
            try:
                media_claim = verify_media_claim(
                    arguments.media_token,
                    store_id=conversation.store_id,
                    conversation_id=conversation.id,
                    actor_id=invocation.context.actor_id,
                    idempotency_key=invocation.idempotency_key,
                )
            except AppError as error:
                raise ToolDispatchError("TOOL_MEDIA_PROOF_INVALID") from error
            if media_claim.kind != arguments.message_type:
                raise ToolDispatchError("TOOL_MEDIA_PROOF_INVALID")
        logistics_payload = (
            {"order_id": arguments.card_order_id, "package_id": arguments.card_package_id}
            if arguments.message_type == "logistics_card"
            else None
        )
        order_card_payload = (
            {"kind": "order_card", "order_id": arguments.card_order_id}
            if arguments.message_type == "order_card"
            else None
        )
        media_payload = (
            {"url": media_claim.value, "width": media_claim.width, "height": media_claim.height}
            if media_claim and media_claim.kind == "image"
            else {"vid": media_claim.value}
            if media_claim
            else None
        )
        # 只在所有只读预检之后核对归属，但必须早于处理态消息和平台调用。
        await self._verify_user_owner(invocation, conversation, "workspace.reply")
        message = Message(
            store_id=conversation.store_id,
            conversation_id=conversation.id,
            customer_id=conversation.customer_id,
            platform=conversation.platform,
            external_message_id=f"pending-{uuid.uuid4()}",
            idempotency_key=invocation.idempotency_key,
            role="agent" if invocation.context.actor_type == "user" else "assistant",
            direction="outbound",
            content=arguments.content,
            message_type=arguments.message_type,
            status="processing",
            agent_run_id=invocation.context.agent_run_id,
            raw_payload={
                "delivery_mode": "unknown",
                **({"automation_source_kind": automation.source_kind} if automation else {}),
                **({"logistics_card": logistics_payload} if logistics_payload else {}),
                **({"card": order_card_payload} if order_card_payload else {}),
                **({"media": media_payload} if media_payload else {}),
            },
        )
        self.session.add(message)
        await self.session.commit()
        if automation is not None or notification_authorized:
            # processing 已持久化；重新取得会话/策略锁并复核当前授权，覆盖提交后到网络前的竞态。
            await self.session.refresh(conversation, with_for_update=True)
            await self.session.scalar(select(Store.id).where(Store.id == conversation.store_id).with_for_update())
            if automation is not None:
                automation = await authorize_automation(self.session, get_settings(), invocation, arguments)
                if automation is None:
                    raise ToolDispatchError("TOOL_AUTOMATION_NOT_AUTHORIZED")
            if notification_authorized and not await authorize_persisted_send(
                self.session, get_settings(), invocation, arguments
            ):
                raise ToolDispatchError("TOOL_LOGISTICS_NOTIFICATION_NOT_AUTHORIZED")
        result = await adapter.send_message(
            channel,
            SendMessageCommand(
                external_conversation_id=conversation.external_conversation_id,
                content=arguments.content,
                message_type=arguments.message_type,
                card_order_id=arguments.card_order_id,
                card_package_id=arguments.card_package_id,
                media_value=media_claim.value if media_claim else None,
                media_width=media_claim.width if media_claim else None,
                media_height=media_claim.height if media_claim else None,
                idempotency_key=invocation.idempotency_key,
                human_confirmed=invocation.context.human_confirmed,
                logistics_notification_authorized=notification_authorized,
                automation_authorized=automation is not None,
                sender_role="ROBOT"
                if notification_authorized or (automation is not None and automation.source_kind == "agent")
                else "SYSTEM"
                if automation is not None
                else "CUSTOMER_SERVICE",
            ),
        )
        if result.external_message_id is not None:
            message.external_message_id = result.external_message_id
        message.status = result.status
        message.error_code = result.error_code
        message.sent_at = datetime.now(UTC) if result.status == "sent" else None
        if result.status == "sent" and invocation.context.actor_type == "user" and invocation.context.actor_id:
            # 平台返回发送成功后才确认近期人工回复；刷新行锁避免覆盖期间抵达的新消息。
            await self.session.refresh(conversation, with_for_update=True)
            latest_inbound = await self.session.scalar(
                select(func.max(Message.created_at)).where(
                    Message.conversation_id == conversation.id,
                    Message.direction == "inbound",
                )
            )
            if latest_inbound is None or (message.sent_at is not None and latest_inbound <= message.sent_at):
                conversation.awaiting_reply_since = None
            conversation.last_human_responder_id = invocation.context.actor_id
            conversation.last_human_replied_at = message.sent_at
        message.raw_payload = {
            "delivery_mode": "mock" if result.mock else "real",
            **({"automation_source_kind": automation.source_kind} if automation else {}),
            **({"logistics_card": logistics_payload} if logistics_payload else {}),
            **({"card": order_card_payload} if order_card_payload else {}),
            **({"media": media_payload} if media_payload else {}),
        }
        if result.status == "sent":
            from app.reception.automation import on_reception_outbound

            await on_reception_outbound(
                self.session, conversation, message, source_kind=automation.source_kind if automation else None
            )
        conversation.last_message_id = message.id
        conversation.last_message_at = datetime.now(UTC)
        audit_action = {
            "user": "message.send.manual",
            "agent": "message.send.ai",
            "job": "message.send.job",
        }[invocation.context.actor_type]
        audit_result = "succeeded" if result.status == "sent" else result.status
        self.session.add(
            self._audit_log(
                invocation,
                action=audit_action,
                resource_type="message",
                resource_id=message.id,
                after_data={"status": result.status, "platform": conversation.platform, "mocked": result.mock},
                result=audit_result,
            )
        )
        status: ToolStatus = (
            "succeeded" if result.status == "sent" else ("unknown" if result.status == "unknown" else "failed")
        )
        return ToolDispatchOutcome(
            status=status,
            data={"message_id": str(message.id), "status": result.status, "mocked": result.mock},
            # 只保存消息对象、终态和 Mock 标识，消息正文仍不进入工具摘要。
            output_summary={"message_id": str(message.id), "status": result.status, "mocked": result.mock},
            mocked=result.mock,
            error_code=result.error_code,
        )

    async def _verify_user_owner(
        self, invocation: ToolInvocation, conversation: Conversation, permission_code: str
    ) -> None:
        """在工具执行的行锁内复核店铺权限与归属，避免撤权或转交后的竞态操作。"""
        if invocation.context.actor_type != "user":
            return
        actor_id = invocation.context.actor_id
        actor = await self.session.get(User, actor_id) if actor_id is not None else None
        if actor is None or actor.status != "active":
            raise ToolDispatchError("TOOL_OWNER_MISMATCH")
        if conversation.store_id not in await allowed_store_ids(self.session, actor, permission_code):
            raise ToolDispatchError("TOOL_OWNER_MISMATCH")
        if conversation.assigned_user_id == actor_id:
            return
        if conversation.store_id not in await supervised_store_ids(self.session, actor):
            raise ToolDispatchError("TOOL_OWNER_MISMATCH")

    async def _find_order(self, store_id: uuid.UUID, order_id: str) -> Order | None:
        """按内部或平台订单号查询，并强制绑定可信店铺。"""
        try:
            internal_id = uuid.UUID(order_id)
        except ValueError:
            internal_id = None
        identity = Order.external_order_id == order_id
        if internal_id is not None:
            identity = or_(Order.id == internal_id, identity)
        order: Order | None = await self.session.scalar(select(Order).where(Order.store_id == store_id, identity))
        return order

    async def _finish_after_error(
        self,
        tool_call_id: uuid.UUID,
        started_at: float,
        status: ToolStatus,
        error_code: str,
        invocation: ToolInvocation | None = None,
    ) -> None:
        """回滚未提交变化，并同步持久化工具及已创建出站消息终态。"""
        await self.session.rollback()
        if invocation is not None and invocation.tool_name == "send_platform_message":
            message = await self.session.scalar(
                select(Message).where(
                    Message.store_id == invocation.context.store_id,
                    Message.idempotency_key == invocation.idempotency_key,
                )
            )
            if isinstance(message, Message):
                message.status = status
                message.error_code = error_code
                message.raw_payload = {**message.raw_payload, "delivery_mode": "unknown"}
                self.session.add(
                    self._audit_log(
                        invocation,
                        action="message.send.manual" if invocation.context.actor_type == "user" else "message.send.ai",
                        resource_type="message",
                        resource_id=message.id,
                        after_data={"status": status, "platform": message.platform, "mocked": False},
                        result=status,
                    )
                )
        call = await self.session.get(ToolCall, tool_call_id)
        if call is None:
            raise RuntimeError("工具调用记录不存在")
        await finish_tool_call(self.session, call, started_at, status, None, False, error_code)

    @staticmethod
    def _terminal_status(status: str) -> ToolStatus:
        """把数据库状态收敛到对外终态；running 不允许作为重放结果。"""
        if status in {"succeeded", "failed", "timeout", "unknown"}:
            return status  # type: ignore[return-value]
        raise RuntimeError("工具调用尚未进入终态")

    @staticmethod
    def _input_summary(tool_name: ToolName, arguments: dict[str, object]) -> dict[str, object]:
        """只保留排障所需的 ID、字段名和长度，不保存地址或消息正文。"""
        summary: dict[str, object] = {"tool_name": tool_name}
        for key in ("order_id", "customer_id", "conversation_id"):
            value = arguments.get(key)
            if value is not None:
                summary[key] = value
        if tool_name == "update_shipping_address":
            summary["country_code"] = arguments.get("country_code")
            summary["fields"] = sorted(arguments)
        if tool_name == "send_coupon":
            summary["coupon_code"] = arguments.get("coupon_code")
        if tool_name == "send_platform_message":
            content = arguments.get("content")
            summary["content_length"] = len(content) if isinstance(content, str) else 0
            summary["message_type"] = arguments.get("message_type", "text")
        return summary

    @staticmethod
    def _audit_log(
        invocation: ToolInvocation,
        *,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID,
        after_data: dict[str, object],
        result: str,
    ) -> AuditLog:
        """构造低敏只追加审计记录，关联 trace_id 但不保存工具正文。"""
        return AuditLog(
            store_id=invocation.context.store_id,
            actor_type=invocation.context.actor_type,
            actor_id=invocation.context.actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=invocation.context.trace_id,
            after_data=after_data,
            result=result,
        )
