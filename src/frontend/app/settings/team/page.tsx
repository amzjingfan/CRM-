"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { ArrowClockwise, DotsThree, MagnifyingGlass, Plus, X } from "@phosphor-icons/react";
import { SettingsFrame } from "../../../components/SettingsFrame";
import { EmptyState, ErrorState, LoadingState } from "../../../components/States";
import { changeTeamMemberPassword, createTeamMember, currentUser, deleteTeamMember, disableTeamMember, listDepartments, listStores, listTeam, updateTeamMember, type Department, type StoreView, type TeamMember } from "../../../lib/api";
import { useLanguage } from "../../../lib/i18n";

type Drawer = { kind: "create" } | { kind: "edit" | "password" | "disable" | "delete"; member: TeamMember } | null;
const roleNames: Record<string, string> = { admin: "系统管理员", supervisor: "客服主管", agent: "普通客服" };
type StoreRole = "agent" | "supervisor";

function AccountStorePicker({ stores, roles, role, onToggle, onRoleChange }: { stores: StoreView[]; roles: Record<string, StoreRole>; role: string; onToggle: (id: string, checked: boolean) => void; onRoleChange: (id: string, nextRole: StoreRole) => void }) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ top: number; left: number; width: number; maxHeight: number } | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const closeOutside = (event: PointerEvent) => { if (!buttonRef.current?.contains(event.target as Node) && !menuRef.current?.contains(event.target as Node)) setOpen(false); };
    const closeEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    const closeResize = () => setOpen(false);
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeEscape);
    window.addEventListener("resize", closeResize);
    return () => { document.removeEventListener("pointerdown", closeOutside); document.removeEventListener("keydown", closeEscape); window.removeEventListener("resize", closeResize); };
  }, [open]);
  function toggle() {
    if (open) { setOpen(false); return; }
    const rect = buttonRef.current?.getBoundingClientRect();
    if (!rect) return;
    const spaceBelow = window.innerHeight - rect.bottom - 12;
    const spaceAbove = rect.top - 12;
    const height = Math.min(280, Math.max(spaceBelow, spaceAbove));
    setPosition({ top: spaceBelow >= height ? rect.bottom + 4 : rect.top - height - 4, left: rect.left, width: rect.width, maxHeight: height });
    setOpen(true);
  }
  const selected = Object.keys(roles);
  return <div className="account-store-select"><span>负责店铺（可多选）</span><button aria-expanded={open} aria-haspopup="dialog" className="compact-field account-store-select-trigger" onClick={toggle} ref={buttonRef} type="button">{selected.length ? `已选择 ${selected.length} 家店铺` : "请选择负责店铺"}<span aria-hidden="true">⌄</span></button>
    {open && position ? createPortal(<div aria-label="负责店铺（可多选）" className="account-store-dropdown" ref={menuRef} role="dialog" style={{ top: position.top, left: position.left, width: position.width, maxHeight: position.maxHeight }}>
      {stores.map((store) => <div className="account-store-row" key={store.id}><label><input aria-label={`负责店铺 ${store.name}`} checked={store.id in roles} onChange={(event) => onToggle(store.id, event.target.checked)} type="checkbox" />{store.name}</label>{store.id in roles ? <select aria-label={`${store.name}店铺角色`} className="compact-field" onChange={(event) => onRoleChange(store.id, event.target.value as StoreRole)} value={roles[store.id]}><option value="agent">普通客服</option><option value="supervisor">客服主管</option></select> : null}</div>)}
      {!stores.length ? <Link href="/settings/stores">创建店铺</Link> : null}
    </div>, document.body) : null}
    {!selected.length && role !== "admin" ? <small>至少选择一家负责店铺。</small> : null}
  </div>;
}

export default function TeamPage() {
  const en = useLanguage() === "en";
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [stores, setStores] = useState<StoreView[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | "active" | "disabled">("all");
  const [drawer, setDrawer] = useState<Drawer>(null);
  const [menuId, setMenuId] = useState<string | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const [role, setRole] = useState("agent");
  const [storeRoles, setStoreRoles] = useState<Record<string, StoreRole>>({});
  const [assignmentDirty, setAssignmentDirty] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [people, shops, depts, me] = await Promise.all([listTeam(), listStores(), listDepartments(), currentUser()]);
      setMembers(people); setStores(shops); setDepartments(depts); setIsAdmin(me.role === "admin"); setError("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "账号加载失败"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const activeCount = members.filter((item) => item.status === "active").length;
  const shown = useMemo(() => members.filter((item) =>
    (status === "all" || item.status === status)
    && (item.login_name ?? item.email ?? "").toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
  ), [members, status, query]);
  const selectedStoreIds = Object.keys(storeRoles);
  const eligibleDepartments = departments.filter((department) => role === "admin" || department.store_ids.some((id) => selectedStoreIds.includes(id)));

  function openCreate() {
    const first = departments.flatMap((department) => department.store_ids).find((id) => stores.some((store) => store.id === id)) ?? stores[0]?.id;
    setRole("agent"); setStoreRoles(first ? { [first]: "agent" } : {}); setAssignmentDirty(false); setDrawer({ kind: "create" });
  }

  function openEdit(member: TeamMember) {
    const scoped = member.assignments.filter((item): item is typeof item & { store_id: string; role: StoreRole } => item.store_id !== null && (item.role === "agent" || item.role === "supervisor"));
    const next: Record<string, StoreRole> = {};
    scoped.forEach((item) => { next[item.store_id] = item.role; });
    const distinct = [...new Set(scoped.map((item) => item.role))];
    setRole(member.assignments.some((item) => item.role === "admin") ? "admin" : distinct.length === 1 ? distinct[0] : "mixed");
    setStoreRoles(next); setAssignmentDirty(false); setDrawer({ kind: "edit", member });
  }

  function setAllRoles(nextRole: string) {
    setAssignmentDirty(true);
    setRole(nextRole);
    if (nextRole === "agent" || nextRole === "supervisor") setStoreRoles((current) => Object.fromEntries(Object.keys(current).map((id) => [id, nextRole])));
  }

  function toggleStore(id: string, checked: boolean) {
    setAssignmentDirty(true);
    setStoreRoles((current) => { const next = { ...current }; if (checked) next[id] = role === "supervisor" ? "supervisor" : "agent"; else delete next[id]; return next; });
  }

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
          assignments: role === "admin" ? [{ role: "admin", store_id: null }] : Object.entries(storeRoles).map(([id, storeRole]) => ({ role: storeRole, store_id: id })),
          department_id: String(data.get("department_id") || "") || null,
        });
        setNotice("账号已创建，请通过安全渠道交付初始密码");
      } else if (drawer?.kind === "edit") {
        await updateTeamMember(drawer.member.id, {
          name: String(data.get("name")), email: String(data.get("email") || "") || null,
          phone: String(data.get("phone") || "") || null, timezone: String(data.get("timezone")),
          max_concurrent_sessions: Number(data.get("max_concurrent_sessions")),
          ...(assignmentDirty ? { assignments: role === "admin" ? [{ role: "admin", store_id: null }] : Object.entries(storeRoles).map(([id, storeRole]) => ({ role: storeRole, store_id: id })) } : {}),
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
    const suffix = member.assignments.some((item) => item.role === "admin") ? "（全部店铺）" : `（${new Set(member.assignments.map((item) => item.store_id).filter(Boolean)).size} 店）`;
    const departmentLabel = names.join("、") || (member.department_ids.length ? "其他部门" : "未分部门");
    return `${departmentLabel} | ${roles.join("、") || "—"}${roles.length ? suffix : ""}`;
  }

  function roleFields() {
    if (drawer?.kind !== "create" && drawer?.kind !== "edit") return null;
    if (drawer.kind === "edit" && (drawer.member.assignments.some((item) => !["admin", "agent", "supervisor"].includes(item.role)) || new Set(drawer.member.assignments.map((item) => item.store_id ?? "global")).size !== drawer.member.assignments.length)) return <p className="account-role-note">该账号包含非标准或重复店铺角色；这里只能编辑基本资料，店铺角色请先由管理员核对。</p>;
    return <>
      <h3 className="account-form-section">部门角色</h3>
      <label className="field-label">账号角色
        <select aria-label="账号角色" className="compact-field" name="role" onChange={(event) => setAllRoles(event.target.value)} value={role}>
          {role === "mixed" ? <option value="mixed">按店铺分别设置</option> : null}
          <option value="agent">普通客服</option><option value="supervisor">客服主管</option><option value="admin">系统管理员（全部店铺）</option>
        </select>
      </label>
      {role !== "admin" ? <AccountStorePicker stores={stores} roles={storeRoles} role={role} onToggle={toggleStore} onRoleChange={(id, nextRole) => { setStoreRoles((current) => ({ ...current, [id]: nextRole })); setRole("mixed"); setAssignmentDirty(true); }} /> : <p className="account-role-note">系统管理员拥有全部店铺权限，不参与自动派单。</p>}
      {drawer.kind === "create" ? <label className="field-label">所在部门<select className="compact-field" defaultValue="" key={`${role}:${selectedStoreIds.join(",")}`} name="department_id"><option value="">暂不分配</option>{eligibleDepartments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}</select>{!eligibleDepartments.length && departments.length ? <small>所选店铺未分配给任何部门。请更换负责店铺，或先到部门管理中添加该店铺。</small> : null}</label> : <p className="account-role-note">所属部门请在部门管理中调整；此处修改店铺角色与授权。</p>}
    </>;
  }

  return <SettingsFrame title={en ? "Account management" : "账号管理"} description={en ? "Create and manage employee accounts." : "管理员工登录账号、所属部门和基本信息。"}>
    {notice ? <div className="inline-status" role="status">{notice}</div> : null}
    <section className="settings-card">
      <div className="settings-card-heading"><div><h2>员工账号</h2><p>总账号 {members.length} 位 · 启用 {activeCount} 位</p></div>{isAdmin ? <button className="primary-button" onClick={openCreate} type="button"><Plus size={16} />新建账号</button> : null}</div>
      <div className="settings-toolbar"><div className="settings-segments" aria-label="账号状态">{(["all", "active", "disabled"] as const).map((value) => <button aria-pressed={status === value} className={status === value ? "active" : ""} key={value} onClick={() => setStatus(value)} type="button">{value === "all" ? "全部" : value === "active" ? "启用" : "已禁用"} ({value === "all" ? members.length : value === "active" ? activeCount : members.length - activeCount})</button>)}</div><div className="settings-toolbar-actions"><button aria-label="刷新账号" className="settings-icon-button" onClick={() => void load()} type="button"><ArrowClockwise size={18} /></button><label className="settings-search"><MagnifyingGlass size={17} /><input aria-label="搜索登录账号" onChange={(event) => setQuery(event.target.value)} placeholder="输入登录账号搜索" value={query} /></label></div></div>
      {loading ? <LoadingState label="正在加载账号…" /> : error ? <ErrorState message={error} retry={() => void load()} /> : shown.length ? <div className="settings-table-wrap"><table className="settings-table account-table"><thead><tr><th>序号</th><th>登录账号</th><th>昵称</th><th>状态</th><th>部门 | 角色</th><th>登录邮箱</th><th>手机号码</th><th>操作</th></tr></thead><tbody>{shown.map((member, index) => <tr key={member.id}><td>{index + 1}</td><td><strong>{member.login_name ?? member.email ?? "—"}</strong></td><td>{member.name}</td><td><span className={`status-badge ${member.status}`}>{member.status === "active" ? "启用中" : "已停用"}</span></td><td>{departmentRole(member)}</td><td>{member.email || "—"}</td><td>{member.phone || "—"}</td><td className="account-actions">{isAdmin ? <><button className="text-button" onClick={() => openEdit(member)} type="button">编辑</button><span className="account-more-wrap"><button aria-expanded={menuId === member.id} aria-label={`${member.name} 更多操作`} className="settings-icon-button" onClick={(event) => toggleMenu(event, member.id)} type="button"><DotsThree size={20} /></button>{menuId === member.id ? <span aria-label="账号更多操作" className="account-more-menu portaled" role="menu" style={menuPosition ?? undefined}><button onClick={() => { setDrawer({ kind: "password", member }); setMenuId(null); }} type="button">修改密码</button><button disabled={member.status === "disabled"} onClick={() => { setDrawer({ kind: "disable", member }); setMenuId(null); }} type="button">停用</button><button disabled={member.status !== "disabled"} onClick={() => { setDrawer({ kind: "delete", member }); setMenuId(null); }} title={member.status !== "disabled" ? "请先停用账号" : "永久删除已停用账号"} type="button">删除账号</button></span> : null}</span></> : <span>只读</span>}</td></tr>)}</tbody></table></div> : <EmptyState label={query || status !== "all" ? "没有符合条件的账号" : "暂无员工账号"} />}
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
        {roleFields()}
      </div><footer><button className="secondary-button" onClick={() => setDrawer(null)} type="button">取消</button><button className="primary-button" disabled={busy || (role !== "admin" && selectedStoreIds.length === 0)} type="submit">{busy ? "保存中…" : "保存"}</button></footer></form> : drawer.kind === "password" ? <form className="account-drawer-form" onSubmit={(event) => void submitPassword(event)}><div className="account-drawer-fields"><p>{drawer.member.login_name ?? drawer.member.email}</p><label className="field-label">新密码<input autoComplete="new-password" className="compact-field" minLength={12} name="password" required type="password" /></label></div><footer><button className="secondary-button" onClick={() => setDrawer(null)} type="button">取消</button><button className="primary-button" disabled={busy} type="submit">确认修改</button></footer></form> : drawer.kind === "delete" ? <div className="account-drawer-form"><div className="account-drawer-fields"><p>永久删除已停用账号“{drawer.member.name}”（{drawer.member.login_name ?? drawer.member.email}）？此操作无法恢复。</p><p>有业务记录的账号会由服务端拒绝删除，并保留已停用状态。</p></div><footer><button className="secondary-button" onClick={() => setDrawer(null)} type="button">取消</button><button className="danger-button" disabled={busy} onClick={() => void confirmDelete()} type="button">确认永久删除</button></footer></div> : <div className="account-drawer-form"><div className="account-drawer-fields">确认停用“{drawer.member.name}”？</div><footer><button className="secondary-button" onClick={() => setDrawer(null)} type="button">取消</button><button className="primary-button" disabled={busy} onClick={() => void confirmDisable()} type="button">确认停用</button></footer></div>}
    </aside></div> : null}
  </SettingsFrame>;
}
