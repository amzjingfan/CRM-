"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Plus, MagnifyingGlass, ArrowClockwise } from "@phosphor-icons/react";
import { SettingsFrame } from "../../../components/SettingsFrame";
import { EmptyState, ErrorState, LoadingState } from "../../../components/States";
import { createStore, listStores, type StoreView } from "../../../lib/api";
import { useLanguage } from "../../../lib/i18n";

type StatusFilter = "all" | "active" | "other";

export default function StoresPage() {
  const en = useLanguage() === "en";
  const [items, setItems] = useState<StoreView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setItems(await listStores()); setError(""); }
    catch (caught) { setError(caught instanceof Error ? caught.message : en ? "Failed to load stores" : "店铺加载失败"); }
    finally { setLoading(false); }
  }, [en]);
  useEffect(() => { void load(); }, [load]);

  const filtered = useMemo(() => items.filter((store) => {
    const matchesStatus = statusFilter === "all" || (statusFilter === "active" ? store.status === "active" : store.status !== "active");
    const matchesQuery = `${store.name} ${store.code}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
    return matchesStatus && matchesQuery;
  }), [items, query, statusFilter]);
  const activeCount = items.filter((store) => store.status === "active").length;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await createStore({ name: String(data.get("name")), code: String(data.get("code")), timezone: String(data.get("timezone")), currency: String(data.get("currency")) });
      form.reset();
      setShowCreate(false);
      setNotice(en ? "Store created" : "店铺已创建");
      await load();
    } catch (caught) { setNotice(caught instanceof Error ? caught.message : en ? "Creation failed" : "创建失败"); }
  }

  return <SettingsFrame title={en ? "Store list" : "店铺列表"} description={en ? "Manage internal stores and their data boundaries. Review platform authorizations separately." : "管理内部店铺及数据边界。平台授权状态请在“授权”页查看。"}>
    {notice ? <div className="inline-status" role="status">{notice}</div> : null}
    <section className="settings-card">
      <div className="settings-card-heading"><div><h2>{en ? "Stores" : "店铺列表"}</h2><p>{en ? `${items.length} stores · ${activeCount} active` : `共 ${items.length} 家店铺 · ${activeCount} 家正常`}</p></div><button className="primary-button" onClick={() => setShowCreate((value) => !value)} type="button"><Plus size={16} />{en ? "Add store" : "添加店铺"}</button></div>
      {showCreate ? <form className="settings-create-form" onSubmit={(event) => void submit(event)}>
        <label className="field-label">{en ? "Name" : "店铺名称"}<input className="compact-field" name="name" required maxLength={200} /></label>
        <label className="field-label">{en ? "Code" : "店铺编码"}<input className="compact-field" name="code" required pattern="[a-z0-9](?:[a-z0-9_]|-){1,99}" /></label>
        <label className="field-label">{en ? "Timezone" : "时区"}<input className="compact-field" name="timezone" defaultValue="Asia/Shanghai" required /></label>
        <label className="field-label">{en ? "Currency" : "币种"}<input className="compact-field" name="currency" defaultValue="CNY" minLength={3} maxLength={10} required /></label>
        <button className="primary-button" type="submit">{en ? "Create store" : "创建店铺"}</button>
      </form> : null}
      <div className="settings-toolbar">
        <div className="settings-segments" aria-label={en ? "Store status" : "店铺状态"}>{(["all", "active", "other"] as StatusFilter[]).map((value) => <button aria-pressed={statusFilter === value} className={statusFilter === value ? "active" : ""} key={value} onClick={() => setStatusFilter(value)} type="button">{value === "all" ? (en ? `All (${items.length})` : `全部 (${items.length})`) : value === "active" ? (en ? `Active (${activeCount})` : `正常 (${activeCount})`) : (en ? `Other (${items.length - activeCount})` : `其他 (${items.length - activeCount})`)}</button>)}</div>
        <div className="settings-toolbar-actions"><button aria-label={en ? "Refresh stores" : "刷新店铺"} className="settings-icon-button" onClick={() => void load()} type="button"><ArrowClockwise size={18} /></button><label className="settings-search"><MagnifyingGlass size={17} /><input aria-label={en ? "Search stores" : "搜索店铺"} onChange={(event) => setQuery(event.target.value)} placeholder={en ? "Search name or code" : "搜索店铺名称或编码"} value={query} /></label></div>
      </div>
      {loading ? <LoadingState label={en ? "Loading stores…" : "正在加载店铺…"} /> : error ? <ErrorState message={error} retry={() => void load()} /> : filtered.length ? <div className="settings-table-wrap"><table className="settings-table"><thead><tr><th>{en ? "Store name" : "店铺名称"}</th><th>{en ? "Code" : "店铺编码"}</th><th>{en ? "Status" : "状态"}</th><th>{en ? "Timezone" : "时区"}</th><th>{en ? "Currency" : "币种"}</th><th>{en ? "Added" : "添加时间"}</th><th>{en ? "Authorization" : "授权"}</th></tr></thead><tbody>{filtered.map((store) => <tr key={store.id}><td><strong>{store.name}</strong></td><td>{store.code}</td><td><span className={`status-badge ${store.status}`}>{en ? store.status : store.status === "active" ? "正常" : store.status === "disabled" ? "已停用" : store.status}</span></td><td>{store.timezone}</td><td>{store.currency}</td><td>{new Date(store.created_at).toLocaleString(en ? "en-US" : "zh-CN")}</td><td><Link className="text-button" href="/settings/channels">{en ? "View" : "查看"}</Link></td></tr>)}</tbody></table></div> : <EmptyState label={query || statusFilter !== "all" ? (en ? "No matching stores" : "没有符合条件的店铺") : (en ? "No stores" : "暂无店铺")} />}
    </section>
  </SettingsFrame>;
}
