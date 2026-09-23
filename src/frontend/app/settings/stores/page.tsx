"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { SettingsNav } from "../../../components/SettingsNav";
import { EmptyState, ErrorState, LoadingState } from "../../../components/States";
import { createStore, listStores, type StoreView } from "../../../lib/api";
import { useLanguage } from "../../../lib/i18n";

export default function StoresPage() {
  const en = useLanguage() === "en";
  const [items, setItems] = useState<StoreView[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [notice, setNotice] = useState("");
  const load = useCallback(async () => { setLoading(true); try { setItems(await listStores()); setError(""); } catch (caught) { setError(caught instanceof Error ? caught.message : en ? "Failed to load stores" : "店铺加载失败"); } finally { setLoading(false); } }, [en]);
  useEffect(() => { void load(); }, [load]);
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); try { await createStore({ name: String(data.get("name")), code: String(data.get("code")), timezone: String(data.get("timezone")), currency: String(data.get("currency")) }); form.reset(); setNotice(en ? "Store created" : "店铺已创建"); await load(); } catch (caught) { setNotice(caught instanceof Error ? caught.message : en ? "Creation failed" : "创建失败"); } }
  return <AppShell><main className="management-page"><section className="page-intro"><div><p className="eyebrow">SYSTEM SETTINGS</p><h2>{en ? "Store management" : "店铺管理"}</h2><p>{en ? "Stores are the primary boundary for permissions and data isolation." : "店铺是权限和数据隔离的基本边界。"}</p></div></section><SettingsNav />{notice ? <div className="inline-status" role="status">{notice}</div> : null}<section className="grid gap-4 xl:grid-cols-[1fr_360px]"><article className="management-card"><h3>{en ? "Accessible stores" : "可访问店铺"}</h3>{loading ? <LoadingState label={en ? "Loading stores…" : "正在加载店铺…"} /> : error ? <ErrorState message={error} retry={() => void load()} /> : items.length ? <div className="data-list">{items.map((store) => <div className="data-row" key={store.id}><div><strong>{store.name}</strong><p>{store.code} · {store.timezone} · {store.currency}</p></div><span className={`status-badge ${store.status}`}>{store.status}</span></div>)}</div> : <EmptyState label={en ? "No stores" : "暂无店铺"} />}</article><form className="management-card space-y-4" onSubmit={(event) => void submit(event)}><h3>{en ? "Add store" : "新增店铺"}</h3><label className="field-label">{en ? "Name" : "名称"}<input className="compact-field" name="name" required maxLength={200} /></label><label className="field-label">{en ? "Code" : "编码"}<input className="compact-field" name="code" required pattern="[a-z0-9](?:[a-z0-9_]|-){1,99}" /></label><label className="field-label">{en ? "Timezone" : "时区"}<input className="compact-field" name="timezone" defaultValue="Asia/Shanghai" required /></label><label className="field-label">{en ? "Currency" : "币种"}<input className="compact-field" name="currency" defaultValue="CNY" minLength={3} maxLength={10} required /></label><button className="primary-button" type="submit">{en ? "Create store" : "创建店铺"}</button></form></section></main></AppShell>;
}
