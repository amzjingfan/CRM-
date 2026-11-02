"""当前会话业务工具：可信选单、最小字段投影和本轮可追溯结果。"""

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.core.security import EVALUATION_SECRET_PATTERN
from app.agents.runtime.snapshot import RunSnapshot
from app.agents.safety.input import prepare_untrusted_text
from app.agents.tools.access import current_permissions
from app.agents.tools.arguments import (
    AftersalesArguments,
    CollaborationArguments,
    ConversationHistoryArguments,
    CouponSearchArguments,
    LogisticsArguments,
    OrderSearchArguments,
    OrderSelectionArguments,
    ProductSearchArguments,
    ProductSelectionArguments,
)
from app.agents.tools.business_identifiers import BUSINESS_IDENTIFIER_PATHS, safe_business_identifier
from app.agents.tools.metadata import TOOL_METADATA
from app.agents.tools.product_facts import product_facts
from app.audit.models import AuditLog
from app.conversations.models import Conversation, Message
from app.customers.models import Customer
from app.integrations.tiktok_read import TikTokReturn, TikTokReturnRecord
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.exceptions.errors import AppError, ErrorCode
from app.workspace.sidebar import (
    SidebarOrder,
    SidebarSearch,
    _live_order_view,
    _verified_sidebar_order,
    get_sidebar_enhanced_tracking,
    get_sidebar_order_detail,
    get_sidebar_standard_tracking,
    get_store_product,
    search_sidebar_orders,
    search_store_coupons,
    search_store_products,
)

_CREDENTIAL_VALUE = re.compile(r"[A-Za-z0-9._~+/=-]{8,}")


def safe_text(value: str | None) -> str | None:
    if not value:
        return value
    # 复用生产凭证语法，但标签后必须带值，避免仅提及 Token/API key 就隐藏业务文字。
    if any(
        match.group().lower().startswith("bearer") or _CREDENTIAL_VALUE.match(value[match.end() :].lstrip())
        for match in EVALUATION_SECRET_PATTERN.finditer(value)
    ):
        return "[敏感内容已隐藏]"
    try:
        return prepare_untrusted_text(value, source="tool_result").text
    except AppError:
        return "[敏感内容已隐藏]"


def safe_data(value: object, path: tuple[str, ...] = ()) -> object:
    """只处理调用方已经按字段白名单构造的数据；不处理原始平台响应。"""
    if path in BUSINESS_IDENTIFIER_PATHS:
        return safe_business_identifier(value)
    if isinstance(value, str):
        return safe_text(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list | tuple):
        return [safe_data(item, (*path, "*")) for item in value]
    if isinstance(value, dict):
        return {
            str(key): item
            if key in {"order_ref", "product_ref", "return_ref", "next_page_ref"}
            else safe_data(item, (*path, str(key)))
            for key, item in value.items()
        }
    return value


def _bounded_facts_page(
    rows: list[dict[str, object]], offset: int, budget: int
) -> tuple[list[dict[str, object]], int | None]:
    """按实际DLP后JSON大小续读；两个数组分别预算，避免合法长字段组合超出工具协议。"""
    page: list[dict[str, object]] = []
    used = 2
    for row in rows[offset : offset + 10]:
        safe = cast(dict[str, object], safe_data(row))
        size = len(json.dumps(safe, ensure_ascii=False, separators=(",", ":"), default=str)) + 1
        if used + size > budget:
            if not page:
                raise AppError(ErrorCode.THIRD_PARTY_ERROR, "单条物流记录超过工具内容预算", 502)
            break
        # 仅用脱敏投影量尺寸；返回原类型，invoke统一执行一次DLP，避免ISO时间再次被当标识过滤。
        page.append(row)
        used += size
    next_offset = offset + len(page)
    return page, next_offset if next_offset < len(rows) else None


class AgentBusinessExecutor:
    """每个子 Agent 独立持有候选映射，模型不能注入平台资源标识。"""

    def __init__(
        self,
        session: AsyncSession,
        user: User,
        snapshot: RunSnapshot,
        run_id: uuid.UUID,
        permissions: frozenset[str],
        trace_id: str,
        *,
        preview_only: bool = False,
    ) -> None:
        self.session, self.snapshot = session, snapshot
        # 跨子会话只携带操作者标识；角色、状态和店铺权限每次从数据库核验。
        self.user = User(id=user.id)
        self.run_id, self.permissions, self.trace_id = run_id, permissions, trace_id
        self.preview_only = preview_only
        self.orders: dict[str, SidebarOrder] = {}
        self.products: dict[str, str] = {}
        self.return_cases: dict[str, TikTokReturn] = {}
        self.return_records: dict[str, list[TikTokReturnRecord]] = {}
        self.page_tokens: dict[str, tuple[str, str, str]] = {}
        self._pages = 0

    async def permits(self, permission: str) -> bool:
        try:
            return permission in self.permissions and permission in await current_permissions(
                self.session, self.user, self.snapshot.store_id
            )
        except AppError:
            return False

    async def authorize(self, name: str) -> Conversation | None:
        if not await self.permits(TOOL_METADATA[name].permission):
            raise AppError(ErrorCode.PERMISSION_DENIED, "工具权限已撤销", 403)
        if not TOOL_METADATA[name].requires_context:
            return None
        if self.snapshot.debug_without_conversation:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "请关联授权会话", 404)
        conversation = await self.session.scalar(
            select(Conversation).where(
                Conversation.id == self.snapshot.conversation_id,
                Conversation.store_id == self.snapshot.store_id,
                Conversation.customer_id == self.snapshot.customer_id,
            )
        )
        if conversation is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话上下文不可用", 404)
        metadata = TOOL_METADATA[name]
        if (metadata.scopes or metadata.any_scopes) and conversation.platform != "tiktok":
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "当前平台尚不支持该工具", 404)
        return conversation

    async def invoke(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        metadata = TOOL_METADATA[name]
        parsed = metadata.arguments.model_validate(arguments)
        try:
            conversation = await self.authorize(name)
            if name == "search_customer_orders":
                facts = await self.search_orders(cast(OrderSearchArguments, parsed))
            elif name in {"query_order", "query_logistics", "query_aftersales"}:
                if conversation is None:
                    return {"status": "context_unavailable"}
                selected = await self.select_order(cast(OrderSelectionArguments, parsed))
                if isinstance(selected, dict):
                    return selected
                if name == "query_order":
                    facts = self.order_facts(selected)
                    if conversation.platform == "tiktok" and get_settings().real_tiktok_read_enabled:
                        _conv, _client, remote = await _verified_sidebar_order(
                            self.session, self.user, conversation.id, selected.external_order_id
                        )
                        facts = self.order_facts(_live_order_view(remote))
                        facts["payment"] = remote.payment.model_dump() if remote.payment else None
                elif name == "query_logistics":
                    facts = await self.logistics(selected, cast(LogisticsArguments, parsed))
                else:
                    facts = await self.aftersales(selected, cast(AftersalesArguments, parsed))
            elif name == "search_products":
                facts = await self.search_products(cast(ProductSearchArguments, parsed))
            elif name == "query_product":
                args = cast(ProductSelectionArguments, parsed)
                product_id = self.products.get(args.product_ref)
                if product_id is None:
                    return {"status": "invalid_selection"}
                product = await get_store_product(self.session, self.snapshot.store_id, product_id)
                facts = product_facts(product, args)
            elif name == "query_available_coupons":
                facts = await self.coupons(cast(CouponSearchArguments, parsed))
            elif name == "query_customer_profile":
                customer = await self.session.scalar(
                    select(Customer).where(
                        Customer.id == self.snapshot.customer_id, Customer.store_id == self.snapshot.store_id
                    )
                )
                if customer is None:
                    return {"status": "resource_unavailable"}
                facts = {
                    "tags": customer.tags,
                    "order_count": customer.order_count,
                    "total_spend": customer.total_spend,
                    "last_seen_at": customer.last_seen_at,
                    "buyer_stage_override": (customer.metadata_json or {}).get("buyer_stage_override"),
                    "data_scope": "crm_synced_customer_summary",
                    "platform_history_completeness": "not_verified",
                }
            elif name == "query_conversation_messages":
                facts = await self.messages(cast(ConversationHistoryArguments, parsed))
            elif name in {"create_handoff_request", "add_internal_note"}:
                if self.preview_only:
                    return {
                        "status": "previewed",
                        "facts": {
                            "record_saved": False,
                            "kind": "handoff_request" if name == "create_handoff_request" else "internal_note",
                            "is_ai_suggestion": True,
                            "transfer_performed": False,
                            "send_performed": False,
                        },
                        "source": "debug_preview",
                    }
                from app.agents.tools.collaboration import save_collaboration

                entry = await save_collaboration(
                    self.session,
                    self.snapshot,
                    self.run_id,
                    name,
                    cast(CollaborationArguments, parsed).content,
                    self.user.id,
                    self.trace_id,
                )
                facts = {
                    "record_saved": True,
                    "kind": entry.kind,
                    "is_ai_suggestion": True,
                    "transfer_performed": False,
                    "send_performed": False,
                }
            else:
                return {"status": "tool_unavailable"}
            source = (
                "crm_internal"
                if metadata.operation == "internal_write"
                else (
                    "tiktok_shop_api"
                    if (metadata.scopes or metadata.any_scopes) and get_settings().real_tiktok_read_enabled
                    else "crm_local_snapshot"
                )
            )
            result = {
                "status": "succeeded",
                "facts": safe_data(facts),
                "source": source,
                "observed_at": datetime.now(UTC).isoformat(),
                "fact_scope": hashlib.sha256(
                    json.dumps(
                        [name, facts.get("order_ref"), facts.get("product_ref"), parsed.model_dump(mode="json")],
                        sort_keys=True,
                        ensure_ascii=False,
                    ).encode()
                ).hexdigest()[:16],
            }
            self.session.add(
                AuditLog(
                    store_id=self.snapshot.store_id,
                    actor_type="agent",
                    actor_id=None,
                    action="agent.tool.read" if metadata.operation == "read" else "agent.tool.internal_write",
                    resource_type="agent_run",
                    resource_id=self.run_id,
                    request_id=self.trace_id,
                    after_data={"tool_name": name, "source": source},
                    result="succeeded",
                )
            )
            await self.session.commit()
            return result
        except ValidationError:
            await self.session.rollback()
            return {"status": "tool_failed", "error_code": "TOOL_OUTPUT_INVALID"}
        except AppError as error:
            await self.session.rollback()
            return {
                "status": {403: "permission_denied", 404: "resource_unavailable", 429: "rate_limited"}.get(
                    error.status_code, "tool_failed"
                ),
                "error_code": error.code.value,
            }

    def order_ref(self, order: SidebarOrder) -> str:
        for ref, candidate in self.orders.items():
            if candidate.id == order.id:
                self.orders[ref] = order
                return ref
        # 同一父运行的不同子 Agent 对同一订单使用相同不透明引用，避免汇总时混淆 o1。
        ref = "o" + str(1 + int(hashlib.sha256(f"{self.run_id}:{order.id}".encode()).hexdigest()[:12], 16))
        if ref in self.orders and self.orders[ref].id != order.id:
            raise AppError(ErrorCode.RESOURCE_CONFLICT, "订单候选引用冲突，请重试", 409)
        self.orders[ref] = order
        return ref

    def order_facts(self, order: SidebarOrder) -> dict[str, object]:
        return {
            "order_ref": self.order_ref(order),
            "order_number": order.external_order_id,
            "tracking_number": order.tracking_number,
            "status": order.status,
            "payment_status": order.payment_status,
            "currency": order.currency,
            "total_amount": str(order.total_amount) if order.total_amount is not None else None,
            "ordered_at": order.ordered_at,
            "paid_at": order.paid_at,
            "items": [
                {
                    "name": item.name,
                    "product_number": item.product_id,
                    "sku_number": item.sku_id,
                    "sku": item.sku,
                    "specification": item.sku_name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_amount": item.total_amount,
                }
                for item in order.items
            ],
        }

    async def search_orders(self, args: OrderSearchArguments) -> dict[str, object]:
        # 由工作台在同买家完整集合中先筛选再分页，避免时间搜索重复拉取平台全量订单。
        result = await search_sidebar_orders(
            self.session,
            self.user,
            self.snapshot.conversation_id,
            SidebarSearch(
                section="orders",
                field=args.field,
                query=args.query,
                status=args.status,
                page=args.page,
                created_after=args.created_after,
                created_before=args.created_before,
            ),
        )
        total = result.pagination.total
        collected = result.items
        candidates = [
            {
                "order_ref": self.order_ref(order),
                "order_number": order.external_order_id,
                "status": order.status,
                "ordered_at": order.ordered_at,
                "total_amount": order.total_amount,
                "currency": order.currency,
                "products": [item.name for item in order.items[:3]],
                "item_count": len(order.items),
            }
            for order in collected
        ]
        return {
            "orders": candidates,
            "total": total,
            "page": args.page,
            "next_page": args.page + 1 if args.page * 20 < total else None,
        }

    async def select_order(self, args: OrderSelectionArguments) -> SidebarOrder | dict[str, object]:
        if args.order_ref:
            return self.orders.get(args.order_ref) or {"status": "invalid_selection"}
        result = await self.search_orders(OrderSearchArguments())
        if result["total"] == 0:
            return {
                "status": "succeeded",
                "facts": {"order_count": 0},
                "source": "tiktok_shop_api" if get_settings().real_tiktok_read_enabled else "crm_local_snapshot",
                "observed_at": datetime.now(UTC).isoformat(),
            }
        if result["total"] != 1:
            return {
                "status": "selection_required",
                "facts": safe_data(
                    {
                        "selection_required": True,
                        "candidates": result["orders"],
                        "total": result["total"],
                        "next_page": result["next_page"],
                    }
                ),
                "source": "tiktok_shop_api" if get_settings().real_tiktok_read_enabled else "crm_local_snapshot",
                "observed_at": datetime.now(UTC).isoformat(),
                "fact_scope": hashlib.sha256(f"order_candidates:{self.run_id}".encode()).hexdigest()[:16],
            }
        first = cast(list[dict[str, object]], result["orders"])[0]
        return self.orders[str(first["order_ref"])]

    def next_page(self, prefix: str, tool_name: str, signature: str, token: str | None) -> str | None:
        if not token:
            return None
        self._pages += 1
        ref = f"{prefix}{self._pages}"
        self.page_tokens[ref] = (tool_name, signature, token)
        return ref

    def page_token(self, ref: str | None, name: str, signature: str) -> str | None:
        if ref is None:
            return None
        record = self.page_tokens.get(ref)
        if record is None or record[:2] != (name, signature):
            raise ValueError("翻页引用无效或搜索条件已改变")
        return record[2]

    async def search_products(self, args: ProductSearchArguments) -> dict[str, object]:
        signature = f"{args.field}:{args.query}"
        result = await search_store_products(
            self.session,
            self.snapshot.store_id,
            SidebarSearch(
                section="products",
                field=args.field,
                query=args.query,
                page_token=self.page_token(args.page_ref, "search_products", signature),
            ),
        )
        candidates = []
        for product in result.items:
            ref = "p" + str(1 + int(hashlib.sha256(f"{self.run_id}:{product.id}".encode()).hexdigest()[:12], 16))
            if ref in self.products and self.products[ref] != product.id:
                raise AppError(ErrorCode.RESOURCE_CONFLICT, "商品候选引用冲突，请重试", 409)
            self.products[ref] = product.id
            candidates.append(
                {"product_ref": ref, "product_number": product.id, "title": product.title, "status": product.status}
            )
        return {
            "products": candidates,
            "platform_total_count": result.total_count,
            "matches_this_page": len(candidates),
            "partial_search": result.partial_search,
            "next_page_ref": self.next_page("p", "search_products", signature, result.next_page_token),
        }

    async def coupons(self, args: CouponSearchArguments) -> dict[str, object]:
        signature = f"{args.field}:{args.query}"
        result = await search_store_coupons(
            self.session,
            self.snapshot.store_id,
            SidebarSearch(
                section="coupons",
                field=args.field,
                query=args.query,
                page_token=self.page_token(args.page_ref, "query_available_coupons", signature),
            ),
        )
        return {
            "coupons": [item.model_dump(exclude={"id"}) for item in result.items],
            "platform_total_count": result.total_count,
            "matches_this_page": len(result.items),
            "partial_search": result.partial_search,
            "buyer_eligibility_verified": False,
            "next_page_ref": self.next_page("c", "query_available_coupons", signature, result.next_page_token),
        }

    async def logistics(self, order: SidebarOrder, args: LogisticsArguments) -> dict[str, object]:
        if not get_settings().real_tiktok_read_enabled:
            return {
                "order_ref": self.order_ref(order),
                "order_number": order.external_order_id,
                "tracking_number": order.tracking_number,
                "tracking_status": order.tracking_status,
                "tracking_source": "crm_local_snapshot",
                "packages": [],
                "event_count": 0,
                "package_count": 0,
                "next_event_offset": None,
                "next_package_offset": None,
                "live_tracking_available": False,
            }
        detail = await get_sidebar_order_detail(
            self.session, self.user, self.snapshot.conversation_id, order.external_order_id, include_tracking=False
        )
        if args.enhanced:
            enhanced = await get_sidebar_enhanced_tracking(
                self.session, self.user, self.snapshot.conversation_id, order.external_order_id
            )
            packages = enhanced.packages
        else:
            standard = await get_sidebar_standard_tracking(
                self.session, self.user, self.snapshot.conversation_id, order.external_order_id
            )
            packages = standard.packages
        events: list[dict[str, object]] = [
            {
                "package": index + 1 if args.enhanced else None,
                "carrier": parcel.carrier_name if args.enhanced else None,
                "tracking_number": event.tracking_number or parcel.tracking_number,
                "description": event.description,
                "occurred_at": event.occurred_at,
                "action_code": event.action_code,
            }
            for index, parcel in enumerate(packages)
            for event in parcel.events
        ]
        events.sort(key=lambda event: cast(datetime, event["occurred_at"]), reverse=True)
        package_facts: list[dict[str, object]]
        if args.enhanced:
            package_facts = [
                {
                    "package": index + 1,
                    "carrier": parcel.carrier_name,
                    "tracking_number": parcel.tracking_number,
                    "event_count": len(parcel.events),
                }
                for index, parcel in enumerate(packages)
            ]
        else:
            # 通用 API 的轨迹属于整单；不能把全单轨迹冒充某一个包裹的详情。
            known = [(item.package_id, item.tracking_number) for item in detail.order_packages]
            if not known:
                known = [
                    (item.package_id, item.tracking_number)
                    for item in order.items
                    if item.package_id or item.tracking_number
                ]
            if not known:
                known = [(item.package_id, item.tracking_number) for item in packages]
            package_facts = [
                {"package": index + 1, "carrier": None, "tracking_number": number}
                for index, (_package_id, number) in enumerate(dict.fromkeys(known))
            ]
        event_page, next_event = (
            _bounded_facts_page(events, args.event_offset, 9000) if args.detail == "history" else (events[:1], None)
        )
        package_page, next_package = _bounded_facts_page(package_facts, args.package_offset, 4000)
        return {
            "order_ref": self.order_ref(order),
            "order_number": order.external_order_id,
            "enhanced": args.enhanced,
            "detail": args.detail,
            "enhanced_available": detail.enhanced_tracking_available,
            # 通用轨迹没有核实实际承运商；保留平台履约服务原值，不把揽收方式冒充末端承运商。
            "shipping_provider": detail.shipping_provider,
            "carrier_source": "official_enhanced_tracking" if args.enhanced else "not_verified_by_standard_timeline",
            "packages": package_page,
            "package_count": len(package_facts),
            "next_package_offset": next_package,
            "event_scope": "package" if args.enhanced else "order",
            "events": event_page,
            "event_count": len(events),
            "event_offset": args.event_offset,
            "package_offset": args.package_offset,
            "next_event_offset": next_event,
        }

    async def aftersales(self, order: SidebarOrder, args: AftersalesArguments) -> dict[str, object]:
        _conv, client, _remote = await _verified_sidebar_order(
            self.session, self.user, self.snapshot.conversation_id, order.external_order_id
        )
        if args.return_ref is not None:
            selected = self.return_cases.get(args.return_ref)
            if selected is None or selected.order_id != order.external_order_id:
                raise ValueError("售后申请引用不属于当前订单")
            cases, token = [selected], None
        else:
            cases, token = await client.search_returns(
                order.external_order_id,
                page_token=self.page_token(args.page_ref, "query_aftersales", order.external_order_id),
            )
        rows = []
        has_more_details = False
        for item in cases:
            ref = "r" + str(1 + int(hashlib.sha256(f"{self.run_id}:{item.return_id}".encode()).hexdigest()[:12], 16))
            if ref in self.return_cases and self.return_cases[ref].return_id != item.return_id:
                raise AppError(ErrorCode.RESOURCE_CONFLICT, "售后候选引用冲突，请重试", 409)
            self.return_cases[ref] = item
            row = item.model_dump(exclude={"order_id", "return_id", "return_line_items"})
            row.update(
                {
                    "return_ref": ref,
                    "line_count": len(item.return_line_items),
                    "products": [line.product_name for line in item.return_line_items[:3]],
                }
            )
            if args.return_ref is not None or len(cases) == 1:
                start = (args.page - 1) * args.page_size
                row["line_items"] = [
                    line.model_dump() for line in item.return_line_items[start : start + args.page_size]
                ]
                has_more_details = has_more_details or start + args.page_size < len(item.return_line_items)
                if args.include_records:
                    if item.return_id not in self.return_records:
                        self.return_records[item.return_id] = await client.get_return_records(item.return_id)
                    records = self.return_records[item.return_id]
                    row["records"] = [record.model_dump() for record in records[start : start + args.page_size]]
                    row["record_count"] = len(records)
                    has_more_details = has_more_details or start + args.page_size < len(records)
            rows.append(row)
        return {
            "order_ref": self.order_ref(order),
            "order_number": order.external_order_id,
            "returns": rows,
            "records_selection_required": args.include_records and args.return_ref is None and len(cases) > 1,
            "next_detail_page": args.page + 1 if has_more_details else None,
            "next_page_ref": self.next_page("a", "query_aftersales", order.external_order_id, token),
        }

    async def messages(self, args: ConversationHistoryArguments) -> dict[str, object]:
        ids = self.snapshot.message_ids
        rows = (
            await self.session.scalars(
                select(Message)
                .where(
                    Message.id.in_(ids),
                    Message.store_id == self.snapshot.store_id,
                    Message.conversation_id == self.snapshot.conversation_id,
                )
                .order_by(Message.created_at.desc(), Message.id.desc())
                .offset(args.offset)
                .limit(args.limit)
            )
        ).all()
        return {
            "messages": [
                {"role": row.role, "direction": row.direction, "content": row.content, "created_at": row.created_at}
                for row in rows
            ],
            "frozen_message_count": len(ids),
            "next_offset": args.offset + len(rows)
            if len(rows) == args.limit and args.offset + len(rows) < len(ids)
            else None,
        }
