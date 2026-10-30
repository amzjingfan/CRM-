"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ArrowClockwise, MagnifyingGlass } from "@phosphor-icons/react";
import { SettingsFrame } from "../../../components/SettingsFrame";
import { EmptyState, ErrorState, LoadingState } from "../../../components/States";
import {
  createChannel,
  deleteChannel,
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
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : en ? "Failed to load channels" : "渠道加载失败");
    } finally {
      setLoading(false);
    }
  }, [en]);

  useEffect(() => {
    // 兼容旧回跳地址，统一由店铺页完成授权状态确认与多店选择。
    const params = new URLSearchParams(window.location.search);
    if (params.get("oauth") === "tiktok") {
      window.location.replace(`/settings/stores?${params.toString()}`);
      return;
    }
    void load();
  }, [en, load]);

  async function reauthorize(channel: ChannelView) {
    if (authorizing) return;
    setNotice("");
    setAuthorizing(true);
    try {
      const result = await startTikTokOAuth(channel.store_id, "/settings/stores");
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
  const needsReauthorization = (channel: ChannelView) => channel.platform === "tiktok"
    && (channel.status !== "connected" || channel.authorization_status === "reauthorization_required");

  return <SettingsFrame title={en ? "Store authorizations" : "店铺授权"} description={en ? "Review authorization status. Add TikTok shops from the store list." : "查看授权状态；新增 TikTok 店铺请前往店铺列表。"}>
    {notice ? <div className="inline-status" role="status">{notice}</div> : null}
    <section className="settings-card">
      <div className="settings-platforms" aria-label={en ? "Platform filter" : "平台筛选"}>{platforms.map((platform) => {
        const count = platform === "all" ? items.length : items.filter((channel) => channel.platform === platform).length;
        const label = platform === "all" ? (en ? "All" : "全部") : platform === "tiktok" ? "TikTok" : platform === "shopee" ? "Shopee Mock" : "Amazon Mock";
        return <button aria-pressed={platformFilter === platform} className={platformFilter === platform ? "active" : ""} key={platform} onClick={() => { setPlatformFilter(platform); setStatusFilter("all"); }} type="button">{label} ({count})</button>;
      })}</div>
      <div className="settings-card-heading"><div><h2>{en ? "Authorized accounts" : "授权店铺列表"}</h2><p>{en ? "Only authorization data returned by the API is shown." : "仅展示当前接口返回的授权数据。"}</p></div></div>
      <div className="settings-toolbar">
        <div className="settings-segments" aria-label={en ? "Authorization status" : "授权状态"}><button aria-pressed={statusFilter === "all"} className={statusFilter === "all" ? "active" : ""} onClick={() => setStatusFilter("all")} type="button">{en ? "All" : "全部"} ({platformItems.length})</button>{statuses.map((status) => <button aria-pressed={statusFilter === status} className={statusFilter === status ? "active" : ""} key={status} onClick={() => setStatusFilter(status)} type="button">{status} ({platformItems.filter((channel) => channel.status === status).length})</button>)}</div>
        <div className="settings-toolbar-actions"><button aria-label={en ? "Refresh authorizations" : "刷新授权"} className="settings-icon-button" onClick={() => void load()} type="button"><ArrowClockwise size={18} /></button><label className="settings-search"><MagnifyingGlass size={17} /><input aria-label={en ? "Search authorizations" : "搜索授权店铺"} onChange={(event) => setQuery(event.target.value)} placeholder={en ? "Search store or platform ID" : "搜索店铺或平台 ID"} value={query} /></label></div>
      </div>
      {loading ? <LoadingState label={en ? "Loading authorizations…" : "正在加载授权…"} /> : error ? <ErrorState message={error} retry={() => void load()} /> : filtered.length ? <div className="settings-table-wrap"><table className="settings-table"><thead><tr><th>{en ? "Store name" : "店铺名称"}</th><th>{en ? "Internal store" : "内部店铺"}</th><th>{en ? "Platform" : "平台"}</th><th>{en ? "Platform ID" : "平台 ID"}</th><th>{en ? "Status" : "状态"}</th><th>{en ? "Scopes" : "权限范围"}</th><th>{en ? "Last synced" : "最近同步"}</th><th>{en ? "Actions" : "操作"}</th></tr></thead><tbody>{filtered.map((channel) => <tr key={channel.id}><td><strong>{channel.display_name}</strong></td><td>{stores.find((store) => store.id === channel.store_id)?.name ?? channel.store_id.slice(0, 8)}</td><td>{channel.platform}</td><td>{channel.external_store_id}</td><td><span className={`status-badge ${channel.status === "connected" ? "" : "disabled"}`}>{en ? channel.status : channel.status === "connected" ? "生效中" : channel.status === "disconnected" ? "已断开" : channel.status === "error" ? "异常" : channel.status}</span></td><td>{channel.scopes.join(", ") || "—"}</td><td>{channel.last_sync_at ? new Date(channel.last_sync_at).toLocaleString(en ? "en-US" : "zh-CN") : "—"}</td><td><div className="store-row-actions">{needsReauthorization(channel) ? <button className="text-button" disabled={authorizing} onClick={() => void reauthorize(channel)} type="button">{en ? "Reauthorize" : "重新授权"}</button> : null}{channel.status !== "disconnected" ? <button className="text-button" onClick={() => void revoke(channel)} type="button">{en ? "Disconnect" : "断开"}</button> : null}</div></td></tr>)}</tbody></table></div> : <EmptyState label={query || platformFilter !== "all" || statusFilter !== "all" ? (en ? "No matching authorizations" : "没有符合条件的授权") : (en ? "No channel accounts" : "暂无授权店铺")} />}
    </section>
    <section>
      <form className="settings-card space-y-4" onSubmit={(event) => void submitMock(event)}><h2>{en ? "Add Mock channel" : "添加 Mock 渠道"}</h2><p className="settings-help">{en ? "Shopee and Amazon are contract-level Mocks only." : "Shopee 与 Amazon 目前仅用于契约级 Mock。"}</p><label className="field-label">{en ? "Store" : "店铺"}<select className="compact-field" name="store_id" required>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select></label><label className="field-label">{en ? "Platform" : "平台"}<select className="compact-field" name="platform"><option value="shopee">Shopee</option><option value="amazon">Amazon</option></select></label><label className="field-label">{en ? "Platform store ID" : "平台店铺 ID"}<input className="compact-field" name="external_store_id" required /></label><label className="field-label">{en ? "Display name" : "显示名称"}<input className="compact-field" name="display_name" required /></label><label className="field-label">{en ? "Credential reference" : "凭证引用"}<input className="compact-field" name="access_token_ref" placeholder="secret://platform/account" required /><small>{en ? "Enter only a secret-manager reference." : "仅填写密钥管理引用。"}</small></label><button className="primary-button" disabled={!stores.length} type="submit">{en ? "Add Mock channel" : "添加 Mock 渠道"}</button></form>
    </section>
  </SettingsFrame>;
}
