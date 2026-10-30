"use client";

import { AgentPromptFields } from "../../AgentPromptFields";
import { AgentToolCatalogFields } from "../../AgentToolCatalog";
import type { TemplateCatalog, TemplateConfig } from "../../../lib/agent-templates";
import { KnowledgeSlotFields } from "./KnowledgeSlotFields";

export function TemplateConfigFields({ value, catalog, disabled, onChange }: { value: TemplateConfig; catalog: TemplateCatalog; disabled: boolean; onChange: (value: TemplateConfig) => void }) {
  const update = (patch: Partial<TemplateConfig>) => onChange({ ...value, ...patch });
  return <>
    <div className="form-grid">
      <label className="field-group"><span>默认 Agent 名称</span><input className="field" aria-label="默认 Agent 名称" disabled={disabled} value={value.default_agent_name} required maxLength={200} onChange={(event) => update({ default_agent_name: event.target.value })} /><small className="help">名称和编码仅在新建店铺 Agent 时使用</small></label>
      <label className="field-group"><span>建议 Agent 编码</span><input className="field" disabled={disabled} value={value.suggested_code} required pattern="[a-z0-9][a-z0-9_-]{1,99}" maxLength={100} onChange={(event) => update({ suggested_code: event.target.value })} /></label>
      <label className="field-group"><span>Agent 类型</span><select className="field" disabled={disabled} value={value.agent_type} onChange={(event) => update({ agent_type: event.target.value as TemplateConfig["agent_type"] })}><option value="service">服务类</option><option value="operations">经营类</option></select></label>
      <label className="field-group wide"><span>Agent 职责描述</span><textarea className="field fieldarea" disabled={disabled} value={value.description ?? ""} maxLength={1000} onChange={(event) => update({ description: event.target.value || null })} /></label>
    </div>
    <AgentPromptFields value={value} modelOptions={catalog.model_options} sections={catalog.prompt_sections} disabled={disabled} onChange={update} />
    <AgentToolCatalogFields catalog={catalog} enabled={value.tool_names} onChange={(tool_names) => update({ tool_names })} disabled={disabled} global />
    <KnowledgeSlotFields value={value.knowledge_slots} disabled={disabled} onChange={(knowledge_slots) => update({ knowledge_slots })} />
  </>;
}
