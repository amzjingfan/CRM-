"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowClockwise, DotsThree, MagnifyingGlass, Plus, X } from "@phosphor-icons/react";
import { SettingsFrame } from "../../../components/SettingsFrame";
import { EmptyState, ErrorState, LoadingState } from "../../../components/States";
import { changeTeamMemberPassword, createTeamMember, deleteTeamMember, disableTeamMember, listDepartments, listStores, listTeam, updateTeamMember, type Department, type StoreView, type TeamMember } from "../../../lib/api";
import { useLanguage } from "../../../lib/i18n";

type Drawer = { kind: "create" } | { kind: "edit" | "password" | "disable" | "delete"; member: TeamMember } | null;
const roleNames: Record<string, string> = { admin: "管理员", supervisor: "主管", agent: "客服" };

export default function TeamPage() {
  const en = useLanguage() === "en";
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [stores, setStores] = useState<StoreView[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | "active" | "disabled">("all");
  const [drawer, setDrawer] = useState<Drawer>(null);
  const [menuId, setMenuId] = useState<string | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const [role, setRole] = useState("agent");
  const [storeId, setStoreId] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [people, shops, depts] = await Promise.all([listTeam(), listStores(), listDepartments()]);
      setMembers(people); setStores(shops); setDepartments(depts); setError("");
      setStoreId((previous) => previous || shops[0]?.id || "");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "账号加载失败"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const activeCount = members.filter((item) => item.status === "active").length;
  const shown = useMemo(() => members.filter((item) =>
    (status === "all" || item.status === status)
    && (item.login_name ?? item.email ?? "").toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
  ), [members, status, query]);
  const eligibleDepartments = departments.filter((department) => role === "admin" || department.store_ids.includes(storeId));

  useEffect(() => {
    if (!menuId) return;
    const close = () => setMenuId(null);
    const outside = (event: PointerEvent) => { if (event.target instanceof Element && !event.target.closest(".account-more-wrap, .account-more-menu")) close(); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    document.addEventListener("pointerdown", outside);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    window.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); window.removeEventListener("scroll", close, true); window.removeEventListener("resize", close); window.removeEventListener("keydown", escape); };
  }, [menuId]);

  function toggleMenu(event: React.MouseEvent<HTMLButtonElement>, memberId: string) {
    if (menuId === memberId) { setMenuId(null); return; }
    const rect = event.currentTarget.getBoundingClientRect();
    const menuHeight = 116;
    setMenuPosition({ top: rect.bottom + menuHeight + 8 <= window.innerHeight ? rect.bottom + 4 : Math.max(8, rect.top - menuHeight - 4), left: Math.max(8, Math.min(rect.right - 124, window.innerWidth - 132)) });
    setMenuId(memberId);
  }

  async function submitAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true); setNotice("");
    try {
      if (drawer?.kind === "create") {
        await createTeamMember({
          login_name: String(data.get("login_name")), name: String(data.get("name") || data.get("login_name")), temporary_password: String(data.get("temporary_password")),
          email: String(data.get("email") || "") || null, phone: String(data.get("phone") || "") || null,
          timezone: String(data.get("timezone")), max_concurrent_sessions: Number(data.get("max_concurrent_sessions")),
          assignments: role === "admin" ? [{ role: "admin", store_id: null }] : [{ role: role as "agent" | "supervisor", store_id: storeId }],
          department_id: String(data.get("department_id") || "") || null,
        });
        setNotice("账号已创建，请通过安全渠道交付初始密码");
      } else if (drawer?.kind === "edit") {
        await updateTeamMember(drawer.member.id, {
          name: String(data.get("name")), email: String(data.get("email") || "") || null,
          phone: String(data.get("phone") || "") || null, timezone: String(data.get("timezone")),
          max_concurrent_sessions: Number(data.get("max_concurrent_sessions")),
        });
        setNotice("账号信息已保存");
      }
      setDrawer(null); await load();
    } catch (caught) { setNotice(caught instanceof Error ? caught.message : "保存失败"); }
    finally { setBusy(false); }
  }

  async function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (drawer?.kind !== "password") return;
    setBusy(true); setNotice("");
    try {
      await changeTeamMemberPassword(drawer.member.id, String(new FormData(event.currentTarget).get("password")));
      setDrawer(null); setNotice("密码已修改，该账号原有登录状态已失效");
    } catch (caught) { setNotice(caught instanceof Error ? caught.message : "修改密码失败"); }
    finally { setBusy(false); }
  }

  async function confirmDisable() {
    if (drawer?.kind !== "disable") return;
    setBusy(true); setNotice("");
    try { await disableTeamMember(drawer.member.id); setDrawer(null); setNotice("账号已停用"); await load(); }
    catch (caught) { setNotice(caught instanceof Error ? caught.message : "停用失败"); }
    finally { setBusy(false); }
  }

  async function confirmDelete() {
    if (drawer?.kind !== "delete" || drawer.member.status !== "disabled") return;
    setBusy(true); setNotice("");
    try { await deleteTeamMember(drawer.member.id); setDrawer(null); setNotice("账号已删除"); await load(); }
    catch (caught) { setNotice(caught instanceof Error ? caught.message : "删除失败"); }
    finally { setBusy(false); }
  }

  function departmentRole(member: TeamMember) {
    const names = member.department_ids.map((id) => departments.find((dept) => dept.id === id)?.name).filter(Boolean);
    const roles = [...new Set(member.assignments.map((item) => roleNames[item.role] ?? item.role))];
    return `${names.join("、") || "未分部门"} | ${roles.join("、") || "—"}`;
  }

  return <SettingsFrame title={en ? "Account management" : "账号管理"} description={en ? "Create and manage employee accounts." : "管理员工登录账号、所属部门和基本信息。"}>
    {notice ? <div className="inline-status" role="status">{notice}</div> : null}
    <section className="settings-card">
      <div className="settings-card-heading"><div><h2>员工账号</h2><p>总账号 {members.length} 位 · 启用 {activeCount} 位</p></div><button className="primary-button" onClick={() => { setRole("agent"); setStoreId(departments.flatMap((department) => department.store_ids).find((id) => stores.some((store) => store.id === id)) ?? stores[0]?.id ?? ""); setDrawer({ kind: "create" }); }} type="button"><Plus size={16} />新建账号</button></div>
      <div className="settings-toolbar"><div className="settings-segments" aria-label="账号状态">{(["all", "active", "disabled"] as const).map((value) => <button aria-pressed={status === value} className={status === value ? "active" : ""} key={value} onClick={() => setStatus(value)} type="button">{value === "all" ? "全部" : value === "active" ? "启用" : "已禁用"} ({value === "all" ? members.length : value === "active" ? activeCount : members.length - activeCount})</button>)}</div><div className="settings-toolbar-actions"><button aria-label="刷新账号" className="settings-icon-button" onClick={() => void load()} type="button"><ArrowClockwise size={18} /></button><label className="settings-search"><MagnifyingGlass size={17} /><input aria-label="搜索登录账号" onChange={(event) => setQuery(event.target.value)} placeholder="输入登录账号搜索" value={query} /></label></div></div>
      {loading ? <LoadingState label="正在加载账号…" /> : error ? <ErrorState message={error} retry={() => void load()} /> : shown.length ? <div className="settings-table-wrap"><table className="settings-table account-table"><thead><tr><th>序号</th><th>登录账号</th><th>昵称</th><th>状态</th><th>部门 | 角色</th><th>登录邮箱</th><th>手机号码</th><th>操作</th></tr></thead><tbody>{shown.map((member, index) => <tr key={member.id}><td>{index + 1}</td><td><strong>{member.login_name ?? member.email ?? "—"}</strong></td><td>{member.name}</td><td><span className={`status-badge ${member.status}`}>{member.status === "active" ? "启用中" : "已停用"}</span></td><td>{departmentRole(member)}</td><td>{member.email || "—"}</td><td>{member.phone || "—"}</td><td className="account-actions"><button className="text-button" onClick={() => setDrawer({ kind: "edit", member })} type="button">编辑</button><span className="account-more-wrap"><button aria-expanded={menuId === member.id} aria-label={`${member.name} 更多操作`} className="settings-icon-button" onClick={(event) => toggleMenu(event, member.id)} type="button"><DotsThree size={20} /></button>{menuId === member.id ? <span aria-label="账号更多操作" className="account-more-menu portaled" role="menu" style={menuPosition ?? undefined}><button onClick={() => { setDrawer({ kind: "password", member }); setMenuId(null); }} type="button">修改密码</button><button disabled={member.status === "disabled"} onClick={() => { setDrawer({ kind: "disable", member }); setMenuId(null); }} type="button">停用</button><button disabled={member.status !== "disabled"} onClick={() => { setDrawer({ kind: "delete", member }); setMenuId(null); }} title={member.status !== "disabled" ? "请先停用账号" : "永久删除已停用账号"} type="button">删除账号</button></span> : null}</span></td></tr>)}</tbody></table></div> : <EmptyState label={query || status !== "all" ? "没有符合条件的账号" : "暂无员工账号"} />}
    </section>
    {drawer ? <div className="account-drawer-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setDrawer(null); }}><aside aria-label={drawer.kind === "create" ? "新建账号" : drawer.kind === "edit" ? "编辑账号" : drawer.kind === "password" ? "修改密码" : drawer.kind === "delete" ? "删除账号" : "停用账号"} aria-modal="true" className="account-drawer" role={drawer.kind === "delete" ? "alertdialog" : "dialog"}><header><div><h2>{drawer.kind === "create" ? "新建账号" : drawer.kind === "edit" ? "编辑账号" : drawer.kind === "password" ? "修改密码" : drawer.kind === "delete" ? "删除账号" : "停用账号"}</h2><p>{drawer.kind === "create" ? "填写员工登录和组织信息" : drawer.kind === "edit" ? "更新账号基本信息" : drawer.kind === "password" ? "修改后该账号须重新登录" : drawer.kind === "delete" ? "永久操作，请核对账号" : "确认后该账号无法继续登录"}</p></div><button aria-label="关闭" className="settings-icon-button" onClick={() => setDrawer(null)} type="button"><X size={18} /></button></header>
      {notice ? <div className="inline-status" role="alert">{notice}</div> : null}
      {drawer.kind === "create" || drawer.kind === "edit" ? <form className="account-drawer-form" onSubmit={(event) => void submitAccount(event)}><div className="account-drawer-fields"><h3 className="account-form-section">基础信息</h3>
        {drawer.kind === "create" ? <label className="field-label">登录账号<input autoComplete="off" className="compact-field" maxLength={16} minLength={6} name="login_name" pattern="[A-Za-z][A-Za-z0-9_-]{5,15}" required /><small>6–16 位，以字母开头；创建后不可修改</small></label> : <label className="field-label">登录账号<input className="compact-field" disabled value={drawer.member.login_name ?? drawer.member.email ?? ""} /></label>}
        {drawer.kind === "create" ? <label className="field-label">登录密码<input autoComplete="new-password" className="compact-field" minLength={12} name="temporary_password" required type="password" /><small>至少 12 位</small></label> : null}
        <label className="field-label">账号并发数<input className="compact-field" defaultValue={drawer.kind === "edit" ? drawer.member.max_concurrent_sessions : 50} max={1000} min={1} name="max_concurrent_sessions" required type="number" /><small>当前仅保存和展示，暂不限制同时登录</small></label>
        <label className="field-label">账号工作时区<select className="compact-field" defaultValue={drawer.kind === "edit" ? drawer.member.timezone : "Asia/Shanghai"} name="timezone" required>{["Asia/Shanghai", "America/Los_Angeles", "America/New_York", "Europe/London", "UTC", ...(drawer.kind === "edit" ? [drawer.member.timezone] : [])].filter((value, index, values) => values.indexOf(value) === index).map((value) => <option key={value} value={value}>{value === "Asia/Shanghai" ? "东八区 (UTC+8) · 北京" : value}</option>)}</select></label>
        <label className="field-label">昵称<input className="compact-field" defaultValue={drawer.kind === "edit" ? drawer.member.name : ""} maxLength={100} name="name" placeholder="可选，默认使用登录账号" /></label>
        <label className="field-label">登录邮箱<input className="compact-field" defaultValue={drawer.kind === "edit" ? drawer.member.email ?? "" : ""} name="email" type="email" /></label>
        <label className="field-label">手机号码<input className="compact-field" defaultValue={drawer.kind === "edit" ? drawer.member.phone ?? "" : ""} name="phone" pattern="\+?[0-9][0-9 -]{5,19}" placeholder="13800000000" type="tel" /></label>
        {drawer.kind === "create" ? <><h3 className="account-form-section">部门角色</h3><label className="field-label">账号角色<select className="compact-field" name="role" onChange={(event) => setRole(event.target.value)} value={role}><option value="agent">客服</option><option value="supervisor">主管</option><option value="admin">管理员</option></select></label>{role !== "admin" ? <label className="field-label">负责店铺<select className="compact-field" name="store_id" onChange={(event) => setStoreId(event.target.value)} required value={storeId}>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select></label> : null}{role !== "admin" && !stores.length ? <Link href="/settings/stores">创建店铺</Link> : null}<label className="field-label">所在部门<select className="compact-field" defaultValue="" key={`${role}:${storeId}`} name="department_id"><option value="">暂不分配</option>{eligibleDepartments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}</select>{!eligibleDepartments.length && departments.length ? <small>当前店铺未分配给任何部门。请更换负责店铺，或先到部门管理中添加该店铺。</small> : null}</label></> : null}
      </div><footer><button className="secondary-button" onClick={() => setDrawer(null)} type="button">取消</button><button className="primary-button" disabled={busy || (drawer.kind === "create" && role !== "admin" && stores.length === 0)} type="submit">{busy ? "保存中…" : "保存"}</button></footer></form> : drawer.kind === "password" ? <form className="account-drawer-form" onSubmit={(event) => void submitPassword(event)}><div className="account-drawer-fields"><p>{drawer.member.login_name ?? drawer.member.email}</p><label className="field-label">新密码<input autoComplete="new-password" className="compact-field" minLength={12} name="password" required type="password" /></label></div><footer><button className="secondary-button" onClick={() => setDrawer(null)} type="button">取消</button><button className="primary-button" disabled={busy} type="submit">确认修改</button></footer></form> : drawer.kind === "delete" ? <div className="account-drawer-form"><div className="account-drawer-fields"><p>永久删除已停用账号“{drawer.member.name}”（{drawer.member.login_name ?? drawer.member.email}）？此操作无法恢复。</p><p>有业务记录的账号会由服务端拒绝删除，并保留已停用状态。</p></div><footer><button className="secondary-button" onClick={() => setDrawer(null)} type="button">取消</button><button className="danger-button" disabled={busy} onClick={() => void confirmDelete()} type="button">确认永久删除</button></footer></div> : <div className="account-drawer-form"><div className="account-drawer-fields">确认停用“{drawer.member.name}”？</div><footer><button className="secondary-button" onClick={() => setDrawer(null)} type="button">取消</button><button className="primary-button" disabled={busy} onClick={() => void confirmDisable()} type="button">确认停用</button></footer></div>}
    </aside></div> : null}
  </SettingsFrame>;
}
