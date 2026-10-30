"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "../../../../../components/AppShell";
import { AgentTemplateNav } from "../../../../../components/agents/templates/AgentTemplateNav";
import { FieldReview } from "../../../../../components/agents/templates/FieldReview";
import { TemplateModal } from "../../../../../components/agents/templates/TemplateModal";
import { fieldLabel, TemplateValue } from "../../../../../components/agents/templates/TemplateValue";
import { confirmTemplateBatch, getAgentTemplate, getAgentTemplateCatalog, getTemplateBatch, listAgentTemplateVersions, listApplicationKnowledgeFiles, listApplicationStores, previewTemplateApplication, type AgentTemplate, type ApplicationItemRequest, type ApplicationItemView, type ApplicationPreview, type ApplicationStoreOption, type KnowledgeFileOption, type Page, type TemplateCatalog, type TemplateVersion } from "../../../../../lib/agent-templates";
import { ApiError, createIdempotencyKey } from "../../../../../lib/api";
import "../../../agent-prototype.css";
import "../../../../../components/agents/templates/templates.css";

type Row = { store: ApplicationStoreOption; item: ApplicationItemRequest; review?: ApplicationItemView; skipped?: string[]; targetInvalid?: boolean };
const errorText = (error: unknown) => error instanceof Error ? error.message : "操作失败，请重试";
function newRow(store: ApplicationStoreOption, template: AgentTemplate, version: TemplateVersion): Row {
  const agent = store.agents.find((a) => a.template_id === template.id);
  return { store, item: { store_id: store.id, action: agent ? "update" : "create", ...(agent ? { agent_id: agent.id, expected_revision: agent.draft_revision } : { name: version.config.default_agent_name, code: version.config.suggested_code }), fields: null, knowledge_mappings: {}, unbind_removed_file_ids: [], include_existing_draft: false, publish: false, enable_after_publish: false } };
}

export default function ApplyTemplatePage() {
  const params = useParams<{ templateId: string }>(); const router = useRouter();
  const id = params.templateId;
  const [template, setTemplate] = useState<AgentTemplate | null>(null); const [versions, setVersions] = useState<TemplateVersion[]>([]);
  const [catalog, setCatalog] = useState<TemplateCatalog | null>(null); const [version, setVersion] = useState(0);
  const [stores, setStores] = useState<Page<ApplicationStoreOption> | null>(null); const [page, setPage] = useState(1); const [search, setSearch] = useState("");
  const [rows, setRows] = useState<Row[]>([]); const [files, setFiles] = useState<Record<string, KnowledgeFileOption[]>>({});
  const [preview, setPreview] = useState<ApplicationPreview | null>(null); const [error, setError] = useState(""); const [busy, setBusy] = useState("");
  const [pendingId, setPendingId] = useState(""); const [recovery, setRecovery] = useState("");
  const [parentId, setParentId] = useState(""); const [leave, setLeave] = useState(""); const [pendingVersion, setPendingVersion] = useState(0); const generation = useRef(0); const committed = useRef(false); const sourceLoaded = useRef(false);
  useEffect(() => {
    let active = true; const query = new URLSearchParams(window.location.search); const requested = Number(query.get("version")); setParentId(query.get("parent_batch_id") ?? "");
    void Promise.all([getAgentTemplate(id), listAgentTemplateVersions(id), getAgentTemplateCatalog()]).then(([t, v, c]) => { if (active) { setTemplate(t); setVersions(v); setCatalog(c); if (query.has("version") && !v.some((x) => x.version === requested)) { setVersion(0); setError("指定的模板发布版本不存在或不可用，请选择有效版本。"); } else setVersion(query.has("version") ? requested : t.published_version ?? 0); } }).catch((e: unknown) => { if (active) setError(errorText(e)); });
    return () => { active = false; };
  }, [id]);
  useEffect(() => { let active = true; void listApplicationStores(page, 20, search).then((result) => { if (active) setStores(result); }).catch((e: unknown) => { if (active) setError(errorText(e)); }); return () => { active = false; }; }, [page, search]);
  useEffect(() => { const pending = sessionStorage.getItem(`template-pending:${id}`); if (pending) setPendingId(pending); }, [id]);
  async function recoverPending(retry = false) {
    if (!pendingId || busy) return; setBusy("recover"); setError("");
    try {
      const current = await getTemplateBatch(pendingId);
      if (current.status !== "preview") { sessionStorage.removeItem(`template-pending:${id}`); committed.current = true; router.push(`/agents/template-batches?batch_id=${encodeURIComponent(current.id)}`); return; }
      if (retry) {
        const key = sessionStorage.getItem(`template-batch:${pendingId}`); if (!key) throw new Error("原确认凭据不可用，无法安全重试");
        try { const result = await confirmTemplateBatch(pendingId, key); sessionStorage.removeItem(`template-pending:${id}`); committed.current = true; router.push(`/agents/template-batches?batch_id=${encodeURIComponent(result.id)}`); }
        catch (e) { await confirmationFailure(pendingId, e); }
      } else setRecovery("服务端仍是未确认预览，可以使用原确认重试。");
    } catch (e) { setError(`无法确认原任务状态：${errorText(e)}`); }
    finally { setBusy(""); }
  }
  useEffect(() => {
    if (!parentId || !template) return; let active = true;
    void (async () => {
      const first = await getTemplateBatch(parentId, 1, 100); const all = [...first.items];
      for (let p = 2; p <= first.pagination.total_pages; p++) all.push(...(await getTemplateBatch(parentId, p, 100)).items);
      const candidates: ApplicationStoreOption[] = [];
      for (let p = 1, total = 1; p <= total; p++) { const result = await listApplicationStores(p, 100); candidates.push(...result.items); total = result.pagination.total_pages; }
      const resumed = all.filter((item) => item.status !== "succeeded" && item.preview?.request).flatMap((item) => {
        const store = candidates.find((s) => s.id === item.store_id); const request = item.preview?.request;
        if (!store || !request || !item.preview) return [];
        const same = store.agents.find((agent) => agent.id === request.agent_id);
        const linked = store.agents.find((agent) => agent.template_id === template.id);
        const targetInvalid = request.action === "create" ? Boolean(linked)
          : !same || (request.action === "update" ? same.template_id !== template.id : same.template_id !== null || Boolean(linked));
        return [{ store, item: same && !targetInvalid ? { ...request, expected_revision: same.draft_revision } : request, review: targetInvalid || (same && same.draft_revision !== request.expected_revision) ? undefined : item.preview, targetInvalid }];
      });
      if (active) { setRows(resumed); for (const row of resumed) void fetchFiles(row.store); if (resumed.length < all.filter((item) => item.status !== "succeeded").length) setError("部分未成功项目当前不可管理或缺少原始请求，未加入续接，请查看原任务。"); }
    })().catch((e: unknown) => { if (active) setError(errorText(e)); });
    return () => { active = false; };
  // 续接只在批次和快照改变时恢复；文件加载不应覆盖已编辑的行。
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parentId, template]);
  useEffect(() => {
    if (!template || !version || sourceLoaded.current) return;
    const query = new URLSearchParams(window.location.search); const requestedStore = query.get("store_id"); const requestedAgent = query.get("agent_id");
    if (!requestedStore || !requestedAgent || query.has("parent_batch_id")) return;
    sourceLoaded.current = true; let active = true;
    void (async () => {
      let found: ApplicationStoreOption | undefined;
      for (let p = 1, total = 1; p <= total && !found; p++) { const result = await listApplicationStores(p, 100); found = result.items.find((s) => s.id === requestedStore); total = result.pagination.total_pages; }
      const selectedVersion = versions.find((item) => item.version === version); const agent = found?.agents.find((a) => a.id === requestedAgent && a.template_id === template.id);
      if (!found || !agent || !selectedVersion) throw new Error("本店 Agent 不在可管理候选中，请重新选择。");
      if (active) { setRows([newRow(found, template, selectedVersion)]); void fetchFiles(found); }
    })().catch((e: unknown) => { if (active) setError(errorText(e)); });
    return () => { active = false; };
  // 只在来源链接首次加载时选择，后续手工编辑不应被覆盖。
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [template, version, versions]);
  useEffect(() => {
    if (!rows.length || committed.current) return;
    const unload = (event: BeforeUnloadEvent) => event.preventDefault();
    const navigation = (event: MouseEvent) => { if (event.defaultPrevented || event.button || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return; const a = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null; if (!a || (a.target && a.target.toLowerCase() !== "_self") || a.hasAttribute("download")) return; const target = new URL(a.href, location.href); if (target.origin !== location.origin || (target.pathname === location.pathname && target.search === location.search)) return; event.preventDefault(); event.stopPropagation(); if (busy) setError("操作正在处理，请等待结果后离开页面。"); else setLeave(target.href); };
    window.addEventListener("beforeunload", unload); document.addEventListener("click", navigation, true);
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", navigation, true); };
  }, [rows.length, busy]);
  function invalidate() { generation.current++; setPreview(null); }
  async function confirmationFailure(previewId: string, error: unknown) {
    try {
      const result = await getTemplateBatch(previewId);
      if (result.status !== "preview") { sessionStorage.removeItem(`template-pending:${id}`); committed.current = true; router.push(`/agents/template-batches?batch_id=${encodeURIComponent(result.id)}`); }
      else if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 408) { sessionStorage.removeItem(`template-pending:${id}`); setPendingId(""); setRecovery(""); invalidate(); setError(`确认被拒绝，请检查并重新预览：${errorText(error)}`); }
      else setError(`确认结果未完成，可使用原确认重试：${errorText(error)}`);
    } catch { setError(`确认结果未知，请重试查询或使用原确认重试：${errorText(error)}`); }
  }
  function update(storeId: string, fn: (row: Row) => Row) { invalidate(); setRows((old) => old.map((row) => row.store.id === storeId ? fn(row) : row)); }
  const snapshot = versions.find((v) => v.version === version);
  async function fetchFiles(store: ApplicationStoreOption) {
    if (!store.can_view_knowledge || Object.hasOwn(files, store.id)) return;
    try { const result: KnowledgeFileOption[] = []; for (let p = 1, total = 1; p <= total; p++) { const response = await listApplicationKnowledgeFiles(store.id, p, 100); result.push(...response.items); total = response.pagination.total_pages; } setFiles((old) => ({ ...old, [store.id]: result })); } catch (e) { setError(errorText(e)); }
  }
  async function runPreview() {
    if (busy || !rows.length || !version || rows.some((row) => row.targetInvalid)) return;
    if (rows.some((row) => row.review?.diffs.some((diff) => diff.status === "conflict" && !row.item.fields?.[diff.field] && !row.skipped?.includes(diff.field)))) { setError("请逐项选择冲突处理方式或明确跳过。"); return; }
    const seq = ++generation.current; setBusy("preview"); setError(""); setPreview(null);
    try {
      const result = await previewTemplateApplication(id, { template_version: version, items: rows.map((row) => row.item), ...(parentId ? { parent_batch_id: parentId } : {}) });
      if (seq !== generation.current) return;
      setRows((old) => old.map((row) => { const review = result.items.find((item) => item.store_id === row.store.id); return review ? { ...row, review, item: { ...row.item, fields: row.item.fields === null ? review.field_choices : row.item.fields } } : row; }));
      setPreview(result);
    } catch (e) { if (seq === generation.current) setError(errorText(e)); }
    finally { setBusy(""); }
  }
  async function confirm() {
    if (busy || !preview || preview.items.some((item) => !item.valid)) return;
    const keyName = `template-batch:${preview.preview_id}`;
    const key = sessionStorage.getItem(keyName) ?? createIdempotencyKey(); sessionStorage.setItem(keyName, key);
    sessionStorage.setItem(`template-pending:${id}`, preview.preview_id); setPendingId(preview.preview_id);
    setBusy("confirm"); setError("");
    try {
      const result = await confirmTemplateBatch(preview.preview_id, key); sessionStorage.removeItem(`template-pending:${id}`); committed.current = true; router.push(`/agents/template-batches?batch_id=${encodeURIComponent(result.id)}`);
    } catch (e) { await confirmationFailure(preview.preview_id, e); }
    finally { setBusy(""); }
  }
  function choose(store: ApplicationStoreOption, checked: boolean) {
    if (!template || !snapshot) return; invalidate();
    setRows((old) => checked ? [...old, newRow(store, template, snapshot)] : old.filter((row) => row.store.id !== store.id));
    if (checked) void fetchFiles(store);
  }
  return <AppShell><div className="agent-page template-page"><div className="shell">
    <header className="topbar"><div className="title"><div><h1>批量应用 / 差异更新</h1><p>{template?.name ?? "加载中"} · 已发布快照逐店审阅</p></div></div></header><AgentTemplateNav current="templates" />
    <main className="main">{error ? <p role="alert">{error}</p> : null}{pendingId ? <section className="config"><h2>恢复未确定的确认</h2><p>{recovery || "先查询原任务状态，再决定是否重试。"}</p><button className="btn" disabled={Boolean(busy)} onClick={() => void recoverPending()}>查询原任务</button>{" "}<button className="btn" disabled={Boolean(busy) || !recovery} onClick={() => void recoverPending(true)}>使用原确认重试</button></section> : null}{template?.archived_at ? <p role="alert">模板已归档，不能新建应用。</p> : null}
      <label className="field-group"><span>模板版本</span><select className="field" value={version} disabled={Boolean(busy)} onChange={(e) => { const next = Number(e.target.value); if (rows.length) setPendingVersion(next); else { invalidate(); setVersion(next); } }}>{!version ? <option value={0}>请选择有效版本</option> : null}{versions.map((v) => <option value={v.version} key={v.version}>已发布 v{v.version}</option>)}</select></label>
      {snapshot ? <p>快照 v{snapshot.version} · {snapshot.config.default_agent_name} · {snapshot.config.description ?? "未填写职责"}</p> : <p>没有可用的已发布快照</p>}
      <section><h2>选择授权店铺</h2><p>已选 {rows.length} 店；跨页选择会保留。</p><label>搜索店铺 <input className="field" type="search" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} /></label>
        {stores?.items.map((store) => <label className="bound-item" key={store.id}><input type="checkbox" disabled={Boolean(busy) || Boolean(template?.archived_at)} checked={rows.some((row) => row.store.id === store.id)} onChange={(e) => choose(store, e.target.checked)} /> {store.name} · {store.code}</label>)}
        {stores && !stores.items.length ? <p>没有符合条件的可管理店铺。</p> : null}
        <button className="btn small" disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button> 第 {page} 页 <button className="btn small" disabled={!stores || page >= stores.pagination.total_pages} onClick={() => setPage(page + 1)}>下一页</button>
      </section>
      {rows.map((row) => <section className="config" key={row.store.id}><div className="config-body"><fieldset disabled={busy === "confirm" || busy === "recover"}><h2>{row.store.name}</h2><button className="btn small" disabled={Boolean(busy)} onClick={() => choose(row.store, false)}>移除此店</button>
        {row.targetInvalid ? <p role="alert">原目标已不可用或关联已变化，请重新选择目标。</p> : null}
        <label className="field-group"><span>操作与目标</span><select className="field" value={row.targetInvalid ? "" : row.item.action === "create" ? "create" : `${row.item.action}:${row.item.agent_id}`} disabled={Boolean(busy)} onChange={(e) => { const [action, agentId] = e.target.value.split(":"); const agent = row.store.agents.find((a) => a.id === agentId); update(row.store.id, (old) => ({ ...old, targetInvalid: false, review: undefined, item: { store_id: old.store.id, action: action as ApplicationItemRequest["action"], ...(agent ? { agent_id: agent.id, expected_revision: agent.draft_revision } : { name: snapshot?.config.default_agent_name ?? "", code: snapshot?.config.suggested_code ?? "" }), fields: null, knowledge_mappings: {}, unbind_removed_file_ids: [], include_existing_draft: false, publish: false, enable_after_publish: false } })); }}><option value="" disabled>请选择目标</option><option value="create">新建 Agent</option>{row.store.agents.filter((a) => a.template_id === id || a.template_id === null).map((a) => <option key={a.id} value={`${a.template_id === id ? "update" : "adopt"}:${a.id}`}>{a.template_id === id ? "更新" : "关联"} · {a.name} ({a.code})</option>)}</select></label>
        {row.item.action === "create" ? <><label>名称 <input className="field" value={row.item.name ?? ""} onChange={(e) => update(row.store.id, (old) => ({ ...old, item: { ...old.item, name: e.target.value } }))} /></label><label>编码 <input className="field" value={row.item.code ?? ""} onChange={(e) => update(row.store.id, (old) => ({ ...old, item: { ...old.item, code: e.target.value } }))} /></label>{row.store.agents.some((agent) => agent.name === row.item.name || agent.code === row.item.code) ? <p role="status">本店已有同名或同编码 Agent；不会自动覆盖，请确认目标。编码冲突以服务端预览为准。</p> : null}</> : null}
        {!row.store.can_view_knowledge && row.item.action !== "create" && row.item.fields === null ? <p>若自动建议涉及知识绑定而无权预览，可先保留现有绑定，再逐项审阅其他字段。 <button className="btn small" onClick={() => update(row.store.id, (old) => ({ ...old, item: { ...old.item, fields: {} } }))}>保留绑定并手工审阅</button></p> : null}
        <label><input type="checkbox" checked={row.item.publish} onChange={(e) => update(row.store.id, (old) => ({ ...old, item: { ...old.item, publish: e.target.checked, enable_after_publish: e.target.checked && old.item.enable_after_publish, include_existing_draft: e.target.checked && old.item.include_existing_draft } }))} /> 发布目标版本（未选则只保存草稿）</label>{row.item.action === "create" && row.item.publish ? <label><input type="checkbox" checked={row.item.enable_after_publish} onChange={(e) => update(row.store.id, (old) => ({ ...old, item: { ...old.item, enable_after_publish: e.target.checked } }))} /> 发布后启用新 Agent</label> : null}
        {row.review?.has_existing_draft && row.item.publish ? <label><input type="checkbox" checked={row.item.include_existing_draft} onChange={(e) => update(row.store.id, (old) => ({ ...old, item: { ...old.item, include_existing_draft: e.target.checked } }))} /> 我确认同时发布此 Agent 原有的全部未发布草稿</label> : null}
        {row.review ? <><div>{row.review.issues.map((issue, i) => <p role="alert" key={`${issue.code}:${i}`}>阻止确认：{issue.message}</p>)}{row.review.warnings.map((issue, i) => <p role="status" key={`${issue.code}:${i}`}>提示：{issue.message}</p>)}</div>
          <details><summary>当前运行版本 → 完整目标配置</summary>{Object.entries(row.review.full_target).map(([key, value]) => <div key={key}><strong>{fieldLabel(key)}</strong><div>当前运行：<TemplateValue value={row.review?.published_snapshot?.[key] ?? null} /></div><div>完整目标：<TemplateValue value={value} /></div></div>)}</details>
          <fieldset disabled={Boolean(busy)}><legend>字段审阅</legend>{row.review.diffs.map((diff) => catalog ? <FieldReview key={diff.field} diff={diff} catalog={catalog} skipped={row.skipped?.includes(diff.field)} decision={row.item.fields?.[diff.field]} onChange={(decision) => update(row.store.id, (old) => { const choices = { ...(old.item.fields ?? {}) }; if (decision) choices[diff.field] = decision; else delete choices[diff.field]; return { ...old, skipped: decision ? (old.skipped ?? []).filter((field) => field !== diff.field) : [...(old.skipped ?? []), diff.field], item: { ...old.item, fields: choices, ...(diff.field === "knowledge_slots" ? { knowledge_mappings: {} } : {}) } }; })} /> : null)}</fieldset>
          <fieldset disabled={Boolean(busy)}><legend>本店知识映射</legend>{!row.store.can_view_knowledge ? <p>无知识查看权限；保留原绑定，可继续审阅其他字段。</p> : <>{row.review.knowledge_slots.map((slot) => { const current = Object.hasOwn(row.item.knowledge_mappings, slot.key) ? row.item.knowledge_mappings[slot.key] : Object.hasOwn(row.review!.mappings, slot.key) ? row.review!.mappings[slot.key] : []; return <fieldset key={slot.key}><legend>{slot.name} ({slot.key}) {slot.required ? "必需" : "可选"}</legend>{(files[row.store.id] ?? []).map((file) => <label className="bound-item" key={file.id}><input type="checkbox" checked={current.includes(file.id)} onChange={(e) => update(row.store.id, (old) => { const mappings = Object.fromEntries(Object.entries(old.review?.mappings ?? {}).map(([key, ids]) => [key, [...ids]])); for (const [key, ids] of Object.entries(old.item.knowledge_mappings)) Object.defineProperty(mappings, key, { value: [...ids], enumerable: true, configurable: true, writable: true }); Object.defineProperty(mappings, slot.key, { value: e.target.checked ? [...current, file.id] : current.filter((id) => id !== file.id), enumerable: true, configurable: true, writable: true }); return { ...old, item: { ...old.item, knowledge_mappings: mappings } }; })} /> {file.name} · 有效版本 {file.active_version_number ?? "无"} · {file.can_publish ? "可发布" : "不可发布"}</label>)}</fieldset>; })}<p>移除槽默认保留文件为额外绑定；选择仅解除已移除槽的模板来源，人工来源仍保留。</p>{Array.isArray(row.review.full_target.knowledge_file_ids) ? row.review.full_target.knowledge_file_ids.filter((fileId): fileId is string => typeof fileId === "string" && !Object.values({ ...row.review!.mappings, ...row.item.knowledge_mappings }).some((ids) => ids.includes(fileId))).map((fileId) => typeof fileId === "string" ? <label className="bound-item" key={fileId}><input type="checkbox" checked={row.item.unbind_removed_file_ids.includes(fileId)} onChange={(e) => update(row.store.id, (old) => ({ ...old, item: { ...old.item, unbind_removed_file_ids: e.target.checked ? [...old.item.unbind_removed_file_ids, fileId] : old.item.unbind_removed_file_ids.filter((id) => id !== fileId) } }))} /> 解绑已移除槽的模板来源：{files[row.store.id]?.find((f) => f.id === fileId)?.name ?? fileId}</label> : null) : null}</>}</fieldset>
        </> : <p>生成预览后审阅字段、完整目标和本店知识。</p>}
      </fieldset></div></section>)}
      <button className="btn" disabled={Boolean(busy) || Boolean(pendingId) || !rows.length || rows.some((row) => row.targetInvalid) || !snapshot || Boolean(template?.archived_at)} onClick={() => void runPreview()}>{busy === "preview" ? "正在预览…" : "生成预览"}</button>
      {preview ? <section className="config"><div className="config-body"><h2>确认冻结计划</h2><p>新建 {rows.filter((r) => r.item.action === "create").length} · 关联 {rows.filter((r) => r.item.action === "adopt").length} · 更新 {rows.filter((r) => r.item.action === "update").length} · 仅草稿 {rows.filter((r) => !r.item.publish).length} · 发布 {rows.filter((r) => r.item.publish).length} · 新启用 {rows.filter((r) => r.item.enable_after_publish).length}</p>{preview.items.map((item) => <details key={item.id}><summary>{item.store_name} · {item.action === "create" ? "新建" : item.action === "adopt" ? "关联" : "更新"} · {String(item.full_target.name ?? item.agent_id ?? "目标")} ({String(item.full_target.code ?? "—")}) · {item.flags.publish ? "发布" : "仅草稿"} · {item.valid ? "可确认" : "需处理"}</summary>{Object.entries(item.full_target).map(([field, value]) => <div key={field}><strong>{fieldLabel(field)}</strong>：<TemplateValue value={value} /></div>)}</details>)}<button className="btn primary" disabled={Boolean(busy) || preview.items.some((item) => !item.valid)} onClick={() => void confirm()}>{busy === "confirm" ? "正在确认…" : "确认批量任务"}</button></div></section> : null}
    </main>{leave ? <TemplateModal title="放弃当前编辑" onClose={() => setLeave("")}><div className="modal-body">当前未确认的编辑将丢失。</div><div className="modal-foot"><button className="btn" onClick={() => setLeave("")}>继续编辑</button><button className="btn primary" onClick={() => { committed.current = true; router.push(leave); }}>放弃并离开</button></div></TemplateModal> : null}{pendingVersion ? <TemplateModal title="切换模板版本" onClose={() => setPendingVersion(0)}><div className="modal-body">{parentId ? "切换后保留续接店铺和字段选择，清除手工知识映射并重新预览。" : "切换版本将清除当前选店与未确认编辑。"}</div><div className="modal-foot"><button className="btn" onClick={() => setPendingVersion(0)}>继续编辑</button><button className="btn primary" onClick={() => { invalidate(); if (parentId) setRows((old) => old.map((row) => ({ ...row, review: undefined, skipped: [], item: { ...row.item, knowledge_mappings: {}, unbind_removed_file_ids: [] } }))); else setRows([]); setVersion(pendingVersion); setPendingVersion(0); }}>{parentId ? "切换并重新预览" : "放弃并切换"}</button></div></TemplateModal> : null}
  </div></div></AppShell>;
}
