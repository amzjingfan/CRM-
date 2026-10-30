import { Package, ShoppingBag, Ticket, Truck } from "@phosphor-icons/react";
import type { RichMessageCardView } from "../lib/api";

export function TikTokMessageCard({ card, en }: { card: RichMessageCardView; en: boolean }) {
  const product = card.kind.includes("product");
  const logistics = card.kind === "logistics_card";
  const coupon = card.kind === "coupon_card";
  const heading = product ? (en ? "Product" : "商品") : logistics ? (en ? "Tracking" : "物流") : coupon ? (en ? "Coupon" : "优惠券") : card.kind === "return_refund_card" ? (en ? "Return / refund" : "退货退款") : (en ? "Order" : "订单");
  const identifier = card.product_id ?? card.order_id ?? card.coupon_id;
  return <div aria-label={en ? `${heading} card` : `${heading}卡片`} className="tiktok-message-card">
    <div className="tiktok-message-card-heading">{product ? <ShoppingBag size={16} /> : logistics ? <Truck size={16} /> : coupon ? <Ticket size={16} /> : <Package size={16} />}<strong>{heading}</strong></div>
    <div className="tiktok-message-card-body">
      {card.image_url ? <img alt="" className="tiktok-message-card-image" loading="lazy" referrerPolicy="no-referrer" src={card.image_url} /> : null}
      <div className="tiktok-message-card-details">
        <strong>{card.title ?? (identifier ? `${heading} ${identifier}` : heading)}</strong>
        {card.price || card.paid_price ? <span>{card.price ?? card.paid_price}</span> : null}
        {card.status ? <span>{card.status}</span> : null}
        {card.tracking_number ? <span>{en ? "Tracking" : "物流单号"}：{card.tracking_number}</span> : null}
        {card.carrier_name ? <span>{card.carrier_name}</span> : null}
        {card.latest_description ? <span>{card.latest_description}</span> : null}
        {card.quantity ? <span>{en ? "Quantity" : "数量"}：{card.quantity}</span> : null}
        {card.sold_quantity ? <span>{en ? "Sold" : "已售"}：{card.sold_quantity}</span> : null}
      </div>
    </div>
    {card.packages?.map((item, index) => <div className="tiktok-message-card-package" key={`${item.package_id ?? "package"}-${index}`}>
      {item.image_url ? <img alt="" className="tiktok-message-card-image" loading="lazy" referrerPolicy="no-referrer" src={item.image_url} /> : null}
      <div className="tiktok-message-card-details">
        <strong>{item.title ?? (en ? `Package ${index + 1}` : `包裹 ${index + 1}`)}</strong>
        {item.paid_price ? <span>{item.paid_price}</span> : null}
        {item.tracking_number ? <span>{en ? "Tracking" : "物流单号"}：{item.tracking_number}</span> : null}
        {item.carrier_name ? <span>{item.carrier_name}</span> : null}
        {item.latest_description ? <span>{item.latest_description}</span> : null}
      </div>
    </div>)}
    {card.url ? <a href={card.url} rel="noopener noreferrer" referrerPolicy="no-referrer" target="_blank">{en ? "View on TikTok Shop" : "在 TikTok Shop 查看"}</a> : null}
  </div>;
}
