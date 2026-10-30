"use client";

import { useState, type FormEvent } from "react";
import { type AgentConfig } from "../../../lib/api";
import { createAgentTemplateFromAgent, type KnowledgeSlot } from "../../../lib/agent-templates";
import { KnowledgeSlotFields } from "./KnowledgeSlotFields";
import { TemplateModal } from "./TemplateModal";
import "./templates.css";

export function SaveAgentTemplate({ agent, onClose, onSaved }: { agent: AgentConfig; onClose: () => void; onSaved: () => void }) {
  const [source, setSource] = useState("");
  const [slots, setSlots] = useState<KnowledgeSlot[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy || !source) return;
    const data = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      await createAgentTemplateFromAgent({ name: String(data.get("name")).trim(), code: String(data.get("code")).trim(), description: null,
        source_agent_id: agent.id, source_version: source === "published" ? agent.published_version : null,
        source_draft_revision: source === "draft" ? agent.draft_revision : null, knowledge_slots: slots });
      onSaved();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "创建模板草稿失败"); }
    finally { setBusy(false); }
  }
  return <TemplateModal title="保存为模板" onClose={() => { if (!busy) onClose(); }}><form onSubmit={(event) => void submit(event)}><div className="modal-body">
    <p className="inline-note">提取已保存的精确版本；当前页面未保存编辑不在其中。仅创建模板草稿，不发布、不修改店铺。知识文件和回复参数不会复制，应用时须逐店映射本店文件。</p>
    <label className="field-group"><span>提取来源</span><select className="field" required disabled={busy} value={source} onChange={(event) => setSource(event.target.value)}><option value="">请选择精确来源</option>{agent.published_version !== null ? <option value="published">已发布版本 v{agent.published_version}</option> : null}<option value="draft">已保存草稿 r{agent.draft_revision}</option></select></label>
    <label className="field-group"><span>模板名称</span><input className="field" name="name" aria-label="模板名称" required maxLength={200} disabled={busy} /></label>
    <label className="field-group"><span>模板编码</span><input className="field" name="code" aria-label="模板编码" required maxLength={100} pattern="[a-z0-9][a-z0-9_-]{1,99}" disabled={busy} /></label>
    <KnowledgeSlotFields value={slots} onChange={setSlots} disabled={busy} />
    {error ? <p role="alert">{error}</p> : null}
  </div><div className="modal-foot"><button type="button" className="btn" disabled={busy} onClick={onClose}>取消</button><button type="submit" className="btn primary" disabled={busy || !source}>{busy ? "正在创建…" : "创建模板草稿"}</button></div></form></TemplateModal>;
}
