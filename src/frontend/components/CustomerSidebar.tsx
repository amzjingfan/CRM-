"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Copy, MagnifyingGlass, X } from "@phosphor-icons/react";
import { TrackingTimelinePopover } from "./TrackingTimelinePopover";
import type { LogisticsCardDraft } from "../lib/api";
import { buyerAvatarText } from "../lib/message-display";
import {
  getCustomerSidebarOrderDetail,
  getCustomerSidebarStandardTracking,
  getCustomerSidebarProduct,
  searchCustomerSidebar,
  translateSidebarTracking,
  type SessionMessagesData,
  type SidebarCoupon,
  type SidebarCoupons,
  type SidebarOrder,
  type SidebarOrderDetail,
  type SidebarOrders,
  type SidebarProduct,
  type SidebarProducts,
} from "../lib/api";

type Section = "orders" | "products" | "coupons";
type OrderStatus = "all" | "unpaid" | "ship" | "transit" | "done" | "cancel";
const fields: Record<Section, Array<{ value: string; zh: string; en: string }>> = {
  orders: [
    { value: "order", zh: "订单编号", en: "Order ID" },
    { value: "tracking", zh: "物流单号", en: "Tracking ID" },
    { value: "product", zh: "商品名称", en: "Product name" },
    { value: "spu", zh: "SPU ID", en: "Product ID" },
    { value: "sku", zh: "SKU", en: "SKU" },
    { value: "sellerSku", zh: "卖家 SKU", en: "Seller SKU" },
  ],
  products: [
    { value: "name", zh: "商品名称", en: "Product name" },
    { value: "productId", zh: "商品 ID", en: "Product ID" },
    { value: "sku", zh: "SKU", en: "SKU ID" },
    { value: "sellerSku", zh: "SKU 货号", en: "Seller SKU" },
  ],
  coupons: [
    { value: "name", zh: "优惠券名称", en: "Coupon name" },
    { value: "code", zh: "优惠券编码", en: "Coupon code" },
  ],
};
const statuses: Array<{ value: OrderStatus; zh: string; en: string }> = [
  { value: "all", zh: "全部", en: "All" },
  { value: "unpaid", zh: "未付款", en: "Unpaid" },
  { value: "ship", zh: "待出货", en: "To ship" },
  { value: "transit", zh: "运送中", en: "In transit" },
  { value: "done", zh: "已完成", en: "Completed" },
  { value: "cancel", zh: "已取消", en: "Cancelled" },
];
const statusText: Record<string, { zh: string; en: string }> = {
  UNPAID: { zh: "未付款", en: "Unpaid" },
  AWAITING_SHIPMENT: { zh: "待出货", en: "To ship" },
  AWAITING_COLLECTION: { zh: "待揽收", en: "Awaiting collection" },
  IN_TRANSIT: { zh: "运送中", en: "In transit" },
  SHIPPED: { zh: "已发货", en: "Shipped" },
  DELIVERED: { zh: "已送达", en: "Delivered" },
  COMPLETED: { zh: "已完成", en: "Completed" },
  CANCELLED: { zh: "已取消", en: "Cancelled" },
  CANCELED: { zh: "已取消", en: "Cancelled" },
};
const logisticsStatusText: Record<string, { zh: string; en: string }> = {
  AWAITING_COLLECTION: { zh: "待揽收", en: "Awaiting collection" },
  PICKED_UP: { zh: "已揽收", en: "Picked up" },
  SHIPPED: { zh: "已发货", en: "Shipped" },
  IN_TRANSIT: { zh: "运送中", en: "In transit" },
  OUT_FOR_DELIVERY: { zh: "派送中", en: "Out for delivery" },
  DELIVERY_ATTEMPTED: { zh: "派送未成功", en: "Delivery attempted" },
  DELIVERED: { zh: "已送达", en: "Delivered" },
  RETURNED: { zh: "已退回", en: "Returned" },
  EXCEPTION: { zh: "物流异常", en: "Shipping exception" },
  LOST: { zh: "包裹丢失", en: "Lost" },
  CANCELLED: { zh: "已取消", en: "Cancelled" },
};
const logisticsDescriptionStages: Array<[RegExp, string]> = [
  [/^(?:delivered\b|signed for\b|已签收|已送达)/i, "DELIVERED"],
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
  if (logisticsStatusText[normalized]) return normalized;
  return logisticsDescriptionStages.find(([pattern]) => pattern.test(value.trim()))?.[1] ?? null;
}
const productStatusText: Record<string, { zh: string; en: string }> = {
  ACTIVATE: { zh: "上架中", en: "Active" },
  INACTIVE: { zh: "未上架", en: "Inactive" },
  SELLER_DEACTIVATED: { zh: "已下架", en: "Deactivated" },
  DELETED: { zh: "已删除", en: "Deleted" },
};
const couponStatusText: Record<string, { zh: string; en: string }> = {
  NOT_START: { zh: "未开始", en: "Not started" },
  ONGOING: { zh: "进行中", en: "Ongoing" },
  EXPIRED: { zh: "已过期", en: "Expired" },
  DEACTIVATED: { zh: "已停用", en: "Deactivated" },
};
const couponDisplayText: Record<string, { zh: string; en: string }> = {
  REGULAR: { zh: "常规展示", en: "Regular" },
  PROMO_CODE: { zh: "优惠码", en: "Promo code" },
  CHAT: { zh: "聊天", en: "Chat" },
};
const paymentStatusText: Record<string, { zh: string; en: string }> = {
  PAID: { zh: "已付款", en: "Paid" },
  UNPAID: { zh: "未付款", en: "Unpaid" },
  REFUNDED: { zh: "已退款", en: "Refunded" },
};
function couponDiscount(coupon: SidebarCoupon, en: boolean) {
  const value = coupon.discount_value;
  if (!value || value.startsWith("{")) return "—";
  if (coupon.discount_type === "AMOUNT_OFF" || coupon.discount_type === "FIXED_AMOUNT") return `${en ? "Amount off" : "立减"} ${value}`;
  if (coupon.discount_type === "PERCENTAGE_OFF") return `${en ? "Percentage off" : "折扣"} ${value}${value.endsWith("%") ? "" : "%"}`;
  return value;
}

function money(currency: string, value: string | null) {
  if (value === null) return "—";
  const amount = Number(value);
  return Number.isFinite(amount) ? `${currency ? `${currency} ` : ""}${amount.toFixed(2)}` : `${currency ? `${currency} ` : ""}${value}`;
}
function dateTime(value: string | null, en: boolean) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString(en ? "en-US" : "zh-CN", { hour12: false });
}

function createOrderDetailLimiter(maxConcurrent: number) {
  let active = 0;
  const waiting: Array<() => void> = [];
  const startNext = () => { while (active < maxConcurrent && waiting.length) waiting.shift()?.(); };
  return (signal: AbortSignal, request: () => Promise<SidebarOrderDetail>): Promise<SidebarOrderDetail> => new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException("Aborted", "AbortError")); return; }
    const run = () => {
      signal.removeEventListener("abort", cancel);
      if (signal.aborted) { reject(new DOMException("Aborted", "AbortError")); return; }
      active += 1;
      Promise.resolve().then(request).then(resolve, reject).finally(() => { active -= 1; startNext(); });
    };
    const cancel = () => {
      const index = waiting.indexOf(run);
      if (index >= 0) { waiting.splice(index, 1); reject(new DOMException("Aborted", "AbortError")); }
    };
    signal.addEventListener("abort", cancel, { once: true });
    waiting.push(run);
    startNext();
  });
}

function CopyableValue({ value, label, en }: { value: string | null | undefined; label: string; en: boolean }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  if (!value) return <span>—</span>;
  return <span className="customer-copy-value" title={value}><span>{value}</span><button aria-label={en ? `Copy ${label}` : `复制${label}`} className="customer-copy-button" onClick={() => { setCopyError(false); setCopied(false); void navigator.clipboard.writeText(value).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1500); }).catch(() => setCopyError(true)); }} title={copyError ? (en ? "Copy failed, retry" : "复制失败，请重试") : copied ? (en ? "Copied" : "已复制") : (en ? "Copy value" : "复制值")} type="button"><Copy size={12} /></button>{copied || copyError ? <span className="customer-copy-feedback" role="status">{copyError ? (en ? "Copy failed" : "复制失败") : (en ? "Copied" : "已复制")}</span> : null}</span>;
}

function OrderCard({ order, sessionId, en, trackingTranslationEnabled, fillOrderDraft, onCardDraft, onDetails, scheduleDetail }: { order: SidebarOrder; sessionId: string; en: boolean; trackingTranslationEnabled: boolean; fillOrderDraft: (order: SidebarOrder) => void; onCardDraft: (value: LogisticsCardDraft) => void; onDetails: (order: SidebarOrder, detail: SidebarOrderDetail | null) => void; scheduleDetail: ReturnType<typeof createOrderDetailLimiter> }) {
  const [detail, setDetail] = useState<SidebarOrderDetail | null>(null);
  const [detailError, setDetailError] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const [trackingLoading, setTrackingLoading] = useState(false);
  const [trackingError, setTrackingError] = useState("");
  const [trackingTranslation, setTrackingTranslation] = useState("");
  const [showTrackingTranslation, setShowTrackingTranslation] = useState(false);
  const [trackingTranslationError, setTrackingTranslationError] = useState("");
  const [trackingTranslationLoading, setTrackingTranslationLoading] = useState(false);
  const cardRef = useRef<HTMLElement>(null);
  const detailRequestInFlight = useRef(false);
  const trackingRequestInFlight = useRef(false);
  const detailController = useRef<AbortController | null>(null);
  const trackingRequestId = useRef(0);
  useEffect(() => () => detailController.current?.abort(), []);
  const loadTracking = useCallback((controller: AbortController) => {
    if (trackingRequestInFlight.current) return;
    trackingRequestInFlight.current = true;
    setTrackingLoading(true);
    setTrackingError("");
    getCustomerSidebarStandardTracking(sessionId, order.external_order_id, controller.signal)
      .then((tracking) => { if (!controller.signal.aborted) setDetail((current) => current ? { ...current, latest_tracking_description: tracking.latest_tracking_description, latest_tracking_at: tracking.latest_tracking_at, tracking_packages: tracking.packages, tracking_loaded: true } : current); })
      .catch((cause) => { if (!controller.signal.aborted) setTrackingError(cause instanceof Error ? cause.message : "物流加载失败"); })
      .finally(() => { trackingRequestInFlight.current = false; if (!controller.signal.aborted) setTrackingLoading(false); });
  }, [sessionId, order.external_order_id]);
  const loadDetail = useCallback(() => {
    if (detailRequestInFlight.current) return;
    const controller = new AbortController();
    detailController.current = controller;
    detailRequestInFlight.current = true;
    setDetailLoading(true);
    setDetail(null);
    setDetailError("");
    setTrackingError("");
    trackingRequestId.current += 1;
    setTrackingTranslation("");
    setShowTrackingTranslation(false);
    setTrackingTranslationError("");
    scheduleDetail(controller.signal, () => getCustomerSidebarOrderDetail(sessionId, order.external_order_id, controller.signal, false))
      .then((value) => {
        if (controller.signal.aborted) return;
        setDetail(value);
        if (["IN_TRANSIT", "SHIPPED", "DELIVERED", "COMPLETED"].includes(order.status) || order.tracking_number || order.items.some((item) => item.tracking_number)) loadTracking(controller);
        else setDetail({ ...value, tracking_loaded: true });
      })
      .catch((cause) => { if (!controller.signal.aborted) setDetailError(cause instanceof Error ? cause.message : "订单详情加载失败"); })
      .finally(() => { if (!controller.signal.aborted) { detailRequestInFlight.current = false; setDetailLoading(false); } });
  }, [sessionId, order.external_order_id, order.status, order.tracking_number, order.items, loadTracking, scheduleDetail]);
  async function requestTrackingTranslation() {
    const source = detail?.latest_tracking_description;
    if (!source || trackingTranslationLoading) return;
    const requestId = ++trackingRequestId.current;
    setTrackingTranslationLoading(true);
    setTrackingTranslationError("");
    try {
      const result = await translateSidebarTracking(sessionId, order.external_order_id);
      if (requestId !== trackingRequestId.current) return;
      if (result.source_description !== source || !result.translated_text.trim()) throw new Error("物流描述已更新，请刷新详情后重试");
      setTrackingTranslation(result.translated_text);
      setShowTrackingTranslation(true);
    } catch (error) {
      if (requestId === trackingRequestId.current) setTrackingTranslationError(error instanceof Error ? error.message : "翻译失败，请重试");
    } finally {
      if (requestId === trackingRequestId.current) setTrackingTranslationLoading(false);
    }
  }
  useEffect(() => {
    if (!order.live_detail_available || !cardRef.current) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { observer.disconnect(); loadDetail(); }
    }, { rootMargin: "100px 0px" });
    observer.observe(cardRef.current);
    return () => observer.disconnect();
  }, [loadDetail, order.live_detail_available]);
  const first = order.items[0];
  const label = statusText[order.status]?.[en ? "en" : "zh"] ?? order.status;
  const isCancelled = ["CANCELLED", "CANCELED"].includes(order.status);
  const totalLabel = order.paid_at || order.payment_status?.toUpperCase() === "PAID" ? (en ? "Buyer paid amount" : "买家实付金额") : (en ? "Order amount" : "订单金额");
  const orderStage = ["IN_TRANSIT", "SHIPPED", "DELIVERED"].includes(order.status) ? order.status : null;
  const stage = logisticsStage(order.tracking_status) ?? orderStage ?? logisticsStage(detail?.latest_tracking_description);
  const logisticsStatus = stage ? logisticsStatusText[stage][en ? "en" : "zh"] : en ? "Status pending" : "状态待更新";
  const breakdown: Array<{ key: string; zh: string; en: string }> = [
    { key: "original_total_product_price", zh: "商品总价", en: "Original product total" },
    { key: "sub_total", zh: "商品小计", en: "Product subtotal" },
    { key: "seller_discount", zh: "店铺折扣", en: "Seller discount" },
    { key: "platform_discount", zh: "平台折扣", en: "Platform discount" },
    { key: "shipping_fee", zh: "实付运费", en: "Shipping" },
    { key: "tax", zh: "税费", en: "Tax" },
  ];
  return <article className="customer-side-card" data-testid="customer-order-card" ref={cardRef}>
    <div className="customer-card-top"><strong>{label}</strong><time>{dateTime(order.ordered_at, en)}</time></div>
    <p className="customer-order-id"><CopyableValue en={en} label={en ? "order ID" : "订单编号"} value={order.external_order_id} /></p>
    {first ? <div className="customer-item-row">{first.image_url ? <img alt="" className="customer-product-image" src={first.image_url} /> : <div className="customer-item-thumb" aria-hidden="true">{first.name.slice(0, 1)}</div>}<div className="customer-item-copy"><strong><CopyableValue en={en} label={en ? "product name" : "商品名称"} value={first.name} /></strong><small>{en ? "SPU: " : "SPU："}<CopyableValue en={en} label="SPU" value={first.product_id} /></small><small className="customer-item-variant"><span>{en ? "Variant: " : "商品规格："}</span><CopyableValue en={en} label={en ? "variant" : "商品规格"} value={first.sku_name} /></small><small>SKU: <CopyableValue en={en} label="SKU" value={first.sku_id} /></small>{first.sku ? <small className="customer-item-seller-sku"><span>{en ? "Seller SKU: " : "SKU 货号："}</span><CopyableValue en={en} label={en ? "seller SKU" : "SKU 货号"} value={first.sku} /></small> : null}</div><div className="customer-item-price">{money(order.currency, first.total_amount)}<small>×{first.quantity}</small></div></div> : <p className="customer-side-muted">{en ? "Item details unavailable" : "暂无商品明细"}</p>}
    {order.items.length > 1 ? <p className="customer-side-muted">{en ? `${order.items.length} line items` : `共 ${order.items.length} 项商品`}</p> : null}
    <details className="customer-money"><summary><span>{totalLabel}</span><strong>{money(order.currency, order.total_amount)}</strong></summary><div className="customer-money-grid">{breakdown.filter((row) => order.payment_breakdown?.[row.key] !== undefined).map((row) => <div key={row.key}><span>{row[en ? "en" : "zh"]}</span><span>{money(order.currency, order.payment_breakdown[row.key])}</span></div>)}<div className="customer-money-total"><span>{totalLabel}</span><span>{money(order.currency, order.total_amount)}</span></div>{!Object.keys(order.payment_breakdown ?? {}).length ? <small>{en ? "Discount, tax and shipping breakdown is unavailable from the synced order." : "当前同步订单未提供折扣、税费及运费拆分。"}</small> : null}</div></details>
    <div className="customer-info-line"><span>{en ? "Payment" : "支付状态"}</span><span>{paymentStatusText[(order.payment_status ?? order.status).toUpperCase()]?.[en ? "en" : "zh"] ?? "—"}</span></div>
    {order.status === "UNPAID" ? <div className="customer-info-line"><span>{en ? "Payment deadline" : "付款截止"}</span><span>—</span></div> : null}
    <div className="customer-info-line"><span>{en ? "Paid at" : "付款时间"}</span><span>{dateTime(order.paid_at, en)}</span></div>
    <div className="customer-info-line"><span>{en ? "Payment method" : "支付方式"}</span><span>{detail?.payment_method_name ?? "—"}</span></div>
    <div className="customer-info-line"><span>{en ? "Fulfillment" : "出货状态"}</span><span>{label}</span></div>
    <div className="customer-info-line"><span>{en ? "Ship by" : "最晚发货"}</span><span>—</span></div>
    <div className="customer-info-line"><span>{en ? "Logistics status" : "物流状态"}</span><div className="customer-logistics-status"><span>{logisticsStatus}</span>{detail?.tracking_loaded ? <TrackingTimelinePopover en={en} enhancedAvailable={detail.enhanced_tracking_available} initialPackages={detail.tracking_packages ?? []} onCardDraft={onCardDraft} order={order} orderId={order.external_order_id} sessionId={sessionId} translationEnabled={trackingTranslationEnabled} /> : null}</div></div>
    <div className="customer-info-line"><span>{en ? "Tracking number" : "物流单号"}</span><span title={order.tracking_number ?? ""}>{order.tracking_number ?? "—"}</span></div>
    <div className="customer-info-line"><span>{en ? "Carrier" : "物流商"}</span><span>{detail?.shipping_provider ?? "—"}</span></div>
    <div className="customer-info-line"><span>{en ? "Latest tracking description" : "最新物流描述"}</span><div className="customer-tracking-detail"><span className={showTrackingTranslation ? "customer-tracking-translation" : undefined}>{showTrackingTranslation ? trackingTranslation : detail?.latest_tracking_description ?? "—"}</span>{!en && trackingTranslationEnabled && detail?.latest_tracking_description && /[A-Za-z]/.test(detail.latest_tracking_description) ? <button disabled={trackingTranslationLoading} onClick={() => { if (trackingTranslation) setShowTrackingTranslation((shown) => !shown); else void requestTrackingTranslation(); }} type="button">{trackingTranslationLoading ? "翻译中…" : trackingTranslation ? showTrackingTranslation ? "查看原文" : "查看译文" : trackingTranslationError ? "重试翻译" : "译成中文"}</button> : null}{trackingTranslationError ? <span className="customer-tracking-error" role="alert">{trackingTranslationError}</span> : null}</div></div>
    <div className="customer-info-line"><span>{en ? "Latest tracking time" : "最新物流时间"}</span><span>{dateTime(detail?.latest_tracking_at ?? null, en)}</span></div>
    {isCancelled ? <><div className="customer-info-line"><span>{en ? "Cancellation reason" : "取消原因"}</span><span>—</span></div><div className="customer-info-line"><span>{en ? "Refund status" : "退款状态"}</span><span>—</span></div></> : null}
    {detailLoading && !detail ? <p className="customer-side-muted" role="status">{en ? "Loading order details…" : "正在读取订单详情…"}</p> : null}
    {trackingLoading ? <p className="customer-side-muted" role="status">{en ? "Loading tracking…" : "正在读取物流…"}</p> : null}
    {trackingError ? <p className="customer-side-muted" role="alert">{trackingError} <button onClick={() => { if (detailController.current) loadTracking(detailController.current); }} type="button">{en ? "Retry tracking" : "重试物流"}</button></p> : null}
    {detailError ? <p className="customer-side-muted" role="alert">{detailError}</p> : null}
    <div className="customer-card-actions"><button onClick={() => onDetails(order, detail)} type="button">{en ? "Details" : "详情"}</button>{detailError ? <button disabled={detailLoading} onClick={loadDetail} type="button">{en ? "Retry details" : "重试详情"}</button> : null}<button onClick={() => fillOrderDraft(order)} type="button">{en ? "Use in draft" : "填入回复草稿"}</button><span className="customer-unavailable-action">{en ? "Refund unavailable" : "退款暂未开放"}</span></div>
  </article>;
}

function OrderDetailsView({ order, detail: initialDetail, buyerName, storeName, en, onBack, sessionId }: { order: SidebarOrder; detail: SidebarOrderDetail | null; buyerName: string | null; storeName: string | null; en: boolean; onBack: () => void; sessionId: string }) {
  const [detail, setDetail] = useState(initialDetail);
  const [detailError, setDetailError] = useState("");
  const [detailLoading, setDetailLoading] = useState(!initialDetail && order.live_detail_available);
  const [detailRetry, setDetailRetry] = useState(0);
  const [trackingLoading, setTrackingLoading] = useState(false);
  const [trackingError, setTrackingError] = useState("");
  const [trackingRetry, setTrackingRetry] = useState(0);
  useEffect(() => {
    if (initialDetail || !order.live_detail_available) return;
    const controller = new AbortController();
    setDetailLoading(true);
    setDetailError("");
    getCustomerSidebarOrderDetail(sessionId, order.external_order_id, controller.signal, false)
      .then((value) => { if (!controller.signal.aborted) setDetail(value); })
      .catch((cause) => { if (!controller.signal.aborted) setDetailError(cause instanceof Error ? cause.message : "订单详情加载失败"); })
      .finally(() => { if (!controller.signal.aborted) setDetailLoading(false); });
    return () => controller.abort();
  }, [initialDetail, order.external_order_id, order.live_detail_available, sessionId, detailRetry]);
  useEffect(() => {
    if (!detail || detail.tracking_loaded !== false) return;
    if (!["IN_TRANSIT", "SHIPPED", "DELIVERED", "COMPLETED"].includes(order.status) && !order.tracking_number && !order.items.some((item) => item.tracking_number)) {
      setDetail({ ...detail, tracking_loaded: true });
      return;
    }
    const controller = new AbortController();
    setTrackingLoading(true);
    setTrackingError("");
    getCustomerSidebarStandardTracking(sessionId, order.external_order_id, controller.signal)
      .then((tracking) => { if (!controller.signal.aborted) setDetail({ ...detail, latest_tracking_description: tracking.latest_tracking_description, latest_tracking_at: tracking.latest_tracking_at, tracking_packages: tracking.packages, tracking_loaded: true }); })
      .catch((cause) => { if (!controller.signal.aborted) setTrackingError(cause instanceof Error ? cause.message : "物流加载失败"); })
      .finally(() => { if (!controller.signal.aborted) setTrackingLoading(false); });
    return () => controller.abort();
  }, [detail, order.external_order_id, order.items, order.status, order.tracking_number, sessionId, trackingRetry]);
  const [receiptOpen, setReceiptOpen] = useState(false);
  const [trackingExpanded, setTrackingExpanded] = useState(false);
  useEffect(() => {
    if (!receiptOpen) return;
    const close = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") setReceiptOpen(false); };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [receiptOpen]);
  const breakdown = [
    { key: "original_total_product_price", zh: "商品总价", en: "Original product total" },
    { key: "sub_total", zh: "商品小计", en: "Product subtotal" },
    { key: "seller_discount", zh: "店铺折扣", en: "Seller discount" },
    { key: "platform_discount", zh: "平台折扣", en: "Platform discount" },
    { key: "shipping_fee", zh: "实付运费", en: "Shipping" },
    { key: "tax", zh: "税费", en: "Tax" },
  ].filter((row) => order.payment_breakdown[row.key] !== undefined);
  const trackingEvents = detail?.tracking_packages.flatMap((parcel) => parcel.events) ?? [];
  const recipient = detail?.recipient_address;
  return <div aria-label={en ? "Order details" : "订单详情"} className="customer-order-detail-view" role="region">
    <div className="customer-order-detail-heading"><button onClick={onBack} type="button"><ArrowLeft size={15} />{en ? "Back" : "返回"}</button><strong>{en ? "Order details" : "订单详情"}</strong></div>
    <nav aria-label={en ? "Order detail sections" : "订单详情分区"} className="customer-order-detail-nav">{([["overview", "订单", "Order"], ["tracking", "物流", "Tracking"], ["items", "商品", "Items"], ["payment", "付款", "Payment"]] as const).map(([id, zh, english]) => <a href={`#customer-order-${id}`} key={id}>{en ? english : zh}</a>)}</nav>
    {detailLoading ? <p className="customer-side-muted" role="status">{en ? "Loading order details…" : "正在读取订单详情…"}</p> : null}
    {trackingLoading ? <p className="customer-side-muted" role="status">{en ? "Loading tracking…" : "正在读取物流…"}</p> : null}
    {trackingError ? <p className="customer-side-muted" role="alert">{trackingError} <button onClick={() => setTrackingRetry((value) => value + 1)} type="button">{en ? "Retry tracking" : "重试物流"}</button></p> : null}
    {detailError ? <p className="customer-side-muted" role="alert">{detailError} <button disabled={detailLoading} onClick={() => setDetailRetry((value) => value + 1)} type="button">{en ? "Retry details" : "重试详情"}</button></p> : null}
    <div className="customer-order-detail-scroll">
      <section id="customer-order-overview"><h3>{en ? "Order" : "订单"}</h3><div className="customer-info-line"><span>{en ? "Order ID" : "订单编号"}</span><span className="customer-order-overview-value"><CopyableValue en={en} label={en ? "order ID" : "订单编号"} value={order.external_order_id} />{detail?.payment_method_name ? <small>[{detail.payment_method_name}]</small> : null}</span></div><div className="customer-info-line"><span>{en ? "Phone" : "电话"}</span><CopyableValue en={en} label={en ? "phone" : "电话"} value={recipient?.phone_number} /></div><div className="customer-info-line customer-order-address-line"><span>{en ? "Shipping address" : "收货地址"}</span><span className="customer-order-address"><span>{recipient?.name ?? "—"}</span><span>{recipient?.phone_number ?? "—"}</span><CopyableValue en={en} label={en ? "shipping address" : "收货地址"} value={recipient?.full_address} /></span></div></section>
      <section id="customer-order-tracking"><h3>{en ? "Logistics" : "物流"}</h3><div className="customer-info-line"><span>{en ? "Tracking number" : "物流单号"}</span><CopyableValue en={en} label={en ? "tracking number" : "物流单号"} value={order.tracking_number} /></div><div className="customer-info-line"><span>{en ? "Carrier" : "物流商"}</span><span>{detail?.shipping_provider ?? "—"}</span></div><div className="customer-info-line"><span>{en ? "Latest update" : "最新物流"}</span><span>{detail?.latest_tracking_description ?? "—"}</span></div>{trackingEvents.length ? <><ol className="customer-order-timeline">{(trackingExpanded ? trackingEvents : trackingEvents.slice(0, 2)).map((event, index) => <li key={`${event.occurred_at}-${index}`}><span>{event.description}</span><time>{dateTime(event.occurred_at, en)}</time></li>)}</ol>{trackingEvents.length > 2 ? <button aria-expanded={trackingExpanded} className="customer-order-expand" onClick={() => setTrackingExpanded((value) => !value)} type="button">{trackingExpanded ? (en ? "Show less" : "收起") : (en ? "Show more" : "展开更多")}</button> : null}</> : <p className="customer-side-muted">{en ? "Tracking events are unavailable." : "暂无可用物流节点。"}</p>}</section>
      <section id="customer-order-items"><h3>{en ? "Items" : "商品"}</h3>{order.items.map((item, index) => <div className="customer-order-detail-item" key={`${item.sku_id ?? item.product_id ?? index}-${index}`}>{item.image_url ? <img alt="" src={item.image_url} /> : <span aria-hidden="true">{item.name.slice(0, 1)}</span>}<div><strong>{item.name}</strong><small>{en ? "Variant" : "规格"}：{item.sku_name ?? "—"}</small><small>{en ? "Seller SKU" : "SKU 货号"}：{item.sku ?? "—"} · ×{item.quantity}</small></div><b>{money(order.currency, item.total_amount)}</b></div>)}</section>
      <section id="customer-order-payment"><h3>{en ? "Payment" : "付款"}</h3><div className="customer-info-line"><span>{en ? "Paid at" : "付款时间"}</span><span>{dateTime(order.paid_at, en)}</span></div><div className="customer-info-line"><span>{en ? "Method" : "支付方式"}</span><span>{detail?.payment_method_name ?? "—"}</span></div>{breakdown.map((row) => <div className="customer-info-line" key={row.key}><span>{row[en ? "en" : "zh"]}</span><span>{money(order.currency, order.payment_breakdown[row.key])}</span></div>)}<div className="customer-info-line customer-order-total"><span>{en ? "Buyer paid" : "买家实付金额"}</span><strong>{money(order.currency, order.total_amount)}</strong></div><button className="customer-receipt-button" disabled={!order.paid_at} onClick={() => setReceiptOpen(true)} type="button">{en ? "Receipt" : "收据"}</button>{!order.paid_at ? <p className="customer-side-muted">{en ? "Receipt preview is available after payment." : "付款后才可查看收据预览。"}</p> : null}</section>
    </div>
    {receiptOpen ? <div className="customer-receipt-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setReceiptOpen(false); }}><section aria-label={en ? "Order receipt preview" : "订单收据预览"} aria-modal="true" className="customer-receipt-dialog" role="dialog"><header><div><small>{storeName ?? "TikTok"}</small><h2>{en ? "Order receipt preview" : "订单收据预览"}</h2></div><button aria-label={en ? "Close receipt" : "关闭收据"} onClick={() => setReceiptOpen(false)} type="button"><X size={20} /></button></header><p className="customer-receipt-note">{en ? "Read-only order summary; this is not a platform-issued invoice and will not be sent." : "仅供内部核对的订单摘要，并非平台开具的发票，不会发送给买家。"}</p><div className="customer-info-line"><span>{en ? "Order ID" : "订单编号"}</span><span>{order.external_order_id}</span></div><div className="customer-info-line"><span>{en ? "Buyer" : "买家"}</span><span>{buyerName ?? "—"}</span></div><div className="customer-info-line"><span>{en ? "Paid at" : "付款时间"}</span><span>{dateTime(order.paid_at, en)}</span></div><div className="customer-receipt-items">{order.items.map((item, index) => <div key={`${item.sku_id ?? item.product_id ?? index}-${index}`}><span>{item.name} ×{item.quantity}</span><span>{money(order.currency, item.total_amount)}</span></div>)}</div><div className="customer-receipt-total"><span>{en ? "Buyer paid" : "买家实付金额"}</span><strong>{money(order.currency, order.total_amount)}</strong></div><footer><button onClick={() => setReceiptOpen(false)} type="button">{en ? "Close" : "关闭"}</button></footer></section></div> : null}
  </div>;
}

function ProductCard({ product, sessionId, en, fillDraft }: { product: SidebarProduct; sessionId: string; en: boolean; fillDraft: (value: string) => void }) {
  const [full, setFull] = useState<SidebarProduct | null>(null);
  const [detailError, setDetailError] = useState("");
  const [detailLoading, setDetailLoading] = useState(false);
  const cardRef = useRef<HTMLElement>(null);
  const detailRequestInFlight = useRef(false);
  const loadProduct = useCallback(() => {
    if (detailRequestInFlight.current) return;
    detailRequestInFlight.current = true;
    setDetailLoading(true);
    setDetailError("");
    getCustomerSidebarProduct(sessionId, product.id)
      .then((result) => {
        if (!result || !Array.isArray(result.skus)) throw new Error(en ? "Product details are unavailable" : "商品详情暂不可用");
        setFull(result);
      })
      .catch((cause) => setDetailError(cause instanceof Error ? cause.message : "商品详情加载失败"))
      .finally(() => { detailRequestInFlight.current = false; setDetailLoading(false); });
  }, [sessionId, product.id, en]);
  useEffect(() => {
    if (!cardRef.current || product.image_url) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) { observer.disconnect(); loadProduct(); }
    }, { rootMargin: "150px 0px" });
    observer.observe(cardRef.current);
    return () => observer.disconnect();
  }, [loadProduct, product.image_url]);
  const shown = full ?? product;
  const prices = shown.skus.filter((sku) => sku.sale_price !== null).map((sku) => Number(sku.sale_price)).filter(Number.isFinite);
  const currency = shown.skus.find((sku) => sku.currency)?.currency ?? "";
  const price = prices.length ? `${money(currency, String(Math.min(...prices)))}${Math.max(...prices) > Math.min(...prices) ? ` – ${money(currency, String(Math.max(...prices)))}` : ""}` : "—";
  return <article className="customer-product-card" data-testid="customer-product-card" ref={cardRef}><div className="customer-product-head">{shown.image_url ? <img alt="" className="customer-product-image" src={shown.image_url} /> : <div className="customer-item-thumb" aria-hidden="true">{shown.title.slice(0, 1)}</div>}<div><strong title={shown.title}>{shown.title}</strong><small>{price}</small><small>{en ? "Product ID" : "商品 ID"} · {shown.id}</small></div></div><details className="customer-sku-box" onToggle={(event) => { if (event.currentTarget.open && !full && !detailLoading && !detailError) loadProduct(); }}><summary>{en ? "SKU details" : "SKU 信息"} ⌄</summary>{detailLoading && !full ? <p className="customer-side-muted">{en ? "Loading SKU details…" : "正在加载 SKU 详情…"}</p> : null}{detailError ? <p className="customer-side-muted" role="alert">{detailError} <button onClick={loadProduct} type="button">{en ? "Retry" : "重试"}</button></p> : null}<table><thead><tr><th>{en ? "Variant" : "商品规格"}</th><th>{en ? "Seller SKU" : "SKU 货号"}</th><th>{en ? "Stock" : "库存状态"}</th></tr></thead><tbody>{shown.skus.map((sku) => <tr key={sku.id}><td><CopyableValue en={en} label={en ? "variant" : "商品规格"} value={sku.name} /></td><td><CopyableValue en={en} label={en ? "seller SKU" : "SKU 货号"} value={sku.seller_sku} /></td><td>{sku.quantity === null ? "—" : sku.quantity > 0 ? (en ? "In stock" : "有货") : (en ? "Out of stock" : "缺货")}</td></tr>)}</tbody></table></details><div className="customer-product-foot"><span>{productStatusText[shown.status ?? ""]?.[en ? "en" : "zh"] ?? (en ? "Status unavailable" : "状态暂无")}</span><button onClick={() => fillDraft(en ? `Product: ${shown.title} (ID: ${shown.id})` : `商品：${shown.title}（ID：${shown.id}）`)} type="button">{en ? "Use in draft" : "填入回复草稿"}</button></div></article>;
}

function CouponCard({ coupon, en, fillDraft }: { coupon: SidebarCoupon; en: boolean; fillDraft: (value: string) => void }) {
  const discount = couponDiscount(coupon, en);
  return <article className="customer-side-card" data-testid="customer-coupon-card"><div className="customer-card-top"><strong>{coupon.title}</strong><span>{couponStatusText[coupon.status ?? ""]?.[en ? "en" : "zh"] ?? (en ? "Status unavailable" : "状态暂无")}</span></div><div className="customer-info-line"><span>{en ? "Code" : "编码"}</span><span>{coupon.promo_code ?? coupon.id}</span></div><div className="customer-info-line"><span>{en ? "Discount" : "优惠"}</span><span>{discount}</span></div><div className="customer-info-line"><span>{en ? "Display" : "展示渠道"}</span><span>{couponDisplayText[coupon.display_type ?? ""]?.[en ? "en" : "zh"] ?? (en ? "Unknown" : "暂无")}</span></div>{coupon.claim_end_time ? <div className="customer-info-line"><span>{en ? "Claim until" : "领取截止"}</span><span>{dateTime(new Date(coupon.claim_end_time * 1000).toISOString(), en)}</span></div> : null}<p className="customer-side-muted">{coupon.chat_shareable ? (en ? "Chat sharing is subject to buyer eligibility." : "聊天分享仍需核对买家领取条件。") : (en ? "Chat sharing eligibility is unconfirmed." : "未确认此券可在聊天中分享。")}</p><div className="customer-card-actions"><button onClick={() => fillDraft(en ? `Coupon: ${coupon.title}${coupon.promo_code ? ` (${coupon.promo_code})` : ""}. Please check eligibility in TikTok.` : `优惠券：${coupon.title}${coupon.promo_code ? `（${coupon.promo_code}）` : ""}。请先核对 TikTok 领取条件。`)} type="button">{en ? "Use in draft" : "填入回复草稿"}</button></div></article>;
}

export function CustomerSidebar({ detail, storeName, en, onClose, onDraft, onOrderDraft, onCardDraft, onOrderSnapshot }: { detail: SessionMessagesData | null; storeName: string | null; en: boolean; onClose: () => void; onDraft: (value: string) => void; onOrderDraft: (order: SidebarOrder) => void; onCardDraft: (value: LogisticsCardDraft) => void; onOrderSnapshot: (sessionId: string, orders: SidebarOrder[] | null) => void }) {
  const [section, setSection] = useState<Section>("orders");
  const [status, setStatus] = useState<OrderStatus>("all");
  const [field, setField] = useState("order");
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pageToken, setPageToken] = useState<string | null>(null);
  const [orders, setOrders] = useState<SidebarOrders | null>(null);
  const [selectedOrder, setSelectedOrder] = useState<{ order: SidebarOrder; detail: SidebarOrderDetail | null } | null>(null);
  const [products, setProducts] = useState<SidebarProducts | null>(null);
  const [coupons, setCoupons] = useState<SidebarCoupons | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sort, setSort] = useState<"platform" | "priceAsc" | "priceDesc">("platform");
  const [retryCount, setRetryCount] = useState(0);
  const requestId = useRef(0);
  const sideBodyRef = useRef<HTMLDivElement>(null);
  const requestedProductToken = useRef<string | null>(null);
  const forceOrderRefresh = useRef(false);
  const sessionId = detail?.session.id;
  const scheduleDetail = useMemo(() => createOrderDetailLimiter(2), []);
  useEffect(() => { setSection("orders"); setStatus("all"); setField("order"); setInput(""); setQuery(""); setPage(1); setPageToken(null); setOrders(null); setSelectedOrder(null); setProducts(null); setCoupons(null); requestedProductToken.current = null; forceOrderRefresh.current = false; }, [sessionId]);
  useEffect(() => {
    if (!sessionId) return;
    const current = ++requestId.current;
    setLoading(true); setError("");
    const payload = { section, field, query, status, page, page_token: pageToken, refresh: section === "orders" && forceOrderRefresh.current };
    forceOrderRefresh.current = false;
    if (section === "orders") {
      searchCustomerSidebar<SidebarOrders>(sessionId, payload).then((data) => { if (current === requestId.current) { setOrders(data); if (status === "all" && !query && page === 1) onOrderSnapshot(sessionId, data.items); } }).catch((cause) => { if (current === requestId.current) { setError(cause instanceof Error ? cause.message : "订单加载失败"); if (status === "all" && !query && page === 1) onOrderSnapshot(sessionId, null); } }).finally(() => { if (current === requestId.current) setLoading(false); });
    } else if (section === "products") {
      searchCustomerSidebar<SidebarProducts>(sessionId, payload).then((data) => { if (current === requestId.current) setProducts((old) => pageToken && old ? { ...data, items: [...old.items, ...data.items] } : data); }).catch((cause) => { if (current === requestId.current) setError(cause instanceof Error ? cause.message : "商品加载失败"); }).finally(() => { if (current === requestId.current) setLoading(false); });
    } else {
      searchCustomerSidebar<SidebarCoupons>(sessionId, payload).then((data) => { if (current === requestId.current) setCoupons((old) => pageToken && old ? { ...data, items: [...old.items, ...data.items] } : data); }).catch((cause) => { if (current === requestId.current) setError(cause instanceof Error ? cause.message : "优惠券加载失败"); }).finally(() => { if (current === requestId.current) setLoading(false); });
    }
    return () => { requestId.current += 1; };
  }, [sessionId, section, field, query, status, page, pageToken, retryCount, onOrderSnapshot]);
  const sortedProducts = useMemo(() => {
    // 搜索接口会返回下架和缺货项；只有平台明确上架且库存为正的商品可供客服推荐。
    const items = (products?.items ?? []).filter((item) => item.status === "ACTIVATE" && item.skus.some((sku) => sku.quantity !== null && sku.quantity > 0));
    if (sort === "platform") return items;
    const firstPrice = (item: SidebarProduct) => Number(item.skus.find((sku) => sku.sale_price !== null)?.sale_price ?? Number.POSITIVE_INFINITY);
    return [...items].sort((a, b) => sort === "priceAsc" ? firstPrice(a) - firstPrice(b) : firstPrice(b) - firstPrice(a));
  }, [products, sort]);
  const visibleCoupons = (coupons?.items ?? []).filter((coupon) => coupon.status === "ONGOING");
  const loadMoreProducts = useCallback(() => {
    const token = products?.next_page_token;
    if (section !== "products" || loading || error || !token || requestedProductToken.current === token) return;
    requestedProductToken.current = token;
    setPageToken(token);
  }, [section, products?.next_page_token, loading, error]);
  useEffect(() => {
    const node = sideBodyRef.current;
    if (node && section === "products" && products?.next_page_token && node.scrollHeight - node.scrollTop - node.clientHeight < 100) loadMoreProducts();
  }, [section, products, loadMoreProducts]);
  const chooseSection = (next: Section) => { setSection(next); setField(fields[next][0].value); setInput(""); setQuery(""); setPage(1); setPageToken(null); setError(""); requestedProductToken.current = null; };
  const submitSearch = () => { setPage(1); setPageToken(null); setOrders(null); setProducts(null); setCoupons(null); setQuery(input.trim()); requestedProductToken.current = null; };
  const fillDraft = (content: string) => { onDraft(content); onClose(); };
  const fillCardDraft = (card: LogisticsCardDraft) => { onCardDraft(card); onClose(); };
  return <><button aria-label={en ? "Close customer details" : "关闭客户信息"} className="drawer-close" onClick={onClose} type="button"><X size={21} /></button>{!detail ? <p className="customer-side-empty">{en ? "Select a conversation to view customer details" : "选择会话后查看客户信息"}</p> : <>
    <header className="customer-side-profile"><span className="avatar large">{buyerAvatarText(detail.customer.name)}</span><div><h2>{detail.customer.name ?? (en ? "Anonymous customer" : "匿名客户")}</h2><p>{storeName ?? (en ? "Store name unavailable" : "店铺名称不可用")}</p></div></header>
    {selectedOrder ? <OrderDetailsView buyerName={detail.customer.name} detail={selectedOrder.detail} en={en} onBack={() => setSelectedOrder(null)} order={selectedOrder.order} sessionId={detail.session.id} storeName={storeName} /> : <>
    <div className="customer-side-tabs" role="tablist" aria-label={en ? "Customer information" : "客户信息"}>{(["orders", "products", "coupons"] as const).map((value) => <button aria-selected={section === value} className={section === value ? "active" : ""} key={value} onClick={() => chooseSection(value)} role="tab" type="button">{({ orders: en ? "Orders" : "订单", products: en ? "Products" : "商品", coupons: en ? "Coupons" : "优惠券" })[value]}</button>)}</div>
    {section === "orders" ? <div className="customer-side-status" aria-label={en ? "Order status" : "订单状态"}>{statuses.map((item) => <button aria-pressed={status === item.value} className={status === item.value ? "active" : ""} key={item.value} onClick={() => { setStatus(item.value); setPage(1); }} type="button">{item[en ? "en" : "zh"]}</button>)}</div> : null}
    <form className="customer-side-search" onSubmit={(event) => { event.preventDefault(); submitSearch(); }}><select aria-label={en ? "Search field" : "搜索字段"} onChange={(event) => { setField(event.target.value); setInput(""); setQuery(""); setPage(1); setPageToken(null); requestedProductToken.current = null; }} value={field}>{fields[section].map((item) => <option key={item.value} value={item.value}>{item[en ? "en" : "zh"]}</option>)}</select><input aria-label={en ? "Customer information search" : "客户信息搜索"} onChange={(event) => setInput(event.target.value)} placeholder={en ? "Enter search text" : `输入${fields[section].find((item) => item.value === field)?.zh ?? "关键词"}搜索`} value={input} /><button aria-label={en ? "Search" : "搜索"} type="submit"><MagnifyingGlass size={16} /></button></form>
    {section === "products" ? <div className="customer-side-sort"><span>{en ? "Store products" : "店铺商品"}</span><select aria-label={en ? "Product sort" : "商品排序"} onChange={(event) => setSort(event.target.value as typeof sort)} value={sort}><option value="platform">{en ? "Platform order" : "平台顺序"}</option><option value="priceAsc">{en ? "Price ↑ (loaded)" : "价格 ↑（已加载）"}</option><option value="priceDesc">{en ? "Price ↓ (loaded)" : "价格 ↓（已加载）"}</option></select></div> : null}
    <div className="customer-side-body" onScroll={(event) => { const node = event.currentTarget; if (node.scrollHeight - node.scrollTop - node.clientHeight < 100) loadMoreProducts(); }} ref={sideBodyRef} role="tabpanel"><p className="customer-side-tip">{storeName ?? "TikTok"} · {section === "orders" ? (en ? "Customer orders" : "客户订单") : section === "products" ? (en ? "Live shop catalog" : "实时店铺商品") : (en ? "Live shop coupons" : "实时店铺优惠券")}{section === "orders" ? <button disabled={loading} onClick={() => { forceOrderRefresh.current = true; setRetryCount((count) => count + 1); }} type="button">{en ? "Refresh orders" : "刷新订单"}</button> : null}</p>{error ? <div className="customer-side-state" role="alert"><p>{error}</p><button onClick={() => setRetryCount((count) => count + 1)} type="button">{en ? "Retry" : "重试"}</button></div> : null}{loading && !orders && !products && !coupons ? <p className="customer-side-state">{en ? "Loading…" : "正在加载…"}</p> : null}
      {!error && section === "orders" && orders ? <>{orders.items.length ? orders.items.map((item) => <OrderCard en={en} fillOrderDraft={(order) => { onOrderDraft(order); onClose(); }} key={`${detail.session.id}:${item.id}`} onCardDraft={fillCardDraft} onDetails={(order, orderDetail) => setSelectedOrder({ order, detail: orderDetail })} order={item} scheduleDetail={scheduleDetail} sessionId={detail.session.id} trackingTranslationEnabled={detail.translation_enabled === true} />) : <p className="customer-side-state">{en ? "No orders match this view" : "当前搜索或状态下暂无订单"}</p>}{orders.pagination.total > orders.pagination.page * orders.pagination.page_size ? <button className="customer-side-more" disabled={loading} onClick={() => setPage((value) => value + 1)} type="button">{en ? "Next page" : "下一页"}</button> : null}{orders.pagination.page > 1 ? <button className="customer-side-more" disabled={loading} onClick={() => setPage((value) => Math.max(1, value - 1))} type="button">{en ? "Previous page" : "上一页"}</button> : null}</> : null}
      {!error && section === "products" && products ? <>{sortedProducts.length ? sortedProducts.map((item) => <ProductCard en={en} fillDraft={fillDraft} key={item.id} product={item} sessionId={detail.session.id} />) : <p className="customer-side-state">{products.next_page_token ? (en ? "Searching more products…" : "正在继续搜索商品…") : (en ? "No listed products in stock" : "暂无上架且有货商品")}</p>}{products.partial_search ? <p className="customer-side-tip">{en ? "Name search continues across pages; more results may exist." : "名称搜索按平台目录逐页继续，后续页面可能还有结果。"}</p> : null}{products.next_page_token ? <button className="customer-side-more" disabled={loading} onClick={loadMoreProducts} type="button">{loading ? (en ? "Loading…" : "加载中…") : (en ? "Load more products" : "加载更多商品")}</button> : null}{loading && pageToken ? <p className="customer-side-state" role="status">{en ? "Loading more products…" : "正在加载更多商品…"}</p> : null}</> : null}
      {!error && section === "coupons" && coupons ? <>{visibleCoupons.length ? visibleCoupons.map((item) => <CouponCard coupon={item} en={en} fillDraft={fillDraft} key={item.id} />) : <p className="customer-side-state">{coupons.next_page_token ? (en ? "No usable coupons on this page. Search the next page." : "本页暂无有效优惠券，可继续搜索下一页。") : (en ? "No currently usable coupons" : "暂无当前有效优惠券")}</p>}{coupons.partial_search ? <p className="customer-side-tip">{en ? "Code search continues across pages." : "编码搜索按平台目录逐页继续。"}</p> : null}{coupons.next_page_token ? <button className="customer-side-more" disabled={loading} onClick={() => setPageToken(coupons.next_page_token)} type="button">{loading ? (en ? "Loading…" : "加载中…") : (en ? "Load more coupons" : "加载更多优惠券")}</button> : null}</> : null}
    </div></>}
  </>}</>;
}
