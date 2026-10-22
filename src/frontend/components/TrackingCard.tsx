"use client";

import { useState } from "react";
import { Copy, Package } from "@phosphor-icons/react";
import { TrackingTimelinePopover } from "./TrackingTimelinePopover";
import type { LogisticsCardView, SidebarTrackingPackage } from "../lib/api";

const EMPTY_PACKAGES: SidebarTrackingPackage[] = [];

export function TrackingCard({ card, sessionId, packages = EMPTY_PACKAGES, enhancedAvailable = false, selected = 0, translationEnabled = false, en }: {
  card: LogisticsCardView;
  sessionId: string;
  packages?: SidebarTrackingPackage[];
  enhancedAvailable?: boolean;
  selected?: number;
  translationEnabled?: boolean;
  en: boolean;
}) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const price = card.unit_price && card.currency ? `${card.currency} ${card.unit_price}` : null;
  return <div aria-label={en ? "Logistics card" : "物流卡片"} className="tracking-message-card">
    <strong className="tracking-message-title">{en ? "Tracking information" : "物流信息"}</strong>
    {card.product_name ? <div className="tracking-message-product">
      {card.image_url ? <img alt="" src={card.image_url} /> : <span aria-hidden="true" className="tracking-message-image"><Package size={18} /></span>}
      <div><strong title={card.product_name}>{card.product_name}</strong>{card.sku_name ? <small>{en ? "Variant" : "商品规格"}：{card.sku_name}</small> : null}<small>{card.quantity ? `${card.quantity} ${en ? "item(s)" : "件"}` : ""}{price ? ` · ${price}` : ""}</small></div>
    </div> : null}
    <div className="tracking-message-logistics"><span>{card.carrier_name ?? (en ? "Carrier unavailable" : "物流商暂无")}</span>{card.tracking_number ? <small>{en ? "Tracking number" : "物流单号"}：{card.tracking_number} <button aria-label={en ? "Copy tracking number" : "复制物流单号"} className="tracking-card-copy" onClick={() => void navigator.clipboard.writeText(card.tracking_number ?? "").then(() => setCopyState("copied")).catch(() => setCopyState("failed"))} title={en ? "Copy tracking number" : "复制物流单号"} type="button"><Copy size={12} /></button>{copyState !== "idle" ? <span role="status">{copyState === "copied" ? (en ? "Copied" : "已复制") : (en ? "Copy failed" : "复制失败")}</span> : null}</small> : null}</div>
    {card.latest_description ? <div className="tracking-message-latest"><span>{en ? "Latest update" : "最新物流信息"}</span><p>{card.latest_description}</p>{card.latest_at ? <time>{new Date(card.latest_at).toLocaleString(en ? "en-US" : "zh-CN", { hour12: false })}</time> : null}</div> : null}
    <div className="tracking-message-foot"><TrackingTimelinePopover en={en} enhancedAvailable={enhancedAvailable} initialPackages={packages} initialSelected={selected} orderId={card.order_id} selectedPackageId={card.package_id} sessionId={sessionId} translationEnabled={translationEnabled} triggerLabel={en ? "View details" : "查看详情"} /></div>
  </div>;
}
