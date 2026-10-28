"use client";

import { useEffect, useState } from "react";
import { getAgentCollaboration, type AgentCollaborationEntry } from "../lib/api";

export function AgentCollaboration({ conversationId, refreshKey }: { conversationId: string; refreshKey?: string }) {
  const [rows, setRows] = useState<AgentCollaborationEntry[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => { setOffset(0); setRows([]); setHasMore(false); }, [conversationId, refreshKey]);
  useEffect(() => {
    let active = true;
    setError("");
    if (!conversationId) return;
    setLoading(true);
    void getAgentCollaboration(conversationId, offset).then((items) => {
      if (!active) return;
      setRows((old) => offset === 0 ? items : [...old, ...items]); setHasMore(items.length === 20);
    }).catch((caught: unknown) => { if (active) setError(caught instanceof Error ? caught.message : "内部记录加载失败"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [conversationId, refreshKey, offset]);
  if (!conversationId) return null;
  return <section className="collaboration-panel"><div className="section-head"><h3>内部协作记录</h3><p>仅供当前店铺坐席查看。接管请求表示待处理建议，不代表会话已转交。</p></div>
    {error ? <p role="alert">{error}</p> : rows.length === 0 && !loading ? <p className="collaboration-empty">当前会话暂无 AI 接管请求或内部备注。</p> : rows.map((item) => <article className="collaboration-entry" key={item.id}><div><strong>{item.kind === "handoff_request" ? "接管请求" : "内部备注"}</strong><span>AI 建议</span><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time></div><p>{item.content}</p></article>)}
    {loading ? <p role="status">正在加载内部记录…</p> : hasMore ? <button type="button" className="btn" onClick={() => setOffset((old) => old + 20)}>加载更多记录</button> : null}
  </section>;
}
