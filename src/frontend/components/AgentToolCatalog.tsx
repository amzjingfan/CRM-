"use client";

import { useEffect, useState } from "react";
import { getAgentToolCatalog, type AgentToolCatalogView, type AgentToolMetadata } from "../lib/api";

const operationLabels = { read: "只读查询", internal_write: "内部写入", confirmation: "需人工确认", notification: "店铺策略通知" };
const statusLabels = { available: "可用", unavailable: "暂不可用", requires_context: "需关联会话", requires_knowledge: "需绑定文件", confirmation: "人工确认", bound: "已绑定文件" };

function CategoryIcon({ category }: { category: string }) {
  const paths: Record<string, string> = {
    orders: "M3 6h12v11H3z M15 10h4l3 4v3h-7 M7 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4 M18 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4",
    products: "M4 7l8-4 8 4v10l-8 4-8-4z M4 7l8 4 8-4 M12 11v10",
    aftersales: "M4 11a8 8 0 1 1 2 7 M4 4v7h7 M12 7v5l3 2",
    customers: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M19 8h3 M19 12h3 M19 16h3",
    knowledge: "M4 3h7a3 3 0 0 1 3 3v15a4 4 0 0 0-4-2H4z M14 6a3 3 0 0 1 3-3h5v16h-5a4 4 0 0 0-3 2",
    collaboration: "M21 12a8 8 0 0 1-8 8H8l-5 3V9a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z M8 9h8 M8 13h5",
  };
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[category] ?? paths.collaboration} /></svg>;
}

export function AgentToolCatalog({ storeId, enabled, boundFileCount, onChange, onConfigureKnowledge }: {
  storeId: string; enabled: string[]; boundFileCount: number; onChange: (names: string[]) => void; onConfigureKnowledge: () => void;
}) {
  const [catalog, setCatalog] = useState<AgentToolCatalogView | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setCatalog(null); setError("");
    void getAgentToolCatalog(storeId).then((result) => { if (active) setCatalog(result); })
      .catch((caught: unknown) => { if (active) setError(caught instanceof Error ? caught.message : "工具目录加载失败"); });
    return () => { active = false; };
  }, [storeId, retry]);
  return <AgentToolCatalogFields key={storeId} catalog={catalog} error={error} onRetry={() => setRetry((old) => old + 1)} enabled={enabled} boundFileCount={boundFileCount} onChange={onChange} onConfigureKnowledge={onConfigureKnowledge} />;
}

type ToolDisplay = Omit<AgentToolMetadata, "availability" | "reason" | "missing_scopes"> & Partial<Pick<AgentToolMetadata, "availability" | "reason" | "missing_scopes">>;
export function AgentToolCatalogFields({ catalog, enabled, onChange, disabled = false, global = false, boundFileCount = 0, onConfigureKnowledge, error = "", onRetry }: {
  catalog: { groups: AgentToolCatalogView["groups"]; tools: ToolDisplay[] } | null;
  enabled: string[]; onChange: (names: string[]) => void; disabled?: boolean; global?: boolean; boundFileCount?: number;
  onConfigureKnowledge?: () => void; error?: string; onRetry?: () => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const isEnabled = (name: string) => enabled.includes(name) || (name === "search_knowledge" && boundFileCount > 0);
  const selectedCount = catalog?.tools.filter((item) => isEnabled(item.name)).length ?? enabled.length;
  const normalized = query.trim().toLocaleLowerCase();
  const visible = catalog?.tools.filter((item) =>
    (filter !== "selected" || isEnabled(item.name)) && (filter !== "read" || item.operation === "read") &&
    (!normalized || `${item.title} ${item.name} ${item.description}`.toLocaleLowerCase().includes(normalized))) ?? [];
  return <section className="panel active capability-panel" role="tabpanel" aria-label="工具能力配置">
    <div className="capability-heading"><div className="section-head"><h3>工具能力 <span className="count-pill">已配置 {selectedCount} 项</span></h3><p>按职责配置能力，模型从该 Agent 发布的全部工具中自主选择。</p></div><span className="capability-directory-label">{catalog ? `${catalog.tools.length} 项可配置能力` : "加载工具目录"}</span></div>
    <div className="capability-toolbar"><label className="capability-search"><span>搜索工具</span><input className="field" aria-label="搜索工具" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="名称、用途或工具编码" /></label><label className="capability-filter"><span>展示范围</span><select className="field" aria-label="展示范围" value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">全部工具</option><option value="selected">已配置工具</option><option value="read">只读查询</option></select></label></div>
    <div className="capability-legend"><span><i className="legend-dot read" />只读查询 · 核实业务事实</span><span><i className="legend-dot internal_write" />内部写入 · 保存 CRM 记录</span><span><i className="legend-dot confirmation" />需人工确认 · 提出操作建议</span></div>
    {error ? <div className="capability-feedback" role="alert"><p>{error}</p><button type="button" className="btn" onClick={onRetry}>重新加载目录</button></div> : !catalog ? <p className="capability-feedback" role="status">正在加载当前店铺工具和授权状态…</p> : visible.length === 0 ? <p className="capability-feedback" role="status">没有符合条件的工具，请调整搜索或筛选。</p> : catalog.groups.map((group) => {
      const items = visible.filter((item) => item.category === group.key);
      if (!items.length) return null;
      return <section className="capability-group" key={group.key} aria-label={group.title}>
        <div className="capability-group-heading"><span className="capability-group-icon"><CategoryIcon category={group.key} /></span><div><h4>{group.title}</h4><p>{group.description}</p></div><span className="capability-group-count">{items.filter((item) => isEnabled(item.name)).length} / {items.length}</span></div>
        <div className="capability-grid">{items.map((item) => {
          const checked = isEnabled(item.name);
          const availability = item.name === "search_knowledge" && item.availability === "requires_knowledge" && boundFileCount > 0 ? "bound" : item.availability;
          return <article className={`capability-card${checked ? " selected" : ""}`} key={item.name}>
            <label className="capability-card-main"><div className="capability-card-top"><strong>{item.title}</strong><input type="checkbox" aria-label={`启用${item.title}`} name={item.name} checked={checked} disabled={disabled || (item.name === "search_knowledge" && boundFileCount > 0)} onChange={(event) => onChange(event.target.checked ? [...enabled, item.name] : enabled.filter((name) => name !== item.name))} /></div><span className="capability-code">{item.name}</span><span className="capability-description">{item.description}</span></label>
            <div className="capability-card-bottom"><span className={`capability-operation ${item.operation}`}>{operationLabels[item.operation]}</span><span className={`capability-availability ${availability ?? ""}`}>{global ? "应用时逐店校验" : availability ? statusLabels[availability] : "待校验"}</span></div>
            <p className="capability-reason">{global ? "工具授权、会话上下文与知识文件在目标店铺单独校验。" : item.name === "search_knowledge" ? `已绑定 ${boundFileCount} 个文件 · ${item.reason}` : item.reason}</p>
            {!global && item.name === "search_knowledge" ? <button type="button" className="capability-link" onClick={onConfigureKnowledge}>配置知识文件 <span aria-hidden="true">→</span></button> : null}
          </article>;
        })}</div>
      </section>;
    })}
    <div className="tool-footer">勾选后保存并发布，后续运行使用发布版本。缺少授权时可保留配置，执行前会再次校验；内部记录不会发给买家，人工确认类工具不会直接执行。</div>
  </section>;
}
