"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { MagnifyingGlass } from "@phosphor-icons/react";
import { getDepartmentReception, putDepartmentReception, type Department, type ReceptionStore, type StoreView, type TeamMember } from "../../../../lib/api";
import { EmptyState, ErrorState, LoadingState } from "../../../../components/States";

type Props = { department: Department; stores: StoreView[]; members: TeamMember[]; editable: boolean };
const waitLabels: Record<string, string> = { not_configured: "尚未配置", disabled: "派单未开启", department_unlinked: "部门未负责该店", no_eligible_agent: "无合格客服", no_online_agent: "无人在线", all_at_capacity: "均已达到上限", pending: "待重试" };

export function ReceptionPanel({ department, stores, members, editable }: Props) {
  const [storeId, setStoreId] = useState(department.store_ids[0] ?? "");
  const [query, setQuery] = useState("");
  const [summaries, setSummaries] = useState<Record<string, ReceptionStore>>({});
  const [view, setView] = useState<ReceptionStore | null>(null);
  const [draft, setDraft] = useState<ReceptionStore | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => { setStoreId(department.store_ids[0] ?? ""); }, [department.id, department.store_ids]);

  const loadSummaries = useCallback(async () => {
    const results = await Promise.allSettled(department.store_ids.map((id) => getDepartmentReception(department.id, id)));
    const next: Record<string, ReceptionStore> = {};
    results.forEach((result, index) => { if (result.status === "fulfilled") next[department.store_ids[index]] = result.value; });
    setSummaries(next);
  }, [department.id, department.store_ids]);
  useEffect(() => { void loadSummaries(); }, [loadSummaries]);

  const load = useCallback(async () => {
    if (!storeId) { setView(null); setDraft(null); return; }
    setLoading(true); setError("");
    try {
      const result = await getDepartmentReception(department.id, storeId);
      setView(result); setDraft(result);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "接待配置加载失败"); }
    finally { setLoading(false); }
  }, [department.id, storeId]);
  useEffect(() => { void load(); }, [load]);

  async function save() {
    if (!draft || !storeId) return;
    setBusy(true); setNotice("");
    try {
      const saved = await putDepartmentReception(department.id, storeId, {
        enabled: draft.enabled,
        agents: draft.agents.map((agent) => ({ user_id: agent.user_id, auto_enabled: agent.active && agent.auto_enabled, capacity: agent.capacity })),
      });
      setView(saved); setDraft(saved); setSummaries((current) => ({ ...current, [storeId]: saved })); setNotice("接待配置已保存；新店铺默认关闭，开启后仅在线且有容量的客服参与派单。");
    } catch (caught) { setNotice(caught instanceof Error ? caught.message : "保存失败"); }
    finally { setBusy(false); }
  }

  const changed = draft && view && JSON.stringify({ enabled: draft.enabled, agents: draft.agents.map((item) => [item.user_id, item.auto_enabled, item.capacity]) }) !== JSON.stringify({ enabled: view.enabled, agents: view.agents.map((item) => [item.user_id, item.auto_enabled, item.capacity]) });
  const hasReceiver = !!view?.agents.some((agent) => agent.active && agent.auto_enabled && agent.accepting && agent.online && agent.pending_count < agent.capacity);
  const shownStores = useMemo(() => department.store_ids.filter((id) => { const store = stores.find((item) => item.id === id); return `${store?.name ?? ""} ${store?.alias ?? ""} ${store?.code ?? ""}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()); }), [department.store_ids, stores, query]);
  return <div className="department-panel">
    <div className="department-panel-toolbar"><span>共 {shownStores.length} 家店铺</span><label className="settings-search"><MagnifyingGlass size={16} /><input aria-label="搜索咨询分配店铺" onChange={(event) => setQuery(event.target.value)} placeholder="输入店铺名称或别名" value={query} /></label></div>
    <div className="settings-table-wrap"><table className="settings-table department-summary-table"><thead><tr><th>店铺编码</th><th>店铺名称</th><th>咨询分配情况</th><th>操作</th></tr></thead><tbody>{shownStores.map((id) => { const store = stores.find((item) => item.id === id); const summary = summaries[id]; const agents = summary?.agents.filter((agent) => agent.active && agent.auto_enabled).length ?? 0; const supervisors = members.filter((member) => member.assignments.some((assignment) => assignment.role === "supervisor" && assignment.store_id === id)).length; return <tr className={storeId === id ? "department-store-selected" : ""} key={id}><td>{store?.code ?? "—"}</td><td>{store?.name ?? id}</td><td>{summary ? <span>{summary.enabled ? `${agents} 位客服参与派单` : "自动派单关闭"} · {supervisors} 位主管监督 · 待领取 {summary.queue_count}</span> : "配置加载中或不可读取"}</td><td><button aria-label={`查看${store?.name ?? id}咨询分配`} className="department-link-button" onClick={() => setStoreId(id)} type="button">查看</button></td></tr>; })}</tbody></table></div>
    {!shownStores.length ? <EmptyState label="没有符合条件的店铺" /> : null}
    <section aria-label="店铺派单配置" className="department-reception-detail"><div className="department-panel-toolbar"><h3>{stores.find((store) => store.id === storeId)?.name ?? "店铺"} · 派单配置</h3><span>派单只调整 CRM 会话归属，不发送买家消息</span></div>
    {notice ? <p className="inline-status" role="status">{notice}</p> : null}
    {!storeId ? <EmptyState label="请先给部门分配店铺" /> : loading ? <LoadingState label="正在加载接待配置…" /> : error ? <ErrorState message={error} retry={() => void load()} /> : draft ? <>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--border)] p-3">
        <label className="flex items-center gap-2 text-sm"><input checked={draft.enabled} disabled={!editable || busy} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} type="checkbox" />启用该店自动派单</label>
        <span className="text-sm text-[var(--muted)]">待领取 {draft.queue_count} 个</span>
      </div>
      {view?.enabled && !hasReceiver ? <p className="mt-3 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800" role="alert">当前无人可接待，{view.queue_count > 0 ? `${view.queue_count} 个会话留在待领取队列` : "新咨询将进入待领取队列"}。主管可到工作台人工分配。</p> : null}
      {draft.queue_count > 0 ? <p className="mt-2 text-sm text-[var(--muted)]">待领取原因：{Object.entries(draft.queue_reasons).map(([reason, count]) => `${waitLabels[reason] ?? reason} ${count}`).join("、")}</p> : null}
      {draft.takeover_count > 0 ? <div className="mt-3 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800" role="alert">{draft.takeover_count} 个手动分配会话的原负责人已失去接待资格，请主管接管。<div className="mt-1 flex flex-wrap gap-2">{draft.takeover_conversation_ids.map((id) => <Link href={`/workspace?session=${id}`} key={id}>查看会话 {id.slice(0, 8)}</Link>)}</div></div> : null}
      <div className="settings-table-wrap mt-4"><table className="settings-table"><thead><tr><th>客服</th><th>本店回复资格</th><th>参与派单</th><th>在线状态</th><th>待回复 / 上限</th></tr></thead><tbody>{draft.agents.map((agent) => <tr key={agent.user_id}><td>{agent.name}</td><td>{agent.active ? "可回复" : "停用或无本店权限"}</td><td><label><input aria-label={`${agent.name}参与派单`} checked={agent.auto_enabled && agent.active} disabled={!editable || busy || !agent.active} onChange={(event) => setDraft({ ...draft, agents: draft.agents.map((item) => item.user_id === agent.user_id ? { ...item, auto_enabled: event.target.checked } : item) })} type="checkbox" /></label></td><td>{!agent.online ? "离线" : agent.accepting ? "接待中" : "已暂停"}</td><td><span>{agent.pending_count} / </span><input aria-label={`${agent.name}待回复上限`} className="compact-field w-20" disabled={!editable || busy} max={1000} min={1} onChange={(event) => setDraft({ ...draft, agents: draft.agents.map((item) => item.user_id === agent.user_id ? { ...item, capacity: Number(event.target.value) } : item) })} type="number" value={agent.capacity} /></td></tr>)}</tbody></table></div>
      {!draft.agents.length ? <EmptyState label="本部门暂无客服，请先加入账号并授权店铺" /> : null}
      <div className="mt-4 flex justify-end gap-2"><button className="secondary-button" onClick={() => void load()} type="button">刷新</button>{editable ? <button className="primary-button" disabled={!changed || busy} onClick={() => void save()} type="button">保存接待配置</button> : null}</div>
    </> : null}
    </section>
  </div>;
}
