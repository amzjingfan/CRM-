"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { detachAgentTemplate, getAgentTemplateSource, type AgentTemplateSource } from "../../../lib/agent-templates";
import { TemplateModal } from "./TemplateModal";
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
  return <><details className="agent-more"><summary className="btn small">更多</summary><div className="agent-more-menu">
    {error ? <p role="alert">{error}</p> : null}
    {!source ? error ? null : <p role="status">正在读取关联…</p> : source.draft ? <>
      <p>{source.draft.name} · v{source.draft.target_template_version}{source.draft.archived ? " · 已归档" : ""}</p>
      {!source.draft.archived && !disabled ? <Link className="btn small" href={`/agents/templates/${encodeURIComponent(source.draft.template_id)}/apply?version=${source.draft.target_template_version}&store_id=${encodeURIComponent(source.store_id)}&agent_id=${encodeURIComponent(agentId)}`}>本店差异更新 / 恢复跟随</Link> : null}
      <button className="btn small" disabled={disabled || busy} onClick={() => setOpen(true)}>解除模板关联</button>
      {disabled ? <p>请先保存当前编辑，再更新或解除关联。</p> : null}
    </> : <p>当前草稿为独立 Agent，未关联模板。</p>}
  </div></details>{open ? <TemplateModal title="解除模板关联" onClose={() => { if (!busy) setOpen(false); }}><div className="modal-body">解除后保留配置正文、状态、知识文件、历史及当前运行版本；以后不再跟随模板。</div><div className="modal-foot"><button className="btn" disabled={busy} onClick={() => setOpen(false)}>取消</button><button className="btn primary" disabled={busy} onClick={() => void detach()}>确认解除</button></div></TemplateModal> : null}</>;
}
