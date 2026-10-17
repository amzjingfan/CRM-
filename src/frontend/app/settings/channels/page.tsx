"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ArrowClockwise, MagnifyingGlass } from "@phosphor-icons/react";
import { SettingsFrame } from "../../../components/SettingsFrame";
import { EmptyState, ErrorState, LoadingState } from "../../../components/States";
import {
  createChannel,
  deleteChannel,
  getTikTokOAuthJobStatus,
  listChannels,
  listStores,
  startTikTokOAuth,
  type ChannelView,
  type StoreView,
} from "../../../lib/api";
import { useLanguage } from "../../../lib/i18n";

export default function ChannelsPage() {
  const en = useLanguage() === "en";
  const [items, setItems] = useState<ChannelView[]>([]);
  const [stores, setStores] = useState<StoreView[]>([]);
  const [selectedStoreId, setSelectedStoreId] = useState("");
  const [loading, setLoading] = useState(true);
  const [authorizing, setAuthorizing] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [platformFilter, setPlatformFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [channels, storeItems] = await Promise.all([listChannels(), listStores()]);
      setItems(channels);
      setStores(storeItems);
      setSelectedStoreId((current) => current || storeItems[0]?.id || "");
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : en ? "Failed to load channels" : "渠道加载失败");
    } finally {
      setLoading(false);
    }
  }, [en]);

  useEffect(() => {
    void load();
    // 任务 UUID 只用于查本人进度；保留至终态使刷新后仍可恢复轮询。
    const params = new URLSearchParams(window.location.search);
    if (params.get("oauth") === "tiktok") {
      const status = params.get("status");
      const jobId = params.get("job");
      if ((status === "processing" || status === "connected") && jobId && /^[0-9a-f-]{36}$/i.test(jobId)) {
        let cancelled = false;
        let timer: number | undefined;
        let attempts = 0;
        setNotice(en ? "TikTok Shop authorization is being verified…" : "正在验证 TikTok Shop 授权…");
        const poll = async () => {
          try {
            const result = await getTikTokOAuthJobStatus(jobId);
            if (cancelled) return;
            if (result.status === "connected") {
              setNotice(en ? "TikTok Shop authorization completed. Read APIs remain disabled until the next gate." : "TikTok Shop 授权已完成；只读 API 仍需下一阶段放行。");
              window.history.replaceState({}, "", window.location.pathname);
              void load();
              return;
            }
            if (result.status === "failed" || result.status === "denied") {
              setNotice(en ? "TikTok Shop authorization failed. Please authorize again." : "TikTok Shop 授权未完成，请重新授权。");
              window.history.replaceState({}, "", window.location.pathname);
              return;
            }
          } catch (caught) {
            if (cancelled) return;
            setNotice(caught instanceof Error ? caught.message : en ? "Could not check authorization status." : "无法查询授权状态。");
            return;
          }
          attempts += 1;
          if (attempts >= 30) {
            setNotice(en ? "Authorization is taking longer than expected. Refresh this page to check again." : "授权处理时间较长，请刷新页面继续查询。");
            return;
          }
          timer = window.setTimeout(() => void poll(), 2000);
        };
        timer = window.setTimeout(() => void poll(), 500);
        return () => { cancelled = true; window.clearTimeout(timer); };
      }
      setNotice(
        status === "connected" || status === "processing"
          ? en
            ? "Could not verify this TikTok Shop authorization. Please authorize again."
            : "无法确认此次 TikTok Shop 授权，请重新授权。"
          : en
            ? "TikTok Shop authorization was cancelled or failed."
            : "TikTok Shop 授权已取消或失败。",
      );
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [en, load]);

  async function beginOAuth() {
    if (!selectedStoreId || authorizing) return;
    setNotice("");
    setAuthorizing(true);
    try {
      const result = await startTikTokOAuth(selectedStoreId);
      window.location.assign(result.authorization_url);
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : en ? "Authorization failed" : "授权发起失败");
      setAuthorizing(false);
    }
  }

  async function submitMock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await createChannel({
        store_id: String(data.get("store_id")),
        platform: String(data.get("platform")),
        external_store_id: String(data.get("external_store_id")),
        display_name: String(data.get("display_name")),
        access_token_ref: String(data.get("access_token_ref")),
        scopes: [],
      });
      form.reset();
      setNotice(en ? "Mock channel added." : "Mock 渠道已添加。");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : en ? "Creation failed" : "创建失败");
    }
  }

  async function revoke(channel: ChannelView) {
    if (!window.confirm(en ? "Disconnect this channel authorization?" : "确认断开该渠道授权？")) return;
    try {
      await deleteChannel(channel.id);
      setNotice(en ? "Channel disconnected." : "渠道已断开。");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : en ? "Revocation failed" : "撤销失败");
    }
  }

  const platforms = ["all", "tiktok", "shopee", "amazon"] as const;
  const filtered = useMemo(() => items.filter((channel) => {
    const storeName = stores.find((store) => store.id === channel.store_id)?.name ?? "";
    return (platformFilter === "all" || channel.platform === platformFilter)
      && (statusFilter === "all" || channel.status === statusFilter)
      && `${channel.display_name} ${channel.external_store_id} ${storeName}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
  }), [items, stores, platformFilter, statusFilter, query]);
  const platformItems = items.filter((channel) => platformFilter === "all" || channel.platform === platformFilter);
  const statuses = Array.from(new Set(platformItems.map((channel) => channel.status)));

  return <SettingsFrame title={en ? "Store authorizations" : "店铺授权"} description={en ? "Review connected platform accounts and authorize TikTok Shop through server-side OAuth." : "查看真实渠道授权，并通过服务端 OAuth 授权 TikTok Shop。"}>
    {notice ? <div className="inline-status" role="status">{notice}</div> : null}
    <section className="settings-card">
      <div className="settings-platforms" aria-label={en ? "Platform filter" : "平台筛选"}>{platforms.map((platform) => {
        const count = platform === "all" ? items.length : items.filter((channel) => channel.platform === platform).length;
        const label = platform === "all" ? (en ? "All" : "全部") : platform === "tiktok" ? "TikTok" : platform === "shopee" ? "Shopee Mock" : "Amazon Mock";
        return <button aria-pressed={platformFilter === platform} className={platformFilter === platform ? "active" : ""} key={platform} onClick={() => { setPlatformFilter(platform); setStatusFilter("all"); }} type="button">{label} ({count})</button>;
      })}</div>
      <div className="settings-card-heading"><div><h2>{en ? "Authorized accounts" : "授权店铺列表"}</h2><p>{en ? "Only connected data returned by the API is shown." : "仅展示当前接口返回的授权数据。"}</p></div><button className="primary-button" disabled={!selectedStoreId || authorizing} onClick={() => void beginOAuth()} type="button">{authorizing ? (en ? "Redirecting…" : "正在跳转…") : (en ? "Authorize TikTok Shop" : "授权 TikTok Shop")}</button></div>
      <div className="settings-toolbar">
        <div className="settings-segments" aria-label={en ? "Authorization status" : "授权状态"}><button aria-pressed={statusFilter === "all"} className={statusFilter === "all" ? "active" : ""} onClick={() => setStatusFilter("all")} type="button">{en ? "All" : "全部"} ({platformItems.length})</button>{statuses.map((status) => <button aria-pressed={statusFilter === status} className={statusFilter === status ? "active" : ""} key={status} onClick={() => setStatusFilter(status)} type="button">{status} ({platformItems.filter((channel) => channel.status === status).length})</button>)}</div>
        <div className="settings-toolbar-actions"><button aria-label={en ? "Refresh authorizations" : "刷新授权"} className="settings-icon-button" onClick={() => void load()} type="button"><ArrowClockwise size={18} /></button><label className="settings-search"><MagnifyingGlass size={17} /><input aria-label={en ? "Search authorizations" : "搜索授权店铺"} onChange={(event) => setQuery(event.target.value)} placeholder={en ? "Search store or platform ID" : "搜索店铺或平台 ID"} value={query} /></label></div>
      </div>
      {loading ? <LoadingState label={en ? "Loading authorizations…" : "正在加载授权…"} /> : error ? <ErrorState message={error} retry={() => void load()} /> : filtered.length ? <div className="settings-table-wrap"><table className="settings-table"><thead><tr><th>{en ? "Store name" : "店铺名称"}</th><th>{en ? "Internal store" : "内部店铺"}</th><th>{en ? "Platform" : "平台"}</th><th>{en ? "Platform ID" : "平台 ID"}</th><th>{en ? "Status" : "状态"}</th><th>{en ? "Scopes" : "权限范围"}</th><th>{en ? "Last synced" : "最近同步"}</th><th>{en ? "Actions" : "操作"}</th></tr></thead><tbody>{filtered.map((channel) => <tr key={channel.id}><td><strong>{channel.display_name}</strong></td><td>{stores.find((store) => store.id === channel.store_id)?.name ?? channel.store_id.slice(0, 8)}</td><td>{channel.platform}</td><td>{channel.external_store_id}</td><td><span className={`status-badge ${channel.status === "connected" ? "" : "disabled"}`}>{en ? channel.status : channel.status === "connected" ? "生效中" : channel.status === "disconnected" ? "已断开" : channel.status === "error" ? "异常" : channel.status}</span></td><td>{channel.scopes.join(", ") || "—"}</td><td>{channel.last_sync_at ? new Date(channel.last_sync_at).toLocaleString(en ? "en-US" : "zh-CN") : "—"}</td><td>{channel.status !== "disconnected" ? <button className="text-button" onClick={() => void revoke(channel)} type="button">{en ? "Disconnect" : "断开"}</button> : "—"}</td></tr>)}</tbody></table></div> : <EmptyState label={query || platformFilter !== "all" || statusFilter !== "all" ? (en ? "No matching authorizations" : "没有符合条件的授权") : (en ? "No channel accounts" : "暂无授权店铺")} />}
    </section>
    <section className="settings-secondary-grid">
      <article className="settings-card space-y-4"><h2>TikTok Shop OAuth</h2><label className="field-label">{en ? "Internal store" : "内部店铺"}<select className="compact-field" disabled={authorizing} onChange={(event) => setSelectedStoreId(event.target.value)} value={selectedStoreId}>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select></label><p className="settings-help">{en ? "Choose the internal store before starting authorization. Tokens remain encrypted on the server." : "先选择内部店铺，再发起授权。Token 仅在服务端加密保存。"}</p>{!loading && !error && !stores.length ? <p><Link className="text-button" href="/settings/stores">{en ? "Create store" : "创建店铺"}</Link></p> : null}</article>
      <form className="settings-card space-y-4" onSubmit={(event) => void submitMock(event)}><h2>{en ? "Add Mock channel" : "添加 Mock 渠道"}</h2><p className="settings-help">{en ? "Shopee and Amazon are contract-level Mocks only." : "Shopee 与 Amazon 目前仅用于契约级 Mock。"}</p><label className="field-label">{en ? "Store" : "店铺"}<select className="compact-field" name="store_id" required>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select></label><label className="field-label">{en ? "Platform" : "平台"}<select className="compact-field" name="platform"><option value="shopee">Shopee</option><option value="amazon">Amazon</option></select></label><label className="field-label">{en ? "Platform store ID" : "平台店铺 ID"}<input className="compact-field" name="external_store_id" required /></label><label className="field-label">{en ? "Display name" : "显示名称"}<input className="compact-field" name="display_name" required /></label><label className="field-label">{en ? "Credential reference" : "凭证引用"}<input className="compact-field" name="access_token_ref" placeholder="secret://platform/account" required /><small>{en ? "Enter only a secret-manager reference." : "仅填写密钥管理引用。"}</small></label><button className="primary-button" disabled={!stores.length} type="submit">{en ? "Add Mock channel" : "添加 Mock 渠道"}</button></form>
    </section>
  </SettingsFrame>;
}
