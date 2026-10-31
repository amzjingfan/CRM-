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
const states: Record<string, string> = { pending: "待处理", running: "处理中", succeeded: "成功", failed: "失败", needs_repreview: "需要重新预览", cancelled: "已取消", skipped: "已跳过" };
const actions: Record<string, string> = { create: "新建", adopt: "关联", update: "更新" };
function displayTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "时间未知" : new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
}

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
    const sync = () => {
      const query = new URLSearchParams(window.location.search);
      const positivePage = (key: string) => { const value = Number(query.get(key)); return Number.isSafeInteger(value) && value > 0 ? value : 1; };
      setId(query.get("batch_id") ?? ""); setPage(positivePage("page")); setItemPage(positivePage("item_page")); setCancelOpen(false);
    };
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
  function navigate(nextId: string, nextPage = page, nextItemPage = 1) {
    const query = new URLSearchParams();
    if (nextId) query.set("batch_id", nextId);
    if (nextPage > 1) query.set("page", String(nextPage));
    if (nextItemPage > 1) query.set("item_page", String(nextItemPage));
    window.history.pushState(null, "", `/agents/template-batches${query.size ? `?${query}` : ""}`);
    setId(nextId); setPage(nextPage); setItemPage(nextItemPage); setCancelOpen(false);
  }
  const current = detail?.id === id ? detail : null;
  const counts = current?.counts ?? {};
  const total = Object.values(counts).reduce((sum, count) => sum + count, 0);
  const finished = Object.entries(counts).filter(([state]) => !["pending", "running"].includes(state)).reduce((sum, [, count]) => sum + count, 0);
  return <AppShell><div className="agent-page template-page"><div className="shell">
    <header className="topbar"><div className="title"><div><h1>批量任务</h1><p>查看任务进度与各店处理结果</p></div></div></header>
    <AgentTemplateNav current="batches" />
    <main className="main batch-main">
      {error ? <p role="alert">{error}</p> : null}
      <section className="template-library batch-selector" aria-label="任务选择">
        <label className="field-group"><span>选择批量任务</span><select aria-label="选择批量任务" className="field" value={id} disabled={!list} onChange={(event) => navigate(event.target.value)}>
          <option value="">请选择任务</option>
          {id && !list?.items.some((batch) => batch.id === id) ? <option value={id}>{current ? `${label(current)} · 模板 v${current.template_version} · ${displayTime(current.created_at)}` : "当前链接的任务"}</option> : null}
          {list?.items.map((batch, index) => <option key={batch.id} value={batch.id}>任务 {(page - 1) * 20 + index + 1} · {displayTime(batch.created_at)} · 模板 v{batch.template_version} · {label(batch)}</option>)}
        </select></label>
        {!list ? <p role="status">{error ? "任务列表暂不可用，将自动重试。" : "正在加载…"}</p> : !list.items.length ? <p>暂无批量任务</p> : null}
        <div className="template-pagination"><button className="btn small" aria-label="上一页任务" disabled={page <= 1} onClick={() => navigate(id, page - 1, itemPage)}>上一页</button><span>任务第 {page} / {Math.max(list?.pagination.total_pages ?? 1, 1)} 页</span><button className="btn small" aria-label="下一页任务" disabled={!list || page >= list.pagination.total_pages} onClick={() => navigate(id, page + 1, itemPage)}>下一页</button></div>
      </section>
      <section className="config template-editor"><div className="config-body">
        {!id ? <p>选择任务查看详情。</p> : !current ? <p role="status">{error ? "任务暂不可用，将自动重试。" : "正在加载任务…"}</p> : <>
          <div className="batch-heading"><div><h2>{label(current)} · 模板 v{current.template_version}</h2><p className="help">创建于 {displayTime(current.created_at)}</p></div><div className="config-actions">
            {["queued", "running"].includes(current.status) && !current.cancel_requested ? <button className="btn" disabled={busy} onClick={() => setCancelOpen(true)}>取消任务</button> : null}
            {hasRetryable ? <button className="btn" disabled={busy} onClick={() => void action("retry")}>重试可重试失败项</button> : null}
            {current.status === "preview" ? <Link className="btn" href={`/agents/templates/${encodeURIComponent(current.template_id)}/apply?version=${current.template_version}&parent_batch_id=${encodeURIComponent(current.id)}`}>返回应用页</Link> : (counts.failed ?? 0) + (counts.needs_repreview ?? 0) + (counts.cancelled ?? 0) > 0 ? <Link className="btn" href={`/agents/templates/${encodeURIComponent(current.template_id)}/apply?version=${current.template_version}&parent_batch_id=${encodeURIComponent(current.id)}`}>重新预览未成功项</Link> : null}
          </div></div>
          {!current.processor_enabled ? <p className="inline-note" role="status">后台处理器未启用，任务不会自动推进。</p> : null}
          <div className="batch-stats">{Object.entries(current.counts).map(([key, count]) => <div key={key}><span>{states[key] ?? key}：{count}</span></div>)}</div>
          {total ? <div className="batch-progress"><progress aria-label="店铺处理进度" max={total} value={finished} /><span>已处理 {finished} / {total} 店</span></div> : null}
          <p className="help">{current.status === "preview" ? "当前仅为未确认预览，不会执行；请返回应用页审阅并确认。" : "取消不会回滚已成功的店铺；确认后的计划为只读。"}</p>
          <details className="template-details"><summary>任务技术详情</summary><p>任务 {current.id}</p>{current.parent_batch_id ? <p>续接任务 {current.parent_batch_id}</p> : null}</details>
          <div className="batch-results">{current.items.map((item) => <article className="batch-result" key={item.id}><div className="batch-result-head"><strong>{item.store_name}</strong><span className={`batch-state ${item.status}`}>{states[item.status] ?? item.status}</span></div><p className="help">{item.action ? actions[item.action] ?? item.action : "—"}{item.result_version != null ? ` · 结果版本 v${item.result_version}` : ""}</p>
            {item.status === "succeeded" && item.preview ? <p>{item.result_version !== null && (item.old_published_version === null || item.result_version > item.old_published_version) ? "新版本已发布" : item.preview.flags.publish && item.result_version !== null && item.result_version === item.old_published_version ? "已与运行版本一致，未新增发布" : "草稿已保存，运行版本未改变"}</p> : null}
            {item.error_code ? <p role="status">处理失败：{errors[item.error_code] ?? "处理失败，请查看任务并重新预览"} {item.retryable ? "（可重试）" : "（需重新预览）"}</p> : null}
            {item.result_agent_id ? <Link href={`/agents?store_id=${encodeURIComponent(item.store_id ?? "")}&agent_id=${encodeURIComponent(item.result_agent_id)}`}>查看 Agent</Link> : null}
            <details className="template-details"><summary>处理详情</summary><p>原 Agent：{item.agent_id ?? "—"}</p><p>预览时已发布版本 {item.old_published_version ?? "—"} → 结果版本 {item.result_version ?? "—"} · 尝试 {item.attempt_count} 次</p></details>
          </article>)}</div>
          <div className="template-pagination"><button className="btn small" aria-label="上一页店铺结果" disabled={itemPage <= 1} onClick={() => navigate(id, page, itemPage - 1)}>上一页</button><span>店铺结果第 {itemPage} / {Math.max(current.pagination.total_pages, 1)} 页</span><button className="btn small" aria-label="下一页店铺结果" disabled={itemPage >= current.pagination.total_pages} onClick={() => navigate(id, page, itemPage + 1)}>下一页</button></div>
        </>}
      </div></section>
    </main>
    {cancelOpen ? <TemplateModal title="取消批量任务" onClose={() => { if (!busy) setCancelOpen(false); }}><div className="modal-body">已成功的店铺不会回滚，尚未处理的项目将停止。</div><div className="modal-foot"><button className="btn" disabled={busy} onClick={() => setCancelOpen(false)}>返回</button><button className="btn primary" disabled={busy} onClick={() => void action("cancel")}>确认取消</button></div></TemplateModal> : null}
  </div></div></AppShell>;
}
