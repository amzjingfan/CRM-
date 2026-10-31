"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowClockwise, Copy, MagnifyingGlass, PencilSimple, Plus, X } from "@phosphor-icons/react";
import { SettingsFrame } from "../../../components/SettingsFrame";
import { EmptyState, ErrorState, LoadingState } from "../../../components/States";
import {
  currentUser, deleteChannel, getTikTokOAuthJobStatus, listStoreAuthorizations,
  selectTikTokOAuthShops, startNewTikTokStoreOAuth, startTikTokOAuth, updateStoreAlias,
  ApiError,
  type ChannelView, type StoreView, type TikTokOAuthShopChoice,
} from "../../../lib/api";
import { useLanguage } from "../../../lib/i18n";

type Filter = "all" | "abnormal" | "expiring" | "expired";
type StoreRow = { store: StoreView; channel: ChannelView | null; state: "active" | "abnormal" | "expiring" | "expired" };

const sites: Record<string, string> = {
  US: "美国", GB: "英国", UK: "英国", CA: "加拿大", MX: "墨西哥", BR: "巴西",
  DE: "德国", FR: "法国", IT: "意大利", ES: "西班牙", IE: "爱尔兰", JP: "日本",
  AU: "澳大利亚", SG: "新加坡", MY: "马来西亚", TH: "泰国", VN: "越南", ID: "印尼", PH: "菲律宾",
};

function rowState(channel: ChannelView | null): StoreRow["state"] {
  if (!channel) return "abnormal";
  if (channel.status === "expired") return "expired";
  if (channel.status !== "connected") return "abnormal";
  if (!channel.authorization_expires_at) return "abnormal";
  const remaining = new Date(channel.authorization_expires_at).getTime() - Date.now();
  if (!Number.isFinite(remaining)) return "abnormal";
  if (remaining <= 0) return "expired";
  if (channel.authorization_status === "reauthorization_required") return "expiring";
  return remaining <= 30 * 24 * 60 * 60 * 1000 ? "expiring" : "active";
}

function showDate(value: string | null | undefined, en: boolean): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString(en ? "en-US" : "zh-CN", { hour12: false });
}

function oauthFailureReason(code: string | null, en: boolean): string {
  const reasons: Record<string, [string, string]> = {
    STATE_EXPIRED: ["授权等待已过期", "Authorization timed out"],
    SELECTION_EXPIRED: ["店铺选择已过期", "Shop selection expired"],
    INVALID_JOB_CREDENTIAL: ["授权回调凭证无效", "Authorization callback was invalid"],
    TOKEN_INVALID: ["TikTok 授权凭证无效", "TikTok credentials were invalid"],
    PERMISSION_DENIED: ["授权账号或权限不符合要求", "Account or permission was rejected"],
    RESOURCE_CONFLICT: ["店铺绑定冲突或授权范围已变化", "Store binding conflicted or authorization changed"],
    THIRD_PARTY_ERROR: ["TikTok 接口或授权服务暂时失败", "TikTok or the authorization service failed"],
  };
  const reason = reasons[code ?? ""];
  return reason ? reason[en ? 1 : 0] : en ? "Authorization could not be completed" : "授权未能完成";
}

export default function StoresPage() {
  const en = useLanguage() === "en";
  const [rows, setRows] = useState<StoreRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const loadedRef = useRef(false);
  const loadRequestId = useRef(0);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [retryStoreId, setRetryStoreId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [aliasDraft, setAliasDraft] = useState("");
  const [deleteRow, setDeleteRow] = useState<StoreRow | null>(null);
  const [selection, setSelection] = useState<{ jobId: string; shops: TikTokOAuthShopChoice[]; expiresAt: string | null } | null>(null);
  const [selectionOpen, setSelectionOpen] = useState(false);
  const [selectedShopIds, setSelectedShopIds] = useState<string[]>([]);
  const [selectionError, setSelectionError] = useState("");
  const [canManageDetails, setCanManageDetails] = useState(false);

  useEffect(() => { void currentUser().then((user) => setCanManageDetails(user.role === "admin")).catch(() => setCanManageDetails(false)); }, []);

  useEffect(() => {
    if (!deleteRow || working) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDeleteRow(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [deleteRow, working]);

  useEffect(() => {
    if (!selectionOpen || working) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectionOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [selectionOpen, working]);

  const load = useCallback(async () => {
    const requestId = ++loadRequestId.current;
    if (loadedRef.current) setRefreshing(true);
    else setLoading(true);
    setError("");
    try {
      const result = await listStoreAuthorizations();
      if (requestId !== loadRequestId.current) return null;
      // 仅隐藏使用者主动删除的授权；平台侧撤销仍显示异常以便重新添加。
      const nextRows = result.filter(({ store, channel }) => channel.store_id === store.id
        && !(channel.status === "disconnected" && channel.authorization_status === "revoked"))
        .map(({ store, channel }) => ({ store, channel, state: rowState(channel) }));
      setRows(nextRows);
      loadedRef.current = true;
      setHasLoaded(true);
      setError("");
      return nextRows;
    } catch (caught) {
      if (requestId !== loadRequestId.current) return null;
      if (caught instanceof ApiError && (caught.status === 401 || caught.status === 403)) {
        setRows([]);
        loadedRef.current = false;
        setHasLoaded(false);
      }
      setError(caught instanceof Error ? caught.message : en ? "Failed to load stores" : "店铺加载失败");
      return null;
    } finally {
      if (requestId === loadRequestId.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [en]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("oauth") !== "tiktok") return;
    const status = params.get("status");
    const jobId = params.get("job");
    if ((status === "processing" || status === "connected" || status === "selection_required") && jobId && /^[0-9a-f-]{36}$/i.test(jobId)) {
      let stopped = false;
      let timer: number;
      let attempts = 0;
      setNotice(en ? "Verifying TikTok Shop authorization…" : "正在验证 TikTok Shop 授权…");
      const poll = async () => {
        try {
          const result = await getTikTokOAuthJobStatus(jobId);
          if (stopped) return;
          if (result.status === "selection_required") {
            setSelection({ jobId, shops: result.shops, expiresAt: result.selection_expires_at });
            setSelectionOpen(true);
            setSelectedShopIds([]);
            setSelectionError("");
            setNotice(en ? "Select the shops to connect from this seller authorization." : "请选择本次卖家授权要接入的店铺。");
            return;
          }
          if (result.status === "connected" || result.status === "failed" || result.status === "denied") {
            window.history.replaceState({}, "", window.location.pathname);
            if (result.status === "connected") {
              setRetryStoreId(null);
              const refreshed = await load();
              if (!stopped) setNotice(refreshed?.some((row) => (!result.store_id || row.store.id === result.store_id)
                && row.channel?.platform === "tiktok" && row.channel.status === "connected")
                ? en ? "Store and channel are connected." : "店铺与渠道均已连接。"
                : en ? "Authorization finished, but a connected store and channel are not visible yet. Refresh to confirm." : "授权已处理，但尚未看到店铺与渠道均连接；请刷新确认状态。");
            } else if (result.status === "denied") {
              setRetryStoreId(result.store_id);
              setNotice(result.store_id
                ? en ? "Authorization was cancelled. Retry this store if needed." : "授权已取消；可重试该店授权。"
                : en ? "Authorization was cancelled. Add a store to try again." : "授权已取消；可从“添加店铺”重新发起。");
            } else {
              setRetryStoreId(result.store_id);
              setNotice(`${oauthFailureReason(result.error_code, en)}${result.store_id
                ? en ? ". Retry this store." : "；可重试该店授权。"
                : en ? ". Add a store to try again." : "；可从“添加店铺”重新发起。"}`);
            }
            return;
          }
        } catch (caught) {
          if (!stopped) setNotice(caught instanceof Error ? caught.message : en ? "Could not check authorization." : "无法查询授权状态。");
          return;
        }
        attempts += 1;
        if (attempts >= 30) {
          setNotice(en ? "Still processing. Refresh to check again." : "授权处理时间较长，请刷新页面继续查询。");
          return;
        }
        timer = window.setTimeout(() => void poll(), 2000);
      };
      timer = window.setTimeout(() => void poll(), 500);
      return () => { stopped = true; window.clearTimeout(timer); };
    }
    setNotice(status === "denied" ? en ? "Authorization was cancelled. Add a store to try again." : "授权已取消；可从“添加店铺”重新发起。" : en ? "Could not verify authorization. Add a store to try again." : "无法确认授权结果；可从“添加店铺”重新发起。");
    window.history.replaceState({}, "", window.location.pathname);
  }, [en, load]);

  const visible = useMemo(() => rows.filter((row) => {
    const search = query.trim().toLocaleLowerCase();
    return (filter === "all" || row.state === filter)
      && `${row.store.name} ${row.store.alias ?? ""} ${row.channel?.external_store_id ?? ""}`.toLocaleLowerCase().includes(search);
  }), [rows, filter, query]);
  const counts = { all: rows.length, abnormal: rows.filter((row) => row.state === "abnormal").length,
    expiring: rows.filter((row) => row.state === "expiring").length,
    expired: rows.filter((row) => row.state === "expired").length };

  async function authorize(storeId?: string) {
    if (working) return;
    setWorking(true);
    setNotice("");
    setRetryStoreId(null);
    try {
      const result = storeId ? await startTikTokOAuth(storeId, "/settings/stores") : await startNewTikTokStoreOAuth();
      window.location.assign(result.authorization_url);
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : en ? "Authorization could not start." : "无法发起店铺授权。");
      setWorking(false);
    }
  }

  async function confirmSelection() {
    if (!selection || !selectedShopIds.length || working) return;
    const submittedIds = [...selectedShopIds];
    setWorking(true);
    setSelectionError("");
    try {
      await selectTikTokOAuthShops(selection.jobId, selectedShopIds);
      setSelection(null);
      setSelectionOpen(false);
      setSelectedShopIds([]);
      window.history.replaceState({}, "", window.location.pathname);
      const refreshed = await load();
      setNotice(refreshed && submittedIds.every((shopId) => refreshed.some((row) => row.channel?.platform === "tiktok"
        && row.channel.external_store_id === shopId && row.channel.status === "connected"))
        ? en ? "Selected stores and channels are connected." : "所选店铺与渠道均已连接。"
        : en ? "Selection finished, but some connected stores are not visible yet. Refresh to confirm." : "店铺选择已处理，但部分店铺尚未显示已连接；请刷新确认状态。");
    } catch (caught) {
      setSelectionError(caught instanceof Error ? caught.message : en ? "Could not connect selected stores." : "接入所选店铺失败。");
    } finally { setWorking(false); }
  }

  async function saveAlias(storeId: string) {
    if (working) return;
    setWorking(true);
    try {
      const updatedStore = await updateStoreAlias(storeId, aliasDraft.trim() || null);
      setRows((current) => current.map((row) => row.store.id === storeId ? { ...row, store: updatedStore } : row));
      setEditingId(null);
      setNotice(en ? "Alias saved." : "别名已保存。");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : en ? "Could not save alias." : "别名保存失败。");
    } finally { setWorking(false); }
  }

  async function removeAuthorization() {
    if (!deleteRow?.channel || working) return;
    setWorking(true);
    try {
      await deleteChannel(deleteRow.channel.id);
      setRows((current) => current.filter((row) => row.channel?.id !== deleteRow.channel?.id));
      setDeleteRow(null);
      setNotice(en ? "Saved authorization removed. Store history was kept." : "本系统保存的授权已删除，店铺历史数据已保留。");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : en ? "Could not remove authorization." : "删除授权失败。");
    } finally { setWorking(false); }
  }

  async function copySystemId(storeId: string) {
    try {
      await navigator.clipboard.writeText(storeId);
      setNotice(en ? "System ID copied." : "系统 ID 已复制。");
    } catch {
      setNotice(en ? "Could not copy the system ID." : "无法复制系统 ID。");
    }
  }

  return <SettingsFrame title={en ? "Store list" : "店铺列表"} description={en ? "Manage TikTok Shop authorizations." : "管理 TikTok Shop 店铺授权。"}>
    {notice ? <div className="inline-status" role="status">{notice}{retryStoreId ? <> <button className="text-button" disabled={working} onClick={() => void authorize(retryStoreId)} type="button">{en ? "Retry this store" : "重试该店授权"}</button></> : null}</div> : null}
    {selection && !selectionOpen ? <div className="inline-status"><span>{en ? "TikTok shop selection is pending." : "TikTok 店铺选择尚未完成。"}</span> <button className="text-button" onClick={() => setSelectionOpen(true)} type="button">{en ? "Continue selecting shops" : "继续选择店铺"}</button></div> : null}
    <section className="settings-card store-list-card">
      <div className="settings-card-heading"><h2>{en ? "Store list" : "店铺列表"}</h2><button className="primary-button" disabled={working} onClick={() => void authorize()} type="button"><Plus size={16} />{working ? en ? "Redirecting…" : "正在处理…" : en ? "Add store" : "添加店铺"}</button></div>
      <div className="settings-toolbar">
        <div className="settings-segments" aria-label={en ? "Store authorization status" : "店铺授权状态"}>{(["all", "abnormal", "expiring", "expired"] as Filter[]).map((value) => <button aria-pressed={filter === value} className={filter === value ? "active" : ""} key={value} onClick={() => setFilter(value)} type="button">{en ? { all: "All", abnormal: "Abnormal", expiring: "Expiring", expired: "Expired" }[value] : { all: "全部", abnormal: "异常", expiring: "即将失效", expired: "已失效" }[value]} ({counts[value]})</button>)}</div>
        <div className="settings-toolbar-actions"><button aria-label={en ? "Refresh stores" : "刷新店铺"} className="settings-icon-button" disabled={refreshing} onClick={() => void load()} type="button"><ArrowClockwise size={18} /></button><label className="settings-search"><MagnifyingGlass size={17} /><input aria-label={en ? "Search stores" : "搜索店铺"} onChange={(event) => setQuery(event.target.value)} placeholder={en ? "Store name or alias" : "输入店铺名称/别名"} value={query} /></label></div>
      </div>
      {refreshing ? <p role="status">{en ? "Refreshing stores…" : "正在刷新店铺…"}</p> : null}
      {error && hasLoaded ? <div className="store-refresh-error" role="alert">{error} <button onClick={() => void load()} type="button">{en ? "Retry" : "重试"}</button></div> : null}
      {loading ? <LoadingState label={en ? "Loading stores…" : "正在加载店铺…"} /> : error && !hasLoaded ? <ErrorState message={error} retry={() => void load()} /> : visible.length ? <div className="settings-table-wrap"><table className="settings-table store-list-table"><thead><tr><th>{en ? "Store name" : "店铺名称"}</th><th>{en ? "Store alias" : "店铺别名"}</th><th>{en ? "Platform ID" : "店铺平台 ID"}</th><th>{en ? "System ID" : "系统 ID"}</th><th>{en ? "Site" : "所属站点"}</th><th>{en ? "Status" : "状态"}</th><th>{en ? "Authorization expires" : "授权到期时间"}</th><th>{en ? "Recently added" : "最近添加时间"}</th><th>{en ? "Actions" : "操作"}</th></tr></thead><tbody>{visible.map((row) => <tr key={row.store.id}>
        <td><strong>{row.channel?.display_name ?? row.store.name}</strong></td>
        <td>{editingId === row.store.id ? <form className="store-alias-edit" onSubmit={(event) => { event.preventDefault(); void saveAlias(row.store.id); }}><input aria-label={en ? "Store alias" : "店铺别名"} autoFocus maxLength={100} onChange={(event) => setAliasDraft(event.target.value)} value={aliasDraft} /><button disabled={working} type="submit">{en ? "Save" : "保存"}</button><button aria-label={en ? "Cancel editing" : "取消编辑"} onClick={() => setEditingId(null)} type="button"><X size={14} /></button></form> : <span className="store-alias-value">{row.store.alias || "—"}{canManageDetails ? <button aria-label={en ? `Edit alias for ${row.store.name}` : `编辑${row.store.name}的别名`} className="store-small-action" onClick={() => { setEditingId(row.store.id); setAliasDraft(row.store.alias ?? ""); }} type="button"><PencilSimple size={15} /></button> : null}</span>}</td>
        <td>{row.channel?.external_store_id ?? "—"}</td>
        <td><span className="store-system-id">{row.store.id}</span><button aria-label={en ? "Copy system ID" : "复制系统 ID"} className="store-small-action" onClick={() => void copySystemId(row.store.id)} type="button"><Copy size={14} /></button></td>
        <td>{row.channel?.site ? en ? row.channel.site : sites[row.channel.site.toUpperCase()] ?? row.channel.site : "—"}</td>
        <td><span className={`store-status store-status-${row.state}`}>{en ? { active: "Active", abnormal: "Abnormal", expiring: "Expiring", expired: "Expired" }[row.state] : { active: "生效中", abnormal: "异常", expiring: "即将失效", expired: "已失效" }[row.state]}</span></td>
        <td>{showDate(row.channel?.authorization_expires_at, en)}</td>
        <td>{showDate(row.channel?.last_authorized_at ?? row.store.created_at, en)}</td>
        <td className="store-row-actions">{row.channel?.status !== "connected" || row.state === "expired" || row.state === "expiring" ? <button className="text-button" disabled={working} onClick={() => void authorize(row.store.id)} type="button">{en ? "Reauthorize" : "重新授权"}</button> : null}{row.channel && canManageDetails ? <button className="text-button" disabled={working} onClick={() => setDeleteRow(row)} type="button">{en ? "Delete" : "删除"}</button> : null}</td>
      </tr>)}</tbody></table></div> : <EmptyState label={query || filter !== "all" ? en ? "No matching stores" : "没有符合条件的店铺" : en ? "No stores yet" : "暂无店铺"} />}
    </section>
    {deleteRow ? <div className="store-confirm-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !working) setDeleteRow(null); }}><section aria-labelledby="store-delete-title" aria-modal="true" className="store-confirm-dialog" role="dialog"><h2 id="store-delete-title">{en ? "Delete store authorization?" : "删除店铺授权？"}</h2><p>{en ? `Remove CRM's saved TikTok credentials for ${deleteRow.store.name} and hide this row. Its system ID and history remain. TikTok app access must be revoked separately in TikTok.` : `将删除本系统保存的“${deleteRow.store.name}”TikTok 凭证并隐藏该行；系统 ID 和历史数据保留。TikTok 平台的应用授权需在 TikTok 另行撤销。`}</p><div><button className="secondary-button" disabled={working} onClick={() => setDeleteRow(null)} type="button">{en ? "Cancel" : "取消"}</button><button className="primary-button" disabled={working} onClick={() => void removeAuthorization()} type="button">{working ? en ? "Deleting…" : "正在删除…" : en ? "Confirm delete" : "确认删除"}</button></div></section></div> : null}
    {selection && selectionOpen ? <div className="store-confirm-backdrop"><section aria-labelledby="store-selection-title" aria-describedby="store-selection-description" aria-modal="true" className="store-confirm-dialog store-selection-dialog" role="dialog"><h2 id="store-selection-title">{en ? "Select TikTok shops" : "选择 TikTok 店铺"}</h2><p id="store-selection-description">{en ? "Only checked shops will be connected. Each remains a separate CRM store." : "仅接入勾选的店铺；每家店在 CRM 中仍独立管理。"}{selection.expiresAt ? ` ${en ? "Select by" : "请在此前完成："} ${showDate(selection.expiresAt, en)}` : ""}</p><div className="store-selection-options">{selection.shops.map((shop) => <label className="store-selection-option" key={shop.id}><input checked={selectedShopIds.includes(shop.id)} onChange={(event) => setSelectedShopIds((current) => event.target.checked ? [...current, shop.id] : current.filter((id) => id !== shop.id))} type="checkbox" /><span><strong>{shop.name}</strong><small>{shop.code} · {en ? shop.region : sites[shop.region.toUpperCase()] ?? shop.region} · {shop.id}</small></span></label>)}</div>{selectionError ? <p className="store-selection-error" role="alert">{selectionError}</p> : null}<div className="store-selection-actions"><button className="secondary-button" disabled={working} onClick={() => setSelectionOpen(false)} type="button">{en ? "Later" : "稍后处理"}</button><button className="primary-button" disabled={working || !selectedShopIds.length} onClick={() => void confirmSelection()} type="button">{working ? en ? "Connecting…" : "正在接入…" : en ? `Connect ${selectedShopIds.length} shops` : `接入 ${selectedShopIds.length} 家店铺`}</button></div></section></div> : null}
  </SettingsFrame>;
}
