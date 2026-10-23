import type { BuyerStage, OrderSummary } from "./api";

export function stageFromOrders(orders: OrderSummary[]): BuyerStage | "unknown" {
  if (!orders.length) return "pre";
  // recent_orders 已由服务端按创建时间降序排序，以最近一笔订单判断当前阶段。
  const status = orders[0].status.trim().toUpperCase();
  if (["UNPAID", "AWAITING_PAYMENT", "AWAITING_SHIPMENT", "AWAITING_COLLECTION", "SHIPPED", "IN_TRANSIT", "OUT_FOR_DELIVERY", "PARTIALLY_SHIPPING"].includes(status)) return "during";
  if (["DELIVERED", "COMPLETED", "CANCELLED", "CANCELED", "RETURNED", "REFUNDED", "PARTIALLY_REFUNDED"].includes(status)) return "after";
  return "unknown";
}

export function stageLabel(stage: BuyerStage | "unknown", en: boolean): string {
  const labels = {
    pre: en ? "Pre-sale buyer" : "售前买家",
    during: en ? "In-sale buyer" : "售中买家",
    after: en ? "After-sale buyer" : "售后买家",
    unknown: en ? "Stage unknown" : "阶段待判断",
  };
  return labels[stage];
}
