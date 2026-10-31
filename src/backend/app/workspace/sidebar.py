"""客户侧栏只读投影。平台目录按当前会话的店铺授权读取。"""

import hashlib
import json
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, ValidationError, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.auth.store_access import allowed_store_ids, ensure_conversation_access
from app.conversations.models import Conversation
from app.customers.models import Customer
from app.integrations.tiktok_read import (
    TikTokCoupon,
    TikTokCouponDuration,
    TikTokOrder,
    TikTokProduct,
    TikTokProductSku,
    TikTokReadClient,
)
from app.orders.models import Order, OrderItem
from app.shared.config.settings import get_settings
from app.shared.database.base import User
from app.shared.database.redis import redis_client
from app.shared.exceptions.errors import AppError, ErrorCode
from app.stores.models import ChannelAccount, Store
from app.workspace.repository import find_conversation
from app.workspace.schemas import PageMeta

OrderStatus = Literal["all", "unpaid", "ship", "transit", "done", "cancel"]
OrderField = Literal["order", "tracking", "product", "spu", "sku", "sellerSku"]
ProductField = Literal["name", "productId", "sku", "sellerSku"]
CouponField = Literal["name", "code"]


class SidebarSearch(BaseModel):
    section: Literal["orders", "products", "coupons"]
    field: str = Field(max_length=30)
    query: str = Field(default="", max_length=100)
    status: OrderStatus = "all"
    page: int = Field(default=1, ge=1, le=10_000)
    page_token: str | None = Field(default=None, max_length=1000)
    refresh: bool = False
    created_after: AwareDatetime | None = None
    created_before: AwareDatetime | None = None

    @model_validator(mode="after")
    def valid_order_window(self) -> "SidebarSearch":
        if self.created_after and self.created_before and self.created_after >= self.created_before:
            raise ValueError("下单时间范围无效")
        return self


class SidebarOrderItem(BaseModel):
    name: str
    product_id: str | None
    sku: str | None
    sku_id: str | None
    sku_name: str | None
    image_url: str | None
    quantity: int
    unit_price: Decimal | None
    total_amount: Decimal | None
    package_id: str | None = None
    tracking_number: str | None = None


class SidebarOrder(BaseModel):
    id: uuid.UUID
    external_order_id: str
    status: str
    payment_status: str | None
    currency: str
    total_amount: Decimal | None
    payment_breakdown: dict[str, str]
    ordered_at: datetime | None
    paid_at: datetime | None = None
    tracking_number: str | None
    tracking_status: str | None
    items: list[SidebarOrderItem]
    live_detail_available: bool = False


class SidebarOrders(BaseModel):
    items: list[SidebarOrder]
    pagination: PageMeta


@dataclass(frozen=True)
class _CachedLiveOrders:
    expires_at: float
    buyer_user_id: str
    items: tuple[SidebarOrder, ...] | None


@dataclass(frozen=True)
class _VerifiedOrderTracking:
    expires_at: float
    tracking_number: str | None
    shipping_provider: str | None
    package_id: str | None
    item_tracking_numbers: tuple[str, ...]


_LIVE_ORDER_CACHE_TTL_SECONDS = 20
_LIVE_ORDER_CACHE_LIMIT = 64
_LIVE_ORDER_CACHE_ITEM_LIMIT = 100
_live_order_cache: OrderedDict[str, _CachedLiveOrders] = OrderedDict()
_verified_order_cache: OrderedDict[str, _VerifiedOrderTracking] = OrderedDict()


def _live_order_cache_key(conversation: Conversation, customer: Customer, client: TikTokReadClient) -> str | None:
    channel = getattr(client, "channel", None)
    channel_id = getattr(channel, "id", None)
    access_token_ref = getattr(channel, "access_token_ref", None)
    if not isinstance(channel_id, uuid.UUID) or not isinstance(access_token_ref, str):
        return None
    scope = [
        str(conversation.store_id),
        str(conversation.id),
        str(conversation.customer_id),
        conversation.external_conversation_id,
        customer.external_customer_id,
        str(channel_id),
        access_token_ref,
        client.shop_cipher,
    ]
    digest = hashlib.sha256(json.dumps(scope, separators=(",", ":")).encode()).hexdigest()
    return f"workspace:live-orders:{conversation.store_id}:{digest}"


def _cached_live_orders(key: str | None) -> _CachedLiveOrders | None:
    if key is None:
        return None
    cached = _live_order_cache.get(key)
    if cached is None:
        return None
    if cached.expires_at <= time.monotonic():
        del _live_order_cache[key]
        return None
    _live_order_cache.move_to_end(key)
    return cached


def _remember_live_orders(key: str | None, buyer_user_id: str, items: tuple[SidebarOrder, ...] | None) -> None:
    if key is None:
        return
    # 大买家列表不进入进程内存，仍可短时复用核验过的买家 ID。
    if items is not None and len(items) > _LIVE_ORDER_CACHE_ITEM_LIMIT:
        items = None
    _live_order_cache[key] = _CachedLiveOrders(time.monotonic() + _LIVE_ORDER_CACHE_TTL_SECONDS, buyer_user_id, items)
    _live_order_cache.move_to_end(key)
    while len(_live_order_cache) > _LIVE_ORDER_CACHE_LIMIT:
        _live_order_cache.popitem(last=False)


def _verified_order_key(cache_key: str | None, order_id: str) -> str | None:
    return f"{cache_key}:{order_id}" if cache_key is not None else None


def _tracking_from_order(order: TikTokOrder) -> _VerifiedOrderTracking:
    package_ids = {item.package_id for item in order.line_items if item.package_id}
    return _VerifiedOrderTracking(
        expires_at=time.monotonic() + _LIVE_ORDER_CACHE_TTL_SECONDS,
        tracking_number=order.tracking_number,
        shipping_provider=order.shipping_provider,
        package_id=next(iter(package_ids)) if len(package_ids) == 1 else None,
        item_tracking_numbers=tuple(item.tracking_number for item in order.line_items if item.tracking_number),
    )


def _remember_verified_order(key: str | None, tracking: _VerifiedOrderTracking) -> None:
    if key is None:
        return
    _verified_order_cache[key] = tracking
    _verified_order_cache.move_to_end(key)
    while len(_verified_order_cache) > _LIVE_ORDER_CACHE_LIMIT:
        _verified_order_cache.popitem(last=False)


def _cached_verified_order(key: str | None) -> _VerifiedOrderTracking | None:
    if key is None:
        return None
    cached = _verified_order_cache.get(key)
    if cached is None:
        return None
    if cached.expires_at <= time.monotonic():
        del _verified_order_cache[key]
        return None
    _verified_order_cache.move_to_end(key)
    return cached


class SidebarOrderDetailRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=200, pattern=r"^[0-9]+$")
    include_tracking: bool = True


class SidebarTrackingTranslationRequest(SidebarOrderDetailRequest):
    event_description: str | None = Field(default=None, min_length=1, max_length=1000)
    event_at: datetime | None = None
    event_tracking_number: str | None = Field(default=None, max_length=200)
    enhanced: bool = False


class SidebarTrackingTimelineTranslationRequest(SidebarOrderDetailRequest):
    enhanced: bool = False


class SidebarOrderDetail(BaseModel):
    payment_method_name: str | None
    recipient_address: "SidebarRecipientAddress | None" = None
    shipping_provider: str | None
    latest_tracking_description: str | None
    latest_tracking_at: datetime | None
    tracking_packages: list["SidebarTrackingPackage"] = Field(default_factory=list)
    order_packages: list["SidebarTrackingPackage"] = Field(default_factory=list)
    enhanced_tracking_available: bool = False
    tracking_loaded: bool = True


class SidebarStandardTracking(BaseModel):
    latest_tracking_description: str | None = None
    latest_tracking_at: datetime | None = None
    packages: list["SidebarTrackingPackage"] = Field(default_factory=list)


class SidebarRecipientAddress(BaseModel):
    name: str | None = None
    phone_number: str | None = None
    full_address: str | None = None


class SidebarTrackingEvent(BaseModel):
    description: str
    occurred_at: datetime
    tracking_number: str | None = None
    action_code: int
    action_code_name: str | None = None


class SidebarTrackingPackage(BaseModel):
    package_id: str | None = None
    tracking_number: str | None
    carrier_name: str | None
    events: list[SidebarTrackingEvent]


class SidebarTrackingTimeline(BaseModel):
    packages: list[SidebarTrackingPackage]


def _matching_package_id(order: TikTokOrder, tracking_number: str | None) -> str | None:
    """只有订单行能把单号唯一映射到包裹时才选择包裹 ID。"""
    matches = {
        item.package_id for item in order.line_items if item.package_id and item.tracking_number == tracking_number
    }
    return next(iter(matches)) if len(matches) == 1 else None


class SidebarTrackingTranslation(BaseModel):
    source_description: str
    translated_text: str


class SidebarTrackingEventTranslation(SidebarTrackingTranslation):
    occurred_at: datetime
    tracking_number: str | None


class SidebarTrackingTimelineTranslation(BaseModel):
    events: list[SidebarTrackingEventTranslation]


class SidebarSku(BaseModel):
    id: str
    seller_sku: str | None
    name: str | None
    currency: str | None
    sale_price: str | None
    quantity: int | None


class SidebarProduct(BaseModel):
    id: str
    title: str
    status: str | None
    image_url: str | None
    skus: list[SidebarSku]
    brand: str | None = None
    description_html: str | None = None
    attributes: list[dict[str, object]] = Field(default_factory=list)


class SidebarProducts(BaseModel):
    items: list[SidebarProduct]
    next_page_token: str | None
    total_count: int | None
    partial_search: bool = False


class SidebarCoupon(BaseModel):
    id: str
    title: str
    status: str | None
    display_type: str | None
    promo_code: str | None
    discount_type: str | None
    discount_value: str | None
    claim_end_time: int | None
    chat_shareable: bool
    claim_start_time: int | None = None
    redemption_duration: dict[str, object] = Field(default_factory=dict)
    target_buyer_segment: str | None = None
    product_scope: str | None = None
    threshold: dict[str, object] = Field(default_factory=dict)


class SidebarCoupons(BaseModel):
    items: list[SidebarCoupon]
    next_page_token: str | None
    total_count: int | None
    partial_search: bool = False


async def _conversation(session: AsyncSession, user: User, session_id: uuid.UUID) -> Conversation:
    conversation = await find_conversation(
        session, session_id, await allowed_store_ids(session, user, "workspace.view")
    )
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
    await ensure_conversation_access(session, user, conversation)
    return conversation


async def _tiktok_client(session: AsyncSession, store_id: uuid.UUID) -> TikTokReadClient:
    channel = await session.scalar(
        select(ChannelAccount)
        .join(Store, Store.id == ChannelAccount.store_id)
        .where(
            ChannelAccount.store_id == store_id,
            ChannelAccount.platform == "tiktok",
            ChannelAccount.status == "connected",
            Store.status == "active",
            Store.deleted_at.is_(None),
        )
    )
    if channel is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "店铺授权不可用", 404)
    return TikTokReadClient(get_settings(), channel)


def _order_status_condition(status: OrderStatus) -> ColumnElement[bool] | None:
    statuses: dict[str, tuple[str, ...]] = {
        "unpaid": ("UNPAID",),
        "ship": ("AWAITING_SHIPMENT", "AWAITING_COLLECTION"),
        "transit": ("IN_TRANSIT", "SHIPPED"),
        "done": ("DELIVERED", "COMPLETED"),
        "cancel": ("CANCELLED", "CANCELED"),
    }
    return Order.status.in_(statuses[status]) if status != "all" else None


def _live_order_matches(order: SidebarOrder, payload: SidebarSearch) -> bool:
    statuses: dict[str, tuple[str, ...]] = {
        "unpaid": ("UNPAID",),
        "ship": ("AWAITING_SHIPMENT", "AWAITING_COLLECTION"),
        "transit": ("IN_TRANSIT", "SHIPPED"),
        "done": ("DELIVERED", "COMPLETED"),
        "cancel": ("CANCELLED", "CANCELED"),
    }
    if payload.status != "all" and order.status not in statuses[payload.status]:
        return False
    if payload.created_after and (order.ordered_at is None or order.ordered_at < payload.created_after):
        return False
    if payload.created_before and (order.ordered_at is None or order.ordered_at >= payload.created_before):
        return False
    query = payload.query.strip().casefold()
    if not query:
        return True
    values: dict[str, list[str | None]] = {
        "order": [order.external_order_id],
        "tracking": [order.tracking_number, *(item.tracking_number for item in order.items)],
        "product": [item.name if item.name != "商品名称未提供" else None for item in order.items],
        "spu": [item.product_id for item in order.items],
        "sku": [item.sku_id for item in order.items],
        "sellerSku": [item.sku for item in order.items],
    }
    return any(query in value.casefold() for value in values[payload.field] if value)


def _live_order_view(order: TikTokOrder) -> SidebarOrder:
    def amount(value: str | None) -> Decimal | None:
        if value is None:
            return None
        try:
            result = Decimal(value)
        except InvalidOperation as exc:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 订单金额异常", 502) from exc
        if not result.is_finite():
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 订单金额异常", 502)
        return result

    payment = order.payment
    currency = (payment.currency if payment and payment.currency else None) or next(
        (item.currency for item in order.line_items if item.currency), ""
    )
    total_amount = amount(payment.total_amount) if payment else None
    breakdown = {
        key: value
        for key in (
            "original_total_product_price",
            "sub_total",
            "seller_discount",
            "platform_discount",
            "shipping_fee",
            "tax",
        )
        if payment is not None and (value := getattr(payment, key)) is not None
    }
    return SidebarOrder(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"tiktok:order:{order.id}"),
        external_order_id=order.id,
        status=order.status,
        payment_status=None,
        currency=currency,
        total_amount=total_amount,
        payment_breakdown=breakdown,
        ordered_at=datetime.fromtimestamp(order.create_time, UTC) if order.create_time else None,
        paid_at=datetime.fromtimestamp(order.paid_time, UTC) if order.paid_time else None,
        tracking_number=order.tracking_number
        or next((item.tracking_number for item in order.line_items if item.tracking_number), None),
        tracking_status=None,
        live_detail_available=True,
        items=[
            SidebarOrderItem(
                name=item.product_name or "商品名称未提供",
                product_id=item.product_id,
                sku=item.seller_sku,
                sku_id=item.sku_id,
                sku_name=item.sku_name,
                image_url=item.sku_image if item.sku_image and item.sku_image.startswith("https://") else None,
                quantity=1,
                unit_price=amount(item.sale_price),
                total_amount=amount(item.sale_price),
                package_id=item.package_id,
                tracking_number=item.tracking_number,
            )
            for item in order.line_items
        ],
    )


async def _search_live_orders(
    session: AsyncSession, conversation: Conversation, payload: SidebarSearch
) -> SidebarOrders:
    client = await _tiktok_client(session, conversation.store_id)
    customer = await _local_verified_customer(session, conversation)
    cache_key = _live_order_cache_key(conversation, customer, client)
    cached = None if payload.refresh else _cached_live_orders(cache_key)
    if cached is not None and cached.items is not None:
        items = cached.items
    else:
        buyer_user_id = (
            cached.buyer_user_id
            if cached is not None
            else await _verified_buyer_user_id(session, conversation, client, customer)
        )
        orders: list[TikTokOrder] = []
        token: str | None = None
        seen_tokens: set[str] = set()
        seen_order_ids: set[str] = set()
        # 买家订单超过安全上限时显式失败，避免把不完整搜索结果当成全部订单。
        for _ in range(20):
            page, next_token, _ = await client.search_orders(
                page_size=100, page_token=token, buyer_user_id=buyer_user_id
            )
            if any(order.user_id != buyer_user_id for order in page):
                raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 订单买家身份不匹配", 502)
            if len({order.id for order in page}) != len(page) or any(order.id in seen_order_ids for order in page):
                raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 订单分页异常", 502)
            seen_order_ids.update(order.id for order in page)
            orders.extend(page)
            if not next_token:
                break
            if next_token in seen_tokens:
                raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 订单分页异常", 502)
            seen_tokens.add(next_token)
            token = next_token
        else:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "买家订单超过当前查询上限", 502)
        items = tuple(_live_order_view(order) for order in orders)
        _remember_live_orders(cache_key, buyer_user_id, items)
    matches = sorted(
        (order for order in items if _live_order_matches(order, payload)),
        key=lambda order: (order.ordered_at or datetime.min.replace(tzinfo=UTC), order.external_order_id),
        reverse=True,
    )
    page_size = 20
    selected = matches[(payload.page - 1) * page_size : payload.page * page_size]
    return SidebarOrders(
        items=[order.model_copy(deep=True) for order in selected],
        pagination=PageMeta(page=payload.page, page_size=page_size, total=len(matches)),
    )


async def latest_verified_live_order(session: AsyncSession, conversation: Conversation) -> SidebarOrder | None:
    """只读查询已验证会话买家的最新平台订单，供受控 Agent 调试使用。"""
    result = await _search_live_orders(
        session,
        conversation,
        SidebarSearch(section="orders", field="order", query="", page=1, refresh=True),
    )
    return result.items[0] if result.items else None


async def _local_verified_customer(session: AsyncSession, conversation: Conversation) -> Customer:
    customer = await session.get(Customer, conversation.customer_id)
    if (
        customer is None
        or customer.store_id != conversation.store_id
        or customer.platform != conversation.platform
        or not customer.external_customer_id
    ):
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "会话买家身份不可验证", 502)
    return customer


async def _verified_buyer_user_id(
    session: AsyncSession, conversation: Conversation, client: TikTokReadClient, customer: Customer | None = None
) -> str:
    customer = customer or await _local_verified_customer(session, conversation)
    remote = await client.get_conversation(conversation.external_conversation_id)
    buyers = [participant for participant in remote.participants if participant.role == "BUYER"]
    if len(buyers) != 1 or buyers[0].im_user_id != customer.external_customer_id or not buyers[0].user_id:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "会话买家身份不可验证", 502)
    return buyers[0].user_id


async def _verified_sidebar_order(
    session: AsyncSession, user: User, session_id: uuid.UUID, order_id: str
) -> tuple[Conversation, TikTokReadClient, TikTokOrder]:
    conversation = await _conversation(session, user, session_id)
    if conversation.platform != "tiktok" or not get_settings().real_tiktok_read_enabled:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "订单详情不可用", 404)
    if not order_id.isascii() or not order_id.isdigit() or len(order_id) > 200:
        raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 订单 ID 无效", 422)
    client = await _tiktok_client(session, conversation.store_id)
    customer = await _local_verified_customer(session, conversation)
    cache_key = _live_order_cache_key(conversation, customer, client)
    cached = _cached_live_orders(cache_key)
    buyer_user_id = (
        cached.buyer_user_id
        if cached is not None
        else await _verified_buyer_user_id(session, conversation, client, customer)
    )
    orders, _ = await client.get_order_details([order_id])
    if len(orders) != 1 or orders[0].id != order_id or orders[0].user_id != buyer_user_id:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "订单不存在", 404)
    if cached is None:
        _remember_live_orders(cache_key, buyer_user_id, None)
    _remember_verified_order(_verified_order_key(cache_key, order_id), _tracking_from_order(orders[0]))
    return conversation, client, orders[0]


def _tracking_time(millis: int) -> datetime:
    try:
        return datetime.fromtimestamp(millis / 1000, UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "TikTok 物流时间异常", 502) from exc


async def get_sidebar_order_detail(
    session: AsyncSession, user: User, session_id: uuid.UUID, order_id: str, *, include_tracking: bool = True
) -> SidebarOrderDetail:
    _conversation_view, client, order = await _verified_sidebar_order(session, user, session_id, order_id)
    tracking = (
        await _read_standard_tracking(client, order_id, _tracking_from_order(order))
        if include_tracking
        else SidebarStandardTracking()
    )
    return SidebarOrderDetail(
        payment_method_name=order.payment_method_name,
        recipient_address=SidebarRecipientAddress(
            name=order.recipient_address.name,
            phone_number=order.recipient_address.phone_number,
            full_address=order.recipient_address.full_address,
        )
        if order.recipient_address
        else None,
        shipping_provider=order.shipping_provider,
        latest_tracking_description=tracking.latest_tracking_description,
        latest_tracking_at=tracking.latest_tracking_at,
        tracking_packages=tracking.packages,
        order_packages=[
            SidebarTrackingPackage(
                package_id=package_id, tracking_number=tracking_number, carrier_name=order.shipping_provider, events=[]
            )
            for package_id, tracking_number in dict.fromkeys(
                (item.package_id, item.tracking_number)
                for item in order.line_items
                if item.package_id or item.tracking_number
            )
        ],
        enhanced_tracking_available=(
            getattr(getattr(client, "channel", None), "metadata_json", {}).get("seller_type") == "CROSS_BORDER"
        ),
        tracking_loaded=include_tracking,
    )


async def _read_standard_tracking(
    client: TikTokReadClient, order_id: str, proof: _VerifiedOrderTracking
) -> SidebarStandardTracking:
    latest_description: str | None = None
    latest_at: datetime | None = None
    tracking_packages: list[SidebarTrackingPackage] = []
    if proof.tracking_number or proof.item_tracking_numbers:
        events, _ = await client.get_standard_tracking(order_id)
        if events:
            events.sort(key=lambda event: event.update_time_millis, reverse=True)
            latest = events[0]
            latest_at = _tracking_time(latest.update_time_millis)
            latest_description = latest.description
            item_numbers = set(proof.item_tracking_numbers)
            tracking_packages = [
                SidebarTrackingPackage(
                    package_id=proof.package_id,
                    tracking_number=proof.tracking_number
                    or (next(iter(item_numbers)) if len(item_numbers) == 1 else None),
                    carrier_name=proof.shipping_provider,
                    events=[
                        SidebarTrackingEvent(
                            description=event.description,
                            occurred_at=_tracking_time(event.update_time_millis),
                            action_code=event.action_code,
                        )
                        for event in events
                    ],
                )
            ]
    return SidebarStandardTracking(
        latest_tracking_description=latest_description,
        latest_tracking_at=latest_at,
        packages=tracking_packages,
    )


async def get_sidebar_standard_tracking(
    session: AsyncSession, user: User, session_id: uuid.UUID, order_id: str
) -> SidebarStandardTracking:
    """仅对当前授权会话已核验买家订单读取通用物流；短时证明失效时重新核验。"""
    conversation = await _conversation(session, user, session_id)
    if conversation.platform != "tiktok" or not get_settings().real_tiktok_read_enabled:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "物流详情不可用", 404)
    if not order_id.isascii() or not order_id.isdigit() or len(order_id) > 200:
        raise AppError(ErrorCode.VALIDATION_ERROR, "TikTok 订单 ID 无效", 422)
    client = await _tiktok_client(session, conversation.store_id)
    customer = await _local_verified_customer(session, conversation)
    proof = _cached_verified_order(_verified_order_key(_live_order_cache_key(conversation, customer, client), order_id))
    if proof is None:
        _verified_conversation, client, order = await _verified_sidebar_order(session, user, session_id, order_id)
        proof = _tracking_from_order(order)
    return await _read_standard_tracking(client, order_id, proof)


async def get_sidebar_enhanced_tracking(
    session: AsyncSession, user: User, session_id: uuid.UUID, order_id: str
) -> SidebarTrackingTimeline:
    conversation, client, order = await _verified_sidebar_order(session, user, session_id, order_id)
    if client.channel.metadata_json.get("seller_type") != "CROSS_BORDER":
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "当前店铺没有增强物流轨迹", 404)
    # 官方要求每单至少间隔八小时；先占位再请求，跨实例也不会并发触发同单查询。
    shop_hash = hashlib.sha256(client.shop_cipher.encode()).hexdigest()[:16]
    cache_key = f"workspace:tracking:202604:{conversation.store_id}:{shop_hash}:{order_id}"
    cached = await redis_client.get(cache_key)
    if cached and cached not in {"pending", "unavailable"}:
        try:
            return SidebarTrackingTimeline.model_validate_json(cached)
        except ValidationError as exc:
            raise AppError(ErrorCode.THIRD_PARTY_ERROR, "增强物流缓存异常，请查看通用轨迹", 503) from exc
    if cached:
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "增强物流暂不可用，请查看通用轨迹", 503)
    if not await redis_client.set(cache_key, "pending", nx=True, ex=8 * 60 * 60):
        raise AppError(ErrorCode.THIRD_PARTY_ERROR, "增强物流正在读取，请稍后重试", 503)
    try:
        parcels, _ = await client.get_tracking(order_id)
        timeline = SidebarTrackingTimeline(
            packages=[
                SidebarTrackingPackage(
                    package_id=parcel.package_id or _matching_package_id(order, parcel.newest_tracking_no),
                    tracking_number=parcel.newest_tracking_no,
                    carrier_name=parcel.carrier_name,
                    events=[
                        SidebarTrackingEvent(
                            description=event.description,
                            occurred_at=_tracking_time(event.update_time_millis),
                            tracking_number=event.tracking_no,
                            action_code=event.action_code,
                            action_code_name=event.action_code_name,
                        )
                        for event in sorted(parcel.track_list, key=lambda item: item.update_time_millis, reverse=True)
                    ],
                )
                for parcel in parcels
            ]
        )
    except (AppError, ValueError):
        await redis_client.set(cache_key, "unavailable", ex=8 * 60 * 60)
        raise
    await redis_client.set(cache_key, timeline.model_dump_json(), ex=8 * 60 * 60)
    return timeline


async def search_sidebar_orders(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID,
    payload: SidebarSearch,
) -> SidebarOrders:
    conversation = await _conversation(session, user, session_id)
    if payload.field not in {"order", "tracking", "product", "spu", "sku", "sellerSku"}:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不支持的订单搜索字段", 422)
    if conversation.platform == "tiktok" and get_settings().real_tiktok_read_enabled:
        return await _search_live_orders(session, conversation, payload)
    filters = [
        Order.store_id == conversation.store_id,
        Order.customer_id == conversation.customer_id,
        Order.platform == conversation.platform,
    ]
    if payload.created_after:
        filters.append(Order.ordered_at >= payload.created_after)
    if payload.created_before:
        filters.append(Order.ordered_at < payload.created_before)
    status_condition = _order_status_condition(payload.status)
    if status_condition is not None:
        filters.append(status_condition)
    query = payload.query.strip()
    if query:
        escaped_query = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped_query}%"
        item_field = {
            "product": OrderItem.product_name,
            "spu": OrderItem.product_id,
            "sku": OrderItem.raw_payload["sku_id"].astext,
            "sellerSku": OrderItem.sku,
        }
        if payload.field == "order":
            filters.append(Order.external_order_id.ilike(pattern, escape="\\"))
        elif payload.field == "tracking":
            filters.append(Order.tracking_number.ilike(pattern, escape="\\"))
        else:
            filters.append(
                select(OrderItem.id)
                .where(OrderItem.order_id == Order.id, item_field[payload.field].ilike(pattern, escape="\\"))
                .exists()
            )
    total = int(await session.scalar(select(func.count()).select_from(Order).where(*filters)) or 0)
    page_size = 20
    orders = list(
        (
            await session.scalars(
                select(Order)
                .where(*filters)
                .order_by(Order.ordered_at.desc().nullslast(), Order.created_at.desc())
                .offset((payload.page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    order_ids = [order.id for order in orders]
    items_by_order: dict[uuid.UUID, list[SidebarOrderItem]] = {order_id: [] for order_id in order_ids}
    if order_ids:
        order_items = (await session.scalars(select(OrderItem).where(OrderItem.order_id.in_(order_ids)))).all()
        for item in order_items:
            raw = item.raw_payload or {}
            sku_id = raw.get("sku_id")
            sku_name = raw.get("sku_name")
            sku_image = raw.get("sku_image")
            items_by_order[item.order_id].append(
                SidebarOrderItem(
                    name=item.product_name,
                    product_id=item.product_id,
                    sku=item.sku,
                    sku_id=sku_id if isinstance(sku_id, str) else None,
                    sku_name=sku_name if isinstance(sku_name, str) else None,
                    image_url=sku_image if isinstance(sku_image, str) and sku_image.startswith("https://") else None,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_amount=item.total_amount,
                )
            )

    def breakdown(order: Order) -> dict[str, str]:
        raw = (order.raw_payload or {}).get("payment_breakdown")
        return (
            {key: value for key, value in raw.items() if isinstance(key, str) and isinstance(value, str)}
            if isinstance(raw, dict)
            else {}
        )

    return SidebarOrders(
        items=[
            SidebarOrder(
                id=order.id,
                external_order_id=order.external_order_id,
                status=order.status,
                payment_status=order.payment_status,
                currency=order.currency,
                total_amount=order.total_amount,
                payment_breakdown=breakdown(order),
                ordered_at=order.ordered_at,
                paid_at=order.paid_at,
                tracking_number=order.tracking_number,
                tracking_status=order.tracking_status,
                items=items_by_order[order.id],
            )
            for order in orders
        ],
        pagination=PageMeta(page=payload.page, page_size=page_size, total=total),
    )


def _product_view(product: TikTokProduct, *, include_details: bool = False) -> SidebarProduct:
    image_url = None
    if product.main_images:
        urls = product.main_images[0].get("urls")
        if isinstance(urls, list) and urls and isinstance(urls[0], str) and urls[0].startswith("https://"):
            image_url = urls[0]
    skus = []
    for sku in product.skus:
        if not _sku_in_stock(sku):
            continue
        names = [value for attr in sku.sales_attributes if isinstance((value := attr.get("value_name")), str)]
        skus.append(
            SidebarSku(
                id=sku.id,
                seller_sku=sku.seller_sku,
                name=" / ".join(names) or None,
                currency=sku.price.currency if sku.price else None,
                sale_price=sku.price.sale_price if sku.price else None,
                quantity=sum(inv.quantity for inv in sku.inventory if inv.quantity is not None)
                if sku.inventory
                else None,
            )
        )
    return SidebarProduct(
        id=product.id,
        title=product.title,
        status=product.status,
        image_url=image_url,
        skus=skus,
        brand=product.brand.name if include_details and product.brand else None,
        description_html=product.description if include_details else None,
        attributes=[
            {"name": attr.name, "values": [value.name for value in attr.values]} for attr in product.product_attributes
        ]
        if include_details
        else [],
    )


def _sku_in_stock(sku: TikTokProductSku) -> bool:
    return any(inventory.quantity is not None and inventory.quantity > 0 for inventory in sku.inventory)


def _listed_in_stock(product: TikTokProduct) -> bool:
    # 平台目录的未知库存不能当作有货；客服和 Agent 共用此保守筛选。
    return product.status == "ACTIVATE" and any(_sku_in_stock(sku) for sku in product.skus)


async def search_sidebar_products(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID,
    payload: SidebarSearch,
) -> SidebarProducts:
    conversation = await _conversation(session, user, session_id)
    if conversation.platform != "tiktok":
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "当前平台没有商品目录", 404)
    return await search_store_products(session, conversation.store_id, payload)


async def search_store_products(session: AsyncSession, store_id: uuid.UUID, payload: SidebarSearch) -> SidebarProducts:
    """调用方先校验店铺和读取权限；不要求创建买家会话。"""
    if payload.field not in {"name", "productId", "sku", "sellerSku"}:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不支持的商品搜索字段", 422)
    client = await _tiktok_client(session, store_id)
    query = payload.query.strip()
    if payload.field == "productId" and query:
        product = await client.get_product(query)
        available = _listed_in_stock(product)
        return SidebarProducts(
            items=[_product_view(product)] if available else [], next_page_token=None, total_count=int(available)
        )
    sku_ids = [query] if query and payload.field == "sku" else None
    seller_skus = [query] if query and payload.field == "sellerSku" else None
    products, next_token, total = await client.search_products(
        page_token=payload.page_token,
        sku_ids=sku_ids,
        seller_skus=seller_skus,
    )
    if query and payload.field == "name":
        products = [product for product in products if query.casefold() in product.title.casefold()]
    return SidebarProducts(
        items=[_product_view(item) for item in products if _listed_in_stock(item)],
        next_page_token=next_token,
        total_count=total,
        partial_search=bool(query and payload.field == "name" and next_token),
    )


async def get_sidebar_product(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID,
    product_id: str,
) -> SidebarProduct:
    conversation = await _conversation(session, user, session_id)
    if conversation.platform != "tiktok":
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "当前平台没有商品目录", 404)
    return await get_store_product(session, conversation.store_id, product_id)


async def get_store_product(session: AsyncSession, store_id: uuid.UUID, product_id: str) -> SidebarProduct:
    """调用方先校验店铺和读取权限；不要求创建买家会话。"""
    client = await _tiktok_client(session, store_id)
    product = await client.get_product(product_id)
    if not _listed_in_stock(product):
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "商品已下架或无可用库存", 404)
    return _product_view(product, include_details=True)


def _coupon_view(coupon: TikTokCoupon) -> SidebarCoupon:
    discount_type = coupon.discount.get("type")
    discount_value = coupon.discount.get("reduction_amount") or coupon.discount.get("percentage")
    if isinstance(discount_value, dict):
        # 平台金额为对象，不能把 Python 字典转成面向客服的优惠文案。
        raw_amount = discount_value.get("amount")
        currency = discount_value.get("currency")
        if isinstance(raw_amount, (str, int)) and not isinstance(raw_amount, bool) and isinstance(currency, str):
            try:
                amount = Decimal(str(raw_amount))
            except InvalidOperation:
                discount_value = None
            else:
                if amount.is_finite() and amount >= 0 and currency.strip():
                    unit = currency.strip()
                    discount_value = f"{unit}{amount:.2f}" if len(unit) == 1 else f"{unit} {amount:.2f}"
                else:
                    discount_value = None
        else:
            discount_value = None
    elif isinstance(discount_value, (str, int, float)) and not isinstance(discount_value, bool):
        try:
            numeric_value = Decimal(str(discount_value))
        except InvalidOperation:
            discount_value = None
        else:
            discount_value = format(numeric_value, "f") if numeric_value.is_finite() and numeric_value >= 0 else None
    else:
        discount_value = None
    end_time = coupon.claim_duration.get("end_time")
    start_time = coupon.claim_duration.get("start_time")
    return SidebarCoupon(
        id=coupon.id,
        title=coupon.title,
        status=coupon.status,
        display_type=coupon.display_type,
        promo_code=coupon.promo_code,
        discount_type=str(discount_type) if discount_type is not None else None,
        discount_value=str(discount_value) if discount_value is not None else None,
        claim_end_time=end_time if isinstance(end_time, int) else None,
        claim_start_time=start_time if type(start_time) is int else None,
        redemption_duration=TikTokCouponDuration.model_validate(coupon.redemption_duration).model_dump(
            exclude_none=True
        ),
        target_buyer_segment=coupon.target_buyer_segment,
        product_scope=coupon.product_scope,
        threshold=coupon.threshold.model_dump(mode="json", exclude_none=True) if coupon.threshold else {},
        chat_shareable=(
            coupon.status == "ONGOING"
            and coupon.display_type in {"CHAT", "REGULAR"}
            and coupon.creation_source == "SELLER_CENTER"
        ),
    )


def _currently_available_coupon(coupon: TikTokCoupon, now: int) -> bool:
    if coupon.status != "ONGOING":
        return False
    start = coupon.claim_duration.get("start_time")
    end = coupon.claim_duration.get("end_time")
    return (type(start) is not int or start <= now) and (type(end) is not int or end > now)


async def search_sidebar_coupons(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID,
    payload: SidebarSearch,
) -> SidebarCoupons:
    conversation = await _conversation(session, user, session_id)
    if conversation.platform != "tiktok":
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "当前平台没有优惠券目录", 404)
    return await search_store_coupons(session, conversation.store_id, payload)


async def search_store_coupons(session: AsyncSession, store_id: uuid.UUID, payload: SidebarSearch) -> SidebarCoupons:
    """调用方先校验店铺和读取权限；不要求创建买家会话。"""
    if payload.field not in {"name", "code"}:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不支持的优惠券搜索字段", 422)
    client = await _tiktok_client(session, store_id)
    query = payload.query.strip()
    coupons, next_token, total = await client.search_coupons(
        page_token=payload.page_token,
        title=query if query and payload.field == "name" else None,
    )
    if query and payload.field == "code":
        coupons = [
            coupon for coupon in coupons if coupon.promo_code and query.casefold() in coupon.promo_code.casefold()
        ]
    now = int(time.time())
    return SidebarCoupons(
        items=[_coupon_view(item) for item in coupons if _currently_available_coupon(item, now)],
        next_page_token=next_token,
        total_count=total,
        partial_search=bool(query and payload.field == "code" and next_token),
    )
