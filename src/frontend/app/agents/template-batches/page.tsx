"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { AgentTemplateNav } from "../../../components/agents/templates/AgentTemplateNav";
import { TemplateModal } from "../../../components/agents/templates/TemplateModal";
import { cancelTemplateBatch, getTemplateBatch, listTemplateBatches, retryFailedTemplateBatch, type BatchSummary, type BatchView, type Page } from "../../../lib/agent-templates";
import "../agent-prototype.css";
import "../../../components/agents/templates/templates.css";

const message = (error: unknown) => error instanceof Error ? error.message : "请求失败，请重试";
const errors: Record<string, string> = { review_unavailable: "复核服务暂不可用", processing_unavailable: "处理暂不可用", preview_invalid: "冻结预览已失效，请重新预览", configuration_rejected: "目标配置未通过校验，请重新预览" };
const states: Record<string, string> = { pending: "待处理", running: "处理中", succeeded: "成功", failed: "失败", needs_repreview: "需要重新预览", cancelled: "已取消" };
const actions: Record<string, string> = { create: "新建", adopt: "关联", update: "更新" };
function label(batch: BatchSummary) {
  const c = batch.counts;
  if (batch.status === "cancelled") return "已取消";
  if (batch.status === "preview") return "未确认预览";
  if (batch.status === "queued") return "等待执行";
  if (batch.status === "running") return "执行中";
  const failed = (c.failed ?? 0) + (c.needs_repreview ?? 0);
  if (failed && (c.succeeded ?? 0)) return "部分失败";
  if (failed) return "全部失败";
  if (c.succeeded) return "全部成功";
  return batch.status;
}

export default function TemplateBatchesPage() {
  const [id, setId] = useState("");
  const [page, setPage] = useState(1);
  const [itemPage, setItemPage] = useState(1);
  const [list, setList] = useState<Page<BatchSummary> | null>(null);
  const [detail, setDetail] = useState<BatchView | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [hasRetryable, setHasRetryable] = useState(false);
  const actionScope = useRef({ active: false });
  useEffect(() => {
    const scope = { active: true };
    actionScope.current = scope;
    setBusy(false);
    return () => { scope.active = false; };
  }, [id, page, itemPage]);
  useEffect(() => {
    const sync = () => { setId(new URLSearchParams(window.location.search).get("batch_id") ?? ""); setItemPage(1); };
    sync(); window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  const refresh = useCallback(async (isActive: () => boolean) => {
    const [nextList, nextDetail] = await Promise.all([listTemplateBatches(page), id ? getTemplateBatch(id, itemPage) : Promise.resolve(null)]);
    if (!isActive()) return null;
    let retryable = nextDetail?.items.some((item) => item.retryable) ?? false;
    if (nextDetail && !retryable) for (let p = 1; p <= nextDetail.pagination.total_pages && !retryable; p++) {
      if (!isActive()) return null;
      if (p !== itemPage) { const next = await getTemplateBatch(id, p, 50); if (!isActive()) return null; retryable = next.items.some((item) => item.retryable); }
    }
    return { nextList, nextDetail, retryable };
  }, [id, page, itemPage]);
  useEffect(() => {
    let active = true; let inFlight = false;
    const load = () => { if (inFlight || busy) return; inFlight = true; void refresh(() => active).then((result) => { if (active && result) { setList(result.nextList); setDetail(result.nextDetail); setHasRetryable(result.retryable); setError(""); } }).catch((caught: unknown) => { if (active) setError(message(caught)); }).finally(() => { inFlight = false; }); };
    load(); const timer = window.setInterval(load, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, [refresh, busy]);
  async function action(kind: "cancel" | "retry") {
    if (busy || !id) return;
    const scope = actionScope.current;
    const isCurrent = () => scope.active && actionScope.current === scope;
    setBusy(true); setError("");
    try {
      const result = kind === "cancel" ? await cancelTemplateBatch(id) : await retryFailedTemplateBatch(id);
      if (!isCurrent()) return;
      setDetail(result); setCancelOpen(false);
      const nextList = await listTemplateBatches(page);
      if (isCurrent()) setList(nextList);
    } catch (caught) { if (isCurrent()) setError(message(caught)); }
    finally { if (isCurrent()) setBusy(false); }
  }
  return <AppShell><div className="agent-page template-page"><div className="shell">
    <header className="topbar"><div className="title"><div><h1>批量任务</h1><p>查看预览、已确认计划及各店处理结果</p></div></div></header>
    <AgentTemplateNav current="batches" />
    <main className="main">
      {error ? <p role="alert">{error}</p> : null}
      <div className="template-layout"><aside className="template-library"><h2>任务列表</h2>
        {!list ? <p role="status">{error ? "任务列表暂不可用，将自动重试。" : "正在加载…"}</p> : list.items.length ? list.items.map((batch) => <Link className={`template-list-item ${id === batch.id ? "active" : ""}`} key={batch.id} href={`/agents/template-batches?batch_id=${encodeURIComponent(batch.id)}`} onClick={() => { setId(batch.id); setItemPage(1); }}><strong>{label(batch)}</strong><span>模板 v{batch.template_version} · {batch.created_at}</span><small>{batch.id}</small></Link>) : <p>暂无批量任务</p>}
        <div><button className="btn small" disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button><span> 第 {page} 页 </span><button className="btn small" disabled={!list || page >= list.pagination.total_pages} onClick={() => setPage(page + 1)}>下一页</button></div>
      </aside><section className="config template-editor"><div className="config-body">
        {!id ? <p>选择任务查看详情。</p> : !detail || detail.id !== id ? <p role="status">{error ? "任务暂不可用，将自动重试。" : "正在加载任务…"}</p> : <>
          <h2>{label(detail)} · 模板 v{detail.template_version}</h2><p>任务 {detail.id} {detail.parent_batch_id ? `· 续接 ${detail.parent_batch_id}` : ""}</p>
          {!detail.processor_enabled ? <p role="status">后台处理器未启用，任务不会自动推进。</p> : null}
          <p>{Object.entries(detail.counts).map(([key, count]) => `${states[key] ?? key}：${count}`).join(" · ")}</p>
          <p>{detail.status === "preview" ? "当前仅为未确认预览，不会执行；请返回应用页审阅并确认。" : "取消不会回滚已成功的店铺；确认后的计划为只读。"}</p>
          <button className="btn" disabled={busy || !["queued", "running"].includes(detail.status)} onClick={() => setCancelOpen(true)}>取消任务</button>{" "}
          <button className="btn" disabled={busy || !hasRetryable} onClick={() => void action("retry")}>重试可重试失败项</button>{" "}
          <Link className="btn" href={`/agents/templates/${encodeURIComponent(detail.template_id)}/apply?version=${detail.template_version}&parent_batch_id=${encodeURIComponent(detail.id)}`}>重新预览未成功项</Link>
          <div className="bound-list">{detail.items.map((item) => <div className="bound-item" key={item.id}><div className="bound-item-body"><strong>{item.store_name} · {item.action ? actions[item.action] ?? item.action : "—"} · {states[item.status] ?? item.status}</strong><small>原 Agent {item.agent_id ?? "—"} · 预览时已发布版本 {item.old_published_version ?? "—"} → 结果版本 {item.result_version ?? "—"} · 尝试 {item.attempt_count} 次</small>{item.status === "succeeded" && item.preview ? <p>{item.result_version !== null && (item.old_published_version === null || item.result_version > item.old_published_version) ? "新版本已发布" : item.preview.flags.publish && item.result_version !== null && item.result_version === item.old_published_version ? "已与运行版本一致，未新增发布" : "草稿已保存，运行版本未改变"}</p> : null}{item.error_code ? <p>处理失败：{errors[item.error_code] ?? "处理失败，请查看任务并重新预览"} {item.retryable ? "（可重试）" : "（需重新预览）"}</p> : null}{item.result_agent_id ? <Link href={`/agents?store_id=${encodeURIComponent(item.store_id ?? "")}&agent_id=${encodeURIComponent(item.result_agent_id)}`}>查看 Agent</Link> : null}</div></div>)}</div>
          <div><button className="btn small" disabled={itemPage <= 1} onClick={() => setItemPage(itemPage - 1)}>上一页</button><span> 第 {itemPage} 页 </span><button className="btn small" disabled={itemPage >= detail.pagination.total_pages} onClick={() => setItemPage(itemPage + 1)}>下一页</button></div>
        </>}
      </div></section></div>
    </main>
    {cancelOpen ? <TemplateModal title="取消批量任务" onClose={() => { if (!busy) setCancelOpen(false); }}><div className="modal-body">已成功的店铺不会回滚，尚未处理的项目将停止。</div><div className="modal-foot"><button className="btn" disabled={busy} onClick={() => setCancelOpen(false)}>返回</button><button className="btn primary" disabled={busy} onClick={() => void action("cancel")}>确认取消</button></div></TemplateModal> : null}
  </div></div></AppShell>;
}
