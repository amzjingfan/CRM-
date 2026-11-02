"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { getAutomationPolicy, getConversationAutomation, setAutomationPolicy, setConversationAutomation, type AutomationPolicy, type ConversationAutomation } from "../lib/api";

export function StoreAutomationControls({ storeId, canEnable }: { storeId: string; canEnable: boolean }) {
  const [policy, setPolicy] = useState<AutomationPolicy | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const current = useRef(storeId);
  useLayoutEffect(() => { current.current = storeId; }, [storeId]);
  useEffect(() => {
    let active = true;
    setPolicy(null); setError(""); setBusy(false);
    if (storeId) void getAutomationPolicy(storeId).then((value) => { if (active) setPolicy(value); }).catch((caught: unknown) => { if (active) setError(caught instanceof Error ? caught.message : "读取自动化状态失败"); });
    return () => { active = false; };
  }, [storeId]);
  async function change(mode: AutomationPolicy["mode"]) {
    if (!policy || busy) return;
    const target = storeId;
    setBusy(true); setError("");
    try {
      const value = await setAutomationPolicy(target, { mode, expected_revision: policy.revision });
      if (current.current === target) setPolicy(value);
    } catch (caught) { if (current.current === target) setError(caught instanceof Error ? caught.message : "更新自动化状态失败"); }
    finally { if (current.current === target) setBusy(false); }
  }
  return <section className="auto-preview-policy" aria-label="Agent 自动投递策略"><div><h3>Agent 自动投递</h3><p>仅处理策略生效后的新买家消息；通过独立复核、当前授权和平台窗口检查后投递。</p><small>{policy?.global_enabled ? "部署自动投递已开启" : "部署自动投递关闭，可使用预演"}</small></div><label>店铺模式 <select className="field" aria-label="店铺自动投递模式" disabled={!policy || busy} value={policy?.mode ?? "off"} onChange={(event) => void change(event.target.value as AutomationPolicy["mode"])}><option value="off">关闭</option><option value="preview" disabled={!canEnable}>预演 · 仅供坐席复核</option><option value="auto" disabled={!policy?.global_enabled || !canEnable}>自动投递</option></select></label>{error ? <p role="alert">{error}</p> : null}</section>;
}

export function ConversationAutomationControls({ conversationId, en }: { conversationId: string; en: boolean }) {
  const [state, setState] = useState<ConversationAutomation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const current = useRef(conversationId);
  useLayoutEffect(() => { current.current = conversationId; }, [conversationId]);
  useEffect(() => {
    let active = true;
    setState(null); setError(""); setBusy(false);
    void getConversationAutomation(conversationId).then((value) => { if (active) setState(value); }).catch((caught: unknown) => { if (active) setError(caught instanceof Error ? caught.message : "读取会话自动化失败"); });
    return () => { active = false; };
  }, [conversationId]);
  async function toggle() {
    if (!state || busy) return;
    const target = conversationId;
    setBusy(true); setError("");
    try {
      const value = await setConversationAutomation(target, { paused: !state.paused, expected_revision: state.revision });
      if (current.current === target) setState(value);
    } catch (caught) { if (current.current === target) setError(caught instanceof Error ? caught.message : "更新会话自动化失败"); }
    finally { if (current.current === target) setBusy(false); }
  }
  return <div aria-label={en ? "Conversation automation" : "会话自动化"}><button className="text-button" type="button" disabled={!state || busy} onClick={() => void toggle()}>{state?.paused ? (en ? "Resume automation" : "恢复会话自动化") : (en ? "Pause automation" : "暂停会话自动化")}</button>{state?.paused ? <small>{en ? "Automation paused for this conversation" : "此会话自动投递已暂停"}</small> : null}{error ? <p role="alert">{error}</p> : null}</div>;
}
