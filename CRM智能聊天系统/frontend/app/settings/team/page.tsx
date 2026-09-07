"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { AppShell } from "../../../components/AppShell";
import { SettingsNav } from "../../../components/SettingsNav";
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

  return (
    <AppShell>
      <main className="management-page">
        <section className="page-intro">
          <div>
            <p className="eyebrow">SYSTEM SETTINGS</p>
            <h2>{en ? "Team management" : "团队管理"}</h2>
            <p>
              {en
                ? "Only system administrators may create, reassign, disable or delete employees."
                : "创建、角色调整、禁用和删除只允许系统级管理员执行。"}
            </p>
          </div>
        </section>

        <SettingsNav />
        {notice ? <div className="inline-status" role="status">{notice}</div> : null}

        <section className="grid gap-4 xl:grid-cols-[1fr_380px]">
          <article className="management-card">
            <h3>{en ? "Team members" : "团队成员"}</h3>
            {loading ? (
              <LoadingState label={en ? "Loading team…" : "正在加载团队…"} />
            ) : error ? (
              <ErrorState message={error} retry={() => void load()} />
            ) : members.length ? (
              <div className="data-list">
                {members.map((member) => {
                  const isBusy = busyMemberId === member.id;
                  const isDisabled = member.status === "disabled";
                  return (
                    <div className="data-row" key={member.id}>
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <strong>{member.name}</strong>
                          <span className={`status-badge ${member.status}`}>
                            {isDisabled ? (en ? "Disabled" : "已禁用") : (en ? "Active" : "正常")}
                          </span>
                        </div>
                        <p>
                          {member.email} · {member.assignments.map((item) => `${item.role}${item.store_id ? `@${stores.find((store) => store.id === item.store_id)?.name ?? item.store_id.slice(0, 8)}` : ""}`).join(", ")} · {en ? "Last login" : "最近登录"} {member.last_login_at ? new Date(member.last_login_at).toLocaleString(en ? "en-US" : "zh-CN") : (en ? "Never" : "从未")}
                        </p>
                      </div>
                      <div className="row-actions">
                        <select
                          aria-label={en ? `Change ${member.name}'s role` : `调整 ${member.name} 角色`}
                          className="compact-field"
                          value={member.assignments[0]?.role ?? "agent"}
                          onChange={(event) => void changeRole(member, event.target.value)}
                          disabled={isDisabled || isBusy}
                        >
                          <option value="admin">admin</option>
                          <option value="supervisor">supervisor</option>
                          <option value="agent">agent</option>
                        </select>
                        {member.assignments[0]?.role !== "admin" ? (
                          <select
                            aria-label={en ? `Change ${member.name}'s store scope` : `调整 ${member.name} 店铺范围`}
                            className="compact-field"
                            value={member.assignments[0]?.store_id ?? stores[0]?.id ?? ""}
                            onChange={(event) => void changeStore(member, event.target.value)}
                            disabled={isDisabled || isBusy}
                          >
                            {stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}
                          </select>
                        ) : null}
                        {isDisabled ? (
                          <button className="danger-button" disabled={isBusy} type="button" onClick={() => void remove(member)}>
                            {isBusy ? (en ? "Deleting…" : "删除中…") : (en ? "Delete" : "删除")}
                          </button>
                        ) : (
                          <button className="text-button" disabled={isBusy} type="button" onClick={() => void disable(member)}>
                            {isBusy ? (en ? "Disabling…" : "禁用中…") : (en ? "Disable" : "禁用")}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState label={en ? "No team members" : "暂无团队成员"} />
            )}
          </article>

          <form className="management-card space-y-4" onSubmit={(event) => void submit(event)}>
            <h3>{en ? "Add employee" : "新增员工"}</h3>
            <label className="field-label">{en ? "Name" : "姓名"}<input className="compact-field" name="name" required /></label>
            <label className="field-label">{en ? "Email" : "邮箱"}<input className="compact-field" name="email" type="email" required /></label>
            <label className="field-label">{en ? "Temporary password" : "临时密码"}<input className="compact-field" name="temporary_password" type="password" minLength={12} required autoComplete="new-password" /></label>
            <label className="field-label">{en ? "Role" : "角色"}<select className="compact-field" name="role"><option value="agent">agent</option><option value="supervisor">supervisor</option><option value="admin">admin</option></select></label>
            <label className="field-label">
              {en ? "Store scope" : "店铺范围"}
              <select className="compact-field" name="store_id">{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select>
              <small>{en ? "admin automatically uses system-wide scope." : "admin 将自动使用系统级范围。"}</small>
            </label>
            <button className="primary-button" type="submit">{en ? "Create employee" : "创建员工"}</button>
          </form>
        </section>
      </main>
    </AppShell>
  );
}
