import type { SidebarOrder } from "../lib/api";
import { orderStatusLabel } from "../lib/order-display";

export function OrderDraftPreview({ order, en }: { order: SidebarOrder; en: boolean }) {
  const item = order.items[0];
  const amount = order.total_amount === null ? "—" : `${order.currency} ${order.total_amount}`;
  return <article aria-label={en ? "Order card preview" : "订单卡片预览"} className="workspace-order-draft-preview">
    <strong>{en ? "Order summary" : "订单信息"}</strong>
    <div className="workspace-order-draft-product">{item?.image_url ? <img alt="" src={item.image_url} /> : null}<span>{item?.name ?? (en ? "Item unavailable" : "商品信息暂无")}</span></div>
    <dl><div><dt>{en ? "Order ID" : "订单编号"}</dt><dd>{order.external_order_id}</dd></div><div><dt>{en ? "Status" : "订单状态"}</dt><dd>{orderStatusLabel(order.status, en)}</dd></div><div><dt>{en ? "Amount" : "订单金额"}</dt><dd>{amount}</dd></div></dl>
    <small>{en ? "TikTok will generate the final card from this order ID" : "TikTok 将按此订单号生成最终卡片"}</small>
  </article>;
}
