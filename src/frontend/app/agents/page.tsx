"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "../../components/AppShell";
import {
  approveDocumentVersion, createAgent, getAgentLogs, listAgents, listDocumentFiles, listStores, revokeDocumentVersion, setAgentEnabled, updateAgent,
  type AgentConfig, type AgentRunLog, type DocumentFileSummary, type StoreView,
} from "../../lib/api";
import "./agent-prototype.css";

type Tab = "basic" | "reply" | "tools" | "knowledge" | "logs";
type Draft = Pick<AgentConfig, "name" | "description" | "agent_type" | "enabled_tools" | "knowledge_file_ids" | "reply_profile">;
const tabs: { key: Tab; label: string }[] = [
  { key: "basic", label: "⚙ 基础设置" }, { key: "reply", label: "◇ 模型与提示词" },
  { key: "tools", label: "▧ 工具能力" }, { key: "knowledge", label: "▤ 知识库" }, { key: "logs", label: "◷ 运行记录" },
];
const tools = [
  { code: "query_order", name: "查询订单", description: "查询当前店铺订单信息", configurable: true },
  { code: "query_logistics", name: "查询物流", description: "查询配送状态", configurable: true },
  { code: "query_customer_profile", name: "查询客户资料", description: "只读客户上下文", configurable: true },
  { code: "transfer_to_human", name: "转人工", description: "交由坐席处理", configurable: true },
  { code: "update_shipping_address", name: "修改收货地址", description: "高风险写入，当前不可用", configurable: false },
  { code: "send_coupon", name: "发送优惠券", description: "高风险写入，当前不可用", configurable: false },
  { code: "send_platform_message", name: "发送平台消息", description: "真实自动回复未开放", configurable: false },
];
const promptSummary = `角色：TikTok 店铺人工辅助客服建议助手。只为坐席生成待复核建议，不直接发送平台消息。

处理范围：售前、售后和物流咨询；经营类 Agent 仅展示内部分析配置。

事实依据：订单、物流、优惠及政策声明只能引用当前店铺的受控只读工具结果或已审批且检索就绪的知识。缺少可靠来源时说明无法确认并转人工。

安全边界：仅接收允许字段和经过 DLP 处理的输入。结构化结果、引用和安全状态须校验；错误或不确定时失败关闭。真实平台自动回复仍未开放。`;
function draftOf(agent: AgentConfig): Draft {
  return {
    name: agent.name, description: agent.description, agent_type: agent.agent_type ?? "service",
    enabled_tools: agent.enabled_tools.filter((tool) => tools.some((item) => item.code === tool && item.configurable)),
    knowledge_file_ids: agent.knowledge_file_ids ?? [],
    reply_profile: agent.reply_profile ?? { tone: "friendly", reply_language: "auto", operator_language: "zh-CN", brand_name: null },
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
  const [newType, setNewType] = useState<"service" | "operations">("service");
  const [previewInput, setPreviewInput] = useState("");
  const [previewLines, setPreviewLines] = useState<string[]>([]);
  const [demoAutoSend, setDemoAutoSend] = useState<Record<string, boolean>>({});
  const [modelChoices, setModelChoices] = useState<Record<string, string>>({});
  const requestId = useRef(0);
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
    setSelectedId((old) => agents.some((item) => item.id === old && item.store_id === storeId)
      ? old : agents.find((item) => item.store_id === storeId)?.id ?? "");
  }, [agents, storeId]);
  useEffect(() => { setTab("basic"); setPreviewLines([]); }, [storeId, selectedId]);
  useEffect(() => {
    setDraft(selected ? draftOf(selected) : null);
    setPreviewLines([]);
  }, [selected]);
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
      await updateAgent(selected.id, draft);
      await refreshAgents();
      setNotice("配置已保存");
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
  function preview() {
    const input = previewInput.trim();
    if (!input) return;
    const reply = !selected || selected.status !== "enabled" ? "Agent 已停用：当前仅展示本地规则演示。"
      : /(退款|退货|赔偿|投诉|地址|优惠|政策)/.test(input) ? "该咨询需核实当前店铺事实并由坐席处理。"
      : demoAutoSend[selected.id] ? "模拟自动发送：已收到咨询，请稍候，坐席将核实后回复。真实平台消息未发送。"
      : "这是页面内演示建议。真实建议需在客服工作台调用并经过坐席复核。";
    setPreviewLines((old) => [...old, input, reply]); setPreviewInput("");
  }
  return <AppShell><div className="agent-page"><div className="shell">
    <header className="topbar"><div className="title"><span className="title-icon">◇</span><div><h1>Agent 管理</h1><p>配置 TikTok 店铺的人工辅助客服建议</p></div></div>
      <div className="top-actions"><label className="store">▣ 当前店铺：<select aria-label="当前店铺" value={storeId} onChange={(event) => setStoreId(event.target.value)}>{stores.map((store) => <option value={store.id} key={store.id}>{store.name}</option>)}</select></label>
        <button type="button" className="btn primary" onClick={() => setModalOpen(true)} disabled={!storeId}>＋ 新建 Agent</button></div></header>
    {error ? <p className="agent-error" role="alert">{error}</p> : null}
    {notice ? <p className="agent-error" role="status">{notice}</p> : null}
    <main className="main">
      <section className="hero"><div className="hero-copy"><span className="eyebrow">TIKTOK · HUMAN ASSISTED SERVICE</span><h2>让客服建议保持可控</h2><p>按店铺管理 Agent、工具和知识范围。默认由坐席复核建议；自动发送开关只模拟页面交互。</p></div><div className="hero-stats"><div className="hero-stat"><strong>{visibleAgents.filter((item) => item.status === "enabled").length}</strong><small>当前启用</small></div><div className="hero-stat"><strong>{visibleAgents.filter((item) => demoAutoSend[item.id]).length}</strong><small>模拟自动发送</small></div></div></section>
      <div className="page-head"><div><h2>选择 Agent</h2><p>横向切换当前店铺的 Agent 配置。</p></div><span className="count-pill">{visibleAgents.length} 个 Agent</span></div>
      <div className="agent-nav" aria-label="当前店铺的 Agent">{visibleAgents.map((item) => <button type="button" key={item.id} className={`agent-card ${item.id === selectedId ? "active" : ""}`} onClick={() => setSelectedId(item.id)}><span className="agent-card-top"><strong>{item.name}</strong><span className={`status ${item.status === "enabled" ? "" : "off"}`}>{item.status === "enabled" ? "运行中" : "已停用"}</span></span><small>{item.description || "当前店铺 Agent"}</small><span className="agent-card-foot"><span className="scenario">{item.agent_type === "operations" ? "经营类" : "服务类"}</span><span>{item.enabled_tools.length} 项工具</span></span></button>)}</div>
      {loading ? <p className="agent-empty">正在加载 Agent 配置…</p> : !selected || !draft ? <p className="agent-empty">{stores.length ? "当前店铺暂无 Agent，请点击“新建 Agent”。" : <>请先<Link href="/settings/stores">创建店铺</Link>，再配置 Agent。</>}</p> : <>
      <section className="config" aria-labelledby="configTitle"><div className="config-head"><div><h2 id="configTitle">{selected.name}</h2><p>{currentStore?.name} · {selected.code}</p></div><div className="config-actions">{dirty ? <span className="dirty">未保存</span> : null}<button className="btn small" type="button" disabled={draft.agent_type === "operations"} onClick={() => void toggleStatus()}>{draft.agent_type === "operations" ? "仅内部演示" : selected.status === "enabled" ? "停用" : "启用"}</button><button className="btn primary small" type="button" onClick={() => void save()}>保存配置</button></div></div>
        <div className="tabs" role="tablist" aria-label="Agent 配置">{tabs.map((item) => <button type="button" role="tab" aria-selected={tab === item.key} className={`tab ${tab === item.key ? "active" : ""}`} key={item.key} onClick={() => setTab(item.key)}>{item.label}</button>)}</div>
        <div className="config-body">
          {tab === "basic" ? <section className="panel active" role="tabpanel"><div className="section-head"><h3>基础设置</h3><p>管理当前店铺的 Agent 名称和用途。</p></div><div className="form-grid">
            <label className="field-group wide"><span>Agent 类型</span><select className="field" value={draft.agent_type} onChange={(event) => updateDraft({ agent_type: event.target.value as Draft["agent_type"] })}><option value="service">服务类 Agent（人工辅助客服）</option><option value="operations">经营类 Agent（内部分析）</option></select><p className="help">经营类仅保存配置，不参与客服建议运行。</p></label>
            <label className="field-group"><span>所属店铺</span><input className="field" value={currentStore?.name ?? ""} disabled /></label><label className="field-group"><span>Agent 编码</span><input className="field" value={selected.code} disabled /></label>
            <label className="field-group wide"><span>Agent 名称</span><input className="field" maxLength={200} value={draft.name} onChange={(event) => updateDraft({ name: event.target.value })} /></label>
            <label className="field-group wide"><span>用途描述</span><textarea className="field fieldarea" maxLength={1000} value={draft.description ?? ""} onChange={(event) => updateDraft({ description: event.target.value || null })} /></label>
          </div><div className="auto-send-setting"><div><strong>自动发送 · 原型演示</strong><p>仅影响下方本地预览，不连接平台，不保存至服务端。</p></div><button className={`auto-send-switch ${demoAutoSend[selected.id] ? "on" : ""}`} type="button" role="switch" aria-label="自动发送原型演示" aria-checked={Boolean(demoAutoSend[selected.id])} disabled={draft.agent_type === "operations"} onClick={() => setDemoAutoSend((old) => ({ ...old, [selected.id]: !old[selected.id] }))}><span className="switch-track" aria-hidden="true" /><span>{demoAutoSend[selected.id] ? "已开启" : "已关闭"}</span></button></div><div className="inline-note">当前仅提供 TikTok 人工辅助建议。Agent 不直接发送平台消息，坐席须复核并确认回复。</div></section> : null}
          {tab === "reply" ? <section className="panel active" role="tabpanel"><div className="section-head"><h3>模型与提示词</h3><p>模型和系统策略由项目发布基线管理；下方受控回复参数可保存。</p></div>
            <div className="model-section"><label className="field-group"><span>驱动模型 · 已接入</span><select className="field model-select" value={modelChoices[selected.id] ?? selected.runtime.llm_model ?? ""} disabled={draft.agent_type === "operations"} onChange={(event) => setModelChoices((old) => ({ ...old, [selected.id]: event.target.value }))}>{(selected.runtime.available_models?.length ? selected.runtime.available_models : [selected.runtime.llm_model ?? ""]).map((model) => <option value={model} key={model}>{model || "未配置模型"}{model === selected.runtime.llm_model ? " · 主模型" : " · 备用模型"}</option>)}</select></label><p className="model-help">下拉仅列出项目已配置模型。选择只影响本页演示；实际运行模型由服务端配置决定。</p></div>
            <div className="prompt-section"><h4>系统提示词策略摘要 · 只读</h4><textarea className="prompt-summary" aria-label="系统提示词策略摘要" value={promptSummary} readOnly /><p className="prompt-help">此处是策略摘要，完整生产 Prompt 由发布基线管理。</p></div>
            <div className="policy-card"><h4>受控回复参数</h4><div className="form-grid"><label className="field-group"><span>回复语气</span><select className="field" value={draft.reply_profile.tone} onChange={(event) => updateDraft({ reply_profile: { ...draft.reply_profile, tone: event.target.value as typeof draft.reply_profile.tone } })}><option value="friendly">友好</option><option value="professional">专业</option><option value="concise">简洁</option><option value="empathetic">共情</option></select></label>
            <label className="field-group"><span>客户回复语言</span><select className="field" value={draft.reply_profile.reply_language} onChange={(event) => updateDraft({ reply_profile: { ...draft.reply_profile, reply_language: event.target.value as typeof draft.reply_profile.reply_language } })}><option value="auto">自动跟随客户</option><option value="zh-CN">简体中文</option><option value="en">英语</option></select></label>
            <label className="field-group"><span>坐席工作语言</span><select className="field" value={draft.reply_profile.operator_language} onChange={(event) => updateDraft({ reply_profile: { ...draft.reply_profile, operator_language: event.target.value as typeof draft.reply_profile.operator_language } })}><option value="zh-CN">简体中文</option><option value="en">英语</option></select></label></div></div><div className="policy-list"><span>输入字段白名单</span><span>只引用已审批知识</span><span>未知事实转人工</span><span>真实自动回复未接入</span></div></section> : null}
          {tab === "tools" ? <section className="panel active" role="tabpanel"><div className="section-head"><h3>白名单工具 <span className="count-pill">{draft.enabled_tools.length}</span></h3><p>只读查询与转人工可配置。高风险写入保持关闭。</p></div><div className="tool-grid">{tools.map((tool) => <label className="tool-card" key={tool.code}><span><strong>{tool.name}</strong><small>{tool.description}</small></span><input type="checkbox" name={tool.code} disabled={!tool.configurable} checked={tool.configurable && draft.enabled_tools.includes(tool.code)} onChange={(event) => updateDraft({ enabled_tools: event.target.checked ? [...draft.enabled_tools, tool.code] : draft.enabled_tools.filter((value) => value !== tool.code) })} /></label>)}</div><div className="tool-footer">工具执行仍由服务端检查店铺、权限、审计与输出字段。</div></section> : null}
          {tab === "knowledge" ? <section className="panel active" role="tabpanel"><div className="section-head"><h3>绑定知识库中的文档</h3><p>选择当前店铺已导入的文件。仅已审批且索引就绪的有效版本用于 Agent 检索。</p></div>
            <div className="binding-picker"><label htmlFor="knowledgeChoice">选择已导入知识</label><div className="binding-row"><select id="knowledgeChoice" aria-label="选择已导入知识" className="field" value={fileChoice} onChange={(event) => setFileChoice(event.target.value)}><option value="">请选择文件</option>{files.filter((file) => !draft.knowledge_file_ids.includes(file.id)).map((file) => <option key={file.id} value={file.id}>{file.filename}</option>)}</select><button className="btn primary" type="button" disabled={!fileChoice} onClick={() => { updateDraft({ knowledge_file_ids: [...draft.knowledge_file_ids, fileChoice] }); setFileChoice(""); }}>＋ 绑定知识</button></div><p className="binding-help">绑定范围随 Agent 配置保存；不可跨店铺绑定。</p></div>
            <div className="bound-head"><h4>当前 Agent 已绑定</h4><span className="bound-count">{draft.knowledge_file_ids.length} 个文件</span></div><div className="bound-list">{draft.knowledge_file_ids.length ? draft.knowledge_file_ids.map((id) => { const file = files.find((item) => item.id === id); const activeReady = Boolean(file && file.latest_version.is_active && file.latest_version.status === "ready"); const approved = activeReady && file?.latest_version.approval_status === "approved_for_internal_review"; return <div className="bound-item" key={id}><span className="doc-icon">▤</span><div className="bound-item-body"><strong>{file?.filename ?? "文件不可用"}</strong><small>{file ? `v${file.active_version_number ?? "—"} · ${file.latest_version.status}` : "当前店铺无此文件"}</small></div><span className={`bound-state ${approved ? "" : "pending"}`}>{approved ? "可用于内部建议" : "暂不可检索"}</span>{activeReady && !approved && file ? <div className="file-approval-action"><select className="field" aria-label={`确认语义类型：${file.filename}`} value={approvalTypes[file.id] ?? ""} onChange={(event) => setApprovalTypes((old) => ({ ...old, [file.id]: event.target.value as typeof approvalTypes[string] }))}><option value="">确认语义类型</option><option value="policy">政策</option><option value="technical_artifact">技术资料</option><option value="non_assertive_proposition">非断言资料</option></select><button className="btn small" type="button" disabled={!approvalTypes[file.id]} onClick={() => void approveFile(file)}>批准内部建议</button></div> : null}{approved && file ? <button className="btn small" type="button" onClick={() => void revokeFile(file)}>撤销审批</button> : null}<button className="remove-bound" type="button" aria-label={`移除绑定：${file?.filename ?? id}`} onClick={() => updateDraft({ knowledge_file_ids: draft.knowledge_file_ids.filter((value) => value !== id) })}>×</button></div>; }) : <div className="bound-empty">尚未绑定知识库文件</div>}</div>
            <div className="binding-meta"><span>当前店铺：<b>{currentStore?.name}</b></span><span>真实平台自动回复：<b>关闭</b></span><span>检索失败：<b>失败关闭</b></span></div><Link className="binding-link" href={`/knowledge?store_id=${storeId}`}>打开知识库 →</Link></section> : null}
          {tab === "logs" ? <section className="panel active" role="tabpanel"><div className="section-head"><h3>脱敏运行记录</h3><p>真实运行记录，不展示客户原文、完整模型输入或密钥。</p></div><div className="logs">{logsError ? <p role="alert">{logsError}</p> : logs.length ? logs.map((run) => <div className="bound-item" key={run.id}><div className="bound-item-body"><strong>{run.intent ?? "未识别意图"} · {run.action}</strong><small>{run.model_provider}/{run.model_name} · {run.latency_ms ?? "—"} ms · trace {run.trace_id?.slice(0, 12) ?? "—"}</small></div><span className="bound-state">{run.status}</span></div>) : <div className="bound-empty">暂无运行记录</div>}</div></section> : null}
        </div></section>
      <section className="preview" aria-labelledby="previewTitle"><div className="preview-head"><div><h3 id="previewTitle">预览与调试</h3><p>本地规则演示 · 无模型调用 · 不发送真实消息</p></div><button type="button" className="btn small" onClick={() => setPreviewLines([])}>清空</button></div><div className="preview-body" aria-live="polite">{previewLines.length ? previewLines.map((line, index) => <div className={`preview-bubble ${index % 2 ? "assistant" : "user"}`} key={index}>{line}</div>) : <p>输入一条示例问题，查看本地演示反馈。</p>}</div><form className="preview-input" onSubmit={(event) => { event.preventDefault(); preview(); }}><input className="field" maxLength={300} placeholder="试试：你好 / 我的订单什么时候到？" value={previewInput} onChange={(event) => setPreviewInput(event.target.value)} /><button className="btn primary" type="submit">生成演示建议</button></form><p className="preview-note">真实建议请在客服工作台生成，由坐席复核。</p></section>
      </>}
    </main>
    {modalOpen ? <div className="overlay"><form className="modal" role="dialog" aria-modal="true" aria-label="新建 Agent" onSubmit={(event) => void create(event)}><div className="modal-head"><h2>新建 Agent</h2><button type="button" className="close" aria-label="关闭" onClick={() => setModalOpen(false)}>×</button></div><div className="modal-body"><div className="section-head"><h3>选择 Agent 类别</h3><p>新建后默认停用；经营类用于内部分析配置。</p></div><div className="template-grid">{(["service", "operations"] as const).map((type) => <button type="button" className={`template ${newType === type ? "selected" : ""}`} onClick={() => setNewType(type)} key={type}><span className="template-icon">{type === "service" ? "🤝" : "📈"}</span><strong>{type === "service" ? "服务类 Agent" : "经营类 Agent"}</strong><small>{type === "service" ? "售前 / 售后 / 物流咨询" : "数据监测与内部分析"}</small></button>)}</div><div className="form-grid"><label className="field-group"><span>所属店铺</span><input className="field" value={currentStore?.name ?? ""} disabled /></label><label className="field-group"><span>Agent 编码</span><input className="field" name="code" aria-label="Agent 编码" required pattern="[a-z0-9](?:[a-z0-9_]|-){1,99}" maxLength={100} placeholder="例如：service_us_02" /></label><label className="field-group wide"><span>Agent 名称</span><input className="field" name="name" aria-label="Agent 名称" required maxLength={200} placeholder="例如：售前咨询 Agent" /></label></div></div><div className="modal-foot"><button type="button" className="btn" onClick={() => setModalOpen(false)}>取消</button><button type="submit" className="btn primary">创建 Agent</button></div></form></div> : null}
  </div></div></AppShell>;
}
