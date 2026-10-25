"use client";

import Link from "next/link";
import {
  ArrowUpRight,
  ChartLineUp,
  CheckCircle,
  Eye,
  Pause,
  PencilSimple,
  Play,
  Plus,
  ShoppingCart,
  Star,
  Trash,
  X,
} from "@phosphor-icons/react";
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import {
  createCampaign,
  createIdempotencyKey,
  currentUser,
  deleteCampaign,
  getDashboardMetrics,
  isAuthenticationError,
  listCampaigns,
  listMarketingEvents,
  reviewMarketingDraft,
  setCampaignEnabled,
  updateCampaign,
  type Campaign,
  type DashboardMetrics,
  type MarketingEvent,
} from "../../lib/api";
import { useLanguage } from "../../lib/i18n";

function triggerLabel(trigger: string, en: boolean) {
  const labels: Record<string, [string, string]> = { cart_abandoned: ["弃单触发", "Abandoned cart"], bad_review: ["中差评出现", "Bad review"] };
  return labels[trigger]?.[en ? 1 : 0] ?? trigger;
}

function actionLabel(action: string, en: boolean) {
  const labels: Record<string, [string, string]> = { send_message: ["发送消息", "Send message"], send_coupon: ["发送优惠券", "Send coupon"], send_coupon_and_message: ["发券并发送消息", "Coupon and message"] };
  return labels[action]?.[en ? 1 : 0] ?? action;
}

function eventStatusLabel(status: string, en: boolean) {
  const labels: Record<string, [string, string]> = {
    pending: ["待执行", "Pending"], waiting_ai: ["等待 AI", "Waiting for AI"], processing: ["执行中", "Processing"],
    waiting_review: ["待人工审核", "Waiting for review"], approved: ["已批准", "Approved"], rejected: ["已拒绝", "Rejected"],
    succeeded: ["已完成", "Succeeded"], completed: ["已完成", "Completed"], failed: ["失败", "Failed"], converted: ["已转化", "Converted"],
  };
  return labels[status]?.[en ? 1 : 0] ?? status;
}

export default function MarketingPage() {
  const en = useLanguage() === "en";
  const [storeId, setStoreId] = useState("");
  const [stores, setStores] = useState<string[]>([]);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [events, setEvents] = useState<MarketingEvent[]>([]);
  const [eventTotal, setEventTotal] = useState(0);
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [editing, setEditing] = useState<Campaign | null>(null);
  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const [editorOpen, setEditorOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [reviewingEventId, setReviewingEventId] = useState("");
  const loadRequestId = useRef(0);

  const load = useCallback(async () => {
    if (!storeId) return;
    const requestId = ++loadRequestId.current;
    setLoading(true);
    setError("");
    try {
      const [campaignPage, eventPage, dashboardMetrics] = await Promise.all([
        listCampaigns(storeId, page),
        listMarketingEvents(storeId, 1),
        getDashboardMetrics(storeId, "30d"),
      ]);
      if (requestId !== loadRequestId.current) return;
      setCampaigns(campaignPage.items);
      setTotal(campaignPage.total);
      setEvents(eventPage.items);
      setEventTotal(eventPage.total);
      setMetrics(dashboardMetrics);
      setSelectedCampaignId((current) => current && campaignPage.items.some((campaign) => campaign.id === current) ? current : campaignPage.items[0]?.id ?? "");
    } catch (caught) {
      if (requestId === loadRequestId.current) setError(caught instanceof Error ? caught.message : (en ? "Marketing loading failed" : "营销数据加载失败"));
    } finally {
      if (requestId === loadRequestId.current) setLoading(false);
    }
  }, [en, page, storeId]);
  useEffect(() => () => { loadRequestId.current += 1; }, []);

  useEffect(() => {
    void currentUser().then((user) => {
      setStores(user.store_ids);
      setPermissions(user.permissions);
      const params = new URLSearchParams(window.location.search);
      const requestedStoreId = params.get("store_id");
      const nextStoreId = requestedStoreId && user.store_ids.includes(requestedStoreId) ? requestedStoreId : user.store_ids[0] ?? "";
      setStoreId(nextStoreId);
      if (!nextStoreId) setLoading(false);
      setPage(Number(params.get("page") || 1));
    }).catch((caught: unknown) => {
      if (!isAuthenticationError(caught)) {
        setError(caught instanceof Error ? caught.message : (en ? "User loading failed" : "用户信息加载失败"));
        setLoading(false);
      }
    });
  }, [en]);

  useEffect(() => {
    if (!storeId) return;
    const params = new URLSearchParams({ store_id: storeId, page: String(page) });
    window.history.replaceState(null, "", `/marketing?${params}`);
    void load();
  }, [load, page, storeId]);

  async function saveCampaign(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    const submittedForm = event.currentTarget;
    const form = new FormData(submittedForm);
    const action = String(form.get("action_type"));
    const mode = String(form.get("content_mode"));
    const payload = {
      store_id: storeId,
      name: String(form.get("name")),
      trigger_type: String(form.get("trigger_type")),
      action_type: action,
      content_mode: mode,
      template_content: mode === "template" && action.includes("message") ? String(form.get("template_content")) : null,
      coupon_code: action.includes("coupon") ? String(form.get("coupon_code")) : null,
      trigger_delay_minutes: Number(form.get("trigger_delay_minutes")),
      cooldown_hours: 24,
      max_contacts_30d: 3,
    };
    setSaving(true);
    try {
      if (editing) await updateCampaign(editing.id, payload); else await createCampaign(payload);
      submittedForm.reset();
      setEditing(null);
      setEditorOpen(false);
      setNotice(en ? "Campaign saved" : "营销流程已保存");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Save failed" : "保存失败"));
    } finally {
      setSaving(false);
    }
  }

  async function toggleCampaign(campaign: Campaign) {
    try {
      await setCampaignEnabled(campaign.id, campaign.status !== "active");
      setNotice(campaign.status === "active" ? (en ? "Campaign paused" : "流程已暂停") : (en ? "Campaign enabled" : "流程已启用"));
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Status update failed" : "状态切换失败"));
    }
  }

  async function removeCampaign(campaign: Campaign) {
    if (!window.confirm(en ? "Delete this campaign?" : "删除这个营销流程？")) return;
    try {
      await deleteCampaign(campaign.id);
      setNotice(en ? "Campaign deleted" : "营销流程已删除");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Delete failed" : "删除失败"));
    }
  }

  async function reviewDraft(item: MarketingEvent, decision: "approve" | "reject") {
    const warning = en
      ? "This only records the review decision. It will not send a message or issue a coupon. Continue?"
      : "仅记录审核结论，不会发送消息或发放优惠券。是否继续？";
    if (!window.confirm(warning)) return;
    setReviewingEventId(item.id);
    try {
      await reviewMarketingDraft(item.id, decision, createIdempotencyKey());
      setNotice(decision === "approve" ? (en ? "Draft approved; nothing was sent" : "草稿已批准，未执行任何发送") : (en ? "Draft rejected" : "草稿已拒绝"));
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : (en ? "Draft review failed" : "草稿审核失败"));
    } finally {
      setReviewingEventId("");
    }
  }

  const selectedCampaign = campaigns.find((campaign) => campaign.id === selectedCampaignId) ?? null;
  const selectedEvents = selectedCampaign ? events.filter((event) => event.campaign_id === selectedCampaign.id) : events;
  const convertedCount = events.filter((event) => event.converted_at).length;
  const conversionRate = events.length ? convertedCount / events.length * 100 : 0;
  const activeCount = campaigns.filter((campaign) => campaign.status === "active").length;
  const eventCounts = useMemo(() => {
    const counts = new Map<string, { total: number; converted: number }>();
    for (const event of events) {
      const current = counts.get(event.campaign_id) ?? { total: 0, converted: 0 };
      current.total += 1;
      if (event.converted_at) current.converted += 1;
      counts.set(event.campaign_id, current);
    }
    return counts;
  }, [events]);

  return <AppShell><main className="management-page prototype-page">
    <section className="prototype-page-header"><div className="prototype-title"><span className="prototype-title-icon marketing"><ChartLineUp size={25} weight="duotone" /></span><div><h2>{en ? "Smart marketing" : "智能营销"}<span>{en ? "Proactive outreach · Automated workflows" : "主动触达 · 自动化流程"}</span></h2></div></div><div className="prototype-actions"><select aria-label={en ? "Store" : "店铺"} className="compact-field header-select" disabled={saving || Boolean(reviewingEventId)} onChange={(event) => { loadRequestId.current += 1; setEditorOpen(false); setEditing(null); setCampaigns([]); setEvents([]); setMetrics(null); setSelectedCampaignId(""); setLoading(true); setPage(1); setStoreId(event.target.value); }} value={storeId}>{stores.map((id) => <option key={id} value={id}>{id.slice(0, 8)}</option>)}</select><button className="primary-button" disabled={!storeId} onClick={() => { setEditing(null); setEditorOpen(true); }} type="button"><Plus size={18} weight="bold" />{en ? "New workflow" : "新建流程"}</button></div></section>

    {notice ? <section aria-live="polite" className="inline-status" role="status"><span>{notice}</span></section> : null}
    {loading ? <LoadingState label={en ? "Loading marketing workflows…" : "正在加载营销流程…"} /> : error ? <ErrorState message={error} retry={() => void load()} /> : !storeId ? <div className="state-box" role="status"><p>{en ? "Create a store to manage marketing workflows." : "请先创建店铺，再管理营销流程。"}</p><Link className="secondary-button mt-3" href="/settings/stores">{en ? "Create store" : "创建店铺"}</Link></div> : <>
      <section className="campaign-grid" aria-label={en ? "Marketing workflows" : "营销流程"}>{campaigns.length ? campaigns.map((campaign) => {
        const campaignEvents = eventCounts.get(campaign.id) ?? { total: 0, converted: 0 };
        const Icon = campaign.trigger_type === "bad_review" ? Star : ShoppingCart;
        return <article className={selectedCampaignId === campaign.id ? "campaign-card selected" : "campaign-card"} key={campaign.id}><header><div className="campaign-name"><span className={campaign.trigger_type === "bad_review" ? "campaign-icon review" : "campaign-icon cart"}><Icon size={20} weight="fill" /></span><strong>{campaign.name}</strong></div><span className={`status-badge ${campaign.status}`}><i />{campaign.status === "active" ? (en ? "Running" : "运行中") : (en ? "Paused" : "已暂停")}</span></header><p>{en ? "Trigger" : "触发"}: {triggerLabel(campaign.trigger_type, en)} · {en ? "Action" : "动作"}: {campaign.trigger_delay_minutes}min {actionLabel(campaign.action_type, en)}</p><div className="campaign-result"><span>{en ? "Recent" : "近期"}: <b>{campaignEvents.total}</b> {en ? "touches" : "次触达"}</span><span>{en ? "Converted" : "转化"}: <b>{campaignEvents.converted}</b></span></div><footer><button onClick={() => { setEditing(campaign); setEditorOpen(true); }} type="button"><PencilSimple size={15} />{en ? "Edit" : "编辑"}</button><button onClick={() => void toggleCampaign(campaign)} type="button">{campaign.status === "active" ? <Pause size={15} /> : <Play size={15} />}{campaign.status === "active" ? (en ? "Pause" : "暂停") : (en ? "Enable" : "启用")}</button><button onClick={() => setSelectedCampaignId(campaign.id)} type="button"><Eye size={15} />{en ? "View" : "查看"}</button><button className="danger-link" onClick={() => void removeCampaign(campaign)} aria-label={`${en ? "Delete" : "删除"} ${campaign.name}`} type="button"><Trash size={15} /></button></footer></article>;
      }) : <article className="prototype-card campaign-empty"><EmptyState label={en ? "No marketing workflows" : "暂无智能营销流程，可新建弃单或中差评流程"} /></article>}</section>

      <section className="prototype-card marketing-report"><header className="content-panel-heading"><div><p className="eyebrow">{en ? "30-DAY PERFORMANCE" : "近 30 天"}</p><h3>{en ? "Outreach performance" : "触达效果报表"}</h3></div><span className="status-badge"><CheckCircle size={14} />{en ? "Live data" : "实时数据"}</span></header><dl><div><dt>{en ? "Outreach" : "触达量"}</dt><dd>{eventTotal.toLocaleString()}</dd><small>{en ? "Recorded events" : "已记录触达事件"}</small></div><div><dt>{en ? "Conversion rate" : "转化率"}</dt><dd>{conversionRate.toFixed(1)}% <span><ArrowUpRight size={15} />{convertedCount}</span></dd><small>{en ? "Current event sample" : "当前事件样本"}</small></div><div><dt>{en ? "Recovered GMV" : "挽回 GMV"}</dt><dd>{metrics?.currency ?? "—"} {Number(metrics?.recovered_gmv ?? 0).toLocaleString()}</dd><small>{en ? "Converted marketing events" : "已转化营销事件"}</small></div><div><dt>{en ? "Active workflows" : "运行中流程"}</dt><dd>{activeCount}<span> / {total}</span></dd><small>{en ? "Enabled automation" : "已启用自动化"}</small></div></dl></section>

      <section className="prototype-card marketing-events"><header className="content-panel-heading"><div><p className="eyebrow">{en ? "EXECUTION LOG" : "执行记录"}</p><h3>{selectedCampaign?.name ?? (en ? "Recent events" : "最近事件")}</h3></div><button className="secondary-button" onClick={() => void load()} type="button">{en ? "Refresh" : "刷新"}</button></header>{selectedEvents.length ? <div className="event-table" role="table"><div className="event-table-head" role="row"><span>{en ? "Source" : "来源"}</span><span>{en ? "Status" : "状态"}</span><span>{en ? "Attempts" : "尝试"}</span><span>{en ? "Triggered" : "触发时间"}</span><span>{en ? "Result / AI draft" : "结果 / AI 草稿"}</span></div>{selectedEvents.map((item) => <div className="event-table-row" role="row" key={item.id}><span><strong>{item.source_type}</strong><small>{item.source_id.slice(0, 12)}</small></span><span><b className={`status-badge ${item.status}`}>{eventStatusLabel(item.status, en)}</b></span><span>{item.attempt_count}/3</span><span>{new Date(item.triggered_at).toLocaleString(en ? "en-US" : "zh-CN")}</span><span>{item.converted_at ? <b className="converted"><CheckCircle size={15} />{en ? "Converted" : "已转化"}</b> : item.ai_draft_content ? <span className="ai-draft-review"><span>{item.ai_draft_content}</span>{item.ai_review_status === "pending" && permissions.includes("marketing.manage") ? <span className="ai-draft-actions"><button disabled={reviewingEventId === item.id} onClick={() => void reviewDraft(item, "approve")} type="button"><CheckCircle size={14} />{en ? "Approve" : "批准"}</button><button className="danger-link" disabled={reviewingEventId === item.id} onClick={() => void reviewDraft(item, "reject")} type="button"><X size={14} />{en ? "Reject" : "拒绝"}</button></span> : <small>{item.ai_review_status ? eventStatusLabel(item.ai_review_status, en) : "—"}</small>}</span> : item.error_code ?? "—"}</span></div>)}</div> : <EmptyState label={en ? "No events for this workflow" : "该流程暂无触发事件"} />}</section>
      <div className="pagination-row"><small>{total} {en ? "workflows" : "个流程"}</small><div><button className="secondary-button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} type="button">{en ? "Previous" : "上一页"}</button><button className="secondary-button" disabled={page * 20 >= total} onClick={() => setPage((value) => value + 1)} type="button">{en ? "Next" : "下一页"}</button></div></div>
    </>}

    {editorOpen ? <div className="editor-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) { setEditorOpen(false); setEditing(null); } }}><section aria-modal="true" className="editor-modal" role="dialog" aria-label={editing ? (en ? "Edit workflow" : "编辑流程") : (en ? "New workflow" : "新建流程")}><header><h3>{editing ? (en ? "Edit workflow" : "编辑流程") : (en ? "New workflow" : "新建流程")}</h3><button aria-label={en ? "Close" : "关闭"} onClick={() => { setEditorOpen(false); setEditing(null); }} type="button"><X size={20} /></button></header><form className="stack-form" key={editing?.id ?? "new-campaign"} onSubmit={saveCampaign}><label>{en ? "Name" : "流程名称"}<input className="field" defaultValue={editing?.name} name="name" required /></label><div className="form-row"><label>{en ? "Trigger" : "触发器"}<select className="field" defaultValue={editing?.trigger_type ?? "cart_abandoned"} name="trigger_type"><option value="cart_abandoned">{en ? "Abandoned cart" : "弃单挽回"}</option><option value="bad_review">{en ? "Bad review" : "中差评跟进"}</option></select></label><label>{en ? "Trigger delay" : "触发延迟（分钟）"}<input className="field" defaultValue={editing?.trigger_delay_minutes ?? 30} min="5" name="trigger_delay_minutes" type="number" /></label></div><div className="form-row"><label>{en ? "Action" : "执行动作"}<select className="field" defaultValue={editing?.action_type ?? "send_message"} name="action_type"><option value="send_message">{en ? "Send message" : "发送消息"}</option><option value="send_coupon">{en ? "Send coupon" : "发优惠券"}</option><option value="send_coupon_and_message">{en ? "Coupon and message" : "发券并发送消息"}</option></select></label><label>{en ? "Content mode" : "内容模式"}<select className="field" defaultValue={editing?.content_mode ?? "template"} name="content_mode"><option value="template">{en ? "Template" : "固定模板"}</option><option value="ai">{en ? "AI (waiting)" : "AI（等待接入）"}</option></select></label></div><label>{en ? "Message template" : "消息模板"}<textarea className="field min-h-28" defaultValue={editing?.template_content ?? ""} name="template_content" /></label><label>{en ? "Coupon code" : "优惠券编码"}<input className="field" defaultValue={editing?.coupon_code ?? ""} name="coupon_code" /></label><button className="primary-button" disabled={!storeId || saving} type="submit">{saving ? (en ? "Saving…" : "正在保存…") : editing ? (en ? "Save changes" : "保存修改") : (en ? "Create workflow" : "创建流程")}</button></form></section></div> : null}
  </main></AppShell>;
}
