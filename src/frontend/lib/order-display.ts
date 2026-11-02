import type { SidebarOrder, SidebarOrderDetail, SidebarTrackingPackage } from "./api";

const orderStatuses: Record<string, { zh: string; en: string }> = {
  UNPAID: { zh: "未付款", en: "Unpaid" },
  AWAITING_SHIPMENT: { zh: "待出货", en: "To ship" },
  AWAITING_COLLECTION: { zh: "待揽收", en: "Awaiting collection" },
  IN_TRANSIT: { zh: "运送中", en: "In transit" },
  SHIPPED: { zh: "已发货", en: "Shipped" },
  DELIVERED: { zh: "已完成", en: "Completed" },
  COMPLETED: { zh: "已完成", en: "Completed" },
  CANCELLED: { zh: "已取消", en: "Cancelled" },
  CANCELED: { zh: "已取消", en: "Cancelled" },
};

export function orderStatusLabel(status: string, en: boolean): string {
  return orderStatuses[status]?.[en ? "en" : "zh"] ?? status;
}

const logisticsStages = new Set([
  "AWAITING_COLLECTION", "PICKED_UP", "SHIPPED", "IN_TRANSIT", "OUT_FOR_DELIVERY",
  "DELIVERY_ATTEMPTED", "DELIVERED", "RETURNED", "EXCEPTION", "LOST", "CANCELLED",
]);
const descriptionStages: Array<[RegExp, string]> = [
  [/^(?:delivered\b|(?:package|parcel|shipment)(?: has been| was| is)? delivered\b|signed for\b|已签收|已送达)/i, "DELIVERED"],
  [/^(?:out for delivery\b|派送中|正在派送)/i, "OUT_FOR_DELIVERY"],
  [/^(?:delivery attempted\b|failed delivery\b|派送失败)/i, "DELIVERY_ATTEMPTED"],
  [/^(?:returned\b|return to sender\b|已退回)/i, "RETURNED"],
  [/^(?:exception\b|delivery exception\b|物流异常)/i, "EXCEPTION"],
  [/^(?:lost\b|包裹丢失)/i, "LOST"],
  [/^(?:in transit\b|arrived at\b|departed\b|运送中|运输中)/i, "IN_TRANSIT"],
  [/^(?:shipped\b|dispatched\b|package dispatched\b|已发货)/i, "SHIPPED"],
  [/^(?:picked up\b|collected\b|已揽收)/i, "PICKED_UP"],
  [/^(?:awaiting collection\b|label created\b|待揽收)/i, "AWAITING_COLLECTION"],
];

function logisticsStage(value: string | null | undefined): string | null {
  if (!value) return null;
  const normalized = value.trim().replace(/[\s-]+/g, "_").toUpperCase();
  if (logisticsStages.has(normalized)) return normalized;
  return descriptionStages.find(([pattern]) => pattern.test(value.trim()))?.[1] ?? null;
}

export function orderLogisticsStage(status: string, trackingStatus: string | null, latestDescription: string | null): string | null {
  // 独立物流状态与明确的订单物流阶段优先；订单完成不直接推断包裹已送达。
  return logisticsStage(trackingStatus)
    ?? (["IN_TRANSIT", "SHIPPED", "DELIVERED"].includes(status) ? status : null)
    ?? logisticsStage(latestDescription);
}

export function orderCarrierLabel(
  order: Pick<SidebarOrder, "tracking_number" | "items">,
  detail: Pick<SidebarOrderDetail, "shipping_provider" | "tracking_packages"> | null,
  en: boolean,
): string {
  if (!detail) return "—";
  const packages = detail.tracking_packages;
  const packageIds = new Set(order.items.map((item) => item.package_id).filter(Boolean));
  const byPackage = packages.filter((item) => item.package_id && packageIds.has(item.package_id));
  const byTracking = packages.filter((item) => item.tracking_number && item.tracking_number === order.tracking_number);
  const relevant = byPackage.length ? byPackage : byTracking.length ? byTracking : packages;
  const carriers = [...new Set(relevant.map((item) => actualCarrierName(item.carrier_name)).filter((value): value is string => !!value))];
  if (carriers.length === 1 && relevant.every((item) => !!actualCarrierName(item.carrier_name))) return carriers[0];
  if (carriers.length > 1) return en ? "Multiple carriers" : "多家物流商";
  return actualCarrierName(detail.shipping_provider) ?? "—";
}

export function actualCarrierName(value: string | null | undefined): string | null {
  // 平台揽收方式不是实际承运商；拿到包裹承运商前保持未知。
  const name = value?.trim();
  return name && name.toLowerCase() !== "collections by tiktok" ? name : null;
}

export function withTrackingPackages(detail: SidebarOrderDetail, packages: SidebarTrackingPackage[]): SidebarOrderDetail {
  const latest = packages.flatMap((item) => item.events).reduce<SidebarTrackingPackage["events"][number] | null>(
    (current, event) => !current || Date.parse(event.occurred_at) > Date.parse(current.occurred_at) ? event : current,
    null,
  );
  const newer = latest && (!detail.latest_tracking_at || Date.parse(latest.occurred_at) >= Date.parse(detail.latest_tracking_at));
  return {
    ...detail,
    tracking_packages: packages,
    tracking_loaded: true,
    latest_tracking_description: newer ? latest.description : detail.latest_tracking_description,
    latest_tracking_at: newer ? latest.occurred_at : detail.latest_tracking_at,
  };
}
