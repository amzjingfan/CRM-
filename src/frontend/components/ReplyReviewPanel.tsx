"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { TrackingCard } from "./TrackingCard";
import { createIdempotencyKey, getAutoReplyPreview, getLogisticsNotificationPolicy, getReplyLogisticsPreview, saveLogisticsNotificationPolicy, streamChatQuery, submitReplyBatch, type AgentConfig, type AutoReplyPreview, type LogisticsNotificationPolicy, type LogisticsCardDraft, type MessageView, type ReplyBatchPart, type ReplyBatchRequest, type ReplyBatchResult, type Suggestion } from "../lib/api";

type ReviewPlan = { triggerId: string | null; texts: string[]; orders: string[]; translation: Suggestion["translation"]; translationUnavailable: boolean };
type Submission = { request: ReplyBatchRequest; key: string; result?: ReplyBatchResult };
type Props = {
  sessionId: string; triggerMessageId: string | null; recipient: string; en: boolean;
  composerDraft: string; composerRevision: number; sendMode: "disabled" | "mock" | "real";
  busy: boolean; translationEnabled: boolean;
  onUse: (text: string) => void; onDelivered: (messages: MessageView[]) => void;
};

function reviewReason(result: Suggestion, en: boolean): string {
  const codes = result.reason_codes?.length ? result.reason_codes : [result.terminal_state || result.action || "review_required"];
  return `${en ? "No usable reply was generated; review required" : "未生成可用回复，需复核"} · ${codes.map((code) => ({
    review_required: en ? "Review required" : "需要人工复核",
    privacy_review_failed: en ? "Privacy review failed" : "隐私复核未通过",
    generation_failed: en ? "Generation failed" : "生成失败",
    deadline_exceeded: en ? "Generation timed out" : "生成超时",
    cancelled: en ? "Cancelled" : "已取消",
  }[code] ?? `${en ? "Review reason" : "复核原因"}：${code}`)).join("；")}`;
}

export function ReplyReviewPanel(props: Props) {
  const { sessionId, triggerMessageId, recipient, en, composerDraft, composerRevision, sendMode, busy, translationEnabled } = props;
  const latest = useRef(props);
  useLayoutEffect(() => { latest.current = props; });
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [autoPreview, setAutoPreview] = useState<AutoReplyPreview | null>(null);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [plan, setPlan] = useState<ReviewPlan | null>(null);
  const [cards, setCards] = useState<LogisticsCardDraft[]>([]);
  const [cardError, setCardError] = useState("");
  const [cardsLoading, setCardsLoading] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [confirmation, setConfirmation] = useState<Submission | null>(null);
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [batchStatus, setBatchStatus] = useState("");
  const confirmationDialog = useRef<HTMLDialogElement | null>(null);
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const mounted = useRef(true);
  const deliveryAttempt = useRef<{ signature: string; key: string } | null>(null);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; generation.current += 1; controller.current?.abort(); };
  }, []);
  useEffect(() => {
    let active = true;
    setAutoPreview(null);
    if (!triggerMessageId) return () => { active = false; };
    const refresh = () => void getAutoReplyPreview(sessionId)
      .then((result) => { if (active) setAutoPreview(result?.trigger_message_id === triggerMessageId ? result : null); })
      .catch(() => { if (active) setAutoPreview(null); });
    refresh();
    const interval = window.setInterval(refresh, 15000);
    return () => { active = false; window.clearInterval(interval); };
  }, [sessionId, triggerMessageId]);
  useLayoutEffect(() => {
    const dialog = confirmationDialog.current;
    if (!confirmation || !dialog) return;
    if (!dialog.open) dialog.showModal();
    return () => { if (dialog.open) dialog.close(); };
  }, [confirmation]);

  // 编辑栏是选中分段的唯一外发正文，避免发送用户已经修改的旧模型稿。
  const deliveryLocked = !!submission && !submission.request.preview_only;
  const texts = deliveryLocked ? submission.request.parts.flatMap((part) => part.kind === "text" ? [part.content] : []) : plan?.texts.map((text, index) => editing === index ? composerDraft : text) ?? [];
  const parts: ReplyBatchPart[] = [
    ...texts.map((content): ReplyBatchPart => ({ kind: "text", content })),
    ...cards.map(({ card }): ReplyBatchPart => ({ kind: "logistics_card", order_id: card.order_id, package_id: card.package_id })),
  ];
  const planSize = parts.reduce((count, part) => count + (part.kind === "text" ? part.content.length : part.order_id.length + (part.package_id?.length ?? 0) + 32), 0);
  const invalid = !texts.length || texts.some((text) => !text.trim() || text.length > 2000) || planSize > 16000;
  const batchDisabled = loading || submitting || busy || cardsLoading || !!cardError || invalid || deliveryLocked;

  async function loadCards(orders: string[], requestId: number) {
    setCardsLoading(true); setCardError("");
    try {
      const results = await Promise.all(orders.map((order) => getReplyLogisticsPreview(sessionId, order)));
      if (!mounted.current || requestId !== generation.current) return;
      setCards(results.flat().map((item) => ({ card: item.card, packages: item.packages, enhancedAvailable: item.enhanced_available, selected: item.selected })));
    } catch (caught) {
      if (mounted.current && requestId === generation.current) setCardError(caught instanceof Error ? caught.message : en ? "Could not load logistics cards" : "物流卡片读取失败");
    } finally { if (mounted.current && requestId === generation.current) setCardsLoading(false); }
  }

  async function requestSuggestion() {
    if (loading || submitting || busy) return;
    controller.current?.abort();
    const active = new AbortController(); controller.current = active;
    const requestId = ++generation.current;
    const originalRevision = composerRevision;
    const originalDraft = composerDraft;
    const originalTrigger = triggerMessageId;
    const current = () => mounted.current && requestId === generation.current && !active.signal.aborted;
    setLoading(true); setStatus(en ? "Connecting…" : "正在连接…"); setDrafts({}); setPlan(null); setCards([]); setCardError(""); setCardsLoading(false); setEditing(null); setExpanded(true); setSubmission(null); setBatchStatus(""); setConfirmation(null); deliveryAttempt.current = null;
    let usableResult = false;
    let streamError = "";
    try {
      await streamChatQuery(sessionId, ({ event, data }) => {
        if (!current()) return;
        if (event === "status") setStatus(String(data.stage ?? (en ? "Processing…" : "处理中…")));
        if (event === "draft" && data.trigger_message_id === originalTrigger && data.unverified === true && data.sendable === false && data.replace === true && Number.isInteger(data.part_index) && Number(data.part_index) >= 0 && typeof data.text === "string") {
          setDrafts((value) => ({ ...value, [Number(data.part_index)]: data.text as string }));
          setStatus(en ? "Generating unverified draft…" : "正在生成未复核草稿…");
        }
        // review_plan 只显示原生草稿快照；旧安全 delta 不能再次拼入同一正文。
        if (event === "result") {
          const result = data as unknown as Suggestion;
          if (result.trigger_message_id !== undefined && result.trigger_message_id !== originalTrigger) return;
          setDrafts({});
          const verified = (result.reply_parts ?? (result.content ? [result.content] : [])).filter((text) => typeof text === "string" && text.trim());
          if (!verified.length) { setStatus(reviewReason(result, en)); return; }
          usableResult = true;
          const orders = [...new Set(result.logistics_order_numbers?.filter((order) => typeof order === "string" && order) ?? [])];
          setPlan({ triggerId: originalTrigger, texts: verified, orders, translation: result.translation?.trigger_message_id === originalTrigger ? result.translation : null, translationUnavailable: Boolean(result.translation_error_code) });
          setStatus(en ? "Verified reply ready for review" : "回复已复核，请审阅");
          if (latest.current.composerRevision === originalRevision && latest.current.composerDraft === originalDraft && !latest.current.busy) {
            setEditing(0); latest.current.onUse(verified[0]);
          }
          if (orders.length) void loadCards(orders, requestId);
        }
        if (event === "error") {
          streamError = String(data.message ?? (en ? "AI suggestion review failed" : "AI 建议复核失败"));
          usableResult = false; setDrafts({}); setPlan(null); setCards([]); setStatus(streamError);
        }
        if (event === "done") {
          setDrafts({});
          if (!usableResult) setStatus((value) => streamError || (value.includes(en ? "No usable reply" : "未生成可用回复") ? value : en ? "No usable reply was generated; review required" : "未生成可用回复，需复核"));
        }
      }, active.signal, originalTrigger ?? undefined, "review_plan");
    } catch (caught) {
      if (current()) { setDrafts({}); setPlan(null); setCards([]); setStatus(caught instanceof Error ? caught.message : en ? "AI suggestion connection failed" : "AI 建议连接失败"); }
    } finally {
      if (current()) { setDrafts({}); setLoading(false); controller.current = null; }
    }
  }

  function cancelSuggestion() {
    controller.current?.abort(); controller.current = null; generation.current += 1;
    setLoading(false); setDrafts({}); setPlan(null); setCards([]); setCardError(""); setCardsLoading(false); setStatus(en ? "Generation cancelled" : "已取消生成");
  }

  function selectPart(index: number) {
    if (!plan || deliveryLocked) return;
    setPlan({ ...plan, texts }); setEditing(index); props.onUse(texts[index]);
  }

  function snapshot(): Submission {
    const request = { trigger_message_id: plan?.triggerId ?? null, parts, preview_only: false, confirmed: true };
    const signature = JSON.stringify(request);
    if (deliveryAttempt.current?.signature !== signature) deliveryAttempt.current = { signature, key: createIdempotencyKey() };
    return { request, key: deliveryAttempt.current.key };
  }

  async function deliver(attempt: Submission) {
    if (submitting || busy || (!attempt.request.preview_only && sendMode === "disabled")) return;
    const requestId = generation.current;
    setSubmitting(true); setConfirmation(null); setBatchStatus("");
    if (!attempt.request.preview_only) setSubmission(attempt);
    try {
      const result = await submitReplyBatch(sessionId, attempt.request, attempt.key);
      if (!mounted.current || requestId !== generation.current) return;
      setSubmission({ ...attempt, result });
      setBatchStatus(result.status === "previewed" ? (en ? "Preview complete; nothing sent to buyer" : "预演完成，未向买家发送")
        : result.status === "completed" ? (en ? "Delivery completed" : "交付完成")
          : result.status === "unknown" ? (en ? "Delivery unknown. Do not retry; reconcile first." : "交付结果未知，请勿重试，需先对账。")
            : result.status === "partial" ? (en ? "Partial delivery; review failed parts" : "部分交付成功，请核对失败项") : (en ? "Delivery failed; review each part" : "交付失败，请核对各项状态"));
      if (!result.preview_only && result.messages.length) latest.current.onDelivered(result.messages);
    } catch (caught) {
      if (!mounted.current || requestId !== generation.current) return;
      setSubmission(attempt.request.preview_only ? null : { ...attempt, result: { id: "", preview_only: false, status: "unknown", parts: [], messages: [] } });
      setBatchStatus(`${caught instanceof Error ? caught.message : en ? "Delivery request failed" : "交付请求失败"}${attempt.request.preview_only ? "" : en ? " · Result unknown; reconcile before retrying." : " · 结果未知，请先对账，勿盲目重试。"}`);
    } finally { if (mounted.current && requestId === generation.current) setSubmitting(false); }
  }

  const retryCards = submission?.result && !submission.result.preview_only && submission.result.status !== "unknown" && submission.result.parts.length === submission.request.parts.length && submission.result.parts.every((part) => part.kind !== "text" || ["sent", "delivered", "completed"].includes(part.status)) && submission.result.parts.some((part) => part.kind === "logistics_card" && part.status === "failed");
  return <section aria-label={en ? "Reply review" : "回复审阅"} className="reply-review-panel">
    <div className="reply-review-heading"><div><strong>{en ? "AI reply suggestion" : "AI 回复建议"}</strong><p aria-live="polite">{status || (en ? "Generate a draft on demand" : "按需生成草稿")}</p></div><div className="reply-review-actions">{loading ? <button className="text-button" onClick={cancelSuggestion} type="button">{en ? "Cancel" : "取消"}</button> : <button className="text-button" disabled={submitting || busy} onClick={() => void requestSuggestion()} type="button">{plan ? (en ? "Refresh" : "刷新") : (en ? "Generate" : "生成")}</button>}{plan ? <button aria-expanded={expanded} className="text-button" onClick={() => setExpanded(!expanded)} type="button">{expanded ? (en ? "Collapse review" : "收起审阅") : (en ? "Expand review" : "展开审阅")}</button> : null}</div></div>
    {autoPreview?.content ? <div className="reply-review-auto-preview" aria-label={en ? "Automatic suggestion preview" : "自动建议预演"}><div><strong>{en ? "Automatic suggestion · review only" : "自动建议 · 仅供审阅"}</strong><button type="button" className="text-button" disabled={busy || autoPreview.content.length > 2000} onClick={() => props.onUse(autoPreview.content!)}>{en ? "Use draft" : "使用草稿"}</button></div><p>{autoPreview.content}</p><small>{en ? "Nothing was sent to the buyer" : "未向买家发送消息"}</small></div> : autoPreview && ["pending", "processing"].includes(autoPreview.status) ? <p className="reply-review-auto-status" role="status">{en ? "Automatic suggestion is being prepared…" : "正在生成自动建议…"}</p> : null}
    {loading && Object.keys(drafts).length ? <div aria-label={en ? "Unverified draft" : "未复核生成草稿"} className="reply-review-body reply-review-unverified"><small>{en ? "Generating · unverified · unavailable for use or delivery" : "生成中 · 未复核 · 不可使用或发送"}</small>{Object.entries(drafts).sort(([left], [right]) => Number(left) - Number(right)).map(([index, text]) => <p key={index}>{text}</p>)}</div> : null}
    {plan && expanded ? <div className="reply-review-body"><p className="reply-review-binding">{en ? "Reply to buyer message" : "回复原买家消息"} · {plan.triggerId ?? (en ? "No buyer message" : "暂无买家消息")}</p><ol className="reply-review-parts">{texts.map((text, index) => <li data-reply-kind="text" key={`text-${index}`}><div><strong>{en ? `Text ${index + 1}` : `文字 ${index + 1}`}</strong><button className="text-button" disabled={loading || deliveryLocked || submitting || sendMode === "disabled"} onClick={() => selectPart(index)} type="button">{editing === index ? (en ? "Editing in composer" : "正在输入框编辑") : (en ? "Use" : "使用")}</button></div><p>{text}</p></li>)}{cards.map((card, index) => <li data-reply-kind="logistics_card" key={`${card.card.order_id}-${card.card.package_id}-${index}`}><strong>{en ? `Card ${index + 1} · after text` : `卡片 ${index + 1} · 文字之后`}</strong><TrackingCard {...card} en={en} sessionId={sessionId} translationEnabled={translationEnabled} /></li>)}</ol>{plan.translation?.draft_translation ? <details className="reply-review-translation"><summary>{en ? "Operator translation" : "坐席译文"} · {plan.translation.target_language === "en" ? (en ? "English" : "英语") : (en ? "Simplified Chinese" : "简体中文")}</summary><p>{plan.translation.draft_translation}</p><small>{en ? "For internal review only; applies to the generated draft before your edits." : "仅供内部复核，对应生成时草稿；编辑正文后请重新核对。"}</small></details> : plan.translationUnavailable ? <p className="reply-review-translation-note" role="status">{en ? "Operator translation unavailable. Review the customer reply." : "坐席译文暂不可用，请复核客户正文。"}</p> : null}{cardsLoading ? <p role="status">{en ? "Loading authorized logistics cards…" : "正在读取已授权物流卡片…"}</p> : null}{cardError ? <div role="alert">{cardError} <button className="text-button" disabled={submitting} onClick={() => void loadCards(plan.orders, generation.current)} type="button">{en ? "Retry card preview" : "重试卡片预览"}</button></div> : null}{invalid ? <p role="alert">{en ? "Each text must contain 1–2000 characters; total text limit is 16000. Edit before delivery." : "每段需为 1–2000 字符，文字总计不超过 16000；请在交付前编辑。"}</p> : null}<div className="reply-review-actions"><button className="secondary-button" disabled={batchDisabled || sendMode === "disabled"} onClick={() => setConfirmation(snapshot())} type="button">{en ? "Review batch delivery" : "审阅整组发送"}</button></div></div> : null}
    {batchStatus ? <p className="reply-review-result" role="status">{batchStatus}</p> : null}
    {submission?.result && !submission.result.preview_only ? <ol className="reply-review-delivery-status">{submission.result.parts.map((part) => <li key={part.index}>{part.index + 1}. {part.kind === "text" ? (en ? "Text" : "文字") : (en ? "Card" : "卡片")} · {part.status}{part.error_code ? ` · ${part.error_code}` : ""}</li>)}</ol> : null}
    {retryCards ? <button className="text-button" disabled={submitting || busy || sendMode === "disabled"} onClick={() => void deliver(submission!)} type="button">{en ? "Retry failed cards only" : "仅重试失败卡片"}</button> : null}
    {confirmation ? <dialog aria-label={en ? "Review reply batch" : "审阅整组回复"} aria-modal="true" className="action-dialog workspace-review-dialog reply-review-confirm-dialog" onCancel={() => setConfirmation(null)} ref={confirmationDialog}><h2>{en ? "Review reply batch" : "审阅整组回复"}</h2><p>{en ? "Recipient" : "收件人"}：{recipient}</p><ol className="reply-review-confirm-parts">{confirmation.request.parts.map((part, index) => <li key={index}>{part.kind === "text" ? part.content : `${en ? "Native logistics card" : "原生物流卡片"} · ${part.order_id} · ${part.package_id ?? ""}`}</li>)}</ol><p>{sendMode === "real" ? (en ? "Confirmation sends this exact ordered plan to the TikTok buyer." : "确认后将按以上顺序向该 TikTok 买家发送准确内容。") : (en ? "Confirmation simulates this exact ordered plan." : "确认后模拟按以上顺序发送准确内容。")}</p><div className="action-dialog-buttons"><button className="secondary-button" onClick={() => setConfirmation(null)} type="button">{en ? "Back to edit" : "返回修改"}</button><button className="primary-button" disabled={submitting || busy || sendMode === "disabled"} onClick={() => void deliver(confirmation)} type="button">{en ? "Confirm & send batch" : "确认发送整组"}</button></div></dialog> : null}
  </section>;
}

export function LogisticsNotificationPolicyControls({ storeId, agents }: { storeId: string; agents: AgentConfig[] }) {
  const [policy, setPolicy] = useState<LogisticsNotificationPolicy | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [agentId, setAgentId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [reload, setReload] = useState(0);
  const sequence = useRef(0);
  const eligible = agents.filter((agent) => agent.store_id === storeId && agent.status === "enabled" && agent.published_version !== null && agent.enabled_tools.includes("notify_logistics_update"));
  useEffect(() => {
    const requestId = ++sequence.current;
    let active = true;
    setLoading(true); setPolicy(null); setError(""); setNotice(""); setSaving(false);
    void getLogisticsNotificationPolicy(storeId).then((value) => {
      if (!active || requestId !== sequence.current) return;
      setPolicy(value); setEnabled(value.enabled); setAgentId(value.agent_id ?? "");
    }).catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "通知策略读取失败"); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; sequence.current += 1; };
  }, [storeId, reload]);
  async function save() {
    if (!policy || loading || saving || (enabled && !eligible.some((agent) => agent.id === agentId))) return;
    const requestId = sequence.current;
    setSaving(true); setError(""); setNotice("");
    try {
      const value = await saveLogisticsNotificationPolicy(storeId, { enabled, agent_id: agentId || null, mode: "preview", expected_revision: policy.revision });
      if (requestId === sequence.current) { setPolicy(value); setNotice("预演策略已保存；未开启真实通知"); }
    } catch (caught) { if (requestId === sequence.current) setError(caught instanceof Error ? caught.message : "通知策略保存失败"); }
    finally { if (requestId === sequence.current) setSaving(false); }
  }
  return <section aria-label="物流更新通知策略" className="reply-notification-policy"><h3>物流更新通知策略</h3><p>本次只保存预演策略。不会修改部署全局开关或启用真实通知。</p>{loading ? <p role="status">正在读取策略…</p> : null}{policy ? <p>{policy.global_enabled ? "全局通知已启用" : "全局通知未启用"} · {policy.real_delivery_enabled ? "真实外发已启用" : "真实外发未启用"} · 当前{policy.mode === "preview" ? "预演" : "外发"}模式 · 版本 {policy.revision}</p> : null}<label><input checked={enabled} disabled={loading || saving || !policy} onChange={(event) => { setEnabled(event.target.checked); setNotice(""); }} type="checkbox" />启用本店预演策略</label><label>通知 Agent<select disabled={loading || saving || !policy} onChange={(event) => { setAgentId(event.target.value); setNotice(""); }} value={agentId}><option value="">请选择同店已启用并发布物流通知工具的 Agent</option>{eligible.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</select></label>{!eligible.length ? <p>需先启用并发布绑定物流更新通知工具的同店 Agent。</p> : null}{error ? <p role="alert">{error}</p> : null}{notice ? <p role="status">{notice}</p> : null}<div className="reply-review-actions"><button className="secondary-button" disabled={loading || saving || !policy || (enabled && !eligible.some((agent) => agent.id === agentId))} onClick={() => void save()} type="button">{saving ? "保存中…" : "保存为预演策略"}</button><button className="text-button" disabled={saving || loading} onClick={() => setReload((value) => value + 1)} type="button">重新读取策略</button></div></section>;
}
