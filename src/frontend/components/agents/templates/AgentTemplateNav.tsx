import Link from "next/link";

export function AgentTemplateNav({ current }: { current: "agents" | "templates" | "batches" }) {
  return <nav className="tabs" aria-label="Agent 管理导航">{[{ key: "agents", href: "/agents", label: "店铺 Agent" }, { key: "templates", href: "/agents/templates", label: "Agent 模板" }, { key: "batches", href: "/agents/template-batches", label: "批量任务" }].map((item) => <Link className={`tab ${current === item.key ? "active" : ""}`} href={item.href} aria-current={current === item.key ? "page" : undefined} key={item.key}>{item.label}</Link>)}</nav>;
}
