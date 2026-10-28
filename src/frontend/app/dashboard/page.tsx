"use client";

import { ArrowsLeftRight, ChartPieSlice, ChatsCircle, Clock, CurrencyDollar } from "@phosphor-icons/react";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import { currentUser, getDashboardAlerts, getDashboardChannels, getDashboardMetrics, getDashboardTrend, getTopQueries, listStores, type DashboardAlerts, type DashboardChannels, type DashboardMetrics, type DashboardTrend, type StoreView, type TopQuery } from "../../lib/api";
import { useLanguage } from "../../lib/i18n";

type Period = "today" | "7d" | "30d";
type Widget = "trend" | "channels" | "alerts" | "queries";
const pendingWidgets: Record<Widget, boolean> = { trend: true, channels: true, alerts: true, queries: true };

export default function DashboardPage() {
  const en = useLanguage() === "en";
  const [stores, setStores] = useState<Pick<StoreView, "id" | "name">[]>([]); const [storeId, setStoreId] = useState(""); const [period, setPeriod] = useState<Period>("7d");
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null); const [trend, setTrend] = useState<DashboardTrend | null>(null); const [channels, setChannels] = useState<DashboardChannels | null>(null); const [alerts, setAlerts] = useState<DashboardAlerts | null>(null); const [queries, setQueries] = useState<TopQuery[]>([]);
  const [showTable, setShowTable] = useState(false); const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  const [widgetLoading, setWidgetLoading] = useState<Record<Widget, boolean>>(pendingWidgets);
  const [widgetError, setWidgetError] = useState<Partial<Record<Widget, string>>>({});
  const loadRequestId = useRef(0);

  useEffect(() => {
    let active = true;
    const storeNamesRequest = listStores().catch((caught: unknown) => {
      console.warn("店铺名称加载失败", caught);
      return [] as StoreView[];
    });
    void currentUser().then(async (user) => {
      if (!active) return;
      const authorizedIds = user.store_ids;
      const authorizedStores = authorizedIds.map((id) => ({ id, name: id }));
      // 已授权店铺编号可启动看板，弱网下不等待仅用于显示的店铺名称。
      setStores(authorizedStores);
      setStoreId((current) => authorizedIds.includes(current) ? current : authorizedIds[0] ?? "");
      const names = await storeNamesRequest;
      if (!active) return;
      const byId = new Map(names.map((store) => [store.id, store.name]));
      setStores(authorizedStores.map((store) => ({ ...store, name: byId.get(store.id) ?? store.name })));
    }).catch((caught: unknown) => {
      if (!active) return;
      setError(caught instanceof Error ? caught.message : en ? "Failed to load user" : "用户信息加载失败");
      setLoading(false);
    });
    return () => { active = false; };
  }, [en]);
  const load = useCallback(() => {
    const requestId = ++loadRequestId.current;
    if (!storeId) { setLoading(false); return; } setLoading(true); setError("");
    setMetrics(null); setTrend(null); setChannels(null); setAlerts(null); setQueries([]);
    setWidgetLoading(pendingWidgets); setWidgetError({});
    const message = (caught: unknown) => caught instanceof Error ? caught.message : en ? "Failed to load dashboard" : "看板加载失败";
    const loadWidget = <T,>(widget: Widget, request: Promise<T>, show: (value: T) => void) => {
      void request.then((value) => { if (requestId === loadRequestId.current) show(value); })
        .catch((caught) => { if (requestId === loadRequestId.current) setWidgetError((current) => ({ ...current, [widget]: message(caught) })); })
        .finally(() => { if (requestId === loadRequestId.current) setWidgetLoading((current) => ({ ...current, [widget]: false })); });
    };
    const days = period === "30d" ? 30 : 7;
    loadWidget("trend", getDashboardTrend(storeId, days), setTrend);
    loadWidget("channels", getDashboardChannels(storeId, period), setChannels);
    loadWidget("alerts", getDashboardAlerts(storeId), setAlerts);
    loadWidget("queries", getTopQueries(storeId, period), setQueries);
    void getDashboardMetrics(storeId, period)
      .then((value) => { if (requestId === loadRequestId.current) setMetrics(value); })
      .catch((caught) => { if (requestId === loadRequestId.current) setError(message(caught)); })
      .finally(() => { if (requestId === loadRequestId.current) setLoading(false); });
  }, [en, period, storeId]);
  useEffect(() => () => { loadRequestId.current += 1; }, []);
  useEffect(() => { void load(); }, [load]);
  const chartPoints = useMemo(() => { const items = trend?.items ?? []; const max = Math.max(1, ...items.map((item) => item.sessions)); return items.map((item, index) => `${items.length === 1 ? 50 : (index / (items.length - 1)) * 100},${92 - (item.sessions / max) * 80}`).join(" "); }, [trend]);

  return <AppShell><main className="management-page prototype-page"><section className="prototype-page-header"><div className="prototype-title"><span className="prototype-title-icon"><ChartPieSlice size={25} weight="duotone" /></span><div><h2>{en ? "Operations dashboard" : "数据看板"}<span>{en ? "Store operations overview" : "店铺运营总览"}</span></h2></div></div><div className="prototype-actions"><select aria-label={en ? "Store" : "店铺"} className="compact-field header-select" value={storeId} onChange={(event) => { loadRequestId.current += 1; setMetrics(null); setLoading(true); setStoreId(event.target.value); }}>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select><select aria-label={en ? "Period" : "统计周期"} className="compact-field header-select" value={period} onChange={(event) => { loadRequestId.current += 1; setLoading(true); setPeriod(event.target.value as Period); }}><option value="today">{en ? "Today" : "今天"}</option><option value="7d">{en ? "Last 7 days" : "近 7 天"}</option><option value="30d">{en ? "Last 30 days" : "近 30 天"}</option></select></div></section>
    {loading ? <LoadingState label={en ? "Aggregating operations data…" : "正在汇总运营数据…"} /> : error ? <ErrorState message={error} retry={() => void load()} /> : !storeId || !metrics ? <EmptyState label={en ? "No accessible store or metrics" : "暂无可访问店铺或指标数据"} /> : <><section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label={en ? "Core metrics" : "核心指标"}><MetricCard icon={<ChatsCircle size={20} weight="duotone" />} label={en ? "Conversations" : "会话量"} value={metrics.total_sessions.toLocaleString()} note={en ? period : periodLabel(period)} tone="blue" /><MetricCard icon={<ArrowsLeftRight size={20} weight="duotone" />} label={en ? "AI transfer rate" : "AI 转人工率"} value={`${metrics.transfer_rate.toFixed(1)}%`} note={en ? "Valid Agent runs" : "有效 Agent Run"} tone="green" /><MetricCard icon={<Clock size={20} weight="duotone" />} label={en ? "Average response" : "平均响应时间"} value={metrics.avg_response_time == null ? "—" : formatDuration(metrics.avg_response_time, en)} note={en ? "Customer message to first reply" : "客户消息至首次回复"} tone="orange" /><MetricCard icon={<CurrencyDollar size={20} weight="duotone" />} label={en ? "Recovered GMV" : "挽回 GMV"} value={`${metrics.currency} ${Number(metrics.recovered_gmv).toLocaleString()}`} note={en ? "Converted marketing events" : "已转化营销事件"} tone="red" /></section>
    <section className="mt-4 grid gap-4 xl:grid-cols-[1.65fr_1fr]"><article className="management-card chart-card"><div className="flex items-start justify-between gap-4"><div><h3 className="font-semibold">{en ? "Conversation trend" : "会话趋势"}</h3><p className="text-sm text-[var(--muted)]">{widgetLoading.trend ? (en ? "Loading…" : "正在加载…") : en ? `Last ${trend?.items.length ?? 0} calendar days` : `最近 ${trend?.items.length ?? 0} 个自然日`}</p></div><button className="text-button" type="button" onClick={() => setShowTable((value) => !value)}>{showTable ? (en ? "View chart" : "查看图表") : (en ? "View data table" : "查看数据表")}</button></div>{widgetLoading.trend ? <LoadingState label={en ? "Loading conversation trend" : "正在加载会话趋势"} /> : widgetError.trend ? <ErrorState message={widgetError.trend} retry={() => void load()} /> : showTable ? <table className="dashboard-table mt-5 w-full text-sm"><thead><tr><th className="text-left">{en ? "Date" : "日期"}</th><th className="text-right">{en ? "Conversations" : "会话量"}</th></tr></thead><tbody>{trend?.items.map((item) => <tr key={item.date}><td>{item.date}</td><td className="text-right">{item.sessions}</td></tr>)}</tbody></table> : <svg aria-label={en ? "Conversation trend line chart" : "会话趋势折线图"} className="trend-chart mt-6 h-56 w-full overflow-visible" role="img" viewBox="0 0 100 100" preserveAspectRatio="none"><line stroke="var(--border)" x1="0" x2="100" y1="12" y2="12" /><line stroke="var(--border)" x1="0" x2="100" y1="38" y2="38" /><line stroke="var(--border)" x1="0" x2="100" y1="65" y2="65" /><line stroke="var(--border)" x1="0" x2="100" y1="92" y2="92" /><polyline fill="none" points={chartPoints} stroke="var(--primary)" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" vectorEffect="non-scaling-stroke" />{trend?.items.map((item, index, items) => { const max = Math.max(1, ...items.map((row) => row.sessions)); const x = items.length === 1 ? 50 : (index / (items.length - 1)) * 100; const y = 92 - (item.sessions / max) * 80; return <circle key={item.date} cx={x} cy={y} fill="var(--surface)" r="1.5" stroke="var(--primary)" strokeWidth="1" vectorEffect="non-scaling-stroke"><title>{item.date}: {item.sessions}</title></circle>; })}</svg>}</article><article className="management-card"><h3 className="font-semibold">{en ? "Channel distribution" : "渠道分布"}</h3><div className="mt-5 space-y-5">{widgetLoading.channels ? <LoadingState label={en ? "Loading channel distribution" : "正在加载渠道分布"} /> : widgetError.channels ? <ErrorState message={widgetError.channels} retry={() => void load()} /> : channels?.items.length ? channels.items.map((item) => <div key={item.platform}><div className="mb-2 flex justify-between text-sm"><strong className="capitalize">{item.platform}</strong><span className="text-[var(--muted)]">{item.count} · {item.percentage.toFixed(1)}%</span></div><div className="channel-track"><span className={`channel-fill channel-${item.platform}`} style={{ width: `${Math.max(item.percentage, 2)}%` }} /></div></div>) : <EmptyState label={en ? "No channel data" : "暂无渠道数据"} />}</div></article></section>
    <section className="mt-4 grid gap-4 lg:grid-cols-2"><article className="management-card"><h3 className="font-semibold">{en ? "Live alerts" : "实时预警"}</h3><div className="data-list">{widgetLoading.alerts ? <LoadingState label={en ? "Loading live alerts" : "正在加载实时预警"} /> : widgetError.alerts ? <ErrorState message={widgetError.alerts} retry={() => void load()} /> : alerts ? <><AlertRow label={en ? "Refund / return orders" : "退款 / 退货订单"} value={alerts?.refund_requests.total ?? 0} detail={en ? "Live total" : "实时汇总"} /><AlertRow label={en ? "Reviews rated 3 or below" : "三分及以下评价"} value={alerts?.bad_reviews.total ?? 0} detail={alerts?.bad_reviews.golden_window ? (en ? "Within follow-up window" : "处于跟进窗口") : (en ? "Live total" : "实时汇总")} urgent={alerts?.bad_reviews.golden_window} /><AlertRow label={en ? "Overdue unpaid orders" : "超时未支付订单"} value={alerts?.abandoned_carts.total ?? 0} detail={en ? `Potential ${metrics.currency} ${Number(alerts?.abandoned_carts.potential_gmv ?? 0).toLocaleString()}` : `潜在 ${metrics.currency} ${Number(alerts?.abandoned_carts.potential_gmv ?? 0).toLocaleString()}`} /></> : null}</div></article><article className="management-card"><h3 className="font-semibold">{en ? "Top queries" : "热门咨询"}</h3><div className="data-list">{widgetLoading.queries ? <LoadingState label={en ? "Loading top queries" : "正在加载热门咨询"} /> : widgetError.queries ? <ErrorState message={widgetError.queries} retry={() => void load()} /> : queries.length ? queries.map((item) => <div className="data-row" key={item.intent}><span className="count-pill">{item.rank}</span><div className="min-w-0 flex-1"><strong>{item.intent}</strong><p>{en ? `${item.count} queries` : `${item.count} 次咨询`}</p></div></div>) : <EmptyState label={en ? "No query intents to aggregate" : "暂无可聚合的咨询意图"} />}</div></article></section><p className="mt-4 text-right text-xs text-[var(--muted)]">{en ? "Data updated: " : "数据更新时间："}{metrics.updated_at ? new Date(metrics.updated_at).toLocaleString(en ? "en-US" : "zh-CN") : (en ? "Waiting for first aggregation" : "等待首次聚合")}</p></>}</main></AppShell>;
}

function MetricCard({ icon, label, value, note, tone }: { icon: ReactNode; label: string; value: string; note: string; tone: "blue" | "green" | "orange" | "red" }) { return <article className={`management-card metric-card metric-${tone}`}><div className="metric-heading"><p>{label}</p><span aria-hidden="true">{icon}</span></div><strong className="metric-value">{value}</strong><p className="metric-note">{note}</p></article>; }
function AlertRow({ label, value, detail, urgent = false }: { label: string; value: number; detail: string; urgent?: boolean }) { return <div className="data-row"><div><strong>{label}</strong><p>{detail}</p></div><span className={urgent ? "status-badge danger" : "status-badge"}>{value}</span></div>; }
function periodLabel(period: Period) { return period === "today" ? "今天" : period === "7d" ? "近 7 天" : "近 30 天"; }
function formatDuration(seconds: number, en = false) { return seconds < 60 ? `${seconds.toFixed(1)} ${en ? "sec" : "秒"}` : `${(seconds / 60).toFixed(1)} ${en ? "min" : "分钟"}`; }
