"""物流卡片的只读展示投影；不包含消息发送或授权状态变更。"""

from collections.abc import Sequence

from pydantic import BaseModel

from app.integrations.tiktok_read import TikTokOrder, TikTokStandardTrackingEntry
from app.workspace.schemas import LogisticsCardView
from app.workspace.sidebar import SidebarTrackingEvent, SidebarTrackingPackage, _tracking_time


class LogisticsCardPreview(BaseModel):
    card: LogisticsCardView
    packages: list[SidebarTrackingPackage]
    enhanced_available: bool
    selected: int


def standard_tracking_package(
    package_id: str | None, events: Sequence[TikTokStandardTrackingEntry]
) -> SidebarTrackingPackage:
    return SidebarTrackingPackage(
        package_id=package_id,
        tracking_number=None,
        carrier_name=None,
        events=[
            SidebarTrackingEvent(
                description=event.description,
                occurred_at=_tracking_time(event.update_time_millis),
                action_code=event.action_code,
            )
            for event in sorted(events, key=lambda item: item.update_time_millis, reverse=True)
        ],
    )


def logistics_card_snapshot(
    order: TikTokOrder, package: SidebarTrackingPackage, *, packages: Sequence[SidebarTrackingPackage]
) -> LogisticsCardView:
    unique_tracking = sum(item.tracking_number == package.tracking_number for item in packages) == 1
    package_items = [
        item
        for item in order.line_items
        if not package.package_id
        or item.package_id == package.package_id
        or (
            unique_tracking
            and not item.package_id
            and package.tracking_number
            and item.tracking_number == package.tracking_number
        )
    ]
    first_item = package_items[0] if package_items else None
    latest = max(package.events, key=lambda event: event.occurred_at) if package.events else None
    return LogisticsCardView(
        order_id=order.id,
        package_id=package.package_id,
        product_name=first_item.product_name if first_item else None,
        image_url=first_item.sku_image
        if first_item and first_item.sku_image and first_item.sku_image.startswith("https://")
        else None,
        sku_name=first_item.sku_name if first_item else None,
        quantity=sum(1 for item in package_items if item.sku_id == first_item.sku_id) if first_item else None,
        unit_price=first_item.sale_price if first_item else None,
        currency=first_item.currency if first_item else None,
        tracking_number=package.tracking_number
        or (first_item.tracking_number or order.tracking_number if first_item else order.tracking_number),
        carrier_name=package.carrier_name or order.shipping_provider,
        latest_description=latest.description if latest else None,
        latest_at=latest.occurred_at if latest else None,
    )
