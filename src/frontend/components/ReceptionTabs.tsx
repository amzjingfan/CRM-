import Link from "next/link";

const tabs = [
  { href: "/marketing/reception/quick-replies", label: "快捷回复", id: "quick-replies" },
  { href: "/marketing/reception/timeout", label: "超时自动回复", id: "timeout" },
  { href: "/marketing/reception/welcome", label: "进店欢迎语", id: "welcome" },
] as const;

export function ReceptionTabs({ active }: { active: (typeof tabs)[number]["id"] }) {
  return <nav aria-label="基础接待功能" className="reception-page-tabs">{tabs.map((tab) => <Link aria-current={active === tab.id ? "page" : undefined} href={tab.href} key={tab.id}>{tab.label}</Link>)}</nav>;
}
