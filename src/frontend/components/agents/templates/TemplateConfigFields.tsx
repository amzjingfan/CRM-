"use client";

import { AgentPromptFields } from "../../AgentPromptFields";
import { AgentToolCatalogFields } from "../../AgentToolCatalog";
import type { TemplateCatalog, TemplateConfig } from "../../../lib/agent-templates";
import { KnowledgeSlotFields } from "./KnowledgeSlotFields";
import type { ReactNode } from "react";

export function TemplateConfigFields({ value, catalog, disabled, onChange, children }: { value: TemplateConfig; catalog: TemplateCatalog; disabled: boolean; onChange: (value: TemplateConfig) => void; children?: ReactNode }) {
  const update = (patch: Partial<TemplateConfig>) => onChange({ ...value, ...patch });
  return <>
    <section className="template-section"><div className="section-head"><h3>基础信息</h3><p>明确模板名称和 Agent 的路由职责。</p></div>{children}<div className="form-grid">
      <label className="field-group"><span>默认 Agent 名称</span><input className="field" aria-label="默认 Agent 名称" disabled={disabled} value={value.default_agent_name} required maxLength={200} onChange={(event) => update({ default_agent_name: event.target.value })} /><small className="help">名称和编码仅在新建店铺 Agent 时使用</small></label>
      <label className="field-group"><span>Agent 类型</span><select className="field" disabled={disabled} value={value.agent_type} onChange={(event) => update({ agent_type: event.target.value as TemplateConfig["agent_type"] })}><option value="service">服务类</option><option value="operations">经营类</option><option value="logistics_event">物流事件通知</option><option value="fallback">无解兜底</option></select></label>
      <label className="field-group wide"><span>Agent 职责描述</span><textarea aria-label="Agent 职责描述" className="field fieldarea" disabled={disabled} value={value.description ?? ""} maxLength={1000} onChange={(event) => update({ description: event.target.value || null })} /></label>
    </div><details className="template-details" onInvalidCapture={(event) => { event.currentTarget.open = true; }}><summary>新建 Agent 编码</summary><label className="field-group"><span>建议 Agent 编码</span><input className="field" disabled={disabled} value={value.suggested_code} required pattern="[a-z0-9](?:[a-z0-9_]|-){1,99}" maxLength={100} onChange={(event) => update({ suggested_code: event.target.value })} /><small className="help">只在新建店铺 Agent 时使用，已有 Agent 保留原编码。</small></label></details></section>
    <section className="template-section"><div className="section-head"><h3>模型与提示词</h3><p>发布后冻结模型与七段提示词。</p></div><AgentPromptFields value={value} modelOptions={catalog.model_options} sections={catalog.prompt_sections} disabled={disabled} onChange={update} /></section>
    <section className="template-section"><div className="section-head"><h3>工具与知识</h3><p>选择通用能力；知识文件在应用时按店铺绑定。</p></div>
    <AgentToolCatalogFields catalog={catalog} enabled={value.tool_names} onChange={(tool_names) => update({ tool_names })} disabled={disabled} global />
    <KnowledgeSlotFields value={value.knowledge_slots} disabled={disabled} onChange={(knowledge_slots) => update({ knowledge_slots })} /></section>
  </>;
}
