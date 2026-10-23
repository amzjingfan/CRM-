"use client";

import { CaretDown, DotsThree, Info, MagnifyingGlass, Plus, X } from "@phosphor-icons/react";
import { FormEvent, MouseEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "./AppShell";
import { EmptyState, ErrorState, LoadingState } from "./States";
import { currentUser, listStores, type StoreView } from "../lib/api";
import {
  createReceptionPolicy, deleteReceptionPolicy, listReceptionPolicies, updateReceptionPolicy,
  type NewReceptionPolicy, type PolicySchedule, type ReceptionKind, type ReceptionPolicy,
} from "../lib/reception";

type ValidityMode = PolicySchedule["mode"];
type PolicyDraft = {
  name: string; content: string; timeout_minutes: string; store_ids: string[]; enabled: boolean;
  validity_mode: ValidityMode; start_date: string; end_date: string;
  daily_start_time: string; daily_end_time: string; legacy_unchanged: boolean;
};
type DisplayStatus = "active" | "not_started" | "expired" | "disabled";
const statusLabels: Record<DisplayStatus, string> = {
  active: "生效中", not_started: "未开始", expired: "已过期", disabled: "未启用",
};
const blankDraft = (storeId: string): PolicyDraft => ({
  name: "", content: "", timeout_minutes: "30", store_ids: storeId ? [storeId] : [], enabled: true,
  validity_mode: "long_term", start_date: "", end_date: "", daily_start_time: "", daily_end_time: "",
  legacy_unchanged: false,
});
const errorText = (error: unknown) => error instanceof Error ? error.message : "操作失败，请重试。";

function dateAtStore(instant: Date, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(instant);
  const value = (key: string) => parts.find((part) => part.type === key)?.value ?? "00";
  return { date: `${value("year")}-${value("month")}-${value("day")}`, time: `${value("hour")}:${value("minute")}` };
}

function policyStatus(policy: ReceptionPolicy, stores: StoreView[], now = new Date()): DisplayStatus {
  if (!policy.enabled) return "disabled";
  const schedule = policy.schedule;
  if (schedule) {
    if (schedule.mode === "long_term") return "active";
    // 多店时只要一家店处于配置时段，就展示为生效中；实际自动发送仍未接入。
    const perStore = policy.store_ids.map((id): DisplayStatus => {
      const timezone = stores.find((store) => store.id === id)?.timezone || "UTC";
      const local = dateAtStore(now, timezone);
      if (schedule.start_date && local.date < schedule.start_date) return "not_started";
      if (schedule.end_date && local.date > schedule.end_date) return "expired";
      if (schedule.mode === "fixed_hours") {
        if (schedule.daily_start_time && local.time < schedule.daily_start_time.slice(0, 5)) return "not_started";
        if (schedule.daily_end_time && local.time >= schedule.daily_end_time.slice(0, 5)) {
          return schedule.end_date && local.date < schedule.end_date ? "not_started" : "expired";
        }
      }
      return "active";
    });
    return perStore.includes("active") ? "active" : perStore.includes("not_started") ? "not_started" : "expired";
  }
  if (policy.valid_from && now < new Date(policy.valid_from)) return "not_started";
  if (policy.valid_to && now > new Date(policy.valid_to)) return "expired";
  return "active";
}

function validityText(policy: ReceptionPolicy): string {
  const schedule = policy.schedule;
  if (schedule) {
    if (schedule.mode === "long_term") return "长期";
    const dates = `${schedule.start_date} 至 ${schedule.end_date}`;
    return schedule.mode === "fixed_hours"
      ? `${dates} · 每天 ${schedule.daily_start_time?.slice(0, 5)}–${schedule.daily_end_time?.slice(0, 5)}`
      : dates;
  }
  return policy.valid_from || policy.valid_to
    ? `${policy.valid_from ? new Date(policy.valid_from).toLocaleString("zh-CN") : "不限"} 至 ${policy.valid_to ? new Date(policy.valid_to).toLocaleString("zh-CN") : "不限"}`
    : "长期";
}

function StoreMultiSelect({ stores, selected, onChange, label = "适用店铺" }: {
  stores: StoreView[]; selected: string[]; onChange: (ids: string[]) => void; label?: string;
}) {
  const [open, setOpen] = useState(false);
  const names = stores.filter((store) => selected.includes(store.id)).map((store) => store.alias || store.name);
  return <div className="reception-multiselect">
    <button aria-expanded={open} aria-label={label} className="reception-multiselect-trigger" onClick={() => setOpen(!open)} type="button">
      <span>{names.length ? names.join("、") : "请选择已创建的店铺"}</span><CaretDown size={15} />
    </button>
    {open ? <div aria-label={`${label}选项`} className="reception-multiselect-menu" role="group">
      <label><input checked={stores.length > 0 && selected.length === stores.length} onChange={(event) => onChange(event.target.checked ? stores.map((store) => store.id) : [])} type="checkbox" />全部店铺</label>
      {stores.map((store) => <label key={store.id}><input checked={selected.includes(store.id)} onChange={(event) => onChange(event.target.checked ? [...selected, store.id] : selected.filter((id) => id !== store.id))} type="checkbox" />{store.alias || store.name}</label>)}
    </div> : null}
  </div>;
}

export function ReceptionPolicyManager({ kind }: { kind: ReceptionKind }) {
  const title = kind === "timeout" ? "超时自动回复" : "进店欢迎语";
  const [stores, setStores] = useState<StoreView[]>([]);
  const [defaultStoreId, setDefaultStoreId] = useState("");
  const [permissions, setPermissions] = useState<string[]>([]);
  const [booting, setBooting] = useState(true);
  const [bootError, setBootError] = useState("");
  const [policies, setPolicies] = useState<ReceptionPolicy[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [filter, setFilter] = useState<"all" | "effective" | "ineffective">("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [editing, setEditing] = useState<ReceptionPolicy | "new" | null>(null);
  const [draft, setDraft] = useState<PolicyDraft>(blankDraft(""));
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);
  const [menuId, setMenuId] = useState<string | null>(null);
  const [menuPosition, setMenuPosition] = useState({ top: 0, right: 0 });
  const [deleting, setDeleting] = useState<ReceptionPolicy | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkPolicyId, setBulkPolicyId] = useState("");
  const [bulkStoreIds, setBulkStoreIds] = useState<string[]>([]);
  const [now, setNow] = useState(() => new Date());

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
      setDefaultStoreId(requested && user.store_ids.includes(requested) ? requested : user.store_ids[0] ?? "");
    } catch (caught) { setBootError(errorText(caught)); }
    finally { setBooting(false); }
  }, []);

  useEffect(() => { void loadIdentity(); }, [loadIdentity]);
  useEffect(() => { const timer = window.setInterval(() => setNow(new Date()), 60_000); return () => window.clearInterval(timer); }, []);
  const canRead = permissions.includes("marketing.view");
  const canEdit = permissions.includes("marketing.manage");

  useEffect(() => {
    if (!stores.length || !canRead) { setPolicies([]); setLoading(false); return; }
    let cancelled = false;
    setLoading(true); setError("");
    async function load() {
      try {
        const items: ReceptionPolicy[] = [];
        for (let nextPage = 1; ; nextPage += 1) {
          const result = await listReceptionPolicies(null, kind, nextPage);
          items.push(...result.items);
          if (items.length >= result.total || !result.items.length) break;
        }
        if (!cancelled) setPolicies(items);
      } catch (caught) { if (!cancelled) setError(errorText(caught)); }
      finally { if (!cancelled) setLoading(false); }
    }
    void load();
    return () => { cancelled = true; };
  }, [stores.length, kind, canRead, refreshKey]);

  const unassigned = useMemo(() => stores.filter((store) => !policies.some((policy) => policy.store_ids.includes(store.id))), [stores, policies]);
  const shown = useMemo(() => policies.filter((policy) => {
    const state = policyStatus(policy, stores, now);
    const matchesStatus = filter === "all" || (filter === "effective" ? state === "active" : state !== "active");
    const names = policy.store_ids.map((id) => stores.find((store) => store.id === id)).filter((store): store is StoreView => Boolean(store));
    const term = search.trim().toLocaleLowerCase();
    return matchesStatus && (!term || names.some((store) => `${store.name} ${store.alias || ""}`.toLocaleLowerCase().includes(term)));
  }), [policies, stores, filter, search, now]);
  const pages = Math.max(1, Math.ceil(shown.length / pageSize));
  const visible = shown.slice((Math.min(page, pages) - 1) * pageSize, Math.min(page, pages) * pageSize);
  const menuPolicy = policies.find((policy) => policy.id === menuId);

  function toggleMenu(item: ReceptionPolicy, event: MouseEvent<HTMLButtonElement>) {
    if (menuId === item.id) { setMenuId(null); return; }
    const rect = event.currentTarget.getBoundingClientRect();
    const top = rect.bottom + 120 > window.innerHeight ? Math.max(8, rect.top - 116) : rect.bottom + 4;
    setMenuPosition({ top, right: Math.max(8, window.innerWidth - rect.right) });
    setMenuId(item.id);
  }

  function openEditor(item?: ReceptionPolicy) {
    setEditing(item ?? "new"); setFormError(""); setMenuId(null);
    if (!item) { setDraft(blankDraft(defaultStoreId)); return; }
    const schedule = item.schedule;
    const legacy = !schedule && Boolean(item.valid_from || item.valid_to);
    const timezone = stores.find((store) => store.id === item.store_ids[0])?.timezone || "UTC";
    setDraft({
      name: item.name, content: item.content, timeout_minutes: String(item.timeout_minutes ?? 30),
      store_ids: [...item.store_ids], enabled: item.enabled,
      validity_mode: schedule?.mode ?? (legacy ? "date_range" : "long_term"),
      start_date: schedule?.start_date ?? (item.valid_from ? dateAtStore(new Date(item.valid_from), timezone).date : ""),
      end_date: schedule?.end_date ?? (item.valid_to ? dateAtStore(new Date(item.valid_to), timezone).date : ""),
      daily_start_time: schedule?.daily_start_time?.slice(0, 5) ?? "",
      daily_end_time: schedule?.daily_end_time?.slice(0, 5) ?? "", legacy_unchanged: legacy,
    });
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing || busy) return;
    const name = draft.name.trim();
    const content = draft.content.trim();
    if (!name || !content || content.length > 2000) { setFormError("请填写名称和不超过 2000 字的文本内容。"); return; }
    if (!draft.store_ids.length) { setFormError("请至少选择一个适用店铺。"); return; }
    const minutes = kind === "timeout" ? Number(draft.timeout_minutes) : null;
    if (kind === "timeout" && (!Number.isInteger(minutes) || minutes === null || minutes < 1 || minutes > 43_200)) { setFormError("超时分钟需为 1–43200 的整数。"); return; }
    const legacy = editing !== "new" && draft.legacy_unchanged;
    if (!legacy && draft.validity_mode !== "long_term" && (!draft.start_date || !draft.end_date || draft.end_date < draft.start_date)) {
      setFormError("请选择正确的起止日期。"); return;
    }
    if (!legacy && draft.validity_mode === "fixed_hours" && (!draft.daily_start_time || !draft.daily_end_time || draft.daily_end_time <= draft.daily_start_time)) {
      setFormError("请选择同一天内正确的每日起止时间。"); return;
    }
    const schedule: PolicySchedule | null = legacy ? null : {
      mode: draft.validity_mode,
      start_date: draft.validity_mode === "long_term" ? null : draft.start_date,
      end_date: draft.validity_mode === "long_term" ? null : draft.end_date,
      daily_start_time: draft.validity_mode === "fixed_hours" ? draft.daily_start_time : null,
      daily_end_time: draft.validity_mode === "fixed_hours" ? draft.daily_end_time : null,
    };
    const payload: NewReceptionPolicy = {
      kind, name, content, timeout_minutes: minutes, schedule,
      valid_from: legacy ? editing.valid_from : null, valid_to: legacy ? editing.valid_to : null,
      enabled: draft.enabled, store_ids: draft.store_ids,
    };
    setBusy(true); setFormError("");
    try {
      if (editing === "new") await createReceptionPolicy(payload);
      else await updateReceptionPolicy(editing.id, payload);
      setEditing(null); setNotice("配置已保存。自动发送仍未启用。"); setRefreshKey((key) => key + 1);
    } catch (caught) { setFormError(errorText(caught)); }
    finally { setBusy(false); }
  }

  async function copy(item: ReceptionPolicy) {
    setBusy(true); setError(""); setMenuId(null);
    try {
      await createReceptionPolicy({ kind, name: `${item.name}（副本）`, content: item.content, timeout_minutes: item.timeout_minutes,
        schedule: item.schedule, valid_from: item.valid_from, valid_to: item.valid_to, enabled: false, store_ids: item.store_ids });
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

  async function reorder(item: ReceptionPolicy, direction: "down" | "bottom") {
    const ordered = [...policies];
    const from = ordered.findIndex((policy) => policy.id === item.id);
    if (from < 0 || from === ordered.length - 1) return;
    ordered.splice(from, 1);
    ordered.splice(direction === "down" ? from + 1 : ordered.length, 0, item);
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

  async function bulkAssign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = policies.find((policy) => policy.id === bulkPolicyId);
    if (!target || !bulkStoreIds.length) return;
    setBusy(true); setError("");
    try {
      await updateReceptionPolicy(target.id, { store_ids: [...new Set([...target.store_ids, ...bulkStoreIds])] });
      setBulkOpen(false); setNotice("店铺已加入策略。自动发送仍未启用。"); setRefreshKey((key) => key + 1);
    } catch (caught) { setError(errorText(caught)); }
    finally { setBusy(false); }
  }

  return <AppShell><main className="reception-page reception-policy-page">
    <header className="reception-policy-heading"><div><h1>{title}</h1><p>仅保存配置，不自动向买家发送</p></div>
      <label className="reception-policy-search"><input aria-label="按店铺名称或别名搜索" onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="输入店铺名称/别名" value={search} /><MagnifyingGlass aria-hidden="true" size={17} /></label>
    </header>
    {notice ? <p className="reception-notice" role="status">{notice}</p> : null}
    <div className="reception-policy-tools">
      <div aria-label="策略筛选" className="reception-policy-tabs" role="group">
        {([["all", "全部策略"], ["effective", "有效策略"], ["ineffective", "失效策略"]] as const).map(([value, label]) => <button aria-pressed={filter === value} className={filter === value ? "active" : ""} key={value} onClick={() => { setFilter(value); setPage(1); }} type="button">{label}</button>)}
      </div>
      <div className="reception-policy-actions"><span>未加入策略的店铺：{unassigned.length}</span><button disabled={!canEdit || !unassigned.length || !policies.length} onClick={() => { setBulkPolicyId(policies[0]?.id ?? ""); setBulkStoreIds(unassigned.map((store) => store.id)); setBulkOpen(true); }} type="button">批量设置</button><button className="primary-button" disabled={!stores.length || !canEdit} onClick={() => openEditor()} type="button"><Plus size={16} />新增策略</button></div>
    </div>
    {error ? <p className="reception-form-error" role="alert">{error}</p> : null}
    <section className="reception-card reception-policy-card">
      {booting ? <LoadingState label="正在读取授权店铺…" /> : bootError ? <ErrorState message={bootError} retry={() => void loadIdentity()} /> : !stores.length ? <div className="reception-empty"><h2>暂无可管理店铺</h2><p>请先完成店铺授权，再管理基础接待配置。</p></div> : !canRead ? <div className="reception-empty"><h2>当前账号无营销查看权限</h2><p>请联系管理员开通营销权限。</p></div> : loading ? <LoadingState label="正在加载配置…" /> : error ? <ErrorState message={error} retry={() => setRefreshKey((key) => key + 1)} /> : shown.length ? <>
        <div className="reception-table-wrap"><table className="reception-table reception-policy-table"><thead><tr><th>执行顺序</th><th>策略名称</th><th>发送内容</th><th><span className="reception-status-help">策略状态 <Info size={14} aria-label="策略状态说明" tabIndex={0} /><span className="reception-status-tooltip">生效中：开关开启且当前时间在有效期内<br />未开始：开关开启且当前时间在开始时间之前<br />已过期：开关开启且当前时间在结束时间之后<br />未启用：策略开关关闭</span></span></th><th>有效期</th><th>适用店铺</th><th>策略开关</th><th>操作</th></tr></thead><tbody>{visible.map((policy) => {
          const state = policyStatus(policy, stores, now);
          const names = policy.store_ids.map((id) => stores.find((store) => store.id === id)?.alias || stores.find((store) => store.id === id)?.name || id);
          return <tr key={policy.id}><td>{policies.findIndex((item) => item.id === policy.id) + 1}</td><td><strong>{policy.name}</strong>{kind === "timeout" ? <small className="reception-policy-delay">超时 {policy.timeout_minutes} 分钟</small> : null}</td><td><span className="reception-summary" title={policy.content}>{policy.content}</span></td><td><span className={`reception-policy-status ${state}`}><i />{statusLabels[state]}</span></td><td><span className="reception-policy-validity">{validityText(policy)}</span></td><td><span className="reception-policy-store-count" title={names.join("、")}>{names.length} 家店铺 <span>···</span></span></td><td><button aria-label={`${policy.name}配置开关`} aria-pressed={policy.enabled} className={`reception-switch ${policy.enabled ? "on" : ""}`} disabled={!canEdit || busy} onClick={() => void toggle(policy)} title="仅配置状态，不自动发送" type="button"><span />{policy.enabled ? "开" : "关"}</button></td><td><div className="reception-row-actions"><button disabled={!canEdit || busy} onClick={() => openEditor(policy)} type="button">编辑</button><button disabled={!canEdit || busy} onClick={() => void copy(policy)} type="button">复制</button><span className="reception-more-wrap"><button aria-expanded={menuId === policy.id} aria-label={`${policy.name}更多操作`} disabled={!canEdit || busy} onClick={(event) => toggleMenu(policy, event)} type="button"><DotsThree size={17} /> 更多</button></span></div></td></tr>;
        })}</tbody></table></div>
        <div className="reception-pagination"><span>已为您查询到 {shown.length} 条记录</span><button aria-label="上一页" disabled={page <= 1} onClick={() => setPage(page - 1)} type="button">‹</button><strong>{Math.min(page, pages)}</strong><button aria-label="下一页" disabled={page >= pages} onClick={() => setPage(page + 1)} type="button">›</button><select aria-label="每页条数" onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }} value={pageSize}><option value={10}>10 条/页</option><option value={20}>20 条/页</option><option value={50}>50 条/页</option></select></div>
      </> : <EmptyState label={search || filter !== "all" ? "没有符合条件的策略" : `暂无${title}配置`} />}
    </section>

    {menuPolicy ? <div className="reception-more-menu reception-policy-floating-menu" style={menuPosition}><button disabled={policies.at(-1)?.id === menuPolicy.id} onClick={() => void reorder(menuPolicy, "down")} type="button">下移</button><button disabled={policies.at(-1)?.id === menuPolicy.id} onClick={() => void reorder(menuPolicy, "bottom")} type="button">置底</button><button onClick={() => { setDeleting(menuPolicy); setMenuId(null); }} type="button">删除</button></div> : null}
    {editing ? <div className="reception-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setEditing(null); }}><section aria-label={`${editing === "new" ? "新增" : "编辑"}${title}`} aria-modal="true" className="reception-modal reception-policy-editor" role="dialog"><header><div><h2>{editing === "new" ? "新增" : "编辑"}{title}</h2><p>仅保存策略配置；不会自动向买家发送。</p></div><button aria-label="关闭" className="reception-icon-button" onClick={() => setEditing(null)} type="button"><X size={20} /></button></header><form onSubmit={(event) => void save(event)}><div className="reception-policy-fields">
      <label className="reception-field">策略名称<input aria-label="策略名称" maxLength={100} onChange={(event) => setDraft({ ...draft, name: event.target.value })} required value={draft.name} /></label>
      {kind === "timeout" ? <label className="reception-field">超时分钟<input aria-label="超时分钟" max={43200} min={1} onChange={(event) => setDraft({ ...draft, timeout_minutes: event.target.value })} required type="number" value={draft.timeout_minutes} /></label> : null}
      <div className="reception-field"><span>适用店铺</span><StoreMultiSelect onChange={(store_ids) => setDraft({ ...draft, store_ids })} selected={draft.store_ids} stores={stores} /></div>
      <fieldset className="reception-validity"><legend>有效期 <small>任务执行时间以站点时区为准</small></legend><div className="reception-validity-options">{([["long_term", "长期"], ["date_range", "起止"], ["fixed_hours", "固定时段"]] as const).map(([value, label]) => <label key={value}><input checked={draft.validity_mode === value} name="validity_mode" onChange={() => setDraft({ ...draft, validity_mode: value, legacy_unchanged: false })} type="radio" />{label}</label>)}</div>
        {draft.validity_mode !== "long_term" ? <div className="reception-validity-range"><label>起始日期<input aria-label="开始日期" onChange={(event) => setDraft({ ...draft, start_date: event.target.value, legacy_unchanged: false })} required={!draft.legacy_unchanged} type="date" value={draft.start_date} /></label><span>→</span><label>结束日期<input aria-label="结束日期" min={draft.start_date} onChange={(event) => setDraft({ ...draft, end_date: event.target.value, legacy_unchanged: false })} required={!draft.legacy_unchanged} type="date" value={draft.end_date} /></label></div> : null}
        {draft.validity_mode === "fixed_hours" ? <div className="reception-validity-range"><span>每天</span><label>开始时间<input aria-label="每天开始时间" onChange={(event) => setDraft({ ...draft, daily_start_time: event.target.value, legacy_unchanged: false })} required type="time" value={draft.daily_start_time} /></label><span>→</span><label>结束时间<input aria-label="每天结束时间" onChange={(event) => setDraft({ ...draft, daily_end_time: event.target.value, legacy_unchanged: false })} required type="time" value={draft.daily_end_time} /></label></div> : null}
      </fieldset>
      <label className="reception-field">回复内容<textarea aria-label="回复内容" maxLength={2000} onChange={(event) => setDraft({ ...draft, content: event.target.value })} placeholder="输入文本内容" required rows={5} value={draft.content} /><small>{draft.content.length}/2000 字</small></label>
      <div className="reception-media-row"><span>文本内容</span><button disabled title="本期不支持图片" type="button">图片 · 本期不可用</button><button disabled title="本期不支持视频" type="button">视频 · 本期不可用</button></div>
      <label className="reception-check"><input checked={draft.enabled} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} type="checkbox" />启用配置开关（不会自动发送）</label>
    </div>{formError ? <p className="reception-form-error" role="alert">{formError}</p> : null}<footer className="reception-modal-footer"><button className="secondary-button" onClick={() => setEditing(null)} type="button">取消</button><button className="primary-button" disabled={busy || !canEdit} type="submit">{busy ? "正在保存…" : "保存配置"}</button></footer></form></section></div> : null}
    {bulkOpen ? <div className="reception-modal-backdrop"><section aria-label="批量设置店铺" aria-modal="true" className="reception-modal reception-policy-bulk" role="dialog"><header><h2>批量设置未加入策略的店铺</h2><button aria-label="关闭" className="reception-icon-button" onClick={() => setBulkOpen(false)} type="button"><X size={20} /></button></header><form onSubmit={(event) => void bulkAssign(event)}><div className="reception-policy-fields"><label className="reception-field">选择策略<select aria-label="选择策略" onChange={(event) => setBulkPolicyId(event.target.value)} value={bulkPolicyId}>{policies.map((policy) => <option key={policy.id} value={policy.id}>{policy.name}</option>)}</select></label><div className="reception-field"><span>未加入策略的店铺</span><StoreMultiSelect label="批量适用店铺" onChange={setBulkStoreIds} selected={bulkStoreIds} stores={unassigned} /></div></div><footer className="reception-modal-footer"><button className="secondary-button" onClick={() => setBulkOpen(false)} type="button">取消</button><button className="primary-button" disabled={busy || !bulkStoreIds.length} type="submit">保存设置</button></footer></form></section></div> : null}
    {deleting ? <div className="reception-modal-backdrop"><section aria-label="删除策略" aria-modal="true" className="reception-confirm" role="alertdialog"><h2>删除策略“{deleting.name}”？</h2><p>删除后此配置无法在列表中恢复。</p><div><button className="secondary-button" onClick={() => setDeleting(null)} type="button">取消</button><button className="danger-button" disabled={busy} onClick={() => void remove()} type="button">确认删除</button></div></section></div> : null}
  </main></AppShell>;
}
