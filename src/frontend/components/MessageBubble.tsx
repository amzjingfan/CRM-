"use client";

import { useState } from "react";
import { Headset, Robot } from "@phosphor-icons/react";
import { translateMessage, type MessageView } from "../lib/api";
import { TrackingCard } from "./TrackingCard";
import { TikTokMessageCard } from "./TikTokMessageCard";
import { buyerAvatarText, messageSide, senderLabel } from "../lib/message-display";

const statusLabel = (status: MessageView["status"], en: boolean) => ({
  received: en ? "Received" : "已接收",
  processing: en ? "Sending" : "发送中",
  sent: en ? "Sent" : "已发送",
  delivered: en ? "Delivered" : "已送达",
  failed: en ? "Failed" : "发送失败",
  unknown: en ? "Unknown · reconcile manually" : "结果未知 · 请人工对账",
}[status]);

export function MessageBubble({ message, sessionId, customerName, en, translationEnabled }: { message: MessageView; sessionId: string; customerName: string | null; en: boolean; translationEnabled: boolean }) {
  const [translation, setTranslation] = useState("");
  const [translating, setTranslating] = useState(false);
  const [translationError, setTranslationError] = useState(false);
  const [videoFailed, setVideoFailed] = useState(false);
  const side = messageSide(message.role);
  const sender = senderLabel(message.role, en);
  const canTranslate = (message.message_type ?? "text") === "text" && translationEnabled && side !== "system" && /[A-Za-z]/.test(message.content);

  async function requestTranslation() {
    if (translating || translation) return;
    setTranslating(true);
    setTranslationError(false);
    try {
      const result = await translateMessage(sessionId, message.id);
      setTranslation(result.translated_text);
    } catch {
      setTranslationError(true);
    } finally {
      setTranslating(false);
    }
  }

  return <article aria-label={sender} className={`message ${side}`}>
    {side !== "system" ? <span aria-hidden="true" className={`message-avatar ${message.role === "assistant" ? "robot" : ""}`}>{message.role === "user" ? buyerAvatarText(customerName) : message.role === "assistant" ? <Robot size={15} weight="fill" /> : <Headset size={15} weight="fill" />}</span> : null}
    <div className="message-stack">
      <div className="message-bubble">
        {message.message_type === "logistics_card" && message.logistics_card ? <TrackingCard card={message.logistics_card} en={en} sessionId={sessionId} translationEnabled={translationEnabled} /> : message.rich_card ? <TikTokMessageCard card={message.rich_card} en={en} /> : ["image", "emoticons"].includes(message.message_type ?? "") && message.media?.url ? <a href={message.media.url} rel="noopener noreferrer" referrerPolicy="no-referrer" target="_blank"><img alt={message.message_type === "emoticons" ? (en ? "Sticker" : "表情") : (en ? "Image" : "图片")} className="workspace-message-image" loading="lazy" referrerPolicy="no-referrer" src={message.media.url} /></a> : message.message_type === "video" && message.media?.url && !videoFailed ? <video aria-label={en ? "TikTok video" : "TikTok 视频"} className="workspace-message-video" controls onError={() => setVideoFailed(true)} playsInline poster={message.media.cover ?? undefined} preload="none" src={message.media.url} /> : message.message_type === "video" && message.media?.cover ? <div className="workspace-message-video-expired"><img alt="" src={message.media.cover} /><span>{en ? "Video unavailable" : "视频链接已过期或不可用"}</span></div> : <p className="message-original">{message.content}</p>}
        {translation && translation !== message.content ? <p className="message-translation"><span className="sr-only">{en ? "Chinese translation: " : "中文译文："}</span>{translation}</p> : null}
      </div>
      <div className="message-meta">
        <span>{sender} · {new Date(message.created_at).toLocaleTimeString(en ? "en-US" : "zh-CN", { hour: "2-digit", minute: "2-digit" })} · {statusLabel(message.status, en)}{message.delivery_mode === "real" ? (en ? " · real" : " · 真实平台") : message.delivery_mode === "mock" ? (en ? " · simulated" : " · 模拟") : ""}</span>
        {canTranslate && !translation ? <button className="message-translate-button" disabled={translating} onClick={() => void requestTranslation()} type="button">{translating ? (en ? "Translating…" : "翻译中…") : translationError ? (en ? "Retry translation" : "重试翻译") : (en ? "Translate to Chinese" : "译成中文")}</button> : null}
      </div>
    </div>
  </article>;
}
