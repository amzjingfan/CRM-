"use client";

import Link from "next/link";
import { ArrowClockwise, MagnifyingGlass, Plus, X } from "@phosphor-icons/react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "./AppShell";
import { EmptyState, ErrorState, LoadingState } from "./States";
import { currentUser, listStores, type StoreView } from "../lib/api";
import {
  createQuickReply, createQuickReplyGroup, deleteQuickReply, deleteQuickReplyGroup,
  listAllQuickReplyGroups, listQuickReplies, updateQuickReply, updateQuickReplyGroup,
  type NewQuickReply, type QuickReply, type QuickReplyGroup, type ReceptionScope,
} from "../lib/reception";

type ReplyDraft = { group_id: string; shortcut: string; tags: string; site_code: string; messages: string[] };
const blankDraft = (): ReplyDraft => ({ group_id: "", shortcut: "", tags: "", site_code: "", messages: [""] });
const errorText = (error: unknown) => error instanceof Error ? error.message : "操作失败，请重试。";

export function QuickReplyManager() {
  const [stores, setStores] = useState<StoreView[]>([]);
  const [storeId, setStoreId] = useState("");
  const [permissions, setPermissions] = useState<string[]>([]);
  const [booting, setBooting] = useState(true);
  const [bootError, setBootError] = useState("");
  const [scope, setScope] = useState<ReceptionScope>("personal");
  const [groups, setGroups] = useState<QuickReplyGroup[]>([]);
  const [replies, setReplies] = useState<QuickReply[]>([]);
  const [groupId, setGroupId] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [groupDrawer, setGroupDrawer] = useState(false);
  const [groupEditor, setGroupEditor] = useState<QuickReplyGroup | "new" | null>(null);
  const [groupName, setGroupName] = useState("");
  const [deletingGroup, setDeletingGroup] = useState<QuickReplyGroup | null>(null);
  const [editing, setEditing] = useState<QuickReply | "new" | null>(null);
  const [editorScope, setEditorScope] = useState<ReceptionScope>("personal");
  const [editorGroups, setEditorGroups] = useState<QuickReplyGroup[]>([]);
  const [editorGroupsLoading, setEditorGroupsLoading] = useState(false);
  const [draft, setDraft] = useState<ReplyDraft>(blankDraft);
  const [formError, setFormError] = useState("");
  const [deletingReply, setDeletingReply] = useState<QuickReply | null>(null);
  const [busy, setBusy] = useState(false);

  const loadIdentity = useCallback(async () => {
    setBooting(true); setBootError("");
    try {
      const user = await currentUser();
      setPermissions(user.permissions);
      const allowedIds = user.store_ids;
      let names: StoreView[] = [];
      try { names = (await listStores()).filter((store) => allowedIds.includes(store.id)); }
      catch { setNotice("店铺名称暂时无法读取，仍可按授权店铺编号管理快捷回复。"); }
      const byId = new Map(names.map((store) => [store.id, store]));
      setStores(allowedIds.map((id) => byId.get(id) ?? { id, name: id, alias: null, code: id, status: "active", timezone: "UTC", currency: "", created_at: "" }));
      const requested = new URLSearchParams(window.location.search).get("store_id");
      setStoreId(requested && allowedIds.includes(requested) ? requested : allowedIds[0] ?? "");
    } catch (caught) { setBootError(errorText(caught)); }
    finally { setBooting(false); }
  }, []);

  useEffect(() => { void loadIdentity(); }, [loadIdentity]);

  const canRead = scope === "personal" ? permissions.includes("workspace.reply") : permissions.includes("workspace.view");
  const canEdit = scope === "personal" ? permissions.includes("workspace.reply") : permissions.includes("marketing.manage");
  const canCreate = permissions.includes("workspace.reply") || permissions.includes("marketing.manage");
  const canEditEditor = editorScope === "personal" ? permissions.includes("workspace.reply") : permissions.includes("marketing.manage");

  useEffect(() => {
    if (!storeId || !canRead) { setGroups([]); setReplies([]); setTotal(0); setLoading(false); return; }
    let cancelled = false;
    setLoading(true); setError("");
    async function load() {
      try {
        const [allGroups, replyPage] = await Promise.all([
          listAllQuickReplyGroups(storeId, scope),
          listQuickReplies(storeId, scope, { groupId, q: query, page, pageSize: 20, includeDisabled: true }),
        ]);
        if (cancelled) return;
        setGroups(allGroups);
        setReplies(replyPage.items);
        setTotal(replyPage.total);
      } catch (caught) { if (!cancelled) setError(errorText(caught)); }
      finally { if (!cancelled) setLoading(false); }
    }
    void load();
    return () => { cancelled = true; };
  }, [storeId, scope, groupId, query, page, refreshKey, canRead]);

  useEffect(() => {
    if (!editing || !storeId) return;
    let cancelled = false;
    setEditorGroups([]); setEditorGroupsLoading(true);
    void listAllQuickReplyGroups(storeId, editorScope)
      .then((items) => { if (!cancelled) setEditorGroups(items); })
      .catch((caught: unknown) => { if (!cancelled) setFormError(errorText(caught)); })
      .finally(() => { if (!cancelled) setEditorGroupsLoading(false); });
    return () => { cancelled = true; };
  }, [editing, editorScope, storeId, refreshKey]);

  function changeScope(next: ReceptionScope) {
    setScope(next); setGroupId(""); setPage(1); setQuery(""); setSearch(""); setNotice("");
  }

  function openReply(item?: QuickReply) {
    setEditing(item ?? "new");
    const targetScope = item?.scope ?? (canEdit ? scope : "personal");
    setEditorScope(targetScope);
    setDraft(item ? { group_id: item.group_id, shortcut: `/${item.shortcut}`, tags: item.tags.join("，"), site_code: item.site_code ?? "", messages: [...item.messages] } : { ...blankDraft(), group_id: targetScope === scope ? groupId || groups[0]?.id || "" : "" });
    setFormError("");
  }

  function openGroupEditor(item?: QuickReplyGroup) {
    setGroupEditor(item ?? "new"); setGroupName(item?.name ?? ""); setFormError("");
  }

  function updateMessage(index: number, value: string) {
    setDraft((current) => ({ ...current, messages: current.messages.map((message, offset) => offset === index ? value : message) }));
  }

  async function saveReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing || busy) return;
    const shortcut = draft.shortcut.trim().replace(/^\//, "");
    const messages = draft.messages.map((message) => message.trim());
    const tags = [...new Set(draft.tags.split(/[,，]/).map((tag) => tag.trim()).filter(Boolean))];
    if (!canEditEditor) { setFormError("当前账号没有此归属的编辑权限。"); return; }
    if (!draft.group_id || !editorGroups.some((group) => group.id === draft.group_id)) { setFormError("请先选择当前归属下的分组。"); return; }
    if (!/^[A-Za-z0-9]{1,8}$/.test(shortcut)) { setFormError("快捷键需为 1–8 位字母或数字。"); return; }
    if (messages.length < 1 || messages.length > 5 || messages.some((message) => !message)) { setFormError("请填写 1–5 段非空文本消息。"); return; }
    if (messages.join("\n").length > 2000) { setFormError("合并后的内容不能超过 2000 字。"); return; }
    if (tags.length > 3 || tags.some((tag) => tag.length > 20)) { setFormError("最多 3 个标签，每个不超过 20 字。"); return; }
    const payload: NewQuickReply = { store_id: storeId, scope: editorScope, group_id: draft.group_id, shortcut, tags, site_code: draft.site_code.trim().toUpperCase() || null, messages };
    setBusy(true); setFormError("");
    try {
      if (editing === "new") await createQuickReply(payload);
      else await updateQuickReply(editing.id, { group_id: payload.group_id, shortcut: payload.shortcut, tags: payload.tags, site_code: payload.site_code, messages: payload.messages });
      setEditing(null); setNotice("快捷回复已保存。"); setRefreshKey((key) => key + 1);
    } catch (caught) { setFormError(errorText(caught)); }
    finally { setBusy(false); }
  }

  async function saveGroup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = groupName.trim();
    if (!groupEditor || !name) { setFormError("请输入分组名称。"); return; }
    setBusy(true); setFormError("");
    try {
      if (groupEditor === "new") await createQuickReplyGroup({ store_id: storeId, scope, name });
      else await updateQuickReplyGroup(groupEditor.id, { name });
      setGroupName(""); setGroupEditor(null); setNotice("分组已保存。"); setRefreshKey((key) => key + 1);
    } catch (caught) { setFormError(errorText(caught)); }
    finally { setBusy(false); }
  }

  async function removeGroup() {
    if (!deletingGroup) return;
    setBusy(true); setFormError("");
    try {
      await deleteQuickReplyGroup(deletingGroup.id);
      if (groupId === deletingGroup.id) setGroupId("");
      setDeletingGroup(null); setNotice("分组已删除。"); setRefreshKey((key) => key + 1);
    } catch (caught) { setFormError(errorText(caught)); setDeletingGroup(null); }
    finally { setBusy(false); }
  }

  async function toggleGroup(group: QuickReplyGroup) {
    if (busy || !canEdit) return;
    setBusy(true); setFormError("");
    try {
      const saved = await updateQuickReplyGroup(group.id, { enabled: !group.enabled });
      setGroups((current) => current.map((item) => item.id === saved.id ? { ...item, enabled: saved.enabled } : item));
      setNotice(group.enabled ? "分组已停用，工作台不再提供该组话术。" : "分组已启用。");
      setRefreshKey((key) => key + 1);
    } catch (caught) { setFormError(errorText(caught)); }
    finally { setBusy(false); }
  }

  async function removeReply() {
    if (!deletingReply) return;
    setBusy(true); setError("");
    try { await deleteQuickReply(deletingReply.id); setDeletingReply(null); setNotice("快捷回复已删除。"); setRefreshKey((key) => key + 1); }
    catch (caught) { setError(errorText(caught)); setDeletingReply(null); }
    finally { setBusy(false); }
  }

  const siteOptions = [...new Set([
    "US",
    ...replies.flatMap((reply) => reply.site_code ? [reply.site_code] : []),
    ...(draft.site_code ? [draft.site_code] : []),
  ])];

  return <AppShell><main className="reception-page">
    <div className="reception-crumb"><Link href="/marketing">智能营销</Link><span>/</span><span>基础接待</span><span>/</span><strong>快捷回复</strong></div>
    <header className="reception-head"><div><span className="reception-eyebrow">BASIC RECEPTION</span><h1>快捷回复</h1><p>管理个人与团队常用话术，坐席选用后仍需人工审阅。</p></div></header>
    {notice ? <p className="reception-notice" role="status">{notice}</p> : null}
    <section className="reception-card reception-quick-card">
      <div className="reception-quick-scopebar"><div aria-label="回复归属" className="reception-quick-scope"><button aria-pressed={scope === "personal"} className={scope === "personal" ? "active" : ""} onClick={() => changeScope("personal")} type="button">个人</button><button aria-pressed={scope === "team"} className={scope === "team" ? "active" : ""} onClick={() => changeScope("team")} type="button">团队</button></div><div className="reception-filter-row"><label className="reception-select-label">店铺<select aria-label="店铺" disabled={!stores.length} onChange={(event) => { setStoreId(event.target.value); setGroupId(""); setPage(1); }} value={storeId}>{stores.map((store) => <option key={store.id} value={store.id}>{store.alias || store.name}</option>)}</select></label><form className="reception-search" onSubmit={(event) => { event.preventDefault(); setQuery(search); setPage(1); }}><MagnifyingGlass size={17} /><input aria-label="搜索快捷回复" onChange={(event) => setSearch(event.target.value)} placeholder="快捷键 / 标签 / 回复内容" value={search} /><button type="submit">搜索</button></form><button aria-label="刷新快捷回复" className="reception-icon-button" onClick={() => setRefreshKey((key) => key + 1)} type="button"><ArrowClockwise size={18} /></button></div></div>
      <div aria-label="分组筛选" className="reception-group-tabs"><button aria-pressed={!groupId} className={!groupId ? "active" : ""} onClick={() => { setGroupId(""); setPage(1); }} type="button">全部</button>{groups.map((group) => <button aria-pressed={groupId === group.id} className={groupId === group.id ? "active" : ""} key={group.id} onClick={() => { setGroupId(group.id); setPage(1); }} type="button">{group.name}</button>)}</div>
      <div className="reception-quick-actions"><span>共 {total} 条快捷回复</span><div><button className="secondary-button" disabled={!storeId || !canRead} onClick={() => setGroupDrawer(true)} type="button">管理分组</button><button className="secondary-button" disabled={!storeId || !canEdit} onClick={() => openGroupEditor()} type="button"><Plus size={15} />添加分组</button><button className="primary-button" disabled={!storeId || !canCreate} onClick={() => openReply()} type="button"><Plus size={16} />新增快捷回复</button></div></div>
      {booting ? <LoadingState label="正在读取授权店铺…" /> : bootError ? <ErrorState message={bootError} retry={() => void loadIdentity()} /> : !stores.length ? <div className="reception-empty"><h2>暂无可管理店铺</h2><p>请先完成店铺授权，再管理基础接待内容。</p><Link href="/settings/stores">查看店铺设置</Link></div> : !canRead ? <div className="reception-empty"><h2>当前账号无此范围权限</h2><p>请联系管理员开通相应的工作台或营销权限。</p></div> : loading ? <LoadingState label="正在加载快捷回复…" /> : error ? <ErrorState message={error} retry={() => setRefreshKey((key) => key + 1)} /> : replies.length ? <div className="reception-table-wrap"><table className="reception-table"><thead><tr><th>快捷键</th><th>标签</th><th>分组</th><th>回复内容</th><th>站点标签</th><th>操作</th></tr></thead><tbody>{replies.map((reply) => <tr key={reply.id}><td><strong>/{reply.shortcut}</strong></td><td><div className="reception-tags">{reply.tags.slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}{reply.tags.length > 3 ? <small>+{reply.tags.length - 3}</small> : null}</div></td><td>{groups.find((group) => group.id === reply.group_id)?.name ?? "—"}</td><td><span className="reception-summary" title={reply.messages.join("\n")}>{reply.messages.join(" · ")}</span></td><td>{reply.site_code || "全部"}</td><td><div className="reception-row-actions"><button disabled={!canEdit} onClick={() => openReply(reply)} type="button">编辑</button><button disabled={!canEdit} onClick={() => setDeletingReply(reply)} type="button">删除</button></div></td></tr>)}</tbody></table></div> : <EmptyState label={query || groupId ? "没有符合条件的快捷回复" : "暂无快捷回复，先创建分组和话术。"} />}
      {total > 20 ? <div className="reception-pagination"><span>共 {total} 条 · 第 {page} 页</span><button disabled={page === 1 || loading} onClick={() => setPage(page - 1)} type="button">上一页</button><button disabled={page * 20 >= total || loading} onClick={() => setPage(page + 1)} type="button">下一页</button></div> : null}
    </section>

    {groupDrawer ? <div className="reception-modal-backdrop reception-drawer-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setGroupDrawer(false); }}><section aria-label="管理分组" aria-modal="true" className="reception-modal reception-group-drawer" role="dialog"><header><div><h2>管理分组</h2><p>{scope === "personal" ? "个人" : "团队"}话术分组 · {stores.find((store) => store.id === storeId)?.alias || stores.find((store) => store.id === storeId)?.name}</p></div><button aria-label="关闭管理分组" className="reception-icon-button" onClick={() => setGroupDrawer(false)} type="button"><X size={20} /></button></header><div className="reception-group-drawer-body"><table className="reception-table reception-group-table"><thead><tr><th>分组名称</th><th>快捷回复数量</th><th>状态</th><th>操作</th></tr></thead><tbody>{groups.map((group) => <tr key={group.id}><td>{group.name}</td><td>{group.reply_count}</td><td><button aria-checked={group.enabled} aria-label={`${group.name}状态`} className={group.enabled ? "reception-switch on" : "reception-switch"} disabled={!canEdit || busy} onClick={() => void toggleGroup(group)} role="switch" type="button">{group.enabled ? "开" : "关"}<span aria-hidden="true" /></button></td><td><div className="reception-row-actions"><button disabled={!canEdit} onClick={() => openGroupEditor(group)} type="button">重命名</button><button disabled={!canEdit} onClick={() => setDeletingGroup(group)} type="button">删除</button></div></td></tr>)}</tbody></table>{formError ? <p className="reception-form-error" role="alert">{formError}</p> : null}{!groups.length ? <p className="reception-muted">暂无分组，请通过“添加分组”创建。</p> : null}</div></section></div> : null}

    {groupEditor ? <div className="reception-modal-backdrop reception-group-editor-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setGroupEditor(null); }}><section aria-label={groupEditor === "new" ? "添加分组" : "重命名分组"} aria-modal="true" className="reception-modal reception-group-editor" role="dialog"><header><h2>{groupEditor === "new" ? "添加分组" : "重命名分组"}</h2><button aria-label="关闭添加分组" className="reception-icon-button" onClick={() => setGroupEditor(null)} type="button"><X size={20} /></button></header><form onSubmit={(event) => void saveGroup(event)}><label className="reception-field">分组名称<input autoFocus maxLength={40} onChange={(event) => setGroupName(event.target.value)} placeholder="输入分组名称" required value={groupName} /><small>{groupName.length} / 40</small></label>{formError ? <p className="reception-form-error" role="alert">{formError}</p> : null}<footer className="reception-modal-footer"><button className="secondary-button" onClick={() => setGroupEditor(null)} type="button">取消</button><button className="primary-button" disabled={busy || !canEdit} type="submit">保存</button></footer></form></section></div> : null}

    {editing ? <div className="reception-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setEditing(null); }}><section aria-label={editing === "new" ? "新增快捷回复" : "编辑快捷回复"} aria-modal="true" className="reception-modal reception-editor" role="dialog"><header><div><h2>{editing === "new" ? "新增快捷回复" : "编辑快捷回复"}</h2><p>仅保存文本话术；使用时由坐席编辑或审阅确认。</p></div><button aria-label="关闭" className="reception-icon-button" onClick={() => setEditing(null)} type="button"><X size={20} /></button></header><form onSubmit={(event) => void saveReply(event)}><div className="reception-editor-grid"><div className="reception-editor-fields"><div className="reception-form-row"><label className="reception-field">归属<select aria-label="归属" disabled={editing !== "new"} onChange={(event) => { setEditorScope(event.target.value as ReceptionScope); setDraft((current) => ({ ...current, group_id: "" })); setFormError(""); }} value={editorScope}><option disabled={!permissions.includes("workspace.reply")} value="personal">个人</option><option disabled={!permissions.includes("marketing.manage")} value="team">团队</option></select></label><label className="reception-field">分组<select aria-label="分组" disabled={editorGroupsLoading} onChange={(event) => setDraft({ ...draft, group_id: event.target.value })} required value={draft.group_id}><option value="">请选择分组</option>{editorGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></label></div><div className="reception-form-row"><label className="reception-field">快捷键<input aria-label="快捷键" maxLength={9} onChange={(event) => setDraft({ ...draft, shortcut: event.target.value })} placeholder="/hello" required value={draft.shortcut} /><small>输入 / 后接 1–8 位字母或数字</small></label><label className="reception-field">选择站点<select aria-label="选择站点" onChange={(event) => setDraft({ ...draft, site_code: event.target.value })} value={draft.site_code}><option value="">全部站点</option>{siteOptions.map((site) => <option key={site} value={site}>{site === "US" ? "美国（US）" : site}</option>)}</select><small>站点仅作话术标签，暂不按会话站点自动筛选。</small></label></div><label className="reception-field">标签<input aria-label="标签" onChange={(event) => setDraft({ ...draft, tags: event.target.value })} placeholder="多个标签用逗号分隔" value={draft.tags} /></label><div className="reception-section-line"><strong>回复内容</strong><span>{draft.messages.join("\n").length}/2000 字</span></div><div className="reception-media-row"><span>文本消息</span><button disabled title="本期不支持保存或发送图片" type="button">图片 · 本期不可用</button><button disabled title="本期不支持保存或发送视频" type="button">视频 · 本期不可用</button></div>{draft.messages.map((message, index) => <label className="reception-field" key={index}>消息 {index + 1}<textarea aria-label={`消息 ${index + 1}`} maxLength={2000} onChange={(event) => updateMessage(index, event.target.value)} placeholder="输入回复内容" rows={3} value={message} />{draft.messages.length > 1 ? <button className="reception-text-action" onClick={() => setDraft({ ...draft, messages: draft.messages.filter((_, offset) => offset !== index) })} type="button">移除此段</button> : null}</label>)}<button className="reception-add-segment" disabled={draft.messages.length >= 5} onClick={() => setDraft({ ...draft, messages: [...draft.messages, ""] })} type="button"><Plus size={15} />添加文本段（最多 5 段）</button></div><aside className="reception-preview"><h3>内容预览</h3><p>保存后可在客服工作台选用；不会自动发送。</p><div className="reception-preview-chat">{draft.messages.filter((message) => message.trim()).map((message, index) => <div className="reception-preview-bubble" key={index}>{message}</div>)}{draft.messages.every((message) => !message.trim()) ? <span>回复预览将在这里显示</span> : null}</div><small>多段文本在工作台合并为一条草稿。</small></aside></div>{formError ? <p className="reception-form-error" role="alert">{formError}</p> : null}<footer className="reception-modal-footer"><button className="secondary-button" onClick={() => setEditing(null)} type="button">取消</button><button className="primary-button" disabled={busy || !canEditEditor || editorGroupsLoading} type="submit">{busy ? "正在保存…" : "保存快捷回复"}</button></footer></form></section></div> : null}

    {deletingGroup ? <div className="reception-modal-backdrop"><section aria-label="删除分组" aria-modal="true" className="reception-confirm" role="alertdialog"><h2>删除分组“{deletingGroup.name}”？</h2><p>只有空分组可以删除，已有快捷回复时请先移动或删除回复。</p><div><button className="secondary-button" onClick={() => setDeletingGroup(null)} type="button">取消</button><button className="danger-button" disabled={busy} onClick={() => void removeGroup()} type="button">确认删除</button></div></section></div> : null}
    {deletingReply ? <div className="reception-modal-backdrop"><section aria-label="删除快捷回复" aria-modal="true" className="reception-confirm" role="alertdialog"><h2>删除快捷回复“/{deletingReply.shortcut}”？</h2><p>删除后工作台将不再显示这条回复。</p><div><button className="secondary-button" onClick={() => setDeletingReply(null)} type="button">取消</button><button className="danger-button" disabled={busy} onClick={() => void removeReply()} type="button">确认删除</button></div></section></div> : null}
  </main></AppShell>;
}
