"use client";

import { KeyboardEvent, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, MapPin, Package, Star, Ticket, UserFocus, UserSwitch, X } from "@phosphor-icons/react";
import { AppShell } from "../../components/AppShell";
import { MessageBubble } from "../../components/MessageBubble";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { getLogistics, getSessionMessages, getSessionMessagesPage, issueCoupon, listSessionAssignees, listSessions, listStores, markSessionRead, sendMessage, setSessionClosed, setSessionStar, streamChatQuery, transferSession, updateShippingAddress, type SessionAssignee, type SessionListData, type SessionMessagesData, type StoreView, type Suggestion } from "../../lib/api";
import { useLanguage } from "../../lib/i18n";
import { formatConversationTime } from "../../lib/conversationTime";

type Filter = "all" | "unread" | "mine" | "starred" | "closed";
const filterLabels: Record<"zh" | "en", Record<Filter, string>> = {
  zh: { all: "全部", unread: "未读", mine: "我的", starred: "星标", closed: "已关闭" },
  en: { all: "All", unread: "Unread", mine: "Mine", starred: "Starred", closed: "Closed" },
};
const newKey = () => typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
const modeLabel = (mode: SessionMessagesData["send_mode"], en: boolean) => ({
  real: en ? "Real TikTok delivery" : "真实 TikTok 发送",
  mock: en ? "Simulated delivery" : "模拟发送",
  disabled: en ? "Delivery disabled" : "发送已关闭",
}[mode]);

export default function WorkspacePage() {
  const language = useLanguage();
  const en = language === "en";
  const [filter, setFilter] = useState<Filter>("all");
  const [platform, setPlatform] = useState("");
  const [storeId, setStoreId] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [list, setList] = useState<SessionListData | null>(null);
  const [stores, setStores] = useState<StoreView[]>([]);
  const [storeError, setStoreError] = useState("");
  const [detail, setDetail] = useState<SessionMessagesData | null>(null);
  const [detailError, setDetailError] = useState("");
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const draft = selectedId ? drafts[selectedId] ?? "" : "";
  const setDraft = (value: string) => { if (selectedId) setDrafts((current) => ({ ...current, [selectedId]: value })); };
  const [sending, setSending] = useState(false);
  const [failedDraft, setFailedDraft] = useState<{ content: string; key: string } | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [customerOpen, setCustomerOpen] = useState(false);
  const [suggestionDraft, setSuggestionDraft] = useState("");
  const [suggestionStatus, setSuggestionStatus] = useState("");
  const [suggestionLoading, setSuggestionLoading] = useState(false);
  const suggestionController = useRef<AbortController | null>(null);
  const listRequestId = useRef(0);
  const messageScrollRef = useRef<HTMLDivElement | null>(null);
  const stickToBottomRef = useRef(true);
  const pendingPrependRef = useRef<{ sessionId: string; height: number; top: number } | null>(null);
  const [showLatest, setShowLatest] = useState(false);
  const [transferOpen, setTransferOpen] = useState(false);
  const [assignees, setAssignees] = useState<SessionAssignee[]>([]);
  const [assigneeId, setAssigneeId] = useState("");
  const [transferError, setTransferError] = useState("");
  const [actionBusy, setActionBusy] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setSelectedId(params.get("session")); setPlatform(params.get("platform") ?? ""); setStoreId(params.get("store_id") ?? "");
    const savedFilter = params.get("filter");
    if (savedFilter === "unread" || savedFilter === "mine" || savedFilter === "starred" || savedFilter === "closed") setFilter(savedFilter);
  }, []);
  useEffect(() => () => suggestionController.current?.abort(), []);
  useEffect(() => {
    let active = true;
    listStores().then((items) => { if (active) { setStores(items); setStoreError(""); } })
      .catch(() => { if (active) setStoreError(en ? "Could not load stores. Refresh to retry." : "店铺加载失败，请刷新重试。"); });
    return () => { active = false; };
  }, [en]);

  const loadList = useCallback(async () => {
    const requestId = ++listRequestId.current;
    setLoading(true); setLoadingMore(false); setError("");
    const query = new URLSearchParams({ filter, page: "1", page_size: "30" });
    if (platform) query.set("platform", platform); if (storeId) query.set("store_id", storeId);
    try {
      const data = await listSessions(query);
      if (requestId !== listRequestId.current) return;
      setList(data);
      setSelectedId((current) => data.items.some((item) => item.id === current) ? current : data.items[0]?.id ?? null);
    } catch (caught) { if (requestId === listRequestId.current) setError(caught instanceof Error ? caught.message : en ? "Failed to load conversations" : "会话加载失败"); }
    finally { if (requestId === listRequestId.current) setLoading(false); }
  }, [en, filter, platform, storeId]);

  async function loadMoreConversations() {
    if (!list || loading || loadingMore || list.items.length >= list.pagination.total) return;
    const requestId = listRequestId.current;
    const page = list.pagination.page + 1;
    const query = new URLSearchParams({ filter, page: String(list.pagination.page + 1), page_size: "30" });
    if (platform) query.set("platform", platform); if (storeId) query.set("store_id", storeId);
    setLoadingMore(true);
    try {
      const next = await listSessions(query);
      if (requestId !== listRequestId.current) return;
      setList((current) => current?.pagination.page === page - 1 ? {
        ...next,
        items: [...current.items, ...next.items.filter((item) => !current.items.some((loaded) => loaded.id === item.id))],
      } : current);
    } catch (caught) {
      if (requestId === listRequestId.current) setAnnouncement(caught instanceof Error ? caught.message : en ? "Failed to load more conversations" : "加载更多会话失败");
    } finally {
      if (requestId === listRequestId.current) setLoadingMore(false);
    }
  }

  useEffect(() => { void loadList(); return () => { listRequestId.current += 1; }; }, [loadList]);
  useEffect(() => {
    let active = true;
    let refreshing = false;
    const requestId = listRequestId.current;
    const refresh = async () => {
      if (!active || refreshing || document.visibilityState !== "visible") return;
      refreshing = true;
      const query = new URLSearchParams({ filter, page: "1", page_size: "30" });
      if (platform) query.set("platform", platform);
      if (storeId) query.set("store_id", storeId);
      try {
        const freshList = await listSessions(query);
        if (!active || requestId !== listRequestId.current) return;
        // 保留已加载的较早会话与当前选中项；后台新消息只更新列表顶部。
        setList((current) => current ? {
          ...freshList,
          items: current.pagination.page > 1
            ? [...freshList.items, ...current.items.filter((item) => !freshList.items.some((fresh) => fresh.id === item.id))]
            : freshList.items,
          pagination: { ...freshList.pagination, page: current.pagination.page },
        } : freshList);
        if (selectedId) {
          const freshDetail = await getSessionMessages(selectedId);
          if (!active || requestId !== listRequestId.current) return;
          setDetail((current) => {
            if (current?.session.id !== selectedId) return current;
            const byId = new Map(current.messages.map((message) => [message.id, message]));
            for (const message of freshDetail.messages) byId.set(message.id, message);
            return {
              ...freshDetail,
              messages: [...byId.values()].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id)),
              pagination: { ...freshDetail.pagination, page: current.pagination.page },
            };
          });
          if (freshDetail.session.unread_count && stickToBottomRef.current && document.visibilityState === "visible") {
            void markSessionRead(selectedId).then(() => setList((current) => current ? {
              ...current, items: current.items.map((item) => item.id === selectedId ? { ...item, unread_count: 0 } : item),
            } : current)).catch(() => {});
          }
        }
      } catch {
        // 后台刷新失败时保留可操作的当前会话，下一轮继续尝试。
      } finally {
        refreshing = false;
      }
    };
    const timer = window.setInterval(() => { void refresh(); }, 5000);
    document.addEventListener("visibilitychange", refresh);
    return () => { active = false; window.clearInterval(timer); document.removeEventListener("visibilitychange", refresh); };
  }, [filter, platform, selectedId, storeId]);
  useEffect(() => {
    const params = new URLSearchParams();
    if (selectedId) params.set("session", selectedId); if (platform) params.set("platform", platform); if (storeId) params.set("store_id", storeId); if (filter !== "all") params.set("filter", filter);
    window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
  }, [filter, platform, selectedId, storeId]);

  useEffect(() => {
    suggestionController.current?.abort(); setSuggestionDraft(""); setSuggestionStatus(""); setSuggestionLoading(false);
    setFailedDraft(null); setTransferOpen(false); stickToBottomRef.current = true; pendingPrependRef.current = null; setShowLatest(false);
    setDetail(null); setDetailError("");
    if (!selectedId) return;
    let isCurrentRequest = true;
    getSessionMessages(selectedId).then((data) => {
      if (!isCurrentRequest) return;
      setDetail(data);
      if (data.session.unread_count && document.visibilityState === "visible") {
        void markSessionRead(selectedId).then(() => setList((current) => current ? { ...current, items: current.items.map((item) => item.id === selectedId ? { ...item, unread_count: 0 } : item) } : current));
      }
    }).catch((caught) => {
      if (!isCurrentRequest) return;
      const message = caught instanceof Error ? caught.message : en ? "Failed to load messages" : "消息加载失败";
      setDetailError(message); setAnnouncement(message);
    });
    // 快速切换会话时忽略旧请求结果，避免上一位客户的消息覆盖当前会话。
    return () => { isCurrentRequest = false; };
  }, [en, selectedId]);

  const newestMessageId = detail?.messages.at(-1)?.id;
  const messageCount = detail?.messages.length;
  useLayoutEffect(() => {
    const scroll = messageScrollRef.current;
    if (!scroll || detail?.session.id !== selectedId) return;
    const pending = pendingPrependRef.current;
    if (pending?.sessionId === selectedId) {
      scroll.scrollTop = pending.top + scroll.scrollHeight - pending.height;
      pendingPrependRef.current = null;
      return;
    }
    if (stickToBottomRef.current) { scroll.scrollTop = scroll.scrollHeight; setShowLatest(false); }
  }, [detail?.session.id, messageCount, newestMessageId, selectedId]);

  function onMessageScroll() {
    const scroll = messageScrollRef.current;
    if (!scroll) return;
    const nearBottom = scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 120;
    stickToBottomRef.current = nearBottom;
    setShowLatest(!nearBottom);
  }

  function scrollToLatest() {
    const scroll = messageScrollRef.current;
    if (!scroll) return;
    stickToBottomRef.current = true;
    scroll.scrollTo({ top: scroll.scrollHeight, behavior: "smooth" });
    setShowLatest(false);
    if (selectedId && detail?.session.unread_count) {
      const sessionId = selectedId;
      void markSessionRead(sessionId).then(() => {
        setList((current) => current ? { ...current, items: current.items.map((item) => item.id === sessionId ? { ...item, unread_count: 0 } : item) } : current);
        setDetail((current) => current?.session.id === sessionId ? { ...current, session: { ...current.session, unread_count: 0 } } : current);
      }).catch((caught) => setAnnouncement(caught instanceof Error ? caught.message : en ? "Could not mark messages as read" : "标记已读失败"));
    }
  }

  const messageLimit = detail?.send_mode === "real" ? 2000 : 4000;

  async function submitMessage(content = draft, key = newKey()) {
    if (!selectedId || !content.trim() || sending) return;
    if (!detail || detail.send_mode === "disabled") {
      setAnnouncement(en ? "Message delivery is disabled" : "当前平台消息发送已关闭");
      return;
    }
    const prompt = detail.send_mode === "real"
      ? (en ? "Send this message to the real TikTok customer? This action is audited and cannot be undone." : "确认将此消息发送给真实 TikTok 客户？该操作会被审计且不可撤销。")
      : (en ? "Run this simulated message delivery?" : "确认执行本次模拟消息发送？");
    if (!window.confirm(prompt)) return;
    const sessionId = selectedId;
    setSending(true); setFailedDraft(null);
    try {
      const message = await sendMessage(sessionId, content.trim(), key);
      setDetail((current) => current?.session.id === sessionId ? { ...current, messages: current.messages.some((item) => item.id === message.id) ? current.messages.map((item) => item.id === message.id ? message : item) : [...current.messages, message] } : current);
      setDrafts((current) => ({ ...current, [sessionId]: "" }));
      if (message.status === "sent") setAnnouncement(message.delivery_mode === "real" ? (en ? "Message sent to the real TikTok customer" : "消息已发送至真实 TikTok 客户") : (en ? "Simulated message sent" : "消息已模拟发送"));
      else if (message.status === "unknown") setAnnouncement(en ? "Delivery result is unknown. Do not retry; reconcile it in TikTok." : "发送结果未知，请勿重试并前往 TikTok 人工对账。");
      else setAnnouncement(en ? "The platform rejected the message" : "平台已拒绝本次消息发送");
    } catch (caught) { setFailedDraft({ content, key }); setAnnouncement(caught instanceof Error ? caught.message : en ? "Send failed" : "发送失败"); }
    finally { setSending(false); }
  }

  async function loadOlder() {
    if (!selectedId || !detail || detail.pagination.page <= 1 || loadingOlder) return;
    const sessionId = selectedId;
    setLoadingOlder(true);
    try {
      const older = await getSessionMessagesPage(sessionId, detail.pagination.page - 1);
      const scroll = messageScrollRef.current;
      if (scroll) pendingPrependRef.current = { sessionId, height: scroll.scrollHeight, top: scroll.scrollTop };
      setDetail((current) => current?.session.id === sessionId ? {
        ...current,
        messages: [...older.messages, ...current.messages.filter((message) => !older.messages.some((item) => item.id === message.id))],
        pagination: { ...current.pagination, page: older.pagination.page },
      } : current);
    } catch (caught) { setAnnouncement(caught instanceof Error ? caught.message : en ? "Failed to load older messages" : "较早消息加载失败"); }
    finally { setLoadingOlder(false); }
  }
  function composerKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void submitMessage(); }
  }

  async function showLogistics() {
    const order = detail?.recent_orders[0]; if (!order) { setAnnouncement(en ? "No order available" : "暂无可查询订单"); return; }
    try { const result = await getLogistics(order.id); setAnnouncement(en ? `Logistics: ${result.tracking_status ?? "No status"}; tracking number ${result.tracking_number ?? "Unavailable"}` : `物流：${result.tracking_status ?? "暂无状态"}，单号 ${result.tracking_number ?? "暂无"}`); }
    catch (caught) { setAnnouncement(caught instanceof Error ? caught.message : en ? "Logistics lookup failed" : "物流查询失败"); }
  }

  async function changeAddress() {
    const order = detail?.recent_orders[0]; if (!order) { setAnnouncement(en ? "No order can be updated" : "暂无可修改订单"); return; }
    const address = window.prompt(en ? "Enter the new address (Phase 3 uses a simulated submission)" : "请输入新的详细地址（Phase 3 为模拟提交）"); if (!address) return;
    if (!window.confirm(en ? "Submit the address change request? The simulated result will not overwrite the platform address." : "确认提交地址修改请求？模拟结果不会覆盖平台权威地址。")) return;
    try { const result = await updateShippingAddress(order.id, { recipient_name: detail?.customer.name ?? "Customer", address_line1: address, city: "Pending", postal_code: "000000", country_code: "CN" }, newKey()); setAnnouncement(result.mocked ? (en ? "Address change simulated; awaiting platform confirmation" : "地址修改已模拟提交，等待平台确认") : (en ? "Address change submitted" : "地址修改已提交")); }
    catch (caught) { setAnnouncement(caught instanceof Error ? caught.message : en ? "Address update failed" : "地址修改失败"); }
  }

  async function sendCouponToCustomer() {
    if (!detail) return; const code = window.prompt(en ? "Enter coupon code" : "请输入优惠券编码"); if (!code) return;
    if (!window.confirm(en ? `Issue coupon ${code} to this customer?` : `确认向该客户发放优惠券 ${code}？`)) return;
    try { const result = await issueCoupon(detail.customer.id, code, newKey()); setAnnouncement(result.mocked ? (en ? "Coupon issuance simulated" : "优惠券已模拟发放") : (en ? "Coupon issued" : "优惠券已发放")); }
    catch (caught) { setAnnouncement(caught instanceof Error ? caught.message : en ? "Coupon issuance failed" : "发券失败"); }
  }

  async function requestSuggestion() {
    if (!selectedId || suggestionLoading) return;
    suggestionController.current?.abort(); const controller = new AbortController(); suggestionController.current = controller;
    setSuggestionDraft(""); setSuggestionStatus(en ? "Connecting…" : "正在连接…"); setSuggestionLoading(true);
    let streamErrorMessage = "";
    try {
      await streamChatQuery(selectedId, ({ event, data }) => {
        if (event === "status") setSuggestionStatus(String(data.stage ?? (en ? "Processing…" : "处理中…")));
        if (event === "delta") setSuggestionDraft((current) => current + String(data.text ?? ""));
        if (event === "result") {
          const result = data as unknown as Suggestion;
          setSuggestionDraft(result.content ?? "");
          // 只填入空草稿；已有人工输入必须保留。真实发送仍需人工确认。
          const content = result.content;
          if (selectedId && content) setDrafts((current) => current[selectedId] ? current : { ...current, [selectedId]: content });
        }
        if (event === "error") { streamErrorMessage = String(data.message ?? (en ? "Failed to generate AI suggestion" : "AI 建议生成失败")); setSuggestionStatus(streamErrorMessage); }
        if (event === "done") setSuggestionStatus(data.reason === "completed" ? (en ? "Suggestion generated" : "建议已生成") : streamErrorMessage || (en ? "Connection ended; retry is available" : "连接已结束，可重试"));
      }, controller.signal);
    } catch (caught) { if (!controller.signal.aborted) setSuggestionStatus(caught instanceof Error ? caught.message : en ? "AI suggestion connection failed" : "AI 建议连接失败"); }
    finally { if (suggestionController.current === controller) suggestionController.current = null; setSuggestionLoading(false); }
  }

  function cancelSuggestion() {
    suggestionController.current?.abort(); suggestionController.current = null; setSuggestionLoading(false);
    setSuggestionStatus(en ? "Generation cancelled" : "已取消生成");
    setAnnouncement(en ? "AI suggestion generation cancelled" : "已取消 AI 建议生成");
  }

  async function changeStar() {
    if (!detail || actionBusy) return;
    const sessionId = detail.session.id;
    setActionBusy(true);
    try {
      const result = await setSessionStar(sessionId, !detail.session.is_starred);
      setDetail((current) => current?.session.id === sessionId ? { ...current, session: { ...current.session, ...result } } : current);
      setList((current) => current ? { ...current, items: current.items.map((item) => item.id === sessionId ? { ...item, ...result } : item) } : current);
      setAnnouncement(result.is_starred ? (en ? "Marked as review risk" : "已标记差评风险") : (en ? "Review risk mark removed" : "已取消差评风险标记"));
    } catch (caught) { setAnnouncement(caught instanceof Error ? caught.message : en ? "Could not update mark" : "更新标记失败"); }
    finally { setActionBusy(false); }
  }

  async function changeClosed() {
    if (!detail || actionBusy) return;
    const sessionId = detail.session.id;
    const closed = detail.session.status !== "closed";
    if (closed && !window.confirm(en ? "Close this conversation in CRM?" : "确认在 CRM 中关闭该会话？")) return;
    setActionBusy(true);
    try {
      const result = await setSessionClosed(sessionId, closed);
      setDetail((current) => current?.session.id === sessionId ? { ...current, session: { ...current.session, ...result }, send_mode: closed ? "disabled" : current.send_mode } : current);
      setList((current) => current ? { ...current, items: current.items.map((item) => item.id === sessionId ? { ...item, ...result } : item) } : current);
      await loadList();
      if (!closed) {
        const fresh = await getSessionMessages(sessionId);
        setDetail((current) => current?.session.id === sessionId ? fresh : current);
      }
      setAnnouncement(closed ? (en ? "Conversation closed" : "会话已关闭") : (en ? "Conversation reopened" : "会话已重新打开"));
    } catch (caught) { setAnnouncement(caught instanceof Error ? caught.message : en ? "Could not change conversation status" : "变更会话状态失败"); }
    finally { setActionBusy(false); }
  }

  async function openTransfer() {
    if (!detail || actionBusy || detail.session.status === "closed") return;
    setTransferError(""); setAssignees([]); setAssigneeId(""); setTransferOpen(true);
    try { setAssignees(await listSessionAssignees(detail.session.id)); }
    catch (caught) { setTransferError(caught instanceof Error ? caught.message : en ? "Could not load agents" : "坐席加载失败"); }
  }

  async function confirmTransfer() {
    if (!detail || !assigneeId || actionBusy) return;
    const sessionId = detail.session.id;
    setActionBusy(true); setTransferError("");
    try {
      await transferSession(sessionId, en ? "Transferred from customer workspace" : "客服工作台转交会话", newKey(), assigneeId);
      setTransferOpen(false);
      await loadList();
      const fresh = await getSessionMessages(sessionId);
      setDetail((current) => current?.session.id === sessionId ? fresh : current);
      setAnnouncement(en ? "Conversation transferred" : "会话已转交");
    } catch (caught) { setTransferError(caught instanceof Error ? caught.message : en ? "Transfer failed" : "转交失败"); }
    finally { setActionBusy(false); }
  }

  return <AppShell><main className={`workspace-grid ${selectedId ? "has-selection" : ""}`}>
    <section className="conversation-panel" aria-label={en ? "Conversation list" : "会话列表"}>
      <div className="panel-heading"><div><p className="eyebrow">INBOX</p><h2 className="text-xl font-semibold">{en ? "Customer messages" : "客户消息"}</h2></div><span className="count-pill">{list?.pagination.total ?? 0}</span></div>
      <div className="filter-row" aria-label={en ? "Conversation filters" : "会话筛选"}>{(["all", "unread", "mine", "starred", "closed"] as Filter[]).map((item) => <button aria-pressed={filter === item} className={filter === item ? "filter active" : "filter"} key={item} onClick={() => setFilter(item)} type="button">{filterLabels[language][item]}</button>)}</div>
      <div className="grid grid-cols-2 gap-2 border-b border-[var(--border)] p-3"><select aria-label={en ? "Platform" : "平台"} className="compact-field" onChange={(event) => setPlatform(event.target.value)} value={platform}><option value="">{en ? "All platforms" : "全部平台"}</option><option value="tiktok">TikTok</option><option value="shopee">Shopee</option><option value="amazon">Amazon</option></select><select aria-label={en ? "Store" : "店铺"} className="compact-field" onChange={(event) => setStoreId(event.target.value)} value={storeId}><option value="">{en ? "All stores" : "全部店铺"}</option>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}{storeId && !stores.some((store) => store.id === storeId) ? <option value={storeId}>{en ? "Store name unavailable" : "店铺名称不可用"}</option> : null}</select>{storeError ? <p className="col-span-2 text-xs text-red-600" role="alert">{storeError}</p> : null}</div>
      <div className="conversation-scroll">{loading ? <LoadingState label={en ? "Loading conversations…" : "正在加载会话…"} /> : error ? <ErrorState message={error} retry={() => void loadList()} /> : !list?.items.length ? <EmptyState label={en ? "Conversations will appear when platform messages arrive" : "暂无会话，平台消息到达后会显示在这里"} /> : <>{list.items.map((item) => {
        const lastMessageTime = formatConversationTime(item.last_message_at, en ? "en-US" : "zh-CN");
        return <button aria-pressed={selectedId === item.id} className={selectedId === item.id ? "conversation-card active" : "conversation-card"} key={item.id} onClick={() => setSelectedId(item.id)} type="button">
          <span className="avatar">{item.customer.name?.slice(0, 1) ?? "?"}</span>
          <span className="min-w-0 flex-1 text-left">
            <span className="flex items-center justify-between gap-2"><strong className="truncate text-sm">{item.customer.name ?? (en ? "Anonymous customer" : "匿名客户")}</strong>{lastMessageTime ? <time className="conversation-time" dateTime={item.last_message_at ?? undefined}>{lastMessageTime}</time> : null}</span>
            <span className="mt-1 flex items-center justify-between gap-2"><span className="min-w-0 truncate text-sm text-[var(--muted)]">{item.last_message ?? (en ? "No messages" : "暂无消息")}</span><span className="conversation-indicators">{item.is_starred ? <Star aria-label={en ? "Review risk" : "差评风险"} size={14} weight="fill" /> : null}<small className={`platform-badge platform-${item.platform}`}>{item.platform}</small>{item.unread_count > 0 ? <span className="unread" aria-label={en ? `${item.unread_count} unread messages` : `${item.unread_count} 条未读消息`}>{item.unread_count > 99 ? "99+" : item.unread_count}</span> : null}</span></span>
          </span>
        </button>;
      })}{list.items.length < list.pagination.total ? <button className="secondary-button mx-auto my-3 flex" disabled={loadingMore} onClick={() => void loadMoreConversations()} type="button">{loadingMore ? (en ? "Loading…" : "加载中…") : (en ? "Load more conversations" : "加载更多会话")}</button> : null}</>}</div>
    </section>

    <section className="chat-panel" aria-label={en ? "Chat window" : "聊天窗口"}>{!selectedId ? <EmptyState label={en ? "Select a conversation" : "请选择一个会话"} /> : detailError ? <ErrorState message={detailError} /> : !detail ? <LoadingState label={en ? "Loading messages…" : "正在加载消息…"} /> : <>
      <header className="chat-heading"><button className="mobile-back" onClick={() => setSelectedId(null)} type="button" aria-label={en ? "Back to conversation list" : "返回会话列表"}><ArrowLeft size={20} /></button><div className="min-w-0"><h2 className="truncate font-semibold">{detail.customer.name ?? (en ? "Anonymous customer" : "匿名客户")}</h2><p className="text-xs text-[var(--muted)]">{detail.session.platform} · {detail.session.status} · {modeLabel(detail.send_mode, en)}</p></div><div className="chat-actions"><button aria-label={detail.session.is_starred ? (en ? "Remove review risk mark" : "取消差评风险标记") : (en ? "Mark review risk" : "标记差评风险")} aria-pressed={detail.session.is_starred} className="icon-action" disabled={actionBusy} onClick={() => void changeStar()} title={en ? "Review risk" : "差评风险"} type="button"><Star size={19} weight={detail.session.is_starred ? "fill" : "regular"} /></button><button aria-label={en ? "Transfer conversation" : "转交会话"} className="icon-action" disabled={actionBusy || detail.session.status === "closed"} onClick={() => void openTransfer()} title={en ? "Transfer" : "转交会话"} type="button"><UserSwitch size={19} /></button><button aria-label={detail.session.status === "closed" ? (en ? "Reopen conversation" : "重新打开会话") : (en ? "Close conversation" : "关闭会话")} className="icon-action" disabled={actionBusy} onClick={() => void changeClosed()} title={detail.session.status === "closed" ? (en ? "Reopen" : "重新打开") : (en ? "Close" : "关闭会话")} type="button">{detail.session.status === "closed" ? <ArrowRight size={19} /> : <X size={19} />}</button><button className="secondary-button" onClick={() => setCustomerOpen(true)} type="button"><UserFocus size={17} />{en ? "Customer details" : "客户信息"}</button></div></header>
      <div className="message-area"><div className="message-scroll" onScroll={onMessageScroll} ref={messageScrollRef}>{detail.pagination.page > 1 ? <button className="secondary-button self-center" disabled={loadingOlder} onClick={() => void loadOlder()} type="button">{loadingOlder ? (en ? "Loading…" : "加载中…") : (en ? "Load older messages" : "加载更早消息")}</button> : null}{detail.messages.length ? detail.messages.map((message) => <MessageBubble en={en} key={message.id} message={message} sessionId={detail.session.id} translationEnabled={detail.translation_enabled === true} />) : <EmptyState label={en ? "No messages in this conversation" : "该会话暂无消息"} />}</div>{showLatest ? <button className="latest-button" onClick={scrollToLatest} type="button"><ArrowDown size={16} />{en ? "Latest message" : "到最新消息"}</button> : null}</div>
      <section className="ai-suggestion" aria-label={en ? "AI suggestion" : "AI 建议"}><div className="min-w-0 flex-1"><strong>{en ? "AI reply suggestion" : "AI 回复建议"}</strong><p aria-live="polite" className="truncate">{suggestionStatus || (suggestionDraft ? (en ? "Suggestion is ready in the draft" : "建议已填入草稿，可编辑后发送") : (en ? "Generate a draft on demand" : "按需生成草稿"))}</p></div><div className="flex gap-2">{suggestionLoading ? <button className="text-button" type="button" onClick={cancelSuggestion}><X size={16} />{en ? "Cancel" : "取消"}</button> : <button className="text-button" type="button" onClick={() => void requestSuggestion()}>{suggestionDraft ? (en ? "Refresh" : "刷新") : (en ? "Generate" : "生成")}</button>}{suggestionDraft && draft !== suggestionDraft ? <button className="secondary-button" type="button" onClick={() => { setDraft(suggestionDraft); setAnnouncement(en ? "Suggestion inserted; review it before sending" : "建议已填入输入框，确认后再发送"); }}>{en ? "Use" : "使用"}</button> : null}</div></section>
      <div className="composer"><textarea aria-label={en ? "Reply content" : "回复内容"} disabled={detail.send_mode === "disabled"} maxLength={messageLimit} onChange={(event) => setDraft(event.target.value)} onKeyDown={composerKey} placeholder={detail.send_mode === "disabled" ? (en ? "Message delivery is disabled" : "当前平台消息发送已关闭") : (en ? "Type a reply. Enter to review and confirm; Shift+Enter for a new line" : "输入回复，Enter 进入确认，Shift+Enter 换行")} value={draft} />{failedDraft ? <button className="text-button text-red-600" onClick={() => void submitMessage(failedDraft.content, failedDraft.key)} type="button">{en ? "Request interrupted; confirm retry" : "请求中断，确认后重试"}</button> : null}<div className="flex items-center justify-between"><small className="text-[var(--muted)]">{modeLabel(detail.send_mode, en)} · {draft.length}/{messageLimit}</small><button className="primary-button" disabled={!draft.trim() || sending || detail.send_mode === "disabled"} onClick={() => void submitMessage()} type="button">{sending ? (en ? "Sending…" : "发送中…") : (en ? "Review & send" : "确认并发送")}</button></div></div>
    </>}</section>

    <aside className={`customer-panel ${customerOpen ? "open" : ""}`} aria-label={en ? "Customer and quick actions" : "客户与快捷操作"}><button aria-label={en ? "Close customer details" : "关闭客户信息"} className="drawer-close" onClick={() => setCustomerOpen(false)} type="button"><X size={21} /></button>{detail ? <><div className="customer-profile"><span className="avatar large">{detail.customer.name?.slice(0, 1) ?? "?"}</span><h2>{detail.customer.name ?? (en ? "Anonymous customer" : "匿名客户")}</h2><p>{detail.customer.email ?? (en ? "Email not provided" : "未提供邮箱")}</p>{detail.customer.tags.length ? <div className="customer-tags">{detail.customer.tags.map((tag) => <span className="status-badge" key={tag}>{tag}</span>)}</div> : null}</div><section className="side-section"><h3>{en ? "Quick actions" : "快捷操作"}</h3><button className="action-row" onClick={() => void showLogistics()} type="button"><span><Package size={17} />{en ? "Check logistics" : "查询物流"}</span><ArrowRight size={16} /></button><button className="action-row" onClick={() => void changeAddress()} type="button"><span><MapPin size={17} />{en ? "Change address" : "修改地址"}</span><ArrowRight size={16} /></button><button className="action-row" onClick={() => void sendCouponToCustomer()} type="button"><span><Ticket size={17} />{en ? "Issue coupon" : "发优惠券"}</span><ArrowRight size={16} /></button></section><section className="side-section"><h3>{en ? "Recent orders" : "最近订单"}</h3>{detail.recent_orders.length ? detail.recent_orders.map((order) => <div className="order-card" key={order.id}><strong>{order.external_order_id}</strong><span>{order.currency} {order.total_amount}</span><small>{order.status}{order.tracking_status ? ` · ${order.tracking_status}` : ""}</small></div>) : <p className="text-sm text-[var(--muted)]">{en ? "No orders" : "暂无订单"}</p>}</section></> : <EmptyState label={en ? "Select a conversation to view customer details" : "选择会话后查看客户信息"} />}</aside>
    {customerOpen ? <button aria-label={en ? "Close drawer overlay" : "关闭抽屉遮罩"} className="drawer-backdrop" onClick={() => setCustomerOpen(false)} type="button" /> : null}
    {transferOpen ? <div className="action-dialog-backdrop" role="presentation"><section aria-label={en ? "Transfer conversation" : "转交会话"} aria-modal="true" className="action-dialog" role="dialog"><h2>{en ? "Transfer conversation" : "转交会话"}</h2><p>{en ? "Choose an agent who can access this store." : "选择有当前店铺权限的坐席。"}</p><select aria-label={en ? "Target agent" : "目标坐席"} className="compact-field" onChange={(event) => setAssigneeId(event.target.value)} value={assigneeId}><option value="">{en ? "Select an agent" : "请选择坐席"}</option>{assignees.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</select>{transferError ? <p role="alert">{transferError}</p> : null}<div className="action-dialog-buttons"><button className="secondary-button" onClick={() => setTransferOpen(false)} type="button">{en ? "Cancel" : "取消"}</button><button className="primary-button" disabled={!assigneeId || actionBusy} onClick={() => void confirmTransfer()} type="button">{en ? "Confirm transfer" : "确认转交"}</button></div></section></div> : null}
  </main><div aria-live="polite" className="sr-only">{announcement}</div></AppShell>;
}
