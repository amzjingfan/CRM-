"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  CaretDown,
  ChartPieSlice,
  Database,
  GearSix,
  Headset,
  Megaphone,
  Moon,
  Robot,
  SignOut,
  Translate,
  WarningCircle,
} from "@phosphor-icons/react";
import { currentUser, isAuthenticationError, logout, type UserView } from "../lib/api";
import { LoadingState } from "./States";
import "../app/marketing/reception/reception.css";

const copy = {
  zh: { workspace: "客服工作台", dashboard: "数据看板", knowledge: "知识库", marketing: "智能营销", agents: "Agent 管理", settings: "系统配置", signOut: "退出", online: "系统运行正常" },
  en: { workspace: "Workspace", dashboard: "Dashboard", knowledge: "Knowledge", marketing: "Marketing", agents: "Agent operations", settings: "Settings", signOut: "Sign out", online: "System healthy" },
};

const navItems = [
  { href: "/dashboard", key: "dashboard", icon: ChartPieSlice },
  { href: "/workspace", key: "workspace", icon: Headset },
  { href: "/knowledge", key: "knowledge", icon: Database },
  { href: "/marketing", key: "marketing", icon: Megaphone },
  { href: "/agents", key: "agents", icon: Robot },
  { href: "/settings", key: "settings", icon: GearSix, separated: true },
] as const;

function KnowledgeNavIcon({ name }: { name: (typeof navItems)[number]["key"] }) {
  const paths = {
    dashboard: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    workspace: <><path d="M4 13v-2a8 8 0 0 1 16 0v2" /><rect x="2.5" y="12" width="4" height="7" rx="1.5" /><rect x="17.5" y="12" width="4" height="7" rx="1.5" /><path d="M19.5 19a4 4 0 0 1-4 3H12" /></>,
    knowledge: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7" /></>,
    marketing: <><path d="M3 10v4h4l10 5V5L7 10H3Z" /><path d="m7 14 2 6h3M20 9l2-2M20 15l2 2" /></>,
    agents: <><rect x="4" y="6" width="16" height="14" rx="3" /><path d="M12 6V3M9 3h6" /><circle cx="9" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="15" cy="12" r="1" fill="currentColor" stroke="none" /><path d="M9 16h6" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1" /></>,
  };
  return <svg aria-hidden="true" className="nav-icon" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" viewBox="0 0 24 24">{paths[name]}</svg>;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [user, setUser] = useState<UserView | null>(null);
  const [language, setLanguage] = useState<"zh" | "en">("zh");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [authError, setAuthError] = useState("");
  const [authRetry, setAuthRetry] = useState(0);
  const [marketingOpen, setMarketingOpen] = useState(false);
  const marketingNavRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setMarketingOpen(false); }, [pathname]);
  useEffect(() => {
    if (!marketingOpen) return;
    const closeOnOutside = (event: PointerEvent) => { if (!marketingNavRef.current?.contains(event.target as Node)) setMarketingOpen(false); };
    const closeOnEscape = (event: globalThis.KeyboardEvent) => { if (event.key === "Escape") setMarketingOpen(false); };
    document.addEventListener("pointerdown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("pointerdown", closeOnOutside); document.removeEventListener("keydown", closeOnEscape); };
  }, [marketingOpen]);

  useEffect(() => {
    const savedLanguage = localStorage.getItem("crm_language") === "en" ? "en" : "zh";
    const savedTheme = localStorage.getItem("crm_theme") === "dark" ? "dark" : "light";
    setLanguage(savedLanguage);
    setTheme(savedTheme);
    document.documentElement.dataset.theme = savedTheme;
    document.documentElement.lang = savedLanguage === "en" ? "en" : "zh-CN";
    setAuthError("");
    void currentUser().then(setUser).catch((caught: unknown) => {
      // 未登录是访问受保护布局时的正常分支，不应作为未处理异常污染控制台。
      if (isAuthenticationError(caught)) {
        window.location.replace("/login");
        return;
      }
      // 网络故障和服务端异常仍需保留诊断证据，不能与预期 401 一并吞掉。
      console.error("当前用户状态校验失败", caught);
      setAuthError(savedLanguage === "en" ? "The service is temporarily unavailable. Please retry." : "服务暂时不可用，请检查连接后重试。");
    });
  }, [authRetry]);

  function toggleTheme() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem("crm_theme", next);
    document.documentElement.dataset.theme = next;
  }

  function toggleLanguage() {
    const next = language === "zh" ? "en" : "zh";
    setLanguage(next);
    localStorage.setItem("crm_language", next);
    document.documentElement.lang = next === "en" ? "en" : "zh-CN";
    window.dispatchEvent(new Event("crm-language-change"));
  }

  if (!user) return <main className="auth-gate">{authError ? <section className="auth-gate-card" role="alert"><span className="auth-gate-icon" aria-hidden="true"><WarningCircle size={21} /></span><h1>{language === "en" ? "Unable to open the console" : "暂时无法进入管理台"}</h1><p>{authError}</p><button className="primary-button" onClick={() => setAuthRetry((value) => value + 1)} type="button">{language === "en" ? "Retry" : "重新连接"}</button></section> : <LoadingState label={language === "en" ? "Verifying sign-in…" : "正在验证登录状态…"} />}</main>;
  const text = copy[language];
  const current = navItems.find((item) => pathname.startsWith(item.href)) ?? navItems[0];
  const userInitial = user.name.trim().slice(0, 1).toUpperCase() || "U";
  const knowledgePrototype = current.href === "/knowledge";
  const agentPrototype = current.href === "/agents";
  const prototypeNavigation = knowledgePrototype || agentPrototype;

  return <div className={knowledgePrototype ? "app-shell knowledge-prototype-shell" : agentPrototype ? "app-shell agent-prototype-shell" : "app-shell"}>
    <aside className="sidebar" aria-label={language === "en" ? "Main navigation" : "主导航"}>
      {prototypeNavigation ? <div className="knowledge-brand"><span className="knowledge-brand-mark" aria-hidden="true">◇</span><strong>CRM 智能聊天系统</strong></div> : null}
      <nav className="main-nav">{navItems.map((item) => {
        const Icon = item.icon;
        const active = current.href === item.href;
        if (item.key === "marketing") return <div key={item.href} ref={marketingNavRef}>
          <button aria-expanded={marketingOpen} aria-label={text.marketing} className={active ? "nav-link active" : "nav-link"} onClick={() => setMarketingOpen((open) => !open)} type="button"><Icon aria-hidden="true" className="nav-icon" size={20} weight={active ? "fill" : "regular"} /><span>{text.marketing}</span><CaretDown aria-hidden="true" className={marketingOpen ? "reception-nav-caret open" : "reception-nav-caret"} size={14} /></button>
          {marketingOpen ? <div className="reception-side-subnav"><Link aria-current={pathname === "/marketing" ? "page" : undefined} href="/marketing">营销流程</Link><Link aria-current={pathname.startsWith("/marketing/reception") ? "page" : undefined} href="/marketing/reception">基础接待</Link></div> : null}
        </div>;
        return <div className={"separated" in item && item.separated ? "nav-group-separated" : ""} key={item.href}><Link aria-current={pathname === item.href ? "page" : undefined} aria-label={text[item.key]} className={active ? "nav-link active" : "nav-link"} href={item.href}>{prototypeNavigation ? <KnowledgeNavIcon name={item.key} /> : <Icon aria-hidden="true" className="nav-icon" size={20} weight={active ? "fill" : "regular"} />}<span>{text[item.key]}</span></Link></div>;
      })}</nav>
      {knowledgePrototype ? <div className="knowledge-sidebar-note">知识库交互界面 · 按店铺隔离</div> : null}
      {agentPrototype ? <div className="knowledge-sidebar-note">Agent 管理 · 按店铺隔离</div> : null}
      <div className="sidebar-footer">
        <div className="service-status"><span className="live-dot" /> <span>{text.online}</span></div>
        <div className="sidebar-user"><span className="user-avatar" aria-hidden="true">{userInitial}</span><span className="sidebar-user-copy"><strong>{user.name}</strong><small>{user.role}</small></span><div className="sidebar-tools"><button aria-label={language === "en" ? "Switch theme" : "切换主题"} onClick={toggleTheme} title={theme === "light" ? "Dark" : "Light"} type="button"><Moon size={17} /></button><button aria-label={language === "en" ? "Switch language" : "切换语言"} onClick={toggleLanguage} title={language === "zh" ? "English" : "中文"} type="button"><Translate size={17} /></button><button aria-label={text.signOut} onClick={() => logout().finally(() => { window.location.href = "/login"; })} title={text.signOut} type="button"><SignOut size={17} /></button></div></div>
      </div>
    </aside>
    <section className="app-main min-w-0 flex-1">{children}</section>
  </div>;
}
