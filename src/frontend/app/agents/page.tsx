"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { LogisticsNotificationPolicyControls } from "../../components/ReplyReviewPanel";
import { AgentToolCatalog } from "../../components/AgentToolCatalog";
import { AgentCollaboration } from "../../components/AgentCollaboration";
import { AgentPromptFields, promptSections } from "../../components/AgentPromptFields";
import { AgentTemplateNav } from "../../components/agents/templates/AgentTemplateNav";
import { AgentSource } from "../../components/agents/templates/AgentSource";
import { SaveAgentTemplate } from "../../components/agents/templates/SaveAgentTemplate";
import { listAgentTemplates } from "../../lib/agent-templates";
import { AppShell } from "../../components/AppShell";
import {
  approveDocumentVersion, createAgent, streamAgentDebug, getAgentLogs, listAgents, listDocumentFiles, listSessions, listStores, publishAgent, revokeDocumentVersion, setAgentEnabled, updateAgent,
  type AgentConfig, type AgentDebugResult, type AgentRunLog, type DocumentFileSummary, type SessionSummary, type StoreView,
} from "../../lib/api";
import "./agent-prototype.css";
import "../workspace/reply-review.css";

type Tab = "basic" | "reply" | "tools" | "knowledge" | "logs";
type Draft = Pick<AgentConfig, "name" | "description" | "agent_type" | "enabled_tools" | "knowledge_file_ids" | "reply_profile" | "model_provider" | "model_name" | "prompt_sections">;
const tabs: { key: Tab; label: string }[] = [
  { key: "basic", label: "⚙ 基础设置" }, { key: "reply", label: "◇ 模型与提示词" },
  { key: "tools", label: "▧ 工具能力" }, { key: "knowledge", label: "▤ 知识库" }, { key: "logs", label: "◷ 运行记录" },
];
function draftOf(agent: AgentConfig): Draft {
  return {
    name: agent.name, description: agent.description, agent_type: agent.agent_type ?? "service",
    enabled_tools: [...agent.enabled_tools],
    knowledge_file_ids: agent.knowledge_file_ids ?? [],
    reply_profile: agent.reply_profile ?? { tone: "friendly", reply_language: "auto", operator_language: "zh-CN", brand_name: null },
    model_provider: agent.model_provider ?? null,
    model_name: agent.model_name ?? null,
    prompt_sections: Object.fromEntries(promptSections.map((section) => [section.key, agent.prompt_sections?.[section.key] ?? ""])),
  };
}
function message(error: unknown): string { return error instanceof Error ? error.message : "操作失败，请稍后重试"; }

export default function AgentsPage() {
  const [stores, setStores] = useState<StoreView[]>([]);
  const [agents, setAgents] = useState<AgentConfig[]>([]);
  const [storeId, setStoreId] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [tab, setTab] = useState<Tab>("basic");
  const [files, setFiles] = useState<DocumentFileSummary[]>([]);
  const [fileChoice, setFileChoice] = useState("");
  const [approvalTypes, setApprovalTypes] = useState<Record<string, "policy" | "technical_artifact" | "non_assertive_proposition" | "">>({});
  const [logs, setLogs] = useState<AgentRunLog[]>([]);
  const [logsError, setLogsError] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [canManageTemplates, setCanManageTemplates] = useState(false);
  const [templateSource, setTemplateSource] = useState<AgentConfig | null>(null);
  const [newType, setNewType] = useState<"service" | "operations">("service");
  const [previewInput, setPreviewInput] = useState("");
  const [previewLines, setPreviewLines] = useState<Array<{ role: "user" | "assistant"; text: string }>>([]);
  const [previewDrafts, setPreviewDrafts] = useState<Record<number, string>>({});
  const previewAbort = useRef<AbortController | null>(null);
  const previewBody = useRef<HTMLDivElement | null>(null);
  const [previewResult, setPreviewResult] = useState<AgentDebugResult | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [conversationId, setConversationId] = useState("");
  const [previewMode, setPreviewMode] = useState<"single" | "store">("single");
  const requestId = useRef(0);
  const previewRequestId = useRef(0);
  const selected = agents.find((item) => item.id === selectedId && item.store_id === storeId) ?? null;
  const currentStore = stores.find((item) => item.id === storeId);
  const visibleAgents = agents.filter((item) => item.store_id === storeId);
  const dirty = Boolean(selected && draft && JSON.stringify(draft) !== JSON.stringify(draftOf(selected)));

  const refreshAgents = useCallback(async () => {
    const items = await listAgents();
    setAgents(items);
    return items;
  }, []);
  useEffect(() => {
    let active = true;
    void listAgentTemplates().then((result) => { if (active) setCanManageTemplates(result.can_manage); })
      .catch(() => { if (active) setCanManageTemplates(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    let active = true;
    void Promise.all([listStores(), listAgents()]).then(([storeItems, agentItems]) => {
      if (!active) return;
      setStores(storeItems); setAgents(agentItems);
      const requested = new URLSearchParams(window.location.search).get("store_id");
      setStoreId(storeItems.find((item) => item.id === requested)?.id ?? storeItems[0]?.id ?? "");
    }).catch((caught) => { if (active) setError(message(caught)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    setSelectedId((old) => {
      const requested = new URLSearchParams(window.location.search).get("agent_id");
      return agents.some((item) => item.id === old && item.store_id === storeId) ? old
        : agents.find((item) => item.id === requested && item.store_id === storeId)?.id ?? agents.find((item) => item.store_id === storeId)?.id ?? "";
    });
  }, [agents, storeId]);
  useEffect(() => { previewAbort.current?.abort(); setPreviewDrafts({}); setPreviewInput(""); setTab("basic"); setPreviewLines([]); setPreviewResult(null); setPreviewError(""); setPreviewBusy(false); setConversationId(""); setPreviewMode("single"); previewRequestId.current++; }, [storeId, selectedId]);
  useEffect(() => {
    if (previewBody.current) previewBody.current.scrollTop = previewBody.current.scrollHeight;
  }, [previewLines, previewDrafts]);
  useEffect(() => () => { previewRequestId.current++; previewAbort.current?.abort(); }, []);
  useEffect(() => {
    setDraft(selected ? draftOf(selected) : null);
    setPreviewLines([]);
  }, [selected]);
  useEffect(() => {
    let active = true;
    setSessions([]);
    if (storeId) void listSessions(new URLSearchParams({ store_id: storeId, page: "1", page_size: "50" }))
      .then((page) => { if (active) setSessions(page.items.filter((item) => item.store_id === storeId)); })
      .catch(() => { if (active) setSessions([]); });
    return () => { active = false; };
  }, [storeId]);
  useEffect(() => {
    const sequence = ++requestId.current;
    let active = true;
    setFiles([]); setFileChoice(""); setLogs([]); setLogsError(""); setError(""); setNotice("");
    if (!storeId) return;
    void (async () => {
      try {
        const collected: DocumentFileSummary[] = [];
        for (let page = 1; page <= 20; page++) {
          const query = new URLSearchParams({ store_id: storeId, page: String(page), page_size: "100" });
          const result = await listDocumentFiles(query);
          collected.push(...result.items);
          if (collected.length >= result.total) break;
        }
        if (active && sequence === requestId.current) setFiles(collected.filter((file) => !file.archived_at));
      } catch (caught) { if (active && sequence === requestId.current) setError(message(caught)); }
    })();
    return () => { active = false; };
  }, [storeId]);
  useEffect(() => {
    let active = true;
    setLogs([]); setLogsError("");
    if (selectedId) void getAgentLogs(selectedId).then((page) => { if (active) setLogs(page.items); })
      .catch((caught) => { if (active) setLogsError(message(caught)); });
    return () => { active = false; };
  }, [selectedId]);
  useEffect(() => {
    if (!modalOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setModalOpen(false); };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [modalOpen]);
  async function save() {
    if (!selected || !draft) return;
    try {
      setNotice("");
      await updateAgent(selected.id, { ...draft, expected_revision: selected.draft_revision });
      await refreshAgents();
      setNotice("配置已保存");
    } catch (caught) { setNotice(message(caught)); }
  }
  async function publish() {
    if (!selected || dirty) return;
    try {
      setNotice("");
      await publishAgent(selected.id, selected.draft_revision);
      await refreshAgents();
      setNotice("Agent 已发布，后续运行将使用这个不可变版本");
    } catch (caught) { setNotice(message(caught)); }
  }
  async function toggleStatus() {
    if (!selected) return;
    try {
      await setAgentEnabled(selected.id, selected.status !== "enabled");
      await refreshAgents();
      setNotice(selected.status === "enabled" ? "Agent 已停用" : "Agent 已启用");
    } catch (caught) { setNotice(message(caught)); }
  }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      const created = await createAgent({
        store_id: storeId, agent_type: newType, name: String(data.get("name")).trim(),
        code: String(data.get("code")).trim(), description: null, enabled_tools: [], knowledge_file_ids: [],
      });
      await refreshAgents();
      setSelectedId(created.id); setModalOpen(false); setNotice("Agent 已创建，默认停用");
    } catch (caught) { setNotice(message(caught)); }
  }
  function updateDraft(part: Partial<Draft>) { setDraft((current) => current ? { ...current, ...part } : current); }
  async function approveFile(file: DocumentFileSummary) {
    const statementType = approvalTypes[file.id];
    if (!statementType) return;
    try {
      await approveDocumentVersion(file.id, file.latest_version.version_number, statementType);
      setFiles((current) => current.map((item) => item.id === file.id ? {
        ...item, latest_version: { ...item.latest_version, approval_status: "approved_for_internal_review", statement_type: statementType },
      } : item));
      setNotice("当前文件版本已批准用于内部建议");
    } catch (caught) { setNotice(message(caught)); }
  }
  async function revokeFile(file: DocumentFileSummary) {
    try {
      await revokeDocumentVersion(file.id, file.latest_version.version_number);
      setFiles((current) => current.map((item) => item.id === file.id ? {
        ...item, latest_version: { ...item.latest_version, approval_status: "draft" },
      } : item));
      setNotice("文件版本内部建议审批已撤销");
    } catch (caught) { setNotice(message(caught)); }
  }
  async function preview() {
    const input = previewInput.trim();
    if (!input || !selected || previewBusy || dirty) return;
    const sequence = ++previewRequestId.current;
    const controller = new AbortController();
    previewAbort.current?.abort(); previewAbort.current = controller;
    setPreviewBusy(true); setPreviewError(""); setPreviewResult(null); setPreviewDrafts({});
    setPreviewInput("");
    setPreviewLines((old) => [...old, { role: "user", text: input }]);
    let receivedResult = false;
    try {
      await streamAgentDebug(selected.id, input, conversationId || null, previewMode, (event) => {
        if (sequence !== previewRequestId.current || controller.signal.aborted) return;
        if (event.event === "draft" && !receivedResult) {
          const index = event.data.part_index;
          if (typeof index === "number" && typeof event.data.text === "string") {
            setPreviewDrafts((old) => ({ ...old, [index]: event.data.text as string }));
          }
        } else if (event.event === "result") {
          const result = event.data as unknown as AgentDebugResult;
          receivedResult = true; setPreviewDrafts({}); setPreviewResult(result);
          setPreviewLines((old) => [...old, { role: "assistant", text: result.content || "没有可安全展示的建议。请检查绑定知识、工具上下文和运行记录。" }]);
          void getAgentLogs(selected.id).then((page) => { if (sequence === previewRequestId.current) setLogs(page.items); }).catch(() => undefined);
        } else if (event.event === "error") {
          throw new Error(typeof event.data.message === "string" ? event.data.message : "Agent 调试失败");
        }
      }, controller.signal);
      if (!receivedResult && !controller.signal.aborted) throw new Error("Agent 调试未返回最终结果，请重试");
    } catch (caught) {
      if (sequence === previewRequestId.current && !controller.signal.aborted) setPreviewError(message(caught));
    } finally {
      if (sequence === previewRequestId.current) { setPreviewBusy(false); setPreviewDrafts({}); }
    }
  }
  return <AppShell><div className="agent-page"><div className="shell">
    <header className="topbar"><div className="title"><span className="title-icon">◇</span><div><h1>Agent 管理</h1><p>配置 TikTok 店铺的人工辅助客服建议</p></div></div>
      <div className="top-actions"><label className="store">▣ 当前店铺：<select aria-label="当前店铺" value={storeId} onChange={(event) => setStoreId(event.target.value)}>{stores.map((store) => <option value={store.id} key={store.id}>{store.name}</option>)}</select></label>
        <button type="button" className="btn primary" onClick={() => setModalOpen(true)} disabled={!storeId}>＋ 新建 Agent</button></div></header>
    <AgentTemplateNav current="agents" />
    {error ? <p className="agent-error" role="alert">{error}</p> : null}
    {notice ? <p className="agent-error" role="status">{notice}</p> : null}
    <main className="main">
      <section className="hero"><div className="hero-copy"><span className="eyebrow">TIKTOK · HUMAN ASSISTED SERVICE</span><h2>让客服建议保持可控</h2><p>按店铺管理 Agent、工具和知识范围。由坐席审阅模型建议并确认回复。</p></div><div className="hero-stats"><div className="hero-stat"><strong>{visibleAgents.filter((item) => item.status === "enabled").length}</strong><small>当前启用</small></div><div className="hero-stat"><strong>{visibleAgents.filter((item) => item.published_version !== null).length}</strong><small>已发布</small></div></div></section>
      <div className="page-head"><div><h2>选择 Agent</h2><p>横向切换当前店铺的 Agent 配置。</p></div><span className="count-pill">{visibleAgents.length} 个 Agent</span></div>
      <div className="agent-nav" aria-label="当前店铺的 Agent">{visibleAgents.map((item) => <button type="button" key={item.id} className={`agent-card ${item.id === selectedId ? "active" : ""}`} onClick={() => setSelectedId(item.id)}><span className="agent-card-top"><strong>{item.name}</strong><span className={`status ${item.status === "enabled" ? "" : "off"}`}>{item.status === "enabled" ? "运行中" : "已停用"}</span></span><small>{item.description || "当前店铺 Agent"}</small><span className="agent-card-foot"><span className="scenario">{item.agent_type === "operations" ? "经营类" : "服务类"}</span><span>{new Set([...item.enabled_tools, ...(item.knowledge_file_ids?.length ? ["search_knowledge"] : [])]).size} 项工具</span></span></button>)}</div>
      {loading ? <p className="agent-empty">正在加载 Agent 配置…</p> : !selected || !draft ? <p className="agent-empty">{stores.length ? "当前店铺暂无 Agent，请点击“新建 Agent”。" : <>请先<Link href="/settings/stores">创建店铺</Link>，再配置 Agent。</>}</p> : <>
      <section className="config" aria-labelledby="configTitle"><div className="config-head"><div><h2 id="configTitle">{selected.name}</h2><p>{currentStore?.name} · {selected.code} · {selected.published_version ? `已发布 v${selected.published_version}` : "未发布"}</p></div><div className="config-actions"><AgentSource key={`${selected.id}:${selected.draft_revision}:${selected.published_version ?? "none"}`} agentId={selected.id} disabled={dirty} onDetached={refreshAgents} />{canManageTemplates ? <button className="btn small" type="button" onClick={() => setTemplateSource(selected)}>保存为模板</button> : null}{dirty ? <span className="dirty">未保存</span> : null}<button className="btn small" type="button" onClick={() => void toggleStatus()}>{selected.status === "enabled" ? "停用" : "启用"}</button><button className="btn small" type="button" disabled={dirty || !draft.model_provider || !draft.model_name || promptSections.some((section) => !draft.prompt_sections[section.key]?.trim())} onClick={() => void publish()}>发布版本</button><button className="btn primary small" type="button" onClick={() => void save()}>保存配置</button></div></div>
        <div className="tabs" role="tablist" aria-label="Agent 配置">{tabs.map((item) => <button type="button" role="tab" aria-selected={tab === item.key} className={`tab ${tab === item.key ? "active" : ""}`} key={item.key} onClick={() => setTab(item.key)}>{item.label}</button>)}</div>
        <div className="config-body">
          {tab === "basic" ? <section className="panel active" role="tabpanel"><div className="section-head"><h3>基础设置</h3><p>管理当前店铺的 Agent 名称和用途。</p></div><div className="form-grid">
            <label className="field-group wide"><span>Agent 类型</span><select className="field" value={draft.agent_type} onChange={(event) => updateDraft({ agent_type: event.target.value as Draft["agent_type"] })}><option value="service">服务类 Agent（人工辅助客服）</option><option value="operations">经营类 Agent（内部分析）</option></select><p className="help">发布并启用后，模型可根据职责描述选择当前店铺的任意 Agent。</p></label>
            <label className="field-group"><span>所属店铺</span><input className="field" value={currentStore?.name ?? ""} disabled /></label><label className="field-group"><span>Agent 编码</span><input className="field" value={selected.code} disabled /></label>
            <label className="field-group wide"><span>Agent 名称</span><input className="field" maxLength={200} value={draft.name} onChange={(event) => updateDraft({ name: event.target.value })} /></label>
            <label className="field-group wide"><span>用途描述</span><textarea className="field fieldarea" maxLength={1000} value={draft.description ?? ""} onChange={(event) => updateDraft({ description: event.target.value || null })} /></label>
          </div><div className="inline-note">当前仅提供 TikTok 人工辅助建议。Agent 不直接发送平台消息，坐席须复核并确认回复。</div></section> : null}
          {tab === "reply" ? <section className="panel active" role="tabpanel"><div className="section-head"><h3>模型与提示词</h3><p>选择项目已配置模型，编辑七段式系统提示词；保存草稿后发布版本才会用于运行。</p></div>
            <AgentPromptFields value={draft} modelOptions={selected.runtime.model_options?.length ? selected.runtime.model_options : (selected.runtime.available_models ?? []).map((model) => ({ provider: selected.runtime.llm_provider, model_name: model }))} onChange={updateDraft} />
            <div className="policy-card"><h4>回复偏好</h4><p>客户语言用于面向买家的正文；坐席语言用于内部说明或译文，不改变客户正文。随发布版本生效，保存草稿不影响运行。</p><div className="form-grid"><label className="field-group"><span>回复语气</span><select aria-label="回复语气" className="field" value={draft.reply_profile.tone} onChange={(event) => updateDraft({ reply_profile: { ...draft.reply_profile, tone: event.target.value as typeof draft.reply_profile.tone } })}><option value="friendly">友好</option><option value="professional">专业</option><option value="concise">简洁</option><option value="empathetic">共情</option></select></label>
            <label className="field-group"><span>客户回复语言</span><select aria-label="客户回复语言" className="field" value={draft.reply_profile.reply_language} onChange={(event) => updateDraft({ reply_profile: { ...draft.reply_profile, reply_language: event.target.value as typeof draft.reply_profile.reply_language } })}><option value="auto">自动跟随客户</option><option value="zh-CN">简体中文</option><option value="en">英语</option></select></label>
            <label className="field-group"><span>坐席工作语言</span><select aria-label="坐席工作语言" className="field" value={draft.reply_profile.operator_language} onChange={(event) => updateDraft({ reply_profile: { ...draft.reply_profile, operator_language: event.target.value as typeof draft.reply_profile.operator_language } })}><option value="zh-CN">简体中文</option><option value="en">英语</option></select></label></div></div><div className="policy-list"><span>输入字段白名单</span><span>只引用已审批知识</span><span>未知事实转人工</span><span>真实自动回复未接入</span></div></section> : null}
          {tab === "tools" ? <><AgentToolCatalog storeId={storeId} enabled={draft.enabled_tools} boundFileCount={draft.knowledge_file_ids.length} onChange={(names) => updateDraft({ enabled_tools: names })} onConfigureKnowledge={() => setTab("knowledge")} /><LogisticsNotificationPolicyControls agents={agents} key={storeId} storeId={storeId} /></> : null}
          {tab === "knowledge" ? <section className="panel active" role="tabpanel"><div className="section-head"><h3>绑定知识库中的文档</h3><p>选择当前店铺已导入的文件。仅已审批且索引就绪的有效版本用于 Agent 检索。</p></div>
            <div className="binding-picker"><label htmlFor="knowledgeChoice">选择已导入知识</label><div className="binding-row"><select id="knowledgeChoice" aria-label="选择已导入知识" className="field" value={fileChoice} onChange={(event) => setFileChoice(event.target.value)}><option value="">请选择文件</option>{files.filter((file) => !draft.knowledge_file_ids.includes(file.id)).map((file) => <option key={file.id} value={file.id}>{file.filename}</option>)}</select><button className="btn primary" type="button" disabled={!fileChoice} onClick={() => { updateDraft({ knowledge_file_ids: [...draft.knowledge_file_ids, fileChoice] }); setFileChoice(""); }}>＋ 绑定知识</button></div><p className="binding-help">绑定范围随 Agent 配置保存；不可跨店铺绑定。</p></div>
            <div className="bound-head"><h4>当前 Agent 已绑定</h4><span className="bound-count">{draft.knowledge_file_ids.length} 个文件</span></div><div className="bound-list">{draft.knowledge_file_ids.length ? draft.knowledge_file_ids.map((id) => { const file = files.find((item) => item.id === id); const activeReady = Boolean(file && file.latest_version.is_active && file.latest_version.status === "ready"); const approved = activeReady && file?.latest_version.approval_status === "approved_for_internal_review"; return <div className="bound-item" key={id}><span className="doc-icon">▤</span><div className="bound-item-body"><strong>{file?.filename ?? "文件不可用"}</strong><small>{file ? `v${file.active_version_number ?? "—"} · ${file.latest_version.status}` : "当前店铺无此文件"}</small></div><span className={`bound-state ${approved ? "" : "pending"}`}>{approved ? "可用于内部建议" : "暂不可检索"}</span>{activeReady && !approved && file ? <div className="file-approval-action"><select className="field" aria-label={`确认语义类型：${file.filename}`} value={approvalTypes[file.id] ?? ""} onChange={(event) => setApprovalTypes((old) => ({ ...old, [file.id]: event.target.value as typeof approvalTypes[string] }))}><option value="">确认语义类型</option><option value="policy">政策</option><option value="technical_artifact">技术资料</option><option value="non_assertive_proposition">非断言资料</option></select><button className="btn small" type="button" disabled={!approvalTypes[file.id]} onClick={() => void approveFile(file)}>批准内部建议</button></div> : null}{approved && file ? <button className="btn small" type="button" onClick={() => void revokeFile(file)}>撤销审批</button> : null}<button className="remove-bound" type="button" aria-label={`移除绑定：${file?.filename ?? id}`} onClick={() => updateDraft({ knowledge_file_ids: draft.knowledge_file_ids.filter((value) => value !== id) })}>×</button></div>; }) : <div className="bound-empty">尚未绑定知识库文件</div>}</div>
            <div className="binding-meta"><span>当前店铺：<b>{currentStore?.name}</b></span><span>真实平台自动回复：<b>关闭</b></span><span>检索失败：<b>失败关闭</b></span></div><Link className="binding-link" href={`/knowledge?store_id=${storeId}`}>打开知识库 →</Link></section> : null}
          {tab === "logs" ? <section className="panel active" role="tabpanel"><div className="section-head"><h3>脱敏运行记录</h3><p>展示父子运行阶段和版本，不展示客户原文、完整模型输入或密钥。</p></div><div className="logs">{logsError ? <p role="alert">{logsError}</p> : logs.length ? logs.map((run) => <div className="bound-item" key={run.id}><div className="bound-item-body"><strong>{run.parent_run_id ? "子 Agent" : "主运行"} · {run.phase ?? run.intent ?? "待复核"} · {run.action}</strong><small>{run.model_provider}/{run.model_name} · {run.config_version ? `v${run.config_version} · ` : ""}{run.latency_ms ?? "—"} ms · trace {run.trace_id?.slice(0, 12) ?? "—"}</small></div><span className="bound-state">{run.status}</span></div>) : <div className="bound-empty">暂无运行记录</div>}</div></section> : null}
        </div></section>
      <section className="preview" aria-labelledby="previewTitle"><div className="preview-head"><div><h3 id="previewTitle">预览与调试</h3><p>真实模型 · 已绑定知识检索 · 授权会话的只读工具 · 不发送真实消息</p></div><button type="button" className="btn small" onClick={() => { previewRequestId.current++; previewAbort.current?.abort(); setPreviewDrafts({}); setPreviewLines([]); setPreviewResult(null); setPreviewError(""); setPreviewBusy(false); }}>清空</button></div>
        <div ref={previewBody} className="preview-body" aria-live="polite">{previewLines.length ? previewLines.map((line, index) => <div className={`preview-bubble ${line.role}`} key={index}>{line.text}</div>) : <p>输入问题，调试当前 Agent 或当前店铺的多 Agent 路由。</p>}{previewBusy ? <p role="status">{Object.keys(previewDrafts).length ? "正在生成 · 草稿待复核" : "正在调用模型、检索和工具…"}</p> : null}{Object.entries(previewDrafts).sort(([a], [b]) => Number(a) - Number(b)).map(([index, text]) => <div className="preview-bubble assistant" aria-label="待复核草稿" key={index}>{text}</div>)}{previewError ? <p role="alert">{previewError}</p> : null}{previewResult ? <div className="preview-diagnostics"><strong>本次运行 · {previewResult.terminal_state}</strong><p>路由：{previewResult.routed_agents?.length ? previewResult.routed_agents.map((item) => item.name).join("、") : "未选择 Agent"}</p><p>工具：{previewResult.tool_events?.length ? previewResult.tool_events.map((item) => `${item.tool_name}（${item.status}）`).join("、") : previewResult.tool_calls.length ? previewResult.tool_calls.map((call) => `${call.tool_name}（${call.status}）`).join("、") : "未调用"}</p><p>引用：{previewResult.citations.length ? previewResult.citations.map((item) => item.source_label).join("、") : "无"}</p>{previewResult.customer_translation?.draft_translation ? <details className="operator-translation"><summary>坐席译文 · {previewResult.customer_translation.target_language === "en" ? "英语" : "简体中文"}</summary><p>{previewResult.customer_translation.draft_translation}</p><small>仅供坐席理解与复核；面向客户的正文见上方。</small></details> : previewResult.customer_translation_error_code ? <p>坐席译文暂不可用，请复核上方客户正文。</p> : null}{previewResult.reason_code ? <p>需复核：{previewResult.reason_code}</p> : null}<small>追踪 ID：{previewResult.trace_id}</small></div> : null}</div>
        <label className="preview-context">调试范围<select className="field" aria-label="调试范围" value={previewMode} onChange={(event) => setPreviewMode(event.target.value as "single" | "store")}><option value="single">当前 Agent</option><option value="store">当前店铺全部已启用 Agent</option></select></label>
        <label className="preview-context">只读工具上下文（可选）<select className="field" aria-label="只读工具上下文" value={conversationId} onChange={(event) => setConversationId(event.target.value)}><option value="">不关联会话；仅测试模型与已绑定知识</option>{sessions.map((item) => <option key={item.id} value={item.id}>{item.customer.name || "未命名客户"} · {item.id.slice(0, 8)}</option>)}</select></label><form className="preview-input" onSubmit={(event) => { event.preventDefault(); void preview(); }}><input className="field" maxLength={4000} placeholder="试试：你好 / 我的订单什么时候到？" value={previewInput} onChange={(event) => setPreviewInput(event.target.value)} /><button className="btn primary" type="submit" disabled={previewBusy || dirty || !selected.runtime.available}>运行调试</button></form><p className="preview-note">未绑定知识文件时仍可调试模型与授权只读工具，不会检索整店 FAQ。订单、物流和客户工具需关联当前店铺的授权会话；所有建议须由坐席复核。</p></section>
        <AgentCollaboration key={conversationId} conversationId={conversationId} refreshKey={previewResult?.agent_run_id} />
      </>}
    </main>
    {templateSource ? <SaveAgentTemplate key={`${templateSource.id}:${templateSource.draft_revision}`} agent={templateSource} onClose={() => setTemplateSource(null)} onSaved={() => { setTemplateSource(null); setNotice("模板草稿已创建，尚未发布"); }} /> : null}
    {modalOpen ? <div className="overlay"><form className="modal" role="dialog" aria-modal="true" aria-label="新建 Agent" onSubmit={(event) => void create(event)}><div className="modal-head"><h2>新建 Agent</h2><button type="button" className="close" aria-label="关闭" onClick={() => setModalOpen(false)}>×</button></div><div className="modal-body"><div className="section-head"><h3>选择 Agent 类别</h3><p>新建后默认停用；完成模型、提示词、工具和知识配置并发布后可启用。</p></div><div className="template-grid">{(["service", "operations"] as const).map((type) => <button type="button" className={`template ${newType === type ? "selected" : ""}`} onClick={() => setNewType(type)} key={type}><span className="template-icon">{type === "service" ? "🤝" : "📈"}</span><strong>{type === "service" ? "服务类 Agent" : "经营类 Agent"}</strong><small>{type === "service" ? "售前 / 售后 / 物流咨询" : "数据监测与内部分析"}</small></button>)}</div><div className="form-grid"><label className="field-group"><span>所属店铺</span><input className="field" value={currentStore?.name ?? ""} disabled /></label><label className="field-group"><span>Agent 编码</span><input className="field" name="code" aria-label="Agent 编码" required pattern="[a-z0-9](?:[a-z0-9_]|-){1,99}" maxLength={100} placeholder="例如：service_us_02" /></label><label className="field-group wide"><span>Agent 名称</span><input className="field" name="name" aria-label="Agent 名称" required maxLength={200} placeholder="例如：售前咨询 Agent" /></label></div></div><div className="modal-foot"><button type="button" className="btn" onClick={() => setModalOpen(false)}>取消</button><button type="submit" className="btn primary">创建 Agent</button></div></form></div> : null}
  </div></div></AppShell>;
}
