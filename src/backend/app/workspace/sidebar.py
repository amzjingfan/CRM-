"""客户侧栏只读投影。平台目录按当前会话的店铺授权读取。"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.auth.store_access import allowed_store_ids
from app.conversations.models import Conversation
from app.integrations.tiktok_read import TikTokCoupon, TikTokProduct, TikTokReadClient
from app.orders.models import Order, OrderItem
from app.shared.config.settings import get_settings
from app.shared.database.base import User
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


class SidebarOrderItem(BaseModel):
    name: str
    product_id: str | None
    sku: str | None
    sku_id: str | None
    sku_name: str | None
    image_url: str | None
    quantity: int
    unit_price: Decimal
    total_amount: Decimal


class SidebarOrder(BaseModel):
    id: uuid.UUID
    external_order_id: str
    status: str
    payment_status: str | None
    currency: str
    total_amount: Decimal
    payment_breakdown: dict[str, str]
    ordered_at: datetime | None
    tracking_number: str | None
    tracking_status: str | None
    items: list[SidebarOrderItem]


class SidebarOrders(BaseModel):
    items: list[SidebarOrder]
    pagination: PageMeta


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


class SidebarCoupons(BaseModel):
    items: list[SidebarCoupon]
    next_page_token: str | None
    total_count: int | None
    partial_search: bool = False


async def _conversation(session: AsyncSession, user: User, session_id: uuid.UUID) -> Conversation:
    conversation = await find_conversation(session, session_id, await allowed_store_ids(session, user))
    if conversation is None:
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "会话不存在", 404)
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


async def search_sidebar_orders(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID,
    payload: SidebarSearch,
) -> SidebarOrders:
    conversation = await _conversation(session, user, session_id)
    if payload.field not in {"order", "tracking", "product", "spu", "sku", "sellerSku"}:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不支持的订单搜索字段", 422)
    filters = [
        Order.store_id == conversation.store_id,
        Order.customer_id == conversation.customer_id,
        Order.platform == conversation.platform,
    ]
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
                tracking_number=order.tracking_number,
                tracking_status=order.tracking_status,
                items=items_by_order[order.id],
            )
            for order in orders
        ],
        pagination=PageMeta(page=payload.page, page_size=page_size, total=total),
    )


def _product_view(product: TikTokProduct) -> SidebarProduct:
    image_url = None
    if product.main_images:
        urls = product.main_images[0].get("urls")
        if isinstance(urls, list) and urls and isinstance(urls[0], str) and urls[0].startswith("https://"):
            image_url = urls[0]
    skus = []
    for sku in product.skus:
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
    return SidebarProduct(id=product.id, title=product.title, status=product.status, image_url=image_url, skus=skus)


async def search_sidebar_products(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID,
    payload: SidebarSearch,
) -> SidebarProducts:
    conversation = await _conversation(session, user, session_id)
    if conversation.platform != "tiktok":
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "当前平台没有商品目录", 404)
    if payload.field not in {"name", "productId", "sku", "sellerSku"}:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不支持的商品搜索字段", 422)
    client = await _tiktok_client(session, conversation.store_id)
    query = payload.query.strip()
    if payload.field == "productId" and query:
        product = await client.get_product(query)
        return SidebarProducts(items=[_product_view(product)], next_page_token=None, total_count=1)
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
        items=[_product_view(item) for item in products],
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
    client = await _tiktok_client(session, conversation.store_id)
    return _product_view(await client.get_product(product_id))


def _coupon_view(coupon: TikTokCoupon) -> SidebarCoupon:
    discount_type = coupon.discount.get("type")
    discount_value = coupon.discount.get("reduction_amount") or coupon.discount.get("percentage")
    end_time = coupon.claim_duration.get("end_time")
    return SidebarCoupon(
        id=coupon.id,
        title=coupon.title,
        status=coupon.status,
        display_type=coupon.display_type,
        promo_code=coupon.promo_code,
        discount_type=str(discount_type) if discount_type is not None else None,
        discount_value=str(discount_value) if discount_value is not None else None,
        claim_end_time=end_time if isinstance(end_time, int) else None,
        chat_shareable=(
            coupon.status == "ONGOING"
            and coupon.display_type in {"CHAT", "REGULAR"}
            and coupon.creation_source == "SELLER_CENTER"
        ),
    )


async def search_sidebar_coupons(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID,
    payload: SidebarSearch,
) -> SidebarCoupons:
    conversation = await _conversation(session, user, session_id)
    if conversation.platform != "tiktok":
        raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "当前平台没有优惠券目录", 404)
    if payload.field not in {"name", "code"}:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不支持的优惠券搜索字段", 422)
    client = await _tiktok_client(session, conversation.store_id)
    query = payload.query.strip()
    coupons, next_token, total = await client.search_coupons(
        page_token=payload.page_token,
        title=query if query and payload.field == "name" else None,
    )
    if query and payload.field == "code":
        coupons = [
            coupon for coupon in coupons if coupon.promo_code and query.casefold() in coupon.promo_code.casefold()
        ]
    return SidebarCoupons(
        items=[_coupon_view(item) for item in coupons],
        next_page_token=next_token,
        total_count=total,
        partial_search=bool(query and payload.field == "code" and next_token),
    )
