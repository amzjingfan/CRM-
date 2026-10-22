"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ArrowClockwise, MagnifyingGlass, Plus, X } from "@phosphor-icons/react";
import { SettingsFrame } from "../../../../components/SettingsFrame";
import { EmptyState, ErrorState, LoadingState } from "../../../../components/States";
import { addDepartmentMember, createDepartment, listDepartmentMembers, listDepartments, listStores, listTeam, removeDepartmentMember, updateDepartment, type Department, type StoreView, type TeamMember } from "../../../../lib/api";

const roleNames: Record<string, string> = { admin: "管理员", supervisor: "主管", agent: "客服" };

export default function DepartmentsPage() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [stores, setStores] = useState<StoreView[]>([]);
  const [accounts, setAccounts] = useState<TeamMember[]>([]);
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [editor, setEditor] = useState<"create" | "edit" | "add" | null>(null);
  const [removeTarget, setRemoveTarget] = useState<TeamMember | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [items, shops, people] = await Promise.all([listDepartments(), listStores(), listTeam()]);
      setDepartments(items); setStores(shops); setAccounts(people);
      setSelectedId((value) => items.some((item) => item.id === value) ? value : items[0]?.id ?? "");
      setError("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "部门加载失败"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!selectedId) { setMembers([]); return; }
    void listDepartmentMembers(selectedId).then(setMembers).catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "成员加载失败"));
  }, [selectedId, departments]);

  const selected = departments.find((item) => item.id === selectedId);
  const filtered = useMemo(() => members.filter((item) => (item.login_name ?? item.email ?? "").toLocaleLowerCase().includes(query.toLocaleLowerCase())), [members, query]);
  const available = accounts.filter((item) => selected && !item.department_ids.includes(selected.id) && item.status === "active" && item.assignments.some((assignment) => assignment.store_id === null || selected.store_ids.includes(assignment.store_id)));

  async function saveDepartment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const storeIds = data.getAll("store_ids").map(String);
    if (!storeIds.length) { setNotice("请至少选择一个负责店铺"); return; }
    setBusy(true); setNotice("");
    try {
      const payload = { name: String(data.get("name")), store_ids: storeIds };
      if (editor === "edit" && selected) await updateDepartment(selected.id, payload);
      else { const created = await createDepartment(payload); setSelectedId(created.id); }
      setEditor(null); setNotice("部门已保存"); await load();
    } catch (caught) { setNotice(caught instanceof Error ? caught.message : "部门保存失败"); }
    finally { setBusy(false); }
  }

  async function addMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedId) return;
    setBusy(true); setNotice("");
    try { await addDepartmentMember(selectedId, String(new FormData(event.currentTarget).get("user_id"))); setEditor(null); setNotice("成员已加入部门"); await load(); }
    catch (caught) { setNotice(caught instanceof Error ? caught.message : "添加成员失败"); }
    finally { setBusy(false); }
  }

  async function removeMember() {
    if (!selectedId || !removeTarget) return;
    setBusy(true); setNotice("");
    try { await removeDepartmentMember(selectedId, removeTarget.id); setRemoveTarget(null); setNotice("成员已移出部门，账号角色和店铺权限保持不变"); await load(); }
    catch (caught) { setNotice(caught instanceof Error ? caught.message : "移出部门失败"); }
    finally { setBusy(false); }
  }

  return <SettingsFrame title="部门管理" description="管理部门、负责店铺和部门账号；部门归属不改变登录权限。">
    {notice ? <div className="inline-status" role="status">{notice}</div> : null}
    {loading ? <LoadingState label="正在加载部门…" /> : error ? <ErrorState message={error} retry={() => void load()} /> : <div className="department-layout">
      <section className="settings-card department-list"><div className="settings-card-heading"><div><h2>部门</h2><p>共 {departments.length} 个</p></div><button aria-label="新建部门" className="settings-icon-button" onClick={() => setEditor("create")} type="button"><Plus size={18} /></button></div><nav aria-label="部门列表">{departments.map((department) => <button aria-current={selectedId === department.id ? "true" : undefined} className={selectedId === department.id ? "department-link active" : "department-link"} key={department.id} onClick={() => setSelectedId(department.id)} type="button">{department.name}<small>{department.store_ids.length} 个店铺</small></button>)}</nav>{!departments.length ? <EmptyState label="暂无部门，点击右上角新建" /> : null}</section>
      <section className="settings-card department-detail">{selected ? <><div className="settings-card-heading"><div><h2>{selected.name}</h2><p>负责店铺：{selected.store_ids.map((id) => stores.find((store) => store.id === id)?.name ?? id).join("、")}</p></div><button className="secondary-button" onClick={() => setEditor("edit")} type="button">编辑部门</button></div><div className="settings-segments department-tabs"><button aria-pressed="true" className="active" type="button">部门账号 ({members.length})</button><button disabled title="角色权限规则待确定" type="button">部门角色 · 待定</button><button disabled title="咨询分配规则待确定" type="button">部门店铺咨询分配 · 待定</button></div><div className="settings-toolbar"><label className="settings-search"><MagnifyingGlass size={17} /><input aria-label="搜索部门账号" onChange={(event) => setQuery(event.target.value)} placeholder="输入登录账号搜索" value={query} /></label><div className="settings-toolbar-actions"><button aria-label="刷新部门账号" className="settings-icon-button" onClick={() => void load()} type="button"><ArrowClockwise size={18} /></button><button className="primary-button" onClick={() => setEditor("add")} type="button"><Plus size={16} />加入账号</button></div></div>{filtered.length ? <div className="settings-table-wrap"><table className="settings-table department-table"><thead><tr><th>登录账号</th><th>昵称</th><th>手机号码</th><th>状态</th><th>角色</th><th>操作</th></tr></thead><tbody>{filtered.map((member) => <tr key={member.id}><td>{member.login_name ?? member.email ?? "—"}</td><td>{member.name}</td><td>{member.phone || "—"}</td><td><span className={`status-badge ${member.status}`}>{member.status === "active" ? "启用中" : "已停用"}</span></td><td>{[...new Set(member.assignments.map((assignment) => roleNames[assignment.role] ?? assignment.role))].join("、")}</td><td className="department-actions"><button disabled title="待角色权限规则确定" type="button">切换角色</button><button disabled title="待角色权限规则确定" type="button">修改权限</button><button onClick={() => setRemoveTarget(member)} type="button">移出部门</button></td></tr>)}</tbody></table></div> : <EmptyState label={query ? "没有符合条件的部门账号" : "该部门暂无账号"} />}</> : <EmptyState label="先创建部门并分配店铺" />}</section>
    </div>}
    {editor || removeTarget ? <div className="account-drawer-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) { setEditor(null); setRemoveTarget(null); } }}><aside aria-label={removeTarget ? "移出部门" : editor === "add" ? "加入账号" : editor === "edit" ? "编辑部门" : "新建部门"} aria-modal="true" className="account-drawer" role="dialog"><header><div><h2>{removeTarget ? "移出部门" : editor === "add" ? "加入账号" : editor === "edit" ? "编辑部门" : "新建部门"}</h2></div><button aria-label="关闭" className="settings-icon-button" onClick={() => { setEditor(null); setRemoveTarget(null); }} type="button"><X size={18} /></button></header>{notice ? <div className="inline-status" role="alert">{notice}</div> : null}{removeTarget ? <div className="account-drawer-form"><div className="account-drawer-fields">确认将“{removeTarget.name}”移出“{selected?.name}”？账号本身及原有权限不会删除。</div><footer><button className="secondary-button" onClick={() => setRemoveTarget(null)} type="button">取消</button><button className="primary-button" disabled={busy} onClick={() => void removeMember()} type="button">确认移出</button></footer></div> : editor === "add" ? <form className="account-drawer-form" onSubmit={(event) => void addMember(event)}><div className="account-drawer-fields"><label className="field-label">选择账号<select className="compact-field" name="user_id" required>{available.map((member) => <option key={member.id} value={member.id}>{member.login_name ?? member.email} · {member.name}</option>)}</select></label>{!available.length ? <p>没有可加入的账号；请先创建与本部门店铺匹配的账号。</p> : null}</div><footer><button className="secondary-button" onClick={() => setEditor(null)} type="button">取消</button><button className="primary-button" disabled={busy || !available.length} type="submit">确认加入</button></footer></form> : <form className="account-drawer-form" onSubmit={(event) => void saveDepartment(event)}><div className="account-drawer-fields"><label className="field-label">部门名称<input className="compact-field" defaultValue={editor === "edit" ? selected?.name : ""} maxLength={100} name="name" required /></label><fieldset className="department-store-options"><legend>负责店铺</legend>{stores.map((store) => <label key={store.id}><input defaultChecked={editor === "edit" && selected?.store_ids.includes(store.id)} name="store_ids" type="checkbox" value={store.id} />{store.name}</label>)}</fieldset></div><footer><button className="secondary-button" onClick={() => setEditor(null)} type="button">取消</button><button className="primary-button" disabled={busy || !stores.length} type="submit">保存</button></footer></form>}</aside></div> : null}
  </SettingsFrame>;
}
