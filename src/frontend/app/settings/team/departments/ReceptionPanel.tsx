"use client";

import { useCallback, useEffect, useState } from "react";
import { getDepartmentReception, putDepartmentReception, type Department, type ReceptionDepartment, type StoreView, type TeamMember } from "../../../../lib/api";
import { EmptyState, ErrorState, LoadingState } from "../../../../components/States";

type Props = { department: Department; stores: StoreView[]; members: TeamMember[]; editable: boolean };
const waitLabels: Record<string, string> = { not_configured: "尚未配置", disabled: "派单未开启", department_unlinked: "部门未负责该店", no_eligible_agent: "无合格客服", no_online_agent: "无人在线", pending: "待重试" };

export function ReceptionPanel({ department, stores, editable }: Props) {
  const [view, setView] = useState<ReceptionDepartment | null>(null);
  const [draft, setDraft] = useState<ReceptionDepartment | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const result = await getDepartmentReception(department.id);
      setView(result); setDraft(result);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "接待配置加载失败"); }
    finally { setLoading(false); }
  }, [department.id]);
  useEffect(() => { void load(); }, [load]);

  async function save() {
    if (!draft) return;
    setBusy(true); setNotice("");
    try {
      const saved = await putDepartmentReception(department.id, {
        enabled: draft.enabled,
        agents: draft.agents.map((agent) => ({ user_id: agent.user_id, auto_enabled: agent.active && agent.auto_enabled })),
      });
      setView(saved); setDraft(saved);
      setNotice("部门接待配置已保存。派单仅调整 CRM 会话归属，不向买家发送消息。");
    } catch (caught) { setNotice(caught instanceof Error ? caught.message : "保存失败"); }
    finally { setBusy(false); }
  }

  const changed = draft && view && JSON.stringify([draft.enabled, draft.agents.map((item) => [item.user_id, item.auto_enabled])]) !== JSON.stringify([view.enabled, view.agents.map((item) => [item.user_id, item.auto_enabled])]);
  const hasReceiver = !!view?.agents.some((agent) => agent.active && agent.auto_enabled && agent.online);
  const storeName = (id: string) => stores.find((store) => store.id === id)?.name ?? id;

  return <div className="department-panel">
    <div className="department-panel-toolbar"><h3>部门店铺咨询分配</h3><span>统一派单到有对应店铺权限的在线客服</span></div>
    {notice ? <p className="inline-status" role="status">{notice}</p> : null}
    {!department.store_ids.length ? <EmptyState label="请先给部门分配店铺" /> : loading ? <LoadingState label="正在加载接待配置…" /> : error ? <ErrorState message={error} retry={() => void load()} /> : draft ? <>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--border)] p-3">
        <label className="flex items-center gap-2 text-sm"><input checked={draft.enabled} disabled={!editable || busy} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} type="checkbox" />启用本部门所有负责店铺的自动派单</label>
        <span className="text-sm text-[var(--muted)]">{changed ? "有未保存修改" : view?.enabled ? "已开启" : "已关闭"} · 待领取 {draft.queue_count} 个</span>
      </div>
      {view?.enabled && !hasReceiver ? <p className="mt-3 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800" role="alert">当前无人可接待，新咨询会留在待领取队列。请给客服授权店铺、勾选参与派单并确保账号已登录。</p> : null}
      {draft.queue_count > 0 ? <p className="mt-2 text-sm text-[var(--muted)]">待领取原因：{Object.entries(draft.queue_reasons).map(([reason, count]) => `${waitLabels[reason] ?? reason} ${count}`).join("、")}</p> : null}
      <div className="settings-table-wrap mt-4"><table className="settings-table"><thead><tr><th>客服</th><th>可接待店铺</th><th>参与派单</th><th>在线状态</th></tr></thead><tbody>{draft.agents.map((agent) => <tr key={agent.user_id}><td>{agent.name}</td><td>{agent.active ? agent.eligible_store_ids.map(storeName).join("、") : "无部门店铺回复权限"}</td><td><label title={agent.active ? "" : "请先在账号管理中授权负责店铺和角色"}><input aria-label={`${agent.name}参与派单`} checked={agent.auto_enabled && agent.active} disabled={!editable || busy || !agent.active} onChange={(event) => setDraft({ ...draft, agents: draft.agents.map((item) => item.user_id === agent.user_id ? { ...item, auto_enabled: event.target.checked } : item) })} type="checkbox" /></label></td><td>{agent.online ? "在线" : "离线"}</td></tr>)}</tbody></table></div>
      {!draft.agents.length ? <EmptyState label="本部门暂无客服，请先加入账号并授权店铺" /> : null}
      <div className="mt-4 flex justify-end gap-2"><button className="secondary-button" onClick={() => void load()} type="button">刷新</button>{editable ? <button className="primary-button" disabled={!changed || busy} onClick={() => void save()} type="button">保存接待配置</button> : null}</div>
    </> : null}
  </div>;
}
