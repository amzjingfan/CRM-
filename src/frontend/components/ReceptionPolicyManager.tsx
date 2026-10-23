"use client";

import Link from "next/link";
import { ArrowClockwise, DotsThree, Plus, X } from "@phosphor-icons/react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "./AppShell";
import { EmptyState, ErrorState, LoadingState } from "./States";
import { currentUser, listStores, type StoreView } from "../lib/api";
import {
  createReceptionPolicy, deleteReceptionPolicy, listReceptionPolicies, updateReceptionPolicy,
  type NewReceptionPolicy, type ReceptionKind, type ReceptionPolicy,
} from "../lib/reception";

type PolicyDraft = { name: string; content: string; timeout_minutes: string; valid_from: string; valid_to: string; enabled: boolean; store_ids: string[] };
const blankDraft = (storeId: string): PolicyDraft => ({ name: "", content: "", timeout_minutes: "30", valid_from: "", valid_to: "", enabled: true, store_ids: storeId ? [storeId] : [] });
const errorText = (error: unknown) => error instanceof Error ? error.message : "操作失败，请重试。";
function localDate(iso: string | null) {
  if (!iso) return "";
  const date = new Date(iso);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export function ReceptionPolicyManager({ kind }: { kind: ReceptionKind }) {
  const title = kind === "timeout" ? "超时自动回复" : "进店欢迎语";
  const [stores, setStores] = useState<StoreView[]>([]);
  const [storeId, setStoreId] = useState("");
  const [permissions, setPermissions] = useState<string[]>([]);
  const [booting, setBooting] = useState(true);
  const [bootError, setBootError] = useState("");
  const [policies, setPolicies] = useState<ReceptionPolicy[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [status, setStatus] = useState<"all" | "enabled" | "disabled">("all");
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<ReceptionPolicy | "new" | null>(null);
  const [draft, setDraft] = useState<PolicyDraft>(blankDraft(""));
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);
  const [menuId, setMenuId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<ReceptionPolicy | null>(null);

  const loadIdentity = useCallback(async () => {
    setBooting(true); setBootError("");
    try {
      const user = await currentUser();
      setPermissions(user.permissions);
      let names: StoreView[] = [];
      try { names = (await listStores()).filter((store) => user.store_ids.includes(store.id)); }
      catch { setNotice("店铺名称暂时无法读取，仍可按授权店铺编号管理配置。"); }
      const byId = new Map(names.map((store) => [store.id, store]));
      setStores(user.store_ids.map((id) => byId.get(id) ?? { id, name: id, alias: null, code: id, status: "active", timezone: "UTC", currency: "", created_at: "" }));
      const requested = new URLSearchParams(window.location.search).get("store_id");
      setStoreId(requested && user.store_ids.includes(requested) ? requested : user.store_ids[0] ?? "");
    } catch (caught) { setBootError(errorText(caught)); }
    finally { setBooting(false); }
  }, []);

  useEffect(() => { void loadIdentity(); }, [loadIdentity]);
  const canRead = permissions.includes("marketing.view");
  const canEdit = permissions.includes("marketing.manage");

  useEffect(() => {
    if (!storeId || !canRead) { setPolicies([]); setLoading(false); return; }
    let cancelled = false;
    setLoading(true); setError("");
    async function load() {
      try {
        const items: ReceptionPolicy[] = [];
        let nextPage = 1;
        while (true) {
          const result = await listReceptionPolicies(storeId, kind, nextPage);
          items.push(...result.items);
          if (items.length >= result.total || result.items.length === 0) break;
          nextPage += 1;
        }
        if (!cancelled) setPolicies(items);
      } catch (caught) { if (!cancelled) setError(errorText(caught)); }
      finally { if (!cancelled) setLoading(false); }
    }
    void load();
    return () => { cancelled = true; };
  }, [storeId, kind, canRead, refreshKey]);

  const shown = useMemo(() => policies.filter((policy) =>
    (status === "all" || policy.enabled === (status === "enabled"))
    && (`${policy.name} ${policy.content}`).toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()),
  ), [policies, status, search]);

  function openEditor(item?: ReceptionPolicy) {
    setEditing(item ?? "new"); setFormError(""); setMenuId(null);
    setDraft(item ? { name: item.name, content: item.content, timeout_minutes: String(item.timeout_minutes ?? 30), valid_from: localDate(item.valid_from), valid_to: localDate(item.valid_to), enabled: item.enabled, store_ids: [...item.store_ids] } : blankDraft(storeId));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing || busy) return;
    const name = draft.name.trim();
    const content = draft.content.trim();
    if (!name || !content || content.length > 2000) { setFormError("请填写名称和不超过 2000 字的文本内容。"); return; }
    if (!draft.store_ids.length) { setFormError("请至少选择一个适用店铺。"); return; }
    const minutes = kind === "timeout" ? Number(draft.timeout_minutes) : null;
    if (kind === "timeout" && (!Number.isInteger(minutes) || minutes === null || minutes < 1 || minutes > 10080)) { setFormError("超时分钟需为 1–10080 的整数。"); return; }
    const validFrom = draft.valid_from ? new Date(draft.valid_from).toISOString() : null;
    const validTo = draft.valid_to ? new Date(draft.valid_to).toISOString() : null;
    if (validFrom && validTo && validTo <= validFrom) { setFormError("有效期结束时间必须晚于开始时间。"); return; }
    const payload: NewReceptionPolicy = { kind, name, content, timeout_minutes: minutes, valid_from: validFrom, valid_to: validTo, enabled: draft.enabled, store_ids: draft.store_ids };
    setBusy(true); setFormError("");
    try {
      if (editing === "new") await createReceptionPolicy(payload);
      else await updateReceptionPolicy(editing.id, { name, content, timeout_minutes: minutes, valid_from: validFrom, valid_to: validTo, enabled: draft.enabled, store_ids: draft.store_ids });
      setEditing(null); setNotice("配置已保存。自动发送仍未启用。"); setRefreshKey((key) => key + 1);
    } catch (caught) { setFormError(errorText(caught)); }
    finally { setBusy(false); }
  }

  async function copy(item: ReceptionPolicy) {
    setBusy(true); setError(""); setMenuId(null);
    try {
      await createReceptionPolicy({ kind, name: `${item.name}（副本）`, content: item.content, timeout_minutes: item.timeout_minutes, valid_from: item.valid_from, valid_to: item.valid_to, enabled: false, store_ids: item.store_ids });
      setNotice("配置已复制，副本的配置开关已关闭。"); setRefreshKey((key) => key + 1);
    } catch (caught) { setError(errorText(caught)); }
    finally { setBusy(false); }
  }

  async function toggle(item: ReceptionPolicy) {
    setBusy(true); setError("");
    try { await updateReceptionPolicy(item.id, { enabled: !item.enabled }); setNotice(`配置开关已${item.enabled ? "关闭" : "开启"}，自动发送仍未启用。`); setRefreshKey((key) => key + 1); }
    catch (caught) { setError(errorText(caught)); }
    finally { setBusy(false); }
  }

  async function reorder(item: ReceptionPolicy, direction: "up" | "down" | "bottom") {
    const ordered = [...policies];
    const from = ordered.findIndex((policy) => policy.id === item.id);
    if (from < 0 || (direction === "up" && from === 0) || (direction !== "up" && from === ordered.length - 1)) return;
    ordered.splice(from, 1);
    ordered.splice(direction === "up" ? from - 1 : direction === "down" ? from + 1 : ordered.length, 0, item);
    setBusy(true); setError(""); setMenuId(null);
    try {
      for (const [index, policy] of ordered.entries()) await updateReceptionPolicy(policy.id, { sort_order: index + 1 });
      setNotice("策略顺序已保存。"); setRefreshKey((key) => key + 1);
    } catch (caught) { setError(`${errorText(caught)} 请刷新确认当前顺序。`); setRefreshKey((key) => key + 1); }
    finally { setBusy(false); }
  }

  async function remove() {
    if (!deleting) return;
    setBusy(true); setError("");
    try { await deleteReceptionPolicy(deleting.id); setDeleting(null); setNotice("配置已删除。"); setRefreshKey((key) => key + 1); }
    catch (caught) { setError(errorText(caught)); setDeleting(null); }
    finally { setBusy(false); }
  }

  return <AppShell><main className="reception-page">
    <div className="reception-crumb"><Link href="/marketing">智能营销</Link><span>/</span><span>基础接待</span><span>/</span><strong>{title}</strong></div>
    <header className="reception-head"><div><span className="reception-eyebrow">BASIC RECEPTION</span><h1>{title}</h1><p>{kind === "timeout" ? "记录超时接待策略与话术，有序管理不同店铺的配置。" : "记录买家进店时的欢迎话术与适用店铺。"}</p></div><button className="primary-button" disabled={!storeId || !canEdit} onClick={() => openEditor()} type="button"><Plus size={16} />新增{title}</button></header>
    <div className="reception-config-banner" role="status"><strong>仅保存配置，自动发送未启用</strong><span>此处开关只表示配置状态，不会触发 TikTok 消息、营销任务或自动回复。</span></div>
    {notice ? <p className="reception-notice" role="status">{notice}</p> : null}
    <section className="reception-card"><div className="reception-toolbar reception-policy-toolbar"><div className="reception-filter-row"><label className="reception-select-label">店铺<select aria-label="店铺" disabled={!stores.length} onChange={(event) => setStoreId(event.target.value)} value={storeId}>{stores.map((store) => <option key={store.id} value={store.id}>{store.alias || store.name}</option>)}</select></label><label className="reception-select-label">配置状态<select aria-label="配置状态" onChange={(event) => setStatus(event.target.value as typeof status)} value={status}><option value="all">全部状态</option><option value="enabled">已配置</option><option value="disabled">已关闭</option></select></label><label className="reception-search"><input aria-label="搜索策略" onChange={(event) => setSearch(event.target.value)} placeholder="搜索策略名称或内容" value={search} /></label><button aria-label="刷新策略" className="reception-icon-button" onClick={() => setRefreshKey((key) => key + 1)} type="button"><ArrowClockwise size={18} /></button></div><span className="reception-count">共 {shown.length} 条配置</span></div>
      {booting ? <LoadingState label="正在读取授权店铺…" /> : bootError ? <ErrorState message={bootError} retry={() => void loadIdentity()} /> : !stores.length ? <div className="reception-empty"><h2>暂无可管理店铺</h2><p>请先完成店铺授权，再管理基础接待配置。</p><Link href="/settings/stores">查看店铺设置</Link></div> : !canRead ? <div className="reception-empty"><h2>当前账号无营销查看权限</h2><p>请联系管理员开通营销权限。</p></div> : loading ? <LoadingState label="正在加载配置…" /> : error ? <ErrorState message={error} retry={() => setRefreshKey((key) => key + 1)} /> : shown.length ? <div className="reception-table-wrap"><table className="reception-table reception-policy-table"><thead><tr><th>顺序</th><th>策略名称</th>{kind === "timeout" ? <th>超时</th> : null}<th>回复内容</th><th>适用店铺</th><th>有效期</th><th>配置状态</th><th>操作</th></tr></thead><tbody>{shown.map((policy) => <tr key={policy.id}><td>{policies.findIndex((item) => item.id === policy.id) + 1}</td><td><strong>{policy.name}</strong></td>{kind === "timeout" ? <td>{policy.timeout_minutes} 分钟</td> : null}<td><span className="reception-summary" title={policy.content}>{policy.content}</span></td><td>{policy.store_ids.map((id) => stores.find((store) => store.id === id)?.alias || stores.find((store) => store.id === id)?.name || id).join("、")}</td><td>{policy.valid_from || policy.valid_to ? `${policy.valid_from ? new Date(policy.valid_from).toLocaleDateString("zh-CN") : "不限"} — ${policy.valid_to ? new Date(policy.valid_to).toLocaleDateString("zh-CN") : "不限"}` : "长期"}</td><td><button aria-label={`${policy.name}配置开关`} aria-pressed={policy.enabled} className={`reception-switch ${policy.enabled ? "on" : ""}`} disabled={!canEdit || busy} onClick={() => void toggle(policy)} title="仅配置状态，自动发送未启用" type="button"><span />{policy.enabled ? "已配置" : "已关闭"}</button></td><td><div className="reception-row-actions"><button disabled={!canEdit || busy} onClick={() => openEditor(policy)} type="button">编辑</button><button disabled={!canEdit || busy} onClick={() => void copy(policy)} type="button">复制</button><button disabled={!canEdit || busy || policies[0]?.id === policy.id} onClick={() => void reorder(policy, "up")} type="button">上移</button><span className="reception-more-wrap"><button aria-expanded={menuId === policy.id} aria-label={`${policy.name}更多操作`} disabled={!canEdit || busy} onClick={() => setMenuId(menuId === policy.id ? null : policy.id)} type="button"><DotsThree size={20} /></button>{menuId === policy.id ? <span className="reception-more-menu"><button disabled={policies.at(-1)?.id === policy.id} onClick={() => void reorder(policy, "down")} type="button">下移</button><button disabled={policies.at(-1)?.id === policy.id} onClick={() => void reorder(policy, "bottom")} type="button">置底</button><button onClick={() => { setDeleting(policy); setMenuId(null); }} type="button">删除</button></span> : null}</span></div></td></tr>)}</tbody></table></div> : <EmptyState label={search || status !== "all" ? "没有符合条件的策略" : `暂无${title}配置`} />}
    </section>

    {editing ? <div className="reception-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setEditing(null); }}><section aria-label={`${editing === "new" ? "新增" : "编辑"}${title}`} aria-modal="true" className="reception-modal reception-policy-editor" role="dialog"><header><div><h2>{editing === "new" ? "新增" : "编辑"}{title}</h2><p>仅保存策略配置；不会自动向买家发送。</p></div><button aria-label="关闭" className="reception-icon-button" onClick={() => setEditing(null)} type="button"><X size={20} /></button></header><form onSubmit={(event) => void save(event)}><div className="reception-policy-fields"><label className="reception-field">策略名称<input aria-label="策略名称" maxLength={100} onChange={(event) => setDraft({ ...draft, name: event.target.value })} required value={draft.name} /></label>{kind === "timeout" ? <label className="reception-field">超时分钟<input aria-label="超时分钟" max={10080} min={1} onChange={(event) => setDraft({ ...draft, timeout_minutes: event.target.value })} required type="number" value={draft.timeout_minutes} /></label> : null}<div className="reception-field"><span>适用店铺</span><div className="reception-store-checks">{stores.map((store) => <label key={store.id}><input checked={draft.store_ids.includes(store.id)} onChange={(event) => setDraft({ ...draft, store_ids: event.target.checked ? [...draft.store_ids, store.id] : draft.store_ids.filter((id) => id !== store.id) })} type="checkbox" />{store.alias || store.name}</label>)}</div></div><div className="reception-form-row"><label className="reception-field">开始时间<input aria-label="开始时间" onChange={(event) => setDraft({ ...draft, valid_from: event.target.value })} type="datetime-local" value={draft.valid_from} /></label><label className="reception-field">结束时间<input aria-label="结束时间" onChange={(event) => setDraft({ ...draft, valid_to: event.target.value })} type="datetime-local" value={draft.valid_to} /></label></div><label className="reception-field">回复内容<textarea aria-label="回复内容" maxLength={2000} onChange={(event) => setDraft({ ...draft, content: event.target.value })} placeholder="输入文本内容" required rows={6} value={draft.content} /><small>{draft.content.length}/2000 字</small></label><div className="reception-media-row"><span>文本内容</span><button disabled title="本期不支持图片" type="button">图片 · 本期不可用</button><button disabled title="本期不支持视频" type="button">视频 · 本期不可用</button></div><label className="reception-check"><input checked={draft.enabled} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} type="checkbox" />启用配置开关（不会自动发送）</label></div>{formError ? <p className="reception-form-error" role="alert">{formError}</p> : null}<footer className="reception-modal-footer"><button className="secondary-button" onClick={() => setEditing(null)} type="button">取消</button><button className="primary-button" disabled={busy || !canEdit} type="submit">{busy ? "正在保存…" : "保存配置"}</button></footer></form></section></div> : null}
    {deleting ? <div className="reception-modal-backdrop"><section aria-label="删除策略" aria-modal="true" className="reception-confirm" role="alertdialog"><h2>删除策略“{deleting.name}”？</h2><p>删除后此配置无法在列表中恢复。</p><div><button className="secondary-button" onClick={() => setDeleting(null)} type="button">取消</button><button className="danger-button" disabled={busy} onClick={() => void remove()} type="button">确认删除</button></div></section></div> : null}
  </main></AppShell>;
}
