"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Camera, Copy, ListBullets, X } from "@phosphor-icons/react";
import { getCustomerSidebarEnhancedTracking, translateSidebarTracking, type SidebarTrackingEvent, type SidebarTrackingPackage } from "../lib/api";

function formattedTime(value: string, en: boolean) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString(en ? "en-US" : "zh-CN", { hour12: false });
}

function eventKey(event: SidebarTrackingEvent) {
  return `${event.tracking_number ?? ""}\u0000${event.occurred_at}\u0000${event.description}`;
}

function wrapCanvasText(context: CanvasRenderingContext2D, value: string, width: number): string[] {
  const lines: string[] = [];
  let line = "";
  for (const character of value) {
    if (character === "\n" || context.measureText(line + character).width > width) {
      if (line) lines.push(line);
      line = character === "\n" ? "" : character;
    } else line += character;
  }
  if (line) lines.push(line);
  return lines.length ? lines : ["—"];
}

async function downloadTimelineImage(
  item: SidebarTrackingPackage,
  en: boolean,
  translated: Record<string, string>,
  showOriginal: boolean,
) {
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  if (!context) throw new Error(en ? "Screenshot is unavailable" : "当前浏览器无法生成截图");
  const width = 440;
  const lines: Array<{ text: string; color: string; size: number; gap: number }> = [];
  lines.push({ text: en ? "Tracking history" : "物流完整信息", color: "#172451", size: 18, gap: 10 });
  lines.push({ text: `${en ? "Tracking number" : "物流单号"}：${item.tracking_number ?? "—"}`, color: "#172451", size: 13, gap: 3 });
  lines.push({ text: `${en ? "Carrier" : "物流商"}：${item.carrier_name ?? "—"}`, color: "#52617a", size: 13, gap: 12 });
  for (const event of item.events) {
    const description = !showOriginal ? translated[eventKey(event)] ?? event.description : event.description;
    context.font = "13px sans-serif";
    for (const text of wrapCanvasText(context, description, width - 44)) {
      lines.push({ text, color: "#172451", size: 13, gap: 0 });
    }
    lines.push({ text: formattedTime(event.occurred_at, en), color: "#73809a", size: 12, gap: 12 });
  }
  if (!item.events.length) lines.push({ text: en ? "No tracking events" : "暂无物流节点", color: "#73809a", size: 13, gap: 0 });
  const height = 32 + lines.reduce((sum, line) => sum + line.size + 7 + line.gap, 0);
  if (height > 15000) throw new Error(en ? "Too many events for one image" : "节点过多，无法生成单张截图");
  canvas.width = width * 2;
  canvas.height = height * 2;
  context.scale(2, 2);
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, width, height);
  let y = 25;
  for (const line of lines) {
    context.font = `${line.size === 18 ? "bold " : ""}${line.size}px sans-serif`;
    context.fillStyle = line.color;
    context.fillText(line.text, 20, y);
    y += line.size + 7 + line.gap;
  }
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
  if (!blob) throw new Error(en ? "Screenshot failed" : "截图生成失败");
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `tracking-${(item.tracking_number ?? "package").replace(/[^a-zA-Z0-9_-]/g, "-")}.png`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function TrackingTimelinePopover({ sessionId, orderId, initialPackages, enhancedAvailable, en }: {
  sessionId: string;
  orderId: string;
  initialPackages: SidebarTrackingPackage[];
  enhancedAvailable: boolean;
  en: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [packages, setPackages] = useState(initialPackages);
  const [enhanced, setEnhanced] = useState(false);
  const [enhancedTried, setEnhancedTried] = useState(false);
  const [selected, setSelected] = useState(0);
  const [notice, setNotice] = useState("");
  const [copied, setCopied] = useState(false);
  const [translations, setTranslations] = useState<Record<string, string>>({});
  const [showOriginal, setShowOriginal] = useState(false);
  const [translating, setTranslating] = useState("");
  const [position, setPosition] = useState({ left: 8, top: 8, width: 380 });
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const detailVersion = useRef(0);
  const current = packages[selected];

  useEffect(() => {
    detailVersion.current += 1;
    setPackages(initialPackages);
    setEnhanced(false);
    setEnhancedTried(false);
    setSelected(0);
    setTranslations({});
    setNotice("");
  }, [initialPackages]);

  useEffect(() => {
    if (!open || !enhancedAvailable || enhancedTried) return;
    const requestedVersion = detailVersion.current;
    setEnhancedTried(true);
    getCustomerSidebarEnhancedTracking(sessionId, orderId).then((result) => {
      if (requestedVersion !== detailVersion.current) return;
      if (result.packages.length) {
        setPackages(result.packages);
        setEnhanced(true);
        setSelected(0);
      } else setNotice(en ? "TikTok returned no enhanced events; showing standard history." : "TikTok 暂无增强轨迹，已显示通用轨迹。 ");
    }).catch((error) => {
      if (requestedVersion === detailVersion.current) setNotice(error instanceof Error ? error.message : en ? "Enhanced history unavailable" : "增强轨迹暂不可用");
    });
  }, [open, enhancedAvailable, enhancedTried, sessionId, orderId, en]);

  const placePopover = useCallback(() => {
    if (!open || !triggerRef.current || !popoverRef.current) return;
    const anchor = triggerRef.current.getBoundingClientRect();
    const width = Math.min(380, window.innerWidth - 16);
    const height = popoverRef.current.getBoundingClientRect().height;
    const left = Math.max(8, Math.min(anchor.right - width, window.innerWidth - width - 8));
    const top = anchor.bottom + height + 8 <= window.innerHeight
      ? anchor.bottom + 6
      : Math.max(8, anchor.top - height - 6);
    setPosition({ left, top, width });
  }, [open]);

  useLayoutEffect(() => { placePopover(); }, [placePopover, packages, selected]);
  useEffect(() => {
    if (!open) return;
    function onPointer(event: PointerEvent) {
      if (event.target instanceof Node && !popoverRef.current?.contains(event.target) && !triggerRef.current?.contains(event.target)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") { setOpen(false); triggerRef.current?.focus(); }
    }
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", placePopover);
    window.addEventListener("scroll", placePopover, true);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", placePopover);
      window.removeEventListener("scroll", placePopover, true);
    };
  }, [open, placePopover]);

  async function copyAll() {
    const value = packages.map((item, index) => [
      `${en ? "Package" : "包裹"} ${index + 1}`,
      `${en ? "Tracking number" : "物流单号"}：${item.tracking_number ?? "—"}`,
      `${en ? "Carrier" : "物流商"}：${item.carrier_name ?? "—"}`,
      ...item.events.map((event) => `${formattedTime(event.occurred_at, en)}  ${showOriginal ? event.description : translations[eventKey(event)] ?? event.description}`),
    ].join("\n")).join("\n\n");
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setNotice("");
      window.setTimeout(() => setCopied(false), 1500);
    } catch { setNotice(en ? "Copy failed, please retry" : "复制失败，请重试"); }
  }

  async function translateEvent(event: SidebarTrackingEvent) {
    const key = eventKey(event);
    if (translating) return;
    setTranslating(key);
    setNotice("");
    try {
      const result = await translateSidebarTracking(sessionId, orderId, { ...event, enhanced });
      if (result.source_description !== event.description || !result.translated_text.trim()) throw new Error(en ? "History changed; refresh and retry" : "物流轨迹已变化，请刷新后重试");
      setTranslations((current) => ({ ...current, [key]: result.translated_text }));
      setShowOriginal(false);
    } catch (error) { setNotice(error instanceof Error ? error.message : en ? "Translation failed" : "翻译失败，请重试"); }
    finally { setTranslating(""); }
  }

  return <>
    <button aria-expanded={open} aria-label={en ? "View full tracking history" : "查看完整物流"} className="customer-tracking-open" onClick={() => setOpen((value) => !value)} ref={triggerRef} title={en ? "Full tracking history" : "完整物流信息"} type="button"><ListBullets size={14} /></button>
    {open ? createPortal(<div aria-label={en ? "Full tracking history" : "物流完整信息"} className="customer-timeline-popover" ref={popoverRef} role="dialog" style={position}>
      <div className="customer-timeline-header"><strong>{en ? "Tracking history" : "物流完整信息"}</strong><button aria-label={en ? "Close" : "关闭"} onClick={() => { setOpen(false); triggerRef.current?.focus(); }} type="button"><X size={15} /></button></div>
      <div className="customer-timeline-actions"><button disabled={!packages.length} onClick={() => void copyAll()} type="button"><Copy size={13} />{copied ? en ? "Copied" : "已复制" : en ? "Copy all" : "复制全部"}</button><button disabled={!current} onClick={() => { if (current) void downloadTimelineImage(current, en, translations, showOriginal).catch((error) => setNotice(error instanceof Error ? error.message : "截图失败")); }} title={en ? "Screenshot of selected package" : "生成当前包裹截图"} type="button"><Camera size={13} />{en ? "Screenshot" : "生成截图"}</button>{Object.keys(translations).length ? <button onClick={() => setShowOriginal((value) => !value)} type="button">{showOriginal ? en ? "Show translations" : "查看译文" : en ? "Show original" : "查看原文"}</button> : null}</div>
      {notice ? <p className="customer-timeline-notice" role="status">{notice}</p> : null}
      {packages.length > 1 ? <div aria-label={en ? "Packages" : "包裹"} className="customer-timeline-tabs" role="tablist">{packages.map((_, index) => <button aria-selected={selected === index} key={index} onClick={() => setSelected(index)} role="tab" type="button">{en ? "Package" : "包裹"} {index + 1}</button>)}</div> : null}
      {current ? <div className="customer-timeline-content" role="tabpanel"><div className="customer-timeline-meta"><span>{en ? "Tracking number" : "物流单号"}：{current.tracking_number ?? "—"}</span><span>{en ? "Carrier" : "物流商"}：{current.carrier_name ?? "—"}</span></div>{current.events.length ? <ol className="customer-timeline-events">{current.events.map((event, index) => <li key={`${eventKey(event)}-${index}`}><span className="customer-timeline-event-text">{!showOriginal ? translations[eventKey(event)] ?? event.description : event.description}</span><time>{formattedTime(event.occurred_at, en)}</time>{event.tracking_number && event.tracking_number !== current.tracking_number ? <small>{en ? "Tracking" : "节点单号"}：{event.tracking_number}</small> : null}{!en && /[A-Za-z]/.test(event.description) ? <button disabled={Boolean(translating)} onClick={() => void translateEvent(event)} type="button">{translating === eventKey(event) ? "翻译中…" : translations[eventKey(event)] ? "重新翻译" : "译成中文"}</button> : null}</li>)}</ol> : <p className="customer-side-muted">{en ? "No tracking events returned by TikTok" : "TikTok 暂无物流节点"}</p>}</div> : <p className="customer-side-muted">{en ? "No tracking history returned by TikTok" : "TikTok 暂无物流轨迹"}</p>}
    </div>, document.body) : null}
  </>;
}
