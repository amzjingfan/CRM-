"use client";

import type { KnowledgeSlot } from "../../../lib/agent-templates";

export function KnowledgeSlotFields({ value, onChange, disabled = false }: { value: KnowledgeSlot[]; onChange: (slots: KnowledgeSlot[]) => void; disabled?: boolean }) {
  function update(index: number, patch: Partial<KnowledgeSlot>) { onChange(value.map((slot, i) => i === index ? { ...slot, ...patch } : slot)); }
  return <section className="knowledge-slots"><div className="section-head"><h3>知识需求</h3><p>只定义用途；应用时逐店映射本店文件。实际文件、审批和回复参数不会复制。</p></div>
    {value.length === 0 ? <p className="help">尚未定义知识需求</p> : null}
    {value.map((slot, index) => <fieldset className="slot-row" key={index} disabled={disabled}><legend>知识需求 {index + 1}</legend><div className="form-grid">
      <label className="field-group"><span>稳定需求键</span><input className="field" aria-label={`需求键 ${index + 1}`} required pattern="[a-z0-9](?:[a-z0-9_]|-)*" maxLength={100} value={slot.key} onChange={(event) => update(index, { key: event.target.value })} /></label>
      <label className="field-group"><span>需求名称</span><input className="field" aria-label={`需求名称 ${index + 1}`} required maxLength={200} value={slot.name} onChange={(event) => update(index, { name: event.target.value })} /></label>
      <label className="field-group wide"><span>用途说明</span><textarea className="field fieldarea" aria-label={`需求用途 ${index + 1}`} required maxLength={1000} value={slot.purpose} onChange={(event) => update(index, { purpose: event.target.value })} /></label>
      <label><input type="checkbox" checked={slot.required} onChange={(event) => update(index, { required: event.target.checked })} /> 应用时必须映射本店文件</label>
      {!disabled ? <button type="button" className="btn small" onClick={() => onChange(value.filter((_, i) => i !== index))}>移除需求 {index + 1}</button> : null}
    </div></fieldset>)}
    {!disabled ? <button type="button" className="btn" disabled={value.length >= 100} onClick={() => onChange([...value, { key: "", name: "", purpose: "", required: false }])}>添加知识需求</button> : null}
  </section>;
}
