"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "../../../components/AppShell";
import { AgentTemplateNav } from "../../../components/agents/templates/AgentTemplateNav";
import { TemplateModal } from "../../../components/agents/templates/TemplateModal";
import { TemplateConfigFields } from "../../../components/agents/templates/TemplateConfigFields";
import {
  archiveAgentTemplate, createAgentTemplate, getAgentTemplate, getAgentTemplateCatalog, listAgentTemplates,
  listAgentTemplateVersions, publishAgentTemplate, restoreAgentTemplate, updateAgentTemplate,
  type AgentTemplate, type TemplateCatalog, type TemplateConfig, type TemplateVersion,
} from "../../../lib/agent-templates";
import "../agent-prototype.css";
import "../../../components/agents/templates/templates.css";

type Editor = { name: string; description: string | null; config: TemplateConfig };
type Confirm = "archive" | "restore" | "reload" | { select: string } | { href: string } | "create";
const errorMessage = (error: unknown) => error instanceof Error ? error.message : "操作失败，请稍后重试";
function editorOf(template: AgentTemplate): Editor | null { return template.config ? { name: template.name, description: template.description, config: template.config } : null; }

export default function AgentTemplatesPage() {
  const router = useRouter();
  const [items, setItems] = useState<AgentTemplate[]>([]);
  const [canManage, setCanManage] = useState(false);
  const [catalog, setCatalog] = useState<TemplateCatalog | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState<AgentTemplate | null>(null);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [versions, setVersions] = useState<TemplateVersion[]>([]);
  const [version, setVersion] = useState("draft");
  const [query, setQuery] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [retry, setRetry] = useState(0);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const historyRequest = useRef(0);
  const dirty = Boolean(detail && editor && JSON.stringify(editor) !== JSON.stringify(editorOf(detail)));
  const writable = Boolean(canManage && detail?.can_manage && !detail.archived_at && version === "draft");
  const visible = items.filter((item) => (includeArchived || !item.archived_at) && `${item.name} ${item.code} ${item.description ?? ""}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));

  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    void Promise.all([listAgentTemplates(includeArchived), getAgentTemplateCatalog()]).then(([list, directory]) => {
      if (!active) return;
      setItems(list.items); setCanManage(list.can_manage); setCatalog(directory);
      setSelectedId((old) => list.items.some((item) => item.id === old) ? old : list.items[0]?.id ?? "");
    }).catch((caught: unknown) => { if (active) setError(errorMessage(caught)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [includeArchived, retry]);
  useEffect(() => {
    let active = true;
    historyRequest.current++;
    setDetail(null); setEditor(null); setVersions([]); setError("");
    if (!selectedId) { setDetailLoading(false); return; }
    setDetailLoading(true);
    void Promise.all([getAgentTemplate(selectedId), listAgentTemplateVersions(selectedId)]).then(([item, history]) => {
      if (!active) return;
      setDetail(item); setEditor(editorOf(item)); setVersions(history);
      setVersion(item.can_manage ? "draft" : String(item.published_version ?? ""));
    }).catch((caught: unknown) => { if (active) setError(errorMessage(caught)); })
      .finally(() => { if (active) setDetailLoading(false); });
    return () => { active = false; };
  }, [selectedId, reload]);
  useEffect(() => {
    if (!dirty && !busy) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, busy]);
  useEffect(() => {
    if (!dirty && !busy) return;
    // Next Link 不触发 beforeunload；只拦当前页面真正离开的普通同窗站内点击。
    const guardNavigation = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const anchor = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null;
      if (!anchor || anchor.hasAttribute("download") || (anchor.target && anchor.target.toLowerCase() !== "_self")) return;
      const target = new URL(anchor.href, window.location.href);
      const current = new URL(window.location.href);
      if (target.origin !== current.origin || (target.pathname === current.pathname && target.search === current.search)) return;
      event.preventDefault(); event.stopPropagation();
      if (busy) { setNotice("操作正在处理，请等待结果后离开页面。"); return; }
      setConfirm({ href: target.href });
    };
    document.addEventListener("click", guardNavigation, true);
    return () => document.removeEventListener("click", guardNavigation, true);
  }, [dirty, busy]);

  function select(id: string) { if (id === selectedId) return; if (dirty) setConfirm({ select: id }); else { setSelectedId(id); setNotice(""); } }
  function newTemplate() { if (dirty) setConfirm("create"); else setCreateOpen(true); }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy || !canManage) return;
    const data = new FormData(event.currentTarget);
    setBusy("create"); setError("");
    try {
      const item = await createAgentTemplate({ name: String(data.get("name")).trim(), code: String(data.get("code")).trim(), description: null });
      setItems((old) => [...old, item]); setSelectedId(item.id); setCreateOpen(false); setNotice("草稿已创建，尚未发布");
    } catch (caught) { setError(errorMessage(caught)); }
    finally { setBusy(""); }
  }
  function refreshHistory(id: string, request: number) {
    void listAgentTemplateVersions(id).then((history) => { if (request === historyRequest.current) setVersions(history); })
      .catch((caught: unknown) => {
        if (request !== historyRequest.current) return;
        const failure = `版本历史刷新失败：${errorMessage(caught)}`;
        setError((current) => current ? `${current}；${failure}` : failure);
      });
  }
  async function mutate(action: "save" | "publish" | "archive" | "restore") {
    if (busy || !detail?.can_manage || detail.id !== selectedId || !canManage || detail.draft_revision === null || !editor) return;
    // 同模板连续发布也产生独立代次，旧历史的成功与失败都不能覆盖新结果。
    const request = action === "publish" ? ++historyRequest.current : historyRequest.current;
    setBusy(action); setError(""); setNotice("");
    try {
      const result = action === "save" ? await updateAgentTemplate(detail.id, { ...editor, expected_revision: detail.draft_revision })
        : action === "publish" ? await publishAgentTemplate(detail.id, detail.draft_revision)
          : action === "archive" ? await archiveAgentTemplate(detail.id, detail.draft_revision) : await restoreAgentTemplate(detail.id, detail.draft_revision);
      setDetail(result); setEditor(editorOf(result)); setItems((old) => old.map((item) => item.id === result.id ? result : item)); setConfirm(null);
      setNotice(action === "save" ? "草稿已保存；已发布版本和店铺运行保持原样" : action === "publish" ? "模板已发布；关联店铺须另行审阅应用" : action === "archive" ? "模板已归档" : "模板已恢复");
      // 写入结果已确认；历史读取失败单独反馈，不能把成功写入误报为失败。
      if (action === "publish") refreshHistory(result.id, request);
    } catch (caught) {
      setError(errorMessage(caught)); setConfirm(null);
      // 发布失败仍可能有先前成功版本尚未回显；只恢复真实历史，不重载或覆盖编辑。
      if (action === "publish" && request === historyRequest.current) refreshHistory(detail.id, request);
    }
    finally { setBusy(""); }
  }
  function discard() {
    if (typeof confirm === "object" && confirm) {
      if ("select" in confirm) setSelectedId(confirm.select);
      else { setEditor(detail ? editorOf(detail) : null); router.push(confirm.href); }
    }
    else if (confirm === "create") { setEditor(detail ? editorOf(detail) : null); setCreateOpen(true); }
    else setReload((old) => old + 1);
    setConfirm(null); setNotice("");
  }
  const shownConfig = version === "draft" ? editor?.config : versions.find((item) => String(item.version) === version)?.config ?? (version === String(detail?.published_version) ? detail?.published_config : null);
  const modalTitle = confirm === "archive" ? "归档模板" : confirm === "restore" ? "恢复模板" : "放弃当前编辑";
  return <AppShell><div className="agent-page template-page"><div className="shell">
    <header className="topbar"><div className="title"><span className="title-icon">◇</span><div><h1>Agent 模板</h1><p>共享通用配置，发布后逐店审阅应用</p></div></div>{canManage ? <button className="btn primary" type="button" disabled={Boolean(busy) || loading} onClick={newTemplate}>新建模板</button> : null}</header>
    <AgentTemplateNav current="templates" />
    <main className="main">
      {notice ? <p className="inline-note" role="status">{notice}</p> : null}
      {error ? <div className="agent-error" role="alert"><p>{error}</p>{detail ? <button className="btn" type="button" disabled={Boolean(busy)} onClick={() => setConfirm("reload")}>重新加载此模板</button> : <button className="btn" type="button" onClick={() => { setRetry((old) => old + 1); setReload((old) => old + 1); }}>重新加载</button>}</div> : null}
      <div className="template-layout"><aside className="template-library" aria-label="模板库">
        <div className="section-head"><h2>模板库</h2><p>{canManage ? "可维护草稿和已发布版本" : "已发布的共享配置 · 只读"}</p></div>
        <label className="field-group"><span>搜索模板</span><input className="field" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="名称、编码或职责" /></label>
        {canManage ? <label className="archive-filter"><input type="checkbox" checked={includeArchived} disabled={Boolean(busy) || dirty} onChange={(event) => setIncludeArchived(event.target.checked)} /> 包含已归档模板</label> : null}
        {loading ? <p role="status">正在加载模板库…</p> : visible.length ? <div className="template-list">{visible.map((item) => <button className={`template-list-item ${selectedId === item.id ? "active" : ""}`} type="button" disabled={Boolean(busy)} aria-pressed={selectedId === item.id} key={item.id} onClick={() => select(item.id)}><strong>{item.name}</strong><small>{item.description || item.config?.description || "未填写职责"}</small><span>{item.config?.agent_type === "operations" ? "经营类" : "服务类"} · {item.archived_at ? "已归档" : item.published_version ? `发布 v${item.published_version}` : "未发布"}{item.can_manage ? ` · 草稿 r${item.draft_revision}` : ""}</span><span>关联 {item.linked_store_count} 店 · 待更新 {item.update_count} 店</span></button>)}</div> : <p className="help">{query ? "没有符合搜索条件的模板" : "模板库为空"}</p>}
      </aside><section className="config template-editor" aria-label="模板配置">
        {detailLoading ? <p className="agent-empty" role="status">正在加载模板配置…</p> : !detail || !editor || !catalog || !shownConfig ? <p className="agent-empty">{loading ? "正在加载…" : "请选择模板，或新建模板草稿。"}</p> : <>
          <div className="config-head"><div><h2>{detail.name}</h2><p>{detail.published_version ? `已发布 v${detail.published_version}` : "尚未发布"}{detail.archived_at ? " · 已归档" : ""}</p></div><div className="config-actions">{dirty ? <span className="dirty">未保存</span> : null}{canManage && detail.can_manage ? <>{detail.archived_at ? <button className="btn small" type="button" disabled={Boolean(busy)} onClick={() => setConfirm("restore")}>恢复模板</button> : <><button className="btn small" type="button" disabled={Boolean(busy) || dirty || version !== "draft"} onClick={() => void mutate("publish")}>{busy === "publish" ? "正在校验…" : "发布模板"}</button><button className="btn primary small" type="submit" form="template-editor-form" disabled={Boolean(busy) || version !== "draft"}>{busy === "save" ? "正在保存…" : "保存草稿"}</button></>}</> : null}{detail.published_version && !detail.archived_at ? <a className="btn small" href={`/agents/templates/${encodeURIComponent(detail.id)}/apply?version=${version === "draft" ? detail.published_version : encodeURIComponent(version)}`}>批量应用 / 差异更新</a> : null}</div></div>
          <div className="config-body"><details className="template-details template-advanced"><summary>高级设置与历史</summary><div className="template-control-toolbar"><p>模板编码：{detail.code}</p><label className="field-group version-field"><span>查看版本</span><select className="field" value={version} disabled={Boolean(busy)} onChange={(event) => setVersion(event.target.value)}>{canManage && detail.can_manage ? <option value="draft">草稿 r{detail.draft_revision}</option> : null}{versions.map((item) => <option value={String(item.version)} key={item.version}>已发布 v{item.version} · 只读</option>)}</select></label>{writable ? <button className="btn small" type="button" disabled={Boolean(busy) || dirty} onClick={() => setConfirm("archive")}>归档模板</button> : null}</div></details>
            <p className="inline-note">{version === "draft" ? "保存只更新草稿；发布模板不会修改任何店铺 Agent。" : canManage && detail.can_manage ? "已发布版本为不可变快照。选择草稿可继续编辑下一版本。" : "已发布版本为不可变快照，供本账号只读查看。"}</p>
            <form id="template-editor-form" onSubmit={(event) => { event.preventDefault(); if (writable) void mutate("save"); }}>
              <TemplateConfigFields value={shownConfig} catalog={catalog} disabled={!writable || Boolean(busy)} onChange={(config) => setEditor({ ...editor, config })}>
                <label className="field-group template-name"><span>模板名称</span><input className="field" value={editor.name} required maxLength={200} disabled={!writable || Boolean(busy)} onChange={(event) => setEditor({ ...editor, name: event.target.value })} /></label>
              </TemplateConfigFields>
            </form>
          </div></>}
      </section></div>
    </main>
    {createOpen ? <TemplateModal title="新建模板" onClose={() => { if (!busy) setCreateOpen(false); }}><form onSubmit={(event) => void create(event)}><div className="modal-body"><p className="help">先创建草稿，再配置模型、七段提示词、工具和知识需求。</p><label className="field-group"><span>模板名称</span><input className="field" aria-label="模板名称" name="name" required maxLength={200} disabled={Boolean(busy)} /></label><label className="field-group"><span>模板编码</span><input className="field" aria-label="模板编码" name="code" required pattern="[a-z0-9](?:[a-z0-9_]|-){1,99}" maxLength={100} disabled={Boolean(busy)} /></label>{error ? <p role="alert">{error}</p> : null}</div><div className="modal-foot"><button type="button" className="btn" disabled={Boolean(busy)} onClick={() => setCreateOpen(false)}>取消</button><button className="btn primary" type="submit" disabled={Boolean(busy)}>创建草稿</button></div></form></TemplateModal> : null}
    {confirm ? <TemplateModal title={modalTitle} onClose={() => { if (!busy) setConfirm(null); }}><div className="modal-body"><p>{confirm === "archive" ? "归档后停止新的模板应用；关联店铺继续使用现有版本。" : confirm === "restore" ? "恢复后模板可继续维护；关联店铺不会自动更新。" : "当前未保存的编辑将丢失。"}</p></div><div className="modal-foot"><button className="btn" type="button" disabled={Boolean(busy)} onClick={() => setConfirm(null)}>取消</button><button className="btn primary" type="button" disabled={Boolean(busy)} onClick={() => confirm === "archive" || confirm === "restore" ? void mutate(confirm) : discard()}>{confirm === "archive" ? "确认归档" : confirm === "restore" ? "确认恢复" : confirm === "reload" ? "放弃编辑并重新加载" : "放弃编辑并继续"}</button></div></TemplateModal> : null}
  </div></div></AppShell>;
}
