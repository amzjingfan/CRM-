"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Storefront, UsersThree } from "@phosphor-icons/react";
import { useLanguage } from "../lib/i18n";

const groups = [
  { zh: "店铺", en: "Stores", icon: Storefront, links: [
    { href: "/settings/stores", zh: "店铺列表", en: "Store list" },
    { href: "/settings/channels", zh: "授权", en: "Authorizations" },
  ] },
  { zh: "员工", en: "Employees", icon: UsersThree, links: [
    { href: "/settings/team", zh: "账号", en: "Accounts" },
  ] },
];

export function SettingsNav() {
  const pathname = usePathname();
  const en = useLanguage() === "en";
  return <nav aria-label={en ? "System settings" : "系统设置"} className="settings-side-nav">
    {groups.map((group) => {
      const Icon = group.icon;
      return <section className="settings-nav-group" key={group.zh}>
        <h2><Icon aria-hidden="true" size={17} />{en ? group.en : group.zh}</h2>
        {group.links.map((link) => <Link aria-current={pathname === link.href ? "page" : undefined} className={pathname === link.href ? "settings-nav-link active" : "settings-nav-link"} href={link.href} key={link.href}>{en ? link.en : link.zh}</Link>)}
      </section>;
    })}
  </nav>;
}
