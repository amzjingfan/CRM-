"use client";

import { useState } from "react";
import type { StoreView, TeamMember } from "../../../../lib/api";

type Role = "admin" | "supervisor" | "agent";
type Props = {
  members: TeamMember[];
  stores: StoreView[];
  storeIds: string[];
  storeId: string;
  onStoreChange: (id: string) => void;
  drafts: Record<string, string>;
  onDraftChange: (id: string, role: string) => void;
  onSave: (member: TeamMember) => void;
  editable: boolean;
  busy: boolean;
};

const roles: { code: Role; name: string; description: string; mode: string; permissions: string[] }[] = [
  { code: "admin", name: "系统管理员", description: "管理账号、部门和店铺授权，并监督全部获授权会话。", mode: "监督全部店铺", permissions: ["账号与部门管理", "店铺授权", "配置自动派单", "查看、回复、转交及关闭会话"] },
  { code: "supervisor", name: "客服主管", description: "监督获授权店铺的会话，分配、转交及关闭会话。", mode: "监督授权店铺", permissions: ["查看本店全部会话", "分配与转交", "关闭会话", "默认无回复权限"] },
  { code: "agent", name: "普通客服", description: "领取待分配会话，回复及转交本人负责的会话。", mode: "可参与智能分配", permissions: ["领取待分配会话", "回复本人会话", "转交和关闭本人会话"] },
];

function roleForStore(member: TeamMember, storeId: string): Role | null {
  if (member.assignments.some((assignment) => assignment.role === "admin" && assignment.store_id === null)) return "admin";
  const role = member.assignments.find((assignment) => assignment.store_id === storeId)?.role;
  return role === "admin" || role === "supervisor" || role === "agent" ? role : null;
}

export function RolePanel({ members, stores, storeIds, storeId, onStoreChange, drafts, onDraftChange, onSave, editable, busy }: Props) {
  const [selectedRole, setSelectedRole] = useState<Role | null>(null);
  const current = roles.find((item) => item.code === selectedRole);
  return <div className="department-panel">
    <div className="department-panel-toolbar">
      <span>共 {roles.length} 个固定角色</span>
      <label>查看店铺 <select aria-label="查看角色店铺" className="compact-field" onChange={(event) => onStoreChange(event.target.value)} value={storeId}>{storeIds.map((id) => <option key={id} value={id}>{stores.find((store) => store.id === id)?.name ?? id}</option>)}</select></label>
    </div>
    <div className="settings-table-wrap"><table className="settings-table department-summary-table"><thead><tr><th>角色名称</th><th>角色描述</th><th>应用账号数</th><th>分配模式</th><th>操作</th></tr></thead><tbody>{roles.map((role) => <tr key={role.code}><td>{role.name} <span className="department-official-badge">固定</span></td><td>{role.description}</td><td>{members.filter((member) => roleForStore(member, storeId) === role.code).length}</td><td>{role.mode}</td><td><button aria-label={`查看${role.name}权限`} className="department-link-button" onClick={() => setSelectedRole(selectedRole === role.code ? null : role.code)} type="button">{selectedRole === role.code ? "收起" : "查看"}</button></td></tr>)}</tbody></table></div>
    {current ? <section aria-label={`${current.name}权限详情`} className="department-role-detail"><div className="department-panel-toolbar"><h3>{current.name}权限</h3><button className="department-link-button" onClick={() => setSelectedRole(null)} type="button">收起</button></div><ul className="department-permissions">{current.permissions.map((permission) => <li key={permission}>{permission}</li>)}</ul><p>部门归属不会授予店铺权限；角色按账号逐店设置。</p>{selectedRole !== "admin" ? <div className="settings-table-wrap"><table className="settings-table"><thead><tr><th>客服</th><th>当前店铺角色</th><th>调整</th></tr></thead><tbody>{members.map((member) => { const role = roleForStore(member, storeId); return <tr key={member.id}><td>{member.name}</td><td>{roles.find((item) => item.code === role)?.name ?? "无本店授权"}</td><td>{editable && role !== "admin" ? <div className="department-role-editor"><select aria-label={`${member.name}店铺角色`} className="compact-field" onChange={(event) => onDraftChange(member.id, event.target.value)} value={drafts[member.id] ?? role ?? ""}><option value="">选择角色</option><option value="agent">普通客服</option><option value="supervisor">客服主管</option></select><button className="secondary-button" disabled={busy || !drafts[member.id] || drafts[member.id] === role} onClick={() => onSave(member)} type="button">保存</button></div> : "只读"}</td></tr>; })}</tbody></table></div> : null}</section> : null}
  </div>;
}
