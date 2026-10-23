"use client";

import Link from "next/link";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Heart, MagnifyingGlass, X } from "@phosphor-icons/react";
import { listAllQuickReplyGroups, listQuickReplies, type QuickReply, type QuickReplyGroup } from "../lib/reception";

type Scope = "personal" | "team";

type Props = {
  storeId: string;
  en: boolean;
  initialQuery?: string;
  favoritesOnly?: boolean;
  onDraft: (text: string) => void;
  onReview: (text: string) => void;
  onClose: () => void;
};

const replyText = (reply: QuickReply) => reply.messages.filter((message) => message.trim()).join("\n");

export function QuickReplyPicker({ storeId, en, initialQuery = "", favoritesOnly = false, onDraft, onReview, onClose }: Props) {
  const [scope, setScope] = useState<Scope>("personal");
  const [groupId, setGroupId] = useState("");
  const [query, setQuery] = useState(initialQuery);
  const [groups, setGroups] = useState<QuickReplyGroup[]>([]);
  const [replies, setReplies] = useState<QuickReply[]>([]);
  const [favoriteIds, setFavoriteIds] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState("");
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const selectionKey = JSON.stringify([storeId, scope, groupId, query, refresh]);
  const currentSelection = useRef(selectionKey);
  useLayoutEffect(() => { currentSelection.current = selectionKey; }, [selectionKey]);

  useEffect(() => setQuery(initialQuery), [initialQuery]);

  useEffect(() => {
    try {
      const saved: unknown = JSON.parse(localStorage.getItem(`crm-quick-reply-favorites:${storeId}`) ?? "[]");
      setFavoriteIds(Array.isArray(saved) ? saved.filter((id): id is string => typeof id === "string") : []);
    }
    catch { setFavoriteIds([]); }
  }, [storeId]);
  useEffect(() => {
    const onEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [onClose]);
  useEffect(() => {
    let active = true;
    setLoading(true); setLoadingMore(false); setError(""); setMoreError(""); setPage(1);
    Promise.all([listAllQuickReplyGroups(storeId, scope), listQuickReplies(storeId, scope, { groupId, q: query, pageSize: 100 })])
      .then(([groupItems, replyPage]) => { if (active) { setGroups(groupItems.filter((group) => group.enabled)); setReplies(replyPage.items); setTotal(replyPage.total); } })
      .catch((caught: unknown) => { if (active) setError(caught instanceof Error ? caught.message : en ? "Could not load quick replies" : "快捷回复加载失败"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [storeId, scope, groupId, query, refresh, en]);

  async function loadMore() {
    if (loadingMore || loading || replies.length >= total) return;
    const requestedSelection = currentSelection.current;
    const nextPage = page + 1;
    setLoadingMore(true); setMoreError("");
    try {
      const next = await listQuickReplies(storeId, scope, { groupId, q: query, page: nextPage, pageSize: 100 });
      if (currentSelection.current !== requestedSelection) return;
      setReplies((current) => [...current, ...next.items.filter((reply) => !current.some((item) => item.id === reply.id))]);
      setPage(nextPage);
      setTotal(next.total);
    } catch (caught) { if (currentSelection.current === requestedSelection) setMoreError(caught instanceof Error ? caught.message : en ? "Could not load more replies" : "加载更多快捷回复失败"); }
    finally { if (currentSelection.current === requestedSelection) setLoadingMore(false); }
  }

  const filtered = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return replies.filter((reply) => {
      if (groupId && reply.group_id !== groupId) return false;
      if (favoritesOnly && !favoriteIds.includes(reply.id)) return false;
      return !term || [reply.shortcut, ...reply.tags, replyText(reply)].some((value) => value.toLocaleLowerCase().includes(term));
    });
  }, [replies, groupId, favoritesOnly, favoriteIds, query]);

  function toggleFavorite(id: string) {
    setFavoriteIds((current) => {
      const next = current.includes(id) ? current.filter((item) => item !== id) : [...current, id];
      localStorage.setItem(`crm-quick-reply-favorites:${storeId}`, JSON.stringify(next));
      return next;
    });
  }

  return <section aria-label={en ? "Quick replies" : "快捷回复"} className="quick-reply-picker" role="dialog">
    <header className="quick-reply-picker-head"><strong>{en ? "Quick replies" : "快捷回复"}</strong><label className="quick-reply-search"><MagnifyingGlass size={15} /><input aria-label={en ? "Search quick replies" : "搜索快捷回复"} onChange={(event) => setQuery(event.target.value)} placeholder={en ? "Shortcut, tag or content" : "快捷键、标签或内容"} value={query} /></label><button aria-label={en ? "Close quick replies" : "关闭快捷回复"} onClick={onClose} type="button"><X size={16} /></button></header>
    <div aria-label={en ? "Reply scope" : "回复归属"} className="quick-reply-scope" role="tablist"><button aria-selected={scope === "personal"} onClick={() => { setScope("personal"); setGroupId(""); }} role="tab" type="button">{en ? "Personal" : "个人"}</button><button aria-selected={scope === "team"} onClick={() => { setScope("team"); setGroupId(""); }} role="tab" type="button">{en ? "Team" : "团队"}</button><span>{en ? "Select a reply to draft or review" : "选择后可编辑或审阅发送"}</span><Link aria-label={en ? "Manage quick replies" : "管理快捷回复"} href={`/marketing/reception/quick-replies?store_id=${encodeURIComponent(storeId)}&scope=${scope}`}>{en ? "Edit" : "编辑"}</Link></div>
    <div aria-label={en ? "Reply groups" : "快捷回复分组"} className="quick-reply-groups"><button aria-pressed={!groupId} onClick={() => setGroupId("")} type="button">{en ? "All" : "全部"}</button>{groups.map((group) => <button aria-pressed={groupId === group.id} key={group.id} onClick={() => setGroupId(group.id)} type="button">{group.name}</button>)}</div>
    <div className="quick-reply-items">{loading ? <p role="status">{en ? "Loading…" : "正在加载…"}</p> : error ? <p role="alert">{error} <button onClick={() => setRefresh((value) => value + 1)} type="button">{en ? "Retry" : "重试"}</button></p> : filtered.length ? filtered.map((reply) => {
      const text = replyText(reply);
      return <article className="quick-reply-item" key={reply.id}><div className="quick-reply-item-top"><p>{text}</p><button aria-label={favoriteIds.includes(reply.id) ? (en ? "Remove favorite" : "取消收藏") : (en ? "Favorite reply" : "收藏快捷回复")} aria-pressed={favoriteIds.includes(reply.id)} onClick={() => toggleFavorite(reply.id)} type="button"><Heart size={15} weight={favoriteIds.includes(reply.id) ? "fill" : "regular"} /></button></div><div className="quick-reply-item-bottom"><span>/{reply.shortcut}{reply.tags.length ? ` · ${reply.tags.join(" / ")}` : ""}</span><div><button disabled={!text.trim() || text.length > 2000} onClick={() => onDraft(text)} type="button">{en ? "Edit then send" : "编辑后发送"}</button><button disabled={!text.trim() || text.length > 2000} onClick={() => onReview(text)} type="button">{en ? "Review send" : "发送"}</button></div></div></article>;
    }) : <p role="status">{en ? "No matching quick replies" : "暂无匹配的快捷回复"}</p>}{moreError ? <p role="alert">{moreError}</p> : null}{!loading && !error && replies.length < total ? <button className="quick-reply-more" disabled={loadingMore} onClick={() => void loadMore()} type="button">{loadingMore ? (en ? "Loading…" : "加载中…") : (en ? "Load more" : "加载更多")}</button> : null}</div>
  </section>;
}
