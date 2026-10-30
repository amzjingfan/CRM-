"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { detachAgentTemplate, getAgentTemplateSource, type AgentTemplateSource } from "../../../lib/agent-templates";
import { TemplateModal } from "./TemplateModal";
import { fieldLabel } from "./TemplateValue";

function PublishedSource({ published }: { published: NonNullable<AgentTemplateSource["published"]> }) {
  const source = published.template_source_json;
  if (!source) return <p>当前运行：Agent 发布 v{published.version} · 无模板来源</p>;
  const fields = source.fields && typeof source.fields === "object" && !Array.isArray(source.fields) ? Object.entries(source.fields) : [];
  return <><p>当前运行：Agent 发布 v{published.version} · 模板 {typeof source.template_id === "string" ? source.template_id : "未知"}</p>{fields.length ? <details><summary>运行版本的逐字段模板来源</summary>{fields.map(([key, value]) => { const field = value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {}; return <p key={key}>{fieldLabel(key)} · 应用模板版本 {typeof field.applied_template_version === "number" ? `v${field.applied_template_version}` : "—"} · 最后审阅 {typeof field.last_reviewed_template_version === "number" ? `v${field.last_reviewed_template_version}` : "—"}{field.local_override === true ? " · 本店覆盖" : ""}</p>; })}</details> : null}</>;
}

export function AgentSource({ agentId, disabled, onDetached }: { agentId: string; disabled: boolean; onDetached: () => Promise<unknown> }) {
  const [source, setSource] = useState<AgentTemplateSource | null>(null);
  const [error, setError] = useState(""); const [open, setOpen] = useState(false); const [busy, setBusy] = useState(false);
  useEffect(() => { let active = true; setSource(null); setError(""); void getAgentTemplateSource(agentId).then((value) => { if (active) setSource(value); }).catch((e: unknown) => { if (active) setError(e instanceof Error ? e.message : "来源读取失败"); }); return () => { active = false; }; }, [agentId]);
  async function detach() {
    if (!source?.draft || busy || disabled) return; setBusy(true); setError("");
    try {
      await detachAgentTemplate(agentId, source.draft.draft_revision); setSource({ ...source, draft: null }); setOpen(false);
      try { await onDetached(); setSource(await getAgentTemplateSource(agentId)); }
      catch { setError("解除关联已成功，但刷新失败；请重新加载以查看最新状态。"); }
    }
    catch (e) { setError(e instanceof Error ? e.message : "解除关联失败"); }
    finally { setBusy(false); }
  }
  return <section className="slot-row"><h3>模板来源</h3>{error ? <p role="alert">{error}</p> : null}{!source ? error ? null : <p>正在读取来源…</p> : <>
    {source.draft ? <><p>草稿来源：{source.draft.name} · 目标 v{source.draft.target_template_version}{source.draft.archived ? " · 已归档" : ""}</p><p>一致 {source.draft.aligned_count} · 本店覆盖 {source.draft.local_override_count} · 待处理 {source.draft.pending_review_count}</p><details><summary>逐字段来源</summary>{source.draft.fields.map((field) => <p key={field.field}>{fieldLabel(field.field)} · {field.local_override ? "本店覆盖" : "无本店覆盖"} · {field.pending_review ? "待处理" : "已审阅"} · 最后审阅 v{field.last_reviewed_template_version ?? "—"}</p>)}</details>{!source.draft.archived && !disabled ? <Link href={`/agents/templates/${encodeURIComponent(source.draft.template_id)}/apply?version=${source.draft.target_template_version}&store_id=${encodeURIComponent(source.store_id)}&agent_id=${encodeURIComponent(agentId)}`}>本店差异更新 / 恢复跟随</Link> : null}{" "}<button className="btn small" disabled={disabled} onClick={() => setOpen(true)}>解除模板关联</button>{disabled ? <p>请先保存当前编辑，再更新或解除来源。</p> : null}</> : <p>当前草稿为独立 Agent，未关联模板。</p>}
    {source.published ? <PublishedSource published={source.published} /> : <p>当前运行：尚未发布</p>}
  </>}{open ? <TemplateModal title="解除模板关联" onClose={() => { if (!busy) setOpen(false); }}><div className="modal-body">解除后保留配置正文、状态、知识文件、历史及当前运行版本；以后不再跟随模板。</div><div className="modal-foot"><button className="btn" disabled={busy} onClick={() => setOpen(false)}>取消</button><button className="btn primary" disabled={busy} onClick={() => void detach()}>确认解除</button></div></TemplateModal> : null}</section>;
}
