"use client";

import { KeyboardEvent, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, CaretDown, CaretRight, Heart, ImageSquare, MagnifyingGlass, NotePencil, Smiley, Star, UserFocus, UserSwitch, Video, X } from "@phosphor-icons/react";
import { AppShell } from "../../components/AppShell";
import { CustomerSidebar } from "../../components/CustomerSidebar";
import { MessageBubble } from "../../components/MessageBubble";
import { QuickReplyPicker } from "../../components/QuickReplyPicker";
import { resolveQuickReplyShortcut } from "../../lib/reception";
import { TrackingCard } from "../../components/TrackingCard";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { getSessionMessages, getSessionMessagesPage, listSessionAssignees, listSessions, listStores, markSessionRead, sendLogisticsCard, sendMessage, setSessionClosed, setSessionStar, streamChatQuery, transferSession, translateDraft, type DraftTargetLanguage, type LogisticsCardDraft, type SessionAssignee, type SessionListData, type SessionMessagesData, type StoreView, type Suggestion } from "../../lib/api";
import { useLanguage } from "../../lib/i18n";
import { formatConversationTime } from "../../lib/conversationTime";
import "./quick-reply.css";

type Filter = "all" | "unread" | "mine" | "starred" | "closed";
type SearchScope = "all" | "buyer" | "order" | "tracking" | "product";
type ReplyLanguage = "original" | DraftTargetLanguage;
type SendChoice = "direct" | "translated";
const replyLanguages: Array<{ value: ReplyLanguage; zh: string; en: string }> = [
  { value: "original", zh: "不翻译 · 原文", en: "Original · no translation" },
  { value: "en", zh: "英语", en: "English" },
  { value: "id", zh: "印尼语", en: "Indonesian" },
  { value: "fil", zh: "菲律宾语", en: "Filipino" },
  { value: "ms", zh: "马来语", en: "Malay" },
  { value: "th", zh: "泰语", en: "Thai" },
  { value: "my", zh: "缅甸语", en: "Burmese" },
  { value: "vi", zh: "越南语", en: "Vietnamese" },
  { value: "pt", zh: "葡萄牙语", en: "Portuguese" },
  { value: "es", zh: "西班牙语", en: "Spanish" },
  { value: "pl", zh: "波兰语", en: "Polish" },
  { value: "fr", zh: "法语", en: "French" },
  { value: "zh-TW", zh: "中文繁体", en: "Traditional Chinese" },
  { value: "zh-CN", zh: "中文简体", en: "Simplified Chinese" },
];
const filterLabels: Record<"zh" | "en", Record<Filter, string>> = {
  zh: { all: "全部", unread: "未读", mine: "我的", starred: "星标", closed: "已关闭" },
  en: { all: "All", unread: "Unread", mine: "Mine", starred: "Starred", closed: "Closed" },
};
const newKey = () => typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
const searchTerms = (value: string) => [...new Set(value.split(/[\n,，;；]+/).map((term) => term.trim()).filter(Boolean))];
const markReadInList = (current: SessionListData | null, sessionId: string) => current ? {
  ...current,
  unread_messages_total: Math.max(0, current.unread_messages_total - (current.items.find((item) => item.id === sessionId)?.unread_count ?? 0)),
  items: current.items.map((item) => item.id === sessionId ? { ...item, unread_count: 0 } : item),
} : current;
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
  const [searchScope, setSearchScope] = useState<SearchScope>("all");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [list, setList] = useState<SessionListData | null>(null);
  const [stores, setStores] = useState<StoreView[]>([]);
  const [storeError, setStoreError] = useState("");
  const [detail, setDetail] = useState<SessionMessagesData | null>(null);
  const [detailError, setDetailError] = useState("");
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [cardDrafts, setCardDrafts] = useState<Record<string, LogisticsCardDraft | undefined>>({});
  const draft = selectedId ? drafts[selectedId] ?? "" : "";
  const cardDraft = selectedId ? cardDrafts[selectedId] : undefined;
  const setDraft = (value: string) => { if (selectedId) { setDrafts((current) => ({ ...current, [selectedId]: value })); setCardDrafts((current) => ({ ...current, [selectedId]: undefined })); setFailedDraft(null); } };
  const [sending, setSending] = useState(false);
  const [failedDraft, setFailedDraft] = useState<{ sessionId: string; content: string; key: string } | null>(null);
  const [failedCard, setFailedCard] = useState<{ sessionId: string; draft: LogisticsCardDraft; key: string } | null>(null);
  const [cardReview, setCardReview] = useState<{ sessionId: string; draft: LogisticsCardDraft; key: string } | null>(null);
  useEffect(() => { setCardReview(null); }, [selectedId]);
  const [replyLanguage, setReplyLanguage] = useState<DraftTargetLanguage>("en");
  const [sendChoice, setSendChoice] = useState<SendChoice>("translated");
  const [languageMenuOpen, setLanguageMenuOpen] = useState(false);
  const [moreLanguagesOpen, setMoreLanguagesOpen] = useState(false);
  const [moreLanguagesLeft, setMoreLanguagesLeft] = useState(false);
  const [sendMenuOpen, setSendMenuOpen] = useState(false);
  const composerMenusRef = useRef<HTMLDivElement | null>(null);
  const currentComposeRef = useRef({ sessionId: selectedId, draft, language: replyLanguage, choice: sendChoice, translationEnabled: detail?.draft_translation_enabled === true });
  const [preview, setPreview] = useState<{ sessionId: string; source: string; language: DraftTargetLanguage; content: string } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const previewRequestId = useRef(0);
  const [review, setReview] = useState<{ sessionId: string; source: string; language: ReplyLanguage; content: string; key: string } | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [quickReplyOpen, setQuickReplyOpen] = useState(false);
  const [quickReplyFavoritesOnly, setQuickReplyFavoritesOnly] = useState(false);
  const [quickReplyQuery, setQuickReplyQuery] = useState("");
  const [emojiOpen, setEmojiOpen] = useState(false);
  const [composerNotice, setComposerNotice] = useState("");
  const [customerOpen, setCustomerOpen] = useState(false);
  const [suggestionDraft, setSuggestionDraft] = useState("");
  const [suggestionStatus, setSuggestionStatus] = useState("");
  const [suggestionLoading, setSuggestionLoading] = useState(false);
  const suggestionController = useRef<AbortController | null>(null);
  const listRequestId = useRef(0);
  const conversationScrollRef = useRef<HTMLDivElement | null>(null);
  const loadingMoreRef = useRef(false);
  const messageScrollRef = useRef<HTMLDivElement | null>(null);
  const stickToBottomRef = useRef(true);
  const pendingPrependRef = useRef<{ sessionId: string; height: number; top: number } | null>(null);
  const [showLatest, setShowLatest] = useState(false);
  const [transferOpen, setTransferOpen] = useState(false);
  const [assignees, setAssignees] = useState<SessionAssignee[]>([]);
  const [assigneeId, setAssigneeId] = useState("");
  const [transferError, setTransferError] = useState("");
  const [actionBusy, setActionBusy] = useState(false);
  const [closeConfirmId, setCloseConfirmId] = useState<string | null>(null);
  const [closeError, setCloseError] = useState("");
  const closeDialogRef = useRef<HTMLDialogElement | null>(null);

  useEffect(() => { setQuickReplyOpen(false); setEmojiOpen(false); setComposerNotice(""); }, [selectedId]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setSelectedId(params.get("session")); setPlatform(params.get("platform") ?? ""); setStoreId(params.get("store_id") ?? "");
    const savedFilter = params.get("filter");
    if (savedFilter === "unread" || savedFilter === "mine" || savedFilter === "starred" || savedFilter === "closed") setFilter(savedFilter);
  }, []);
  useEffect(() => () => suggestionController.current?.abort(), []);
  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);
  useEffect(() => {
    previewRequestId.current += 1;
    setPreview(null); setPreviewError(""); setPreviewLoading(false);
    setReview((current) => current?.sessionId === selectedId && current.source === draft && (current.language === "original" || current.language === replyLanguage) ? current : null);
  }, [draft, replyLanguage, selectedId]);
  useEffect(() => {
    const dialog = closeDialogRef.current;
    if (!dialog || closeConfirmId !== detail?.session.id) return;
    if (!dialog.open) dialog.showModal();
    return () => { if (dialog.open) dialog.close(); };
  }, [closeConfirmId, detail?.session.id]);
  useLayoutEffect(() => {
    currentComposeRef.current = { sessionId: selectedId, draft, language: replyLanguage, choice: sendChoice, translationEnabled: detail?.draft_translation_enabled === true };
  }, [selectedId, draft, replyLanguage, sendChoice, detail?.draft_translation_enabled]);
  useEffect(() => {
    const closeMenus = (event: PointerEvent) => {
      if (!composerMenusRef.current?.contains(event.target as Node)) {
        setLanguageMenuOpen(false); setSendMenuOpen(false); setMoreLanguagesOpen(false);
      }
    };
    const closeOnEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") { setLanguageMenuOpen(false); setSendMenuOpen(false); setMoreLanguagesOpen(false); }
    };
    document.addEventListener("pointerdown", closeMenus);
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("pointerdown", closeMenus); document.removeEventListener("keydown", closeOnEscape); };
  }, []);
  useEffect(() => {
    let active = true;
    listStores().then((items) => { if (active) { setStores(items); setStoreError(""); } })
      .catch(() => { if (active) setStoreError(en ? "Could not load stores. Refresh to retry." : "店铺加载失败，请刷新重试。"); });
    return () => { active = false; };
  }, [en]);

  const buildListQuery = useCallback((page: number) => {
    const query = new URLSearchParams({ filter, page: String(page), page_size: "30" });
    if (platform) query.set("platform", platform);
    if (storeId) query.set("store_id", storeId);
    const terms = searchTerms(search);
    if (terms.length > 1) { query.set("search_scope", searchScope); terms.forEach((term) => query.append("term", term)); }
    else if (terms.length === 1) { query.set("search_scope", searchScope); query.set("q", terms[0]); }
    return query;
  }, [filter, platform, search, searchScope, storeId]);

  const loadList = useCallback(async () => {
    const requestId = ++listRequestId.current;
    setLoading(true); setLoadingMore(false); setLoadMoreError(""); setError("");
    const query = buildListQuery(1);
    try {
      const data = await listSessions(query);
      if (requestId !== listRequestId.current) return;
      setList(data);
      setSelectedId((current) => data.items.some((item) => item.id === current) ? current : data.items[0]?.id ?? null);
    } catch (caught) { if (requestId === listRequestId.current) setError(caught instanceof Error ? caught.message : en ? "Failed to load conversations" : "会话加载失败"); }
    finally { if (requestId === listRequestId.current) setLoading(false); }
  }, [buildListQuery, en]);

  const loadMoreConversations = useCallback(async () => {
    if (!list || loading || loadingMoreRef.current || list.items.length >= list.pagination.total) return;
    loadingMoreRef.current = true;
    const requestId = listRequestId.current;
    const page = list.pagination.page + 1;
    const query = buildListQuery(page);
    setLoadMoreError("");
    setLoadingMore(true);
    try {
      const next = await listSessions(query);
      if (requestId !== listRequestId.current) return;
      setList((current) => current?.pagination.page === page - 1 ? {
        ...next,
        items: [...current.items, ...next.items.filter((item) => !current.items.some((loaded) => loaded.id === item.id))],
      } : current);
    } catch (caught) {
      if (requestId === listRequestId.current) setLoadMoreError(caught instanceof Error ? caught.message : en ? "Failed to load more conversations" : "加载更多会话失败");
    } finally {
      loadingMoreRef.current = false;
      if (requestId === listRequestId.current) setLoadingMore(false);
    }
  }, [list, loading, buildListQuery, en]);

  useEffect(() => {
    const node = conversationScrollRef.current;
    if (node && !loadingMore && !loadMoreError && list && list.items.length < list.pagination.total && node.scrollHeight - node.scrollTop - node.clientHeight < 100) void loadMoreConversations();
  }, [list, loadingMore, loadMoreError, loadMoreConversations]);

  useEffect(() => { void loadList(); return () => { listRequestId.current += 1; }; }, [loadList]);
  useEffect(() => {
    let active = true;
    let refreshing = false;
    const requestId = listRequestId.current;
    const refresh = async () => {
      if (!active || refreshing || document.visibilityState !== "visible") return;
      refreshing = true;
      const query = buildListQuery(1);
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
            void markSessionRead(selectedId).then(() => setList((current) => markReadInList(current, selectedId))).catch(() => {});
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
  }, [buildListQuery, selectedId]);
  useEffect(() => {
    const params = new URLSearchParams();
    if (selectedId) params.set("session", selectedId); if (platform) params.set("platform", platform); if (storeId) params.set("store_id", storeId); if (filter !== "all") params.set("filter", filter);
    window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
  }, [filter, platform, selectedId, storeId]);

  useEffect(() => {
    suggestionController.current?.abort(); setSuggestionDraft(""); setSuggestionStatus(""); setSuggestionLoading(false);
    setTransferOpen(false); setCloseConfirmId(null); setCloseError(""); stickToBottomRef.current = true; pendingPrependRef.current = null; setShowLatest(false);
    setDetail(null); setDetailError("");
    if (!selectedId) return;
    let isCurrentRequest = true;
    getSessionMessages(selectedId).then((data) => {
      if (!isCurrentRequest) return;
      setDetail(data);
      if (data.session.unread_count && document.visibilityState === "visible") {
        void markSessionRead(selectedId).then(() => setList((current) => markReadInList(current, selectedId)));
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
        setList((current) => markReadInList(current, sessionId));
        setDetail((current) => current?.session.id === sessionId ? { ...current, session: { ...current.session, unread_count: 0 } } : current);
      }).catch((caught) => setAnnouncement(caught instanceof Error ? caught.message : en ? "Could not mark messages as read" : "标记已读失败"));
    }
  }

  const messageLimit = 2000;
  const activeSendChoice: SendChoice = detail?.draft_translation_enabled ? sendChoice : "direct";

  async function submitMessage(content: string, key: string, sessionId: string) {
    if (!selectedId || selectedId !== sessionId || !content.trim() || sending) return;
    if (!detail || detail.send_mode === "disabled") {
      setAnnouncement(en ? "Message delivery is disabled" : "当前平台消息发送已关闭");
      return;
    }
    setReview(null);
    setSending(true); setFailedDraft(null);
    try {
      const message = await sendMessage(sessionId, content.trim(), key);
      setDetail((current) => current?.session.id === sessionId ? { ...current, messages: current.messages.some((item) => item.id === message.id) ? current.messages.map((item) => item.id === message.id ? message : item) : [...current.messages, message] } : current);
      setDrafts((current) => ({ ...current, [sessionId]: "" }));
      if (message.status === "sent") setAnnouncement(message.delivery_mode === "real" ? (en ? "Message sent to the real TikTok customer" : "消息已发送至真实 TikTok 客户") : (en ? "Simulated message sent" : "消息已模拟发送"));
      else if (message.status === "unknown") setAnnouncement(en ? "Delivery result is unknown. Do not retry; reconcile it in TikTok." : "发送结果未知，请勿重试并前往 TikTok 人工对账。");
      else setAnnouncement(en ? "The platform rejected the message" : "平台已拒绝本次消息发送");
    } catch (caught) { setFailedDraft({ sessionId, content, key }); setAnnouncement(caught instanceof Error ? caught.message : en ? "Send failed" : "发送失败"); }
    finally { setSending(false); }
  }

  async function submitCard(toSend: LogisticsCardDraft, key: string, sessionId: string) {
    if (!selectedId || selectedId !== sessionId || cardDrafts[sessionId] !== toSend || sending || !detail || detail.send_mode === "disabled") return;
    setCardReview(null);
    setSending(true); setFailedCard(null);
    try {
      const message = await sendLogisticsCard(sessionId, toSend.card.order_id, toSend.card.package_id, key);
      setDetail((current) => current?.session.id === sessionId ? { ...current, messages: current.messages.some((item) => item.id === message.id) ? current.messages.map((item) => item.id === message.id ? message : item) : [...current.messages, message] } : current);
      if (message.status !== "failed") setCardDrafts((current) => ({ ...current, [sessionId]: undefined }));
      setAnnouncement(message.status === "sent" ? (en ? "Logistics card sent" : "物流卡片已发送") : message.status === "unknown" ? (en ? "Result unknown; reconcile in TikTok before sending again" : "发送结果未知，请先到 TikTok 对账，勿重复发送") : (en ? "TikTok rejected the logistics card" : "平台拒绝发送物流卡片"));
    } catch (caught) { setFailedCard({ sessionId, draft: toSend, key }); setAnnouncement(caught instanceof Error ? caught.message : en ? "Card send failed" : "物流卡片发送失败"); }
    finally { setSending(false); }
  }

  async function previewTranslation(): Promise<string | null> {
    if (!selectedId || !draft.trim() || previewLoading || !detail?.draft_translation_enabled) return null;
    const requestId = ++previewRequestId.current;
    const sessionId = selectedId;
    const source = draft;
    const target = replyLanguage;
    setPreview(null); setPreviewError(""); setPreviewLoading(true);
    try {
      const result = await translateDraft(sessionId, source, target);
      if (requestId !== previewRequestId.current || currentComposeRef.current.sessionId !== sessionId || currentComposeRef.current.draft !== source || currentComposeRef.current.language !== target) return null;
      if (result.target_language !== target || !result.translated_text.trim() || result.translated_text.length > messageLimit) {
        throw new Error(en ? "Translation is invalid or exceeds the message limit" : "译文无效或超过发送字数上限");
      }
      setPreview({ sessionId, source, language: target, content: result.translated_text });
      return result.translated_text;
    } catch (caught) {
      if (requestId === previewRequestId.current) setPreviewError(caught instanceof Error ? caught.message : en ? "Translation failed" : "翻译失败");
      return null;
    } finally { if (requestId === previewRequestId.current) setPreviewLoading(false); }
  }

  async function openReview(choice: SendChoice) {
    if (selectedId && cardDraft && detail?.send_mode !== "disabled" && !sending) {
      setCardReview({ sessionId: selectedId, draft: cardDraft, key: newKey() });
      return;
    }
    if (!selectedId || !detail || !draft.trim() || detail.send_mode === "disabled" || sending) return;
    const sessionId = selectedId;
    const source = draft;
    const language = replyLanguage;
    let content = source.trim();
    if (choice === "translated") {
      if (!detail.draft_translation_enabled) {
        setPreviewError(en ? "Draft translation is unavailable for this conversation" : "当前会话未开放草稿翻译");
        return;
      }
      content = preview?.sessionId === sessionId && preview.source === source && preview.language === language
        ? preview.content.trim() : (await previewTranslation())?.trim() ?? "";
    }
    if (currentComposeRef.current.sessionId !== sessionId || currentComposeRef.current.draft !== source || currentComposeRef.current.language !== language || (choice === "translated" && (!currentComposeRef.current.translationEnabled || currentComposeRef.current.choice !== choice))) return;
    if (!content) return;
    if (content.length > messageLimit) {
      setAnnouncement(en ? "Message exceeds the sending limit" : "消息超过发送字数上限");
      return;
    }
    setReview({ sessionId, source, language: choice === "direct" ? "original" : language, content, key: newKey() });
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
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    const shortcut = /^\/([a-z0-9]{1,8})$/i.exec(draft)?.[1];
    if (!shortcut || !selectedId || !detail) { void openReview(activeSendChoice); return; }
    const source = draft;
    const sessionId = selectedId;
    const storeId = detail.session.store_id;
    void resolveQuickReplyShortcut(storeId, shortcut).then((reply) => {
      if (currentComposeRef.current.sessionId !== sessionId || currentComposeRef.current.draft !== source) return;
      const text = reply?.messages.filter((message) => message.trim()).join("\n") ?? "";
      if (text.trim() && text.length <= messageLimit) applyQuickReply(text, false);
      else void openReview(activeSendChoice);
    }).catch(() => {
      if (currentComposeRef.current.sessionId === sessionId && currentComposeRef.current.draft === source) {
        setComposerNotice(en ? "Could not look up the shortcut. Try again." : "快捷键查询失败，请重试。");
      }
    });
  }

  function updateComposerDraft(value: string) {
    setDraft(value);
    if (/^\/[a-z0-9]{0,8}$/i.test(value)) {
      setQuickReplyQuery(value.slice(1));
      setQuickReplyFavoritesOnly(false);
      setQuickReplyOpen(true);
    }
  }

  function applyQuickReply(text: string, reviewNow: boolean) {
    if (!selectedId || !detail || detail.send_mode === "disabled" || text.length > messageLimit || !text.trim()) return;
    setDraft(text);
    setQuickReplyOpen(false);
    setComposerNotice("");
    if (reviewNow) setReview({ sessionId: selectedId, source: text, language: "original", content: text.trim(), key: newKey() });
    else setAnnouncement(en ? "Quick reply inserted. Review before sending." : "快捷回复已填入草稿，请核对后发送。");
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
          // 用户主动点击生成后直接填入可编辑草稿；发送仍需人工审阅确认。
          const content = result.content;
          if (selectedId && content) setDrafts((current) => ({ ...current, [selectedId]: content }));
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

  async function changeClosed(closed: boolean) {
    if (!detail || actionBusy) return;
    const sessionId = detail.session.id;
    if (closed && (closeConfirmId !== sessionId || selectedId !== sessionId || detail.session.status === "closed")) return;
    setActionBusy(true); setCloseError("");
    try {
      const result = await setSessionClosed(sessionId, closed);
      if (closed) { closeDialogRef.current?.close(); setCloseConfirmId(null); }
      setDetail((current) => current?.session.id === sessionId ? { ...current, session: { ...current.session, ...result }, send_mode: closed ? "disabled" : current.send_mode } : current);
      setList((current) => current ? { ...current, items: current.items.map((item) => item.id === sessionId ? { ...item, ...result } : item) } : current);
      await loadList();
      if (!closed) {
        const fresh = await getSessionMessages(sessionId);
        setDetail((current) => current?.session.id === sessionId ? fresh : current);
      }
      setAnnouncement(closed ? (en ? "Conversation closed" : "会话已关闭") : (en ? "Conversation reopened" : "会话已重新打开"));
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : en ? "Could not change conversation status" : "变更会话状态失败";
      if (closed) setCloseError(message);
      setAnnouncement(message);
    }
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
      <div className="panel-heading"><div><p className="eyebrow">INBOX</p><h2 className="text-xl font-semibold">{en ? "Customer messages" : "客户消息"}</h2></div><span aria-label={en ? "Total unread messages" : "新消息总数"} className="count-pill">{list?.unread_messages_total ?? 0}</span></div>
      <div className="filter-row" aria-label={en ? "Conversation filters" : "会话筛选"}>{(["all", "unread", "mine", "starred", "closed"] as Filter[]).map((item) => <button aria-pressed={filter === item} className={filter === item ? "filter active" : "filter"} key={item} onClick={() => setFilter(item)} type="button">{filterLabels[language][item]}</button>)}</div>
      <div className="workspace-search">
        <div className="workspace-search-controls">
          <select aria-label={en ? "Search scope" : "搜索范围"} className="compact-field" onChange={(event) => setSearchScope(event.target.value as SearchScope)} value={searchScope}>
            <option value="all">{en ? "All" : "全部"}</option><option value="buyer">{en ? "Buyer" : "买家"}</option><option value="order">{en ? "Order number" : "订单号"}</option><option value="tracking">{en ? "Tracking number" : "物流号"}</option><option value="product">{en ? "Product" : "商品"}</option>
          </select>
          <label className="workspace-search-input"><MagnifyingGlass size={16} /><input aria-label={en ? "Search conversations" : "搜索会话"} maxLength={2420} onChange={(event) => setSearchInput(event.target.value)} placeholder={en ? "Order / tracking / buyer / product · separate with commas" : "订单号 / 物流号 / 买家昵称 / 商品，多个用逗号分隔"} value={searchInput} /></label>
        </div>
        {searchTerms(search).length > 1 ? <p className="workspace-search-summary">{en ? `${searchTerms(search).length} keywords · ${list?.pagination.total ?? 0} conversations` : `${searchTerms(search).length} 个关键词 · ${list?.pagination.total ?? 0} 个会话`}</p> : search ? <p className="workspace-search-summary">{en ? `${list?.pagination.total ?? 0} matching conversations` : `找到 ${list?.pagination.total ?? 0} 个会话`}</p> : null}
      </div>
      <div className="grid grid-cols-2 gap-2 border-b border-[var(--border)] p-3"><select aria-label={en ? "Platform" : "平台"} className="compact-field" onChange={(event) => setPlatform(event.target.value)} value={platform}><option value="">{en ? "All platforms" : "全部平台"}</option><option value="tiktok">TikTok</option><option value="shopee">Shopee</option><option value="amazon">Amazon</option></select><select aria-label={en ? "Store" : "店铺"} className="compact-field" onChange={(event) => setStoreId(event.target.value)} value={storeId}><option value="">{en ? "All stores" : "全部店铺"}</option>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}{storeId && !stores.some((store) => store.id === storeId) ? <option value={storeId}>{en ? "Store name unavailable" : "店铺名称不可用"}</option> : null}</select>{storeError ? <p className="col-span-2 text-xs text-red-600" role="alert">{storeError}</p> : null}</div>
      <div className="conversation-scroll" onScroll={(event) => { const node = event.currentTarget; if (node.scrollHeight - node.scrollTop - node.clientHeight < 100) void loadMoreConversations(); }} ref={conversationScrollRef}>{loading ? <LoadingState label={en ? "Loading conversations…" : "正在加载会话…"} /> : error ? <ErrorState message={error} retry={() => void loadList()} /> : !list?.items.length ? <EmptyState label={search ? (en ? "No matching conversations" : "未找到匹配会话") : (en ? "Conversations will appear when platform messages arrive" : "暂无会话，平台消息到达后会显示在这里")} /> : <>{list.items.map((item) => {
        const lastMessageTime = formatConversationTime(item.last_message_at, en ? "en-US" : "zh-CN");
        return <button aria-pressed={selectedId === item.id} className={selectedId === item.id ? "conversation-card active" : "conversation-card"} key={item.id} onClick={() => setSelectedId(item.id)} type="button">
          <span className="avatar">{item.customer.name?.slice(0, 1) ?? "?"}</span>
          <span className="min-w-0 flex-1 text-left">
            <span className="flex items-center justify-between gap-2"><strong className="truncate text-sm">{item.customer.name ?? (en ? "Anonymous customer" : "匿名客户")}</strong>{lastMessageTime ? <time className="conversation-time" dateTime={item.last_message_at ?? undefined}>{lastMessageTime}</time> : null}</span>
            <span className="mt-1 flex items-center justify-between gap-2"><span className="min-w-0 truncate text-sm text-[var(--muted)]">{item.last_message ?? (en ? "No messages" : "暂无消息")}</span><span className="conversation-indicators">{item.is_starred ? <Star aria-label={en ? "Review risk" : "差评风险"} size={14} weight="fill" /> : null}<small className={`platform-badge platform-${item.platform}`}>{item.platform}</small>{item.unread_count > 0 ? <span className="unread" aria-label={en ? `${item.unread_count} unread messages` : `${item.unread_count} 条未读消息`}>{item.unread_count > 99 ? "99+" : item.unread_count}</span> : null}</span></span>
          </span>
        </button>;
      })}{loadingMore ? <p className="workspace-search-summary" role="status">{en ? "Loading more conversations…" : "正在加载更多会话…"}</p> : null}{loadMoreError ? <div className="workspace-search-summary" role="alert">{loadMoreError} <button className="text-button" onClick={() => void loadMoreConversations()} type="button">{en ? "Retry" : "重试"}</button></div> : null}</>}</div>
    </section>

    <section className="chat-panel" aria-label={en ? "Chat window" : "聊天窗口"}>{!selectedId ? <EmptyState label={en ? "Select a conversation" : "请选择一个会话"} /> : detailError ? <ErrorState message={detailError} /> : !detail ? <LoadingState label={en ? "Loading messages…" : "正在加载消息…"} /> : <>
      <header className="chat-heading"><button className="mobile-back" onClick={() => setSelectedId(null)} type="button" aria-label={en ? "Back to conversation list" : "返回会话列表"}><ArrowLeft size={20} /></button><div className="min-w-0"><h2 className="truncate font-semibold">{detail.customer.name ?? (en ? "Anonymous customer" : "匿名客户")}</h2><p className="text-xs text-[var(--muted)]">{detail.session.platform} · {detail.session.status} · {modeLabel(detail.send_mode, en)}</p></div><div className="chat-actions"><button aria-label={detail.session.is_starred ? (en ? "Remove review risk mark" : "取消差评风险标记") : (en ? "Mark review risk" : "标记差评风险")} aria-pressed={detail.session.is_starred} className="icon-action" disabled={actionBusy} onClick={() => void changeStar()} title={en ? "Review risk" : "差评风险"} type="button"><Star size={19} weight={detail.session.is_starred ? "fill" : "regular"} /></button><button aria-label={en ? "Transfer conversation" : "转交会话"} className="icon-action" disabled={actionBusy || detail.session.status === "closed"} onClick={() => void openTransfer()} title={en ? "Transfer" : "转交会话"} type="button"><UserSwitch size={19} /></button><button aria-label={detail.session.status === "closed" ? (en ? "Reopen conversation" : "重新打开会话") : (en ? "Close conversation" : "关闭会话")} className="icon-action" disabled={actionBusy} onClick={() => { if (detail.session.status === "closed") void changeClosed(false); else { setCloseError(""); setCloseConfirmId(detail.session.id); } }} title={detail.session.status === "closed" ? (en ? "Reopen" : "重新打开") : (en ? "Close" : "关闭会话")} type="button">{detail.session.status === "closed" ? <ArrowRight size={19} /> : <X size={19} />}</button><button className="secondary-button" onClick={() => setCustomerOpen(true)} type="button"><UserFocus size={17} />{en ? "Customer details" : "客户信息"}</button></div></header>
      <div className="message-area"><div className="message-scroll" onScroll={onMessageScroll} ref={messageScrollRef}>{detail.pagination.page > 1 ? <button className="secondary-button self-center" disabled={loadingOlder} onClick={() => void loadOlder()} type="button">{loadingOlder ? (en ? "Loading…" : "加载中…") : (en ? "Load older messages" : "加载更早消息")}</button> : null}{detail.messages.length ? detail.messages.map((message) => <MessageBubble en={en} key={message.id} message={message} sessionId={detail.session.id} translationEnabled={detail.translation_enabled === true} />) : <EmptyState label={en ? "No messages in this conversation" : "该会话暂无消息"} />}</div>{showLatest ? <button className="latest-button" onClick={scrollToLatest} type="button"><ArrowDown size={16} />{en ? "Latest message" : "到最新消息"}</button> : null}</div>
      <section className="ai-suggestion" aria-label={en ? "AI suggestion" : "AI 建议"}><div className="min-w-0 flex-1"><strong>{en ? "AI reply suggestion" : "AI 回复建议"}</strong><p aria-live="polite" className="truncate">{suggestionStatus || (suggestionDraft ? (en ? "Suggestion is ready in the draft" : "建议已填入草稿，可编辑后发送") : (en ? "Generate a draft on demand" : "按需生成草稿"))}</p></div><div className="flex gap-2">{suggestionLoading ? <button className="text-button" type="button" onClick={cancelSuggestion}><X size={16} />{en ? "Cancel" : "取消"}</button> : <button className="text-button" type="button" onClick={() => void requestSuggestion()}>{suggestionDraft ? (en ? "Refresh" : "刷新") : (en ? "Generate" : "生成")}</button>}{suggestionDraft && draft !== suggestionDraft ? <button className="secondary-button" type="button" onClick={() => { setDraft(suggestionDraft); setAnnouncement(en ? "Suggestion inserted; review it before sending" : "建议已填入输入框，确认后再发送"); }}>{en ? "Use" : "使用"}</button> : null}</div></section>
      <div className="composer">
        <div className="workspace-composer-tools">
          <button aria-expanded={emojiOpen} aria-label={en ? "Emoji" : "表情"} disabled={!!cardDraft || detail.send_mode === "disabled"} onClick={() => { setEmojiOpen(!emojiOpen); setQuickReplyOpen(false); }} title={en ? "Emoji" : "表情"} type="button"><Smiley size={19} /></button>
          <button aria-label={en ? "Image" : "图片"} onClick={() => setComposerNotice(en ? "Image sending is not available yet" : "图片发送暂不可用")} title={en ? "Image sending is not available" : "图片发送暂不可用"} type="button"><ImageSquare size={19} /></button>
          <button aria-label={en ? "Video" : "视频"} onClick={() => setComposerNotice(en ? "Video sending is not available yet" : "视频发送暂不可用")} title={en ? "Video sending is not available" : "视频发送暂不可用"} type="button"><Video size={19} /></button>
          <button aria-label={en ? "Favorite replies" : "收藏的快捷回复"} disabled={!!cardDraft || detail.send_mode === "disabled"} onClick={() => { setQuickReplyFavoritesOnly(true); setQuickReplyQuery(""); setQuickReplyOpen(true); setEmojiOpen(false); }} title={en ? "Favorite replies" : "收藏的快捷回复"} type="button"><Heart size={19} /></button>
          <span className="workspace-composer-tool-spacer" />
          <button aria-expanded={quickReplyOpen} aria-label={en ? "Quick replies" : "快捷回复"} disabled={!!cardDraft || detail.send_mode === "disabled"} onClick={() => { setQuickReplyFavoritesOnly(false); setQuickReplyQuery(""); setQuickReplyOpen(!quickReplyOpen); setEmojiOpen(false); }} title={en ? "Quick replies" : "快捷回复"} type="button"><NotePencil size={19} /></button>
        </div>
        {emojiOpen ? <div aria-label={en ? "Choose emoji" : "选择表情"} className="workspace-emoji-picker" role="menu">{["😊", "👍", "❤️", "🙏", "🎉"].map((emoji) => <button aria-label={emoji} key={emoji} onClick={() => { setDraft(`${draft}${emoji}`); setEmojiOpen(false); }} role="menuitem" type="button">{emoji}</button>)}</div> : null}
        {composerNotice ? <p className="workspace-composer-notice" role="status">{composerNotice}</p> : null}
        {quickReplyOpen ? <QuickReplyPicker en={en} favoritesOnly={quickReplyFavoritesOnly} initialQuery={quickReplyQuery} onClose={() => setQuickReplyOpen(false)} onDraft={(text) => applyQuickReply(text, false)} onReview={(text) => applyQuickReply(text, true)} storeId={detail.session.store_id} /> : null}
        {cardDraft ? <div className="workspace-card-draft"><TrackingCard card={cardDraft.card} en={en} enhancedAvailable={cardDraft.enhancedAvailable} packages={cardDraft.packages} selected={cardDraft.selected} sessionId={detail.session.id} translationEnabled={detail.translation_enabled === true} /><button className="text-button" onClick={() => { setCardDrafts((current) => ({ ...current, [detail.session.id]: undefined })); setCardReview(null); }} type="button">{en ? "Remove card" : "移除卡片"}</button></div> : <textarea aria-label={en ? "Reply content" : "回复内容"} disabled={detail.send_mode === "disabled"} maxLength={messageLimit} onChange={(event) => updateComposerDraft(event.target.value)} onKeyDown={composerKey} placeholder={detail.send_mode === "disabled" ? (en ? "Message delivery is disabled" : "当前平台消息发送已关闭") : (en ? "Type a message, Enter to review, Shift+Enter for a new line" : "请输入消息，Enter 进入发送审阅 / Shift+Enter 换行")} value={draft} />}
        {previewError ? <p className="workspace-translation-error" role="alert">{previewError}</p> : null}
        {preview && preview.sessionId === selectedId && preview.source === draft && preview.language === replyLanguage ? <div className="workspace-translation-preview" aria-label={en ? "Translation preview" : "译文预览"}><strong>{en ? "Translation preview · review before sending" : "译文预览 · 发送前请核对"}</strong><p>{preview.content}</p><small>{en ? "Original draft" : "原始草稿"}：{draft}</small></div> : null}
        {failedDraft?.sessionId === selectedId ? <button className="text-button text-red-600" onClick={() => setReview({ sessionId: failedDraft.sessionId, source: failedDraft.content, language: "original", content: failedDraft.content, key: failedDraft.key })} type="button">{en ? "Request interrupted; review exact retry" : "请求中断，审阅原内容后重试"}</button> : null}
        {failedCard?.sessionId === selectedId && failedCard.draft === cardDraft ? <button className="text-button text-red-600" onClick={() => setCardReview(failedCard)} type="button">{en ? "Request interrupted; review exact card retry" : "请求中断，审阅原卡片后重试"}</button> : null}
        <div className="workspace-composer-footer" ref={composerMenusRef}>
          <small className="workspace-composer-count">{cardDraft ? (en ? "Logistics card · review before sending" : "物流卡片 · 确认后发送") : `${draft.length}/${messageLimit}`}</small>
          <div className="workspace-composer-actions">
            <div className="workspace-menu-anchor">
              <button aria-expanded={languageMenuOpen} aria-haspopup="menu" aria-label={en ? "Target language" : "目标语言"} className="workspace-toolbar-button" disabled={!!cardDraft || !detail.draft_translation_enabled || detail.send_mode === "disabled"} onClick={() => { setLanguageMenuOpen(!languageMenuOpen); setSendMenuOpen(false); }} type="button">{replyLanguages.find((item) => item.value === replyLanguage)?.[en ? "en" : "zh"]}<CaretDown size={14} /></button>
              {languageMenuOpen ? <div aria-label={en ? "Target language options" : "目标语言选项"} className="workspace-popover workspace-language-menu" role="menu">
                <button aria-checked={replyLanguage === "en"} onClick={() => { setReplyLanguage("en"); setLanguageMenuOpen(false); setMoreLanguagesOpen(false); }} role="menuitemradio" type="button">{en ? "English" : "英语"}</button>
                <button aria-expanded={moreLanguagesOpen} aria-haspopup="menu" className="workspace-more-button" onClick={(event) => { setMoreLanguagesLeft(window.innerWidth - event.currentTarget.getBoundingClientRect().right < 148); setMoreLanguagesOpen(!moreLanguagesOpen); }} role="menuitem" type="button">{en ? "More" : "更多"}<CaretRight size={14} /></button>
                {moreLanguagesOpen ? <div aria-label={en ? "More target languages" : "更多目标语言"} className="workspace-more-languages" data-side={moreLanguagesLeft ? "left" : "right"} role="menu">{replyLanguages.slice(2).map((item) => <button aria-checked={replyLanguage === item.value} key={item.value} onClick={() => { setReplyLanguage(item.value as DraftTargetLanguage); setLanguageMenuOpen(false); setMoreLanguagesOpen(false); }} role="menuitemradio" type="button">{en ? item.en : item.zh}</button>)}</div> : null}
              </div> : null}
            </div>
            <button className="workspace-toolbar-button" disabled={!!cardDraft || !draft.trim() || previewLoading || !detail.draft_translation_enabled || detail.send_mode === "disabled"} onClick={() => { setLanguageMenuOpen(false); setMoreLanguagesOpen(false); setSendMenuOpen(false); void previewTranslation(); }} type="button">{previewLoading ? (en ? "Translating…" : "翻译中…") : (en ? "Translate" : "翻译")}</button>
            <div className="workspace-menu-anchor workspace-send-split">
              <button className="workspace-send-main" disabled={(!cardDraft && !draft.trim()) || sending || previewLoading || detail.send_mode === "disabled"} onClick={() => { setLanguageMenuOpen(false); setMoreLanguagesOpen(false); setSendMenuOpen(false); void openReview(activeSendChoice); }} type="button">{sending ? (en ? "Sending…" : "发送中…") : cardDraft ? (en ? "Send logistics card" : "发送物流卡片") : activeSendChoice === "direct" ? (en ? "Send directly" : "直接发送") : (en ? "Translate & send" : "翻译后发送")}</button>
              <button aria-expanded={sendMenuOpen} aria-haspopup="menu" aria-label={en ? "Choose send mode" : "选择发送方式"} className="workspace-send-toggle" disabled={!!cardDraft || sending || detail.send_mode === "disabled"} onClick={() => { setSendMenuOpen(!sendMenuOpen); setLanguageMenuOpen(false); }} type="button"><CaretDown size={14} /></button>
              {sendMenuOpen ? <div aria-label={en ? "Send mode options" : "发送方式选项"} className="workspace-popover workspace-send-menu" role="menu">
                <button aria-checked={activeSendChoice === "direct"} onClick={() => { setSendChoice("direct"); setSendMenuOpen(false); }} role="menuitemradio" type="button">{en ? "Send directly" : "直接发送"}</button>
                <button aria-checked={activeSendChoice === "translated"} disabled={!detail.draft_translation_enabled} onClick={() => { setSendChoice("translated"); setSendMenuOpen(false); }} role="menuitemradio" type="button">{en ? "Translate & send" : "翻译后发送"}</button>
              </div> : null}
            </div>
          </div>
        </div>
      </div>
    </>}</section>

    <aside className={`customer-panel ${customerOpen ? "open" : ""}`} aria-label={en ? "Customer and quick actions" : "客户与快捷操作"}><CustomerSidebar detail={detail} en={en} key={detail?.session.id ?? "none"} onClose={() => setCustomerOpen(false)} onDraft={(content) => { setDraft(content); setAnnouncement(en ? "Added to draft; review before sending" : "已填入草稿，请核对后发送"); }} onCardDraft={(card) => { if (selectedId) { setCardDrafts((current) => ({ ...current, [selectedId]: card })); setCardReview(null); setFailedCard(null); setAnnouncement(en ? "Logistics card added; review before sending" : "物流卡片已填入发送栏，请核对后发送"); } }} storeName={stores.find((store) => store.id === detail?.session.store_id)?.name ?? null} /></aside>
    {customerOpen ? <button aria-label={en ? "Close drawer overlay" : "关闭抽屉遮罩"} className="drawer-backdrop" onClick={() => setCustomerOpen(false)} type="button" /> : null}
    {closeConfirmId === selectedId && detail?.session.id === closeConfirmId ? <dialog aria-label={en ? "Close conversation" : "关闭会话"} aria-modal="true" className="action-dialog workspace-close-dialog" onCancel={(event) => { if (actionBusy) event.preventDefault(); else setCloseConfirmId(null); }} ref={closeDialogRef}><h2>{en ? "Close conversation" : "关闭会话"}</h2><p>{en ? `Close the conversation with ${detail.customer.name ?? "this customer"}? It will move to Closed and can be reopened.` : `确定关闭与${detail.customer.name ?? "当前客户"}的会话？关闭后会移至“已关闭”，仍可重新打开。`}</p>{closeError ? <p className="workspace-close-error" role="alert">{closeError}</p> : null}<div className="action-dialog-buttons"><button className="secondary-button" disabled={actionBusy} onClick={() => { closeDialogRef.current?.close(); setCloseConfirmId(null); }} type="button">{en ? "Cancel" : "取消"}</button><button className="danger-button" disabled={actionBusy} onClick={() => void changeClosed(true)} type="button">{actionBusy ? (en ? "Closing…" : "正在关闭…") : (en ? "Confirm close" : "确认关闭")}</button></div></dialog> : null}
    {review && review.sessionId === selectedId ? <div className="action-dialog-backdrop" role="presentation"><section aria-label={en ? "Review outgoing message" : "审阅外发消息"} aria-modal="true" className="action-dialog workspace-review-dialog" role="dialog"><h2>{en ? "Review outgoing message" : "审阅外发消息"}</h2><p>{en ? "Recipient" : "收件人"}：{detail?.customer.name ?? (en ? "Anonymous customer" : "匿名客户")} · {detail?.session.platform}</p><p>{en ? "Target language" : "目标语言"}：{replyLanguages.find((item) => item.value === review.language)?.[en ? "en" : "zh"]}</p><div className="workspace-review-content"><strong>{en ? "Exact message to send" : "即将发送的准确内容"}</strong><p>{review.content}</p></div>{review.language !== "original" ? <div className="workspace-review-source"><strong>{en ? "Original draft" : "原始草稿"}</strong><p>{review.source}</p></div> : null}<p>{detail?.send_mode === "real" ? (en ? "This sends a real TikTok message and is audited." : "确认后将向真实 TikTok 买家发送，操作会被审计。") : (en ? "This runs simulated delivery." : "确认后执行模拟发送。")}</p><div className="action-dialog-buttons"><button className="secondary-button" onClick={() => setReview(null)} type="button">{en ? "Back to edit" : "返回修改"}</button><button className="primary-button" disabled={sending || detail?.send_mode === "disabled"} onClick={() => void submitMessage(review.content, review.key, review.sessionId)} type="button">{en ? "Confirm & send" : "确认并发送"}</button></div></section></div> : null}
    {cardReview && cardReview.sessionId === selectedId ? <div className="action-dialog-backdrop" role="presentation"><section aria-label={en ? "Review logistics card" : "审阅物流卡片"} aria-modal="true" className="action-dialog workspace-review-dialog" role="dialog"><h2>{en ? "Review logistics card" : "审阅物流卡片"}</h2><p>{en ? "Recipient" : "收件人"}：{detail?.customer.name ?? (en ? "Anonymous customer" : "匿名客户")} · {detail?.session.platform}</p><TrackingCard card={cardReview.draft.card} en={en} enhancedAvailable={cardReview.draft.enhancedAvailable} packages={cardReview.draft.packages} selected={cardReview.draft.selected} sessionId={cardReview.sessionId} translationEnabled={detail?.translation_enabled === true} /><p>{detail?.send_mode === "real" ? (en ? "Confirming sends this TikTok logistics card to the buyer." : "确认后将向该 TikTok 买家发送原生物流卡片。") : (en ? "Confirming simulates sending this card." : "确认后模拟发送这张卡片。")}</p><div className="action-dialog-buttons"><button className="secondary-button" onClick={() => setCardReview(null)} type="button">{en ? "Back to edit" : "返回修改"}</button><button className="primary-button" disabled={sending || detail?.send_mode === "disabled"} onClick={() => void submitCard(cardReview.draft, cardReview.key, cardReview.sessionId)} type="button">{en ? "Confirm & send card" : "确认发送卡片"}</button></div></section></div> : null}
    {transferOpen ? <div className="action-dialog-backdrop" role="presentation"><section aria-label={en ? "Transfer conversation" : "转交会话"} aria-modal="true" className="action-dialog" role="dialog"><h2>{en ? "Transfer conversation" : "转交会话"}</h2><p>{en ? "Choose an agent who can access this store." : "选择有当前店铺权限的坐席。"}</p><select aria-label={en ? "Target agent" : "目标坐席"} className="compact-field" onChange={(event) => setAssigneeId(event.target.value)} value={assigneeId}><option value="">{en ? "Select an agent" : "请选择坐席"}</option>{assignees.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</select>{transferError ? <p role="alert">{transferError}</p> : null}<div className="action-dialog-buttons"><button className="secondary-button" onClick={() => setTransferOpen(false)} type="button">{en ? "Cancel" : "取消"}</button><button className="primary-button" disabled={!assigneeId || actionBusy} onClick={() => void confirmTransfer()} type="button">{en ? "Confirm transfer" : "确认转交"}</button></div></section></div> : null}
  </main><div aria-live="polite" className="sr-only">{announcement}</div></AppShell>;
}
