import type { SidebarOrder } from "../lib/api";

const statuses: Record<string, { zh: string; en: string }> = {
  UNPAID: { zh: "未付款", en: "Unpaid" },
  AWAITING_SHIPMENT: { zh: "待发货", en: "Awaiting shipment" },
  AWAITING_COLLECTION: { zh: "待揽收", en: "Awaiting collection" },
  IN_TRANSIT: { zh: "运输中", en: "In transit" },
  SHIPPED: { zh: "已发货", en: "Shipped" },
  DELIVERED: { zh: "已送达", en: "Delivered" },
  COMPLETED: { zh: "已完成", en: "Completed" },
  CANCELLED: { zh: "已取消", en: "Cancelled" },
  CANCELED: { zh: "已取消", en: "Cancelled" },
};

export const orderStatusLabel = (status: string, en: boolean) => statuses[status]?.[en ? "en" : "zh"] ?? status;

export function OrderDraftPreview({ order, en }: { order: SidebarOrder; en: boolean }) {
  const item = order.items[0];
  const amount = order.total_amount === null ? "—" : `${order.currency} ${order.total_amount}`;
  return <article aria-label={en ? "Order summary draft preview" : "订单摘要草稿预览"} className="workspace-order-draft-preview">
    <strong>{en ? "Order summary" : "订单信息"}</strong>
    <div className="workspace-order-draft-product">{item?.image_url ? <img alt="" src={item.image_url} /> : null}<span>{item?.name ?? (en ? "Item unavailable" : "商品信息暂无")}</span></div>
    <dl><div><dt>{en ? "Order ID" : "订单编号"}</dt><dd>{order.external_order_id}</dd></div><div><dt>{en ? "Status" : "订单状态"}</dt><dd>{orderStatusLabel(order.status, en)}</dd></div><div><dt>{en ? "Amount" : "订单金额"}</dt><dd>{amount}</dd></div></dl>
    <small>{en ? "Visual preview only · the editable text below is what will be sent" : "仅供预览 · 实际发送以下方可编辑文本为准"}</small>
  </article>;
}
