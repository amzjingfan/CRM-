"use client";

import { AgentToolCatalogFields } from "../../AgentToolCatalog";
import { KnowledgeSlotFields } from "./KnowledgeSlotFields";
import { fieldLabel, TemplateValue } from "./TemplateValue";
import type { FieldDecision, FieldDiff, FieldValue, KnowledgeSlot, TemplateCatalog } from "../../../lib/agent-templates";

const statuses: Record<FieldDiff["status"], string> = { unchanged: "无变化", template_changed: "模板已变", local_changed: "本店已变", converged: "双方一致", conflict: "冲突" };
function initial(field: string, value: FieldValue): FieldValue {
  if (field === "model") return value && !Array.isArray(value) && typeof value === "object" ? value : { provider: null, name: null };
  if (field === "tool_names" || field === "knowledge_slots") return Array.isArray(value) ? value : [];
  if (field === "description") return typeof value === "string" ? value : null;
  if (field === "agent_type") return value === "operations" ? value : "service";
  return typeof value === "string" ? value : "";
}

export function FieldReview({ diff, decision, skipped, catalog, onChange }: { diff: FieldDiff; decision?: FieldDecision; skipped?: boolean; catalog: TemplateCatalog; onChange: (value?: FieldDecision) => void }) {
  const choice = decision?.choice ?? (diff.status === "conflict" && !skipped ? "unresolved" : "skip");
  const value = decision?.choice === "manual" ? decision.value : initial(diff.field, diff.local);
  const manual = (next: FieldValue) => onChange({ choice: "manual", value: next });
  return <fieldset className="slot-row"><legend>{fieldLabel(diff.field)} · {statuses[diff.status]}</legend>
    <div>基线 A：<TemplateValue value={diff.baseline} /></div><div>本店 B：<TemplateValue value={diff.local} /></div><div>模板 C：<TemplateValue value={diff.target} /></div>
    <label className="field-group"><span>本次选择</span><select className="field" value={choice} onChange={(event) => {
      const next = event.target.value;
      if (next === "skip") onChange();
      else if (next === "manual") manual(initial(diff.field, diff.local));
      else onChange({ choice: next as "template" | "local" });
    }}><option value="unresolved" disabled>请选择冲突处理方式</option><option value="skip">跳过此次（保持待处理）</option><option value="template">采用模板</option><option value="local">保留本店</option><option value="manual">手工指定</option></select></label>
    {choice === "manual" ? diff.field === "agent_type" ? <select aria-label="手工 Agent 类型" className="field" value={String(value)} onChange={(e) => manual(e.target.value)}><option value="service">服务类</option><option value="operations">经营类</option></select>
      : diff.field === "model" ? <select aria-label="手工模型" className="field" value={JSON.stringify(value)} onChange={(e) => manual(JSON.parse(e.target.value))}><option value={JSON.stringify({ provider: null, name: null })}>未选择</option>{catalog.model_options.map((item) => <option key={JSON.stringify(item)} value={JSON.stringify({ provider: item.provider, name: item.model_name })}>{item.provider} / {item.model_name}</option>)}</select>
      : diff.field === "tool_names" ? <AgentToolCatalogFields catalog={catalog} enabled={Array.isArray(value) ? value as string[] : []} onChange={manual} disabled={false} global />
      : diff.field === "knowledge_slots" ? <KnowledgeSlotFields value={Array.isArray(value) ? value as KnowledgeSlot[] : []} onChange={manual} />
      : <label className="field-group"><span>手工内容{diff.field === "description" ? "（留空清除）" : ""}</span><textarea className="field fieldarea" value={typeof value === "string" ? value : ""} onChange={(e) => manual(diff.field === "description" && !e.target.value ? null : e.target.value)} /></label> : null}
  </fieldset>;
}
