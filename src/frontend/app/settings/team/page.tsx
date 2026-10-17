"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ArrowClockwise, MagnifyingGlass, Plus } from "@phosphor-icons/react";

import { SettingsFrame } from "../../../components/SettingsFrame";
import { EmptyState, ErrorState, LoadingState } from "../../../components/States";
import {
  createTeamMember,
  deleteTeamMember,
  disableTeamMember,
  listStores,
  listTeam,
  updateTeamMember,
  type StoreView,
  type TeamAssignment,
  type TeamMember,
} from "../../../lib/api";
import { useLanguage } from "../../../lib/i18n";

export default function TeamPage() {
  const en = useLanguage() === "en";
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [stores, setStores] = useState<StoreView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyMemberId, setBusyMemberId] = useState<string | null>(null);
  const [newRole, setNewRole] = useState("agent");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "disabled">("all");
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [people, storeItems] = await Promise.all([listTeam(), listStores()]);
      setMembers(people);
      setStores(storeItems);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : en ? "Failed to load team" : "团队加载失败");
    } finally {
      setLoading(false);
    }
  }, [en]);

  useEffect(() => {
    void load();
  }, [load]);

  function assignment(role: string, storeId: string): TeamAssignment[] {
    return role === "admin"
      ? [{ role: "admin", store_id: null }]
      : [{ role: role as "supervisor" | "agent", store_id: storeId }];
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    try {
      await createTeamMember({
        name: String(data.get("name")),
        email: String(data.get("email")),
        temporary_password: String(data.get("temporary_password")),
        assignments: assignment(String(data.get("role")), String(data.get("store_id"))),
      });
      form.reset();
      setNewRole("agent");
      setShowCreate(false);
      setNotice(en ? "Employee created; send the temporary password through a secure channel" : "员工已创建，请通过安全渠道发送临时密码");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : en ? "Creation failed" : "创建失败");
    }
  }

  async function changeRole(member: TeamMember, role: string) {
    const storeId = member.assignments.find((item) => item.store_id)?.store_id ?? stores[0]?.id ?? "";
    try {
      await updateTeamMember(member.id, { assignments: assignment(role, storeId) });
      setNotice(en ? "Role scope updated" : "角色范围已更新");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : en ? "Update failed" : "更新失败");
    }
  }

  async function changeStore(member: TeamMember, storeId: string) {
    const role = member.assignments[0]?.role ?? "agent";
    if (role === "admin") return;
    try {
      await updateTeamMember(member.id, { assignments: assignment(role, storeId) });
      setNotice(en ? "Store scope updated" : "店铺范围已更新");
      await load();
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : en ? "Update failed" : "更新失败");
    }
  }

  async function disable(member: TeamMember) {
    if (!window.confirm(en ? `Disable ${member.name}?` : `确认禁用 ${member.name}？`)) return;
    setBusyMemberId(member.id);
    setNotice("");
    try {
      await disableTeamMember(member.id);
      await load();
      setNotice(en ? `${member.name} is disabled` : `${member.name} 已禁用`);
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : en ? "Disable failed" : "禁用失败");
    } finally {
      setBusyMemberId(null);
    }
  }

  async function remove(member: TeamMember) {
    const confirmed = window.confirm(
      en
        ? `Permanently delete ${member.name}? This action cannot be undone.`
        : `永久删除 ${member.name}？此操作不可恢复。`,
    );
    if (!confirmed) return;
    setBusyMemberId(member.id);
    setNotice("");
    try {
      await deleteTeamMember(member.id);
      await load();
      setNotice(en ? `${member.name} was permanently deleted` : `${member.name} 已永久删除`);
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : en ? "Deletion failed" : "删除失败");
    } finally {
      setBusyMemberId(null);
    }
  }

  const activeCount = members.filter((member) => member.status === "active").length;
  const filtered = useMemo(() => members.filter((member) =>
    (statusFilter === "all" || member.status === statusFilter)
    && `${member.name} ${member.email}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())
  ), [members, query, statusFilter]);

  return <SettingsFrame title={en ? "Account management" : "账号管理"} description={en ? "System administrators can manage employee accounts, roles and store access." : "系统级管理员可管理员工账号、角色及店铺范围。"}>
    {notice ? <div className="inline-status" role="status">{notice}</div> : null}
    <section className="settings-card">
      <div className="settings-card-heading"><div><h2>{en ? "Employee accounts" : "员工账号"}</h2><p>{en ? `${members.length} accounts · ${activeCount} active` : `总账号 ${members.length} 位 · 启用 ${activeCount} 位`}</p></div><button className="primary-button" onClick={() => setShowCreate((value) => !value)} type="button"><Plus size={16} />{en ? "New account" : "新建账号"}</button></div>
      {showCreate ? <form className="settings-create-form" onSubmit={(event) => void submit(event)}>
        <label className="field-label">{en ? "Name" : "昵称"}<input className="compact-field" name="name" required /></label>
        <label className="field-label">{en ? "Email" : "登录邮箱"}<input className="compact-field" name="email" required type="email" /></label>
        <label className="field-label">{en ? "Temporary password" : "临时密码"}<input autoComplete="new-password" className="compact-field" minLength={12} name="temporary_password" required type="password" /></label>
        <label className="field-label">{en ? "Role" : "角色"}<select className="compact-field" name="role" onChange={(event) => setNewRole(event.target.value)} value={newRole}><option value="agent">agent</option><option value="supervisor">supervisor</option><option value="admin">admin</option></select></label>
        {newRole !== "admin" ? <label className="field-label">{en ? "Store scope" : "店铺范围"}<select className="compact-field" name="store_id" required>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select></label> : null}
        <button className="primary-button" disabled={newRole !== "admin" && !stores.length} type="submit">{en ? "Create employee" : "创建员工"}</button>
        {!stores.length && newRole !== "admin" ? <Link className="text-button" href="/settings/stores">{en ? "Create store" : "创建店铺"}</Link> : null}
      </form> : null}
      <div className="settings-toolbar"><div className="settings-segments" aria-label={en ? "Account status" : "账号状态"}>{(["all", "active", "disabled"] as const).map((status) => <button aria-pressed={statusFilter === status} className={statusFilter === status ? "active" : ""} key={status} onClick={() => setStatusFilter(status)} type="button">{status === "all" ? (en ? "All" : "全部") : status === "active" ? (en ? "Active" : "启用") : (en ? "Disabled" : "已禁用")} ({status === "all" ? members.length : status === "active" ? activeCount : members.length - activeCount})</button>)}</div><div className="settings-toolbar-actions"><button aria-label={en ? "Refresh accounts" : "刷新账号"} className="settings-icon-button" onClick={() => void load()} type="button"><ArrowClockwise size={18} /></button><label className="settings-search"><MagnifyingGlass size={17} /><input aria-label={en ? "Search accounts" : "搜索账号"} onChange={(event) => setQuery(event.target.value)} placeholder={en ? "Search name or email" : "搜索昵称或邮箱"} value={query} /></label></div></div>
      {loading ? <LoadingState label={en ? "Loading team…" : "正在加载团队…"} /> : error ? <ErrorState message={error} retry={() => void load()} /> : filtered.length ? <div className="settings-table-wrap"><table className="settings-table"><thead><tr><th>{en ? "Account" : "登录账号"}</th><th>{en ? "Nickname" : "昵称"}</th><th>{en ? "Status" : "状态"}</th><th>{en ? "Role" : "角色"}</th><th>{en ? "Store scope" : "店铺范围"}</th><th>{en ? "Last login" : "最近登录"}</th><th>{en ? "Actions" : "操作"}</th></tr></thead><tbody>{filtered.map((member) => {
        const isBusy = busyMemberId === member.id;
        const isDisabled = member.status === "disabled";
        const currentRole = member.assignments[0]?.role ?? "agent";
        return <tr key={member.id}><td>{member.email}</td><td><strong>{member.name}</strong></td><td><span className={`status-badge ${member.status}`}>{isDisabled ? (en ? "Disabled" : "已禁用") : (en ? "Active" : "启用中")}</span></td><td><select aria-label={en ? `Change ${member.name}'s role` : `调整 ${member.name} 角色`} className="compact-field" disabled={isDisabled || isBusy} onChange={(event) => void changeRole(member, event.target.value)} value={currentRole}><option value="admin">admin</option><option value="supervisor">supervisor</option><option value="agent">agent</option></select></td><td>{currentRole === "admin" ? (en ? "All stores" : "全部店铺") : <select aria-label={en ? `Change ${member.name}'s store scope` : `调整 ${member.name} 店铺范围`} className="compact-field" disabled={isDisabled || isBusy} onChange={(event) => void changeStore(member, event.target.value)} value={member.assignments[0]?.store_id ?? stores[0]?.id ?? ""}>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select>}</td><td>{member.last_login_at ? new Date(member.last_login_at).toLocaleString(en ? "en-US" : "zh-CN") : (en ? "Never" : "从未")}</td><td>{isDisabled ? <button className="text-button" disabled={isBusy} onClick={() => void remove(member)} type="button">{isBusy ? (en ? "Deleting…" : "删除中…") : (en ? "Delete" : "删除")}</button> : <button className="text-button" disabled={isBusy} onClick={() => void disable(member)} type="button">{isBusy ? (en ? "Disabling…" : "禁用中…") : (en ? "Disable" : "禁用")}</button>}</td></tr>;
      })}</tbody></table></div> : <EmptyState label={query || statusFilter !== "all" ? (en ? "No matching accounts" : "没有符合条件的账号") : (en ? "No team members" : "暂无团队成员")} />}
    </section>
  </SettingsFrame>;
}
