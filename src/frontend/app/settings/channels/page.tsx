"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "../../../components/AppShell";
import { SettingsNav } from "../../../components/SettingsNav";
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
      if (status === "processing" && jobId && /^[0-9a-f-]{36}$/i.test(jobId)) {
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
      const connected = status === "connected";
      setNotice(
        connected
          ? en
            ? "TikTok Shop authorization completed. Read APIs remain disabled until the next gate."
            : "TikTok Shop 授权已完成；只读 API 仍需下一阶段放行。"
          : en
            ? "TikTok Shop authorization was cancelled or failed."
            : "TikTok Shop 授权已取消或失败。",
      );
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [en, load]);

  async function beginOAuth() {
    if (!selectedStoreId || authorizing) return;
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

  return (
    <AppShell>
      <main className="management-page">
        <section className="page-intro">
          <div>
            <p className="eyebrow">SYSTEM SETTINGS</p>
            <h2>{en ? "Channel management" : "渠道管理"}</h2>
            <p>{en ? "TikTok uses server-side OAuth. Shopee and Amazon remain contract-level Mocks." : "TikTok 使用服务端 OAuth；Shopee 和 Amazon 仍为契约级 Mock。"}</p>
          </div>
          <span className="status-badge disabled">Controlled rollout</span>
        </section>
        <SettingsNav />
        {notice ? <div className="inline-status" role="status">{notice}</div> : null}
        <section className="grid gap-4 xl:grid-cols-[1fr_380px]">
          <article className="management-card">
            <h3>{en ? "Channel accounts" : "渠道账号"}</h3>
            {loading ? <LoadingState label={en ? "Loading channels…" : "正在加载渠道…"} /> : error ? <ErrorState message={error} retry={() => void load()} /> : items.length ? (
              <div className="data-list">
                {items.map((channel) => (
                  <div className="data-row" key={channel.id}>
                    <div>
                      <strong>{channel.display_name}</strong>
                      <p>{channel.platform} · {stores.find((store) => store.id === channel.store_id)?.name ?? channel.store_id.slice(0, 8)} · {channel.external_store_id}</p>
                      <p>{en ? "Scopes" : "权限"}: {channel.scopes.join(", ") || "-"}</p>
                      <p>{en ? "Last synced" : "最后同步"}: {channel.last_sync_at ? new Date(channel.last_sync_at).toLocaleString() : "-"}</p>
                    </div>
                    <div className="row-actions flex items-center gap-2">
                      <span className={`status-badge ${channel.status === "connected" ? "" : "disabled"}`}>{channel.status}</span>
                      {channel.status !== "disconnected" ? <button className="text-button" type="button" onClick={() => void revoke(channel)}>{en ? "Disconnect" : "断开"}</button> : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : <EmptyState label={en ? "No channel accounts" : "暂无渠道账号"} />}
          </article>
          <div className="space-y-4">
            <article className="management-card space-y-4">
              <h3>TikTok Shop OAuth</h3>
              <label className="field-label">{en ? "Internal store" : "内部店铺"}<select className="compact-field" value={selectedStoreId} onChange={(event) => setSelectedStoreId(event.target.value)} disabled={authorizing}>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select></label>
              <button className="primary-button" type="button" disabled={!selectedStoreId || authorizing} onClick={() => void beginOAuth()}>{authorizing ? (en ? "Redirecting…" : "正在跳转…") : (en ? "Authorize TikTok Shop" : "授权 TikTok Shop")}</button>
              {!loading && !error && !stores.length ? <p>{en ? "Create an internal store before authorization." : "请先创建内部店铺，再进行授权。"} <Link className="text-button" href="/settings/stores">{en ? "Create store" : "创建店铺"}</Link></p> : null}
              <small>{en ? "Tokens are encrypted on the server and are never returned to this page." : "Token 仅在服务端加密保存，不会返回到页面。"}</small>
            </article>
            <form className="management-card space-y-4" onSubmit={(event) => void submitMock(event)}>
              <h3>{en ? "Add Mock channel" : "添加 Mock 渠道"}</h3>
              <label className="field-label">{en ? "Store" : "店铺"}<select className="compact-field" name="store_id" required>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select></label>
              <label className="field-label">{en ? "Platform" : "平台"}<select className="compact-field" name="platform"><option value="shopee">Shopee</option><option value="amazon">Amazon</option></select></label>
              <label className="field-label">{en ? "Platform store ID" : "平台店铺 ID"}<input className="compact-field" name="external_store_id" required /></label>
              <label className="field-label">{en ? "Display name" : "显示名称"}<input className="compact-field" name="display_name" required /></label>
              <label className="field-label">{en ? "Credential reference" : "凭证引用"}<input className="compact-field" name="access_token_ref" required placeholder="secret://platform/account" /><small>{en ? "Enter only a secret-manager reference." : "仅填写密钥管理引用。"}</small></label>
              <button className="primary-button" disabled={!stores.length} type="submit">{en ? "Add Mock channel" : "添加 Mock 渠道"}</button>
            </form>
          </div>
        </section>
      </main>
    </AppShell>
  );
}
