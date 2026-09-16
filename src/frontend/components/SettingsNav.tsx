"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PlugsConnected, Storefront, UsersThree } from "@phosphor-icons/react";
import { useLanguage } from "../lib/i18n";

const links = [{ href: "/settings/stores", zh: "店铺", en: "Stores", icon: Storefront }, { href: "/settings/channels", zh: "渠道", en: "Channels", icon: PlugsConnected }, { href: "/settings/team", zh: "团队", en: "Team", icon: UsersThree }];

export function SettingsNav() {
  const pathname = usePathname();
  const en = useLanguage() === "en";
  return <nav aria-label={en ? "System settings" : "系统设置"} className="filter-row settings-tabs mb-4">{links.map((link) => { const Icon = link.icon; return <Link aria-current={pathname === link.href ? "page" : undefined} className={pathname === link.href ? "filter active" : "filter"} href={link.href} key={link.href}><Icon size={16} />{en ? link.en : link.zh}</Link>; })}</nav>;
}
