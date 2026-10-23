import { requestApi } from "./api";

export type ReceptionScope = "personal" | "team";
export type ReceptionKind = "timeout" | "welcome";
export type ReceptionPage<T> = { items: T[]; total: number; page: number; page_size: number };

export type QuickReplyGroup = {
  id: string;
  store_id: string;
  scope: ReceptionScope;
  owner_user_id: string | null;
  name: string;
  enabled: boolean;
  reply_count: number;
  sort_order: number;
};

export type QuickReply = {
  id: string;
  store_id: string;
  scope: ReceptionScope;
  owner_user_id: string | null;
  group_id: string;
  shortcut: string;
  tags: string[];
  site_code: string | null;
  messages: string[];
  sort_order: number;
};

export type ReceptionPolicy = {
  id: string;
  kind: ReceptionKind;
  name: string;
  content: string;
  timeout_minutes: number | null;
  valid_from: string | null;
  valid_to: string | null;
  enabled: boolean;
  sort_order: number;
  store_ids: string[];
  delivery_enabled: false;
};

export type NewQuickReplyGroup = Pick<QuickReplyGroup, "store_id" | "scope" | "name"> & { sort_order?: number };
export type NewQuickReply = Pick<QuickReply, "store_id" | "scope" | "group_id" | "shortcut" | "tags" | "site_code" | "messages"> & { sort_order?: number };
export type NewReceptionPolicy = Pick<ReceptionPolicy, "kind" | "name" | "content" | "timeout_minutes" | "valid_from" | "valid_to" | "enabled" | "store_ids"> & { sort_order?: number };

const base = "/marketing/reception";
const itemPath = (collection: string, id: string) => `${base}/${collection}/${encodeURIComponent(id)}`;
const listPath = (collection: string, params: URLSearchParams) => `${base}/${collection}?${params}`;

export function listQuickReplyGroups(storeId: string, scope: ReceptionScope, page = 1) {
  return requestApi<ReceptionPage<QuickReplyGroup>>(listPath("groups", new URLSearchParams({ store_id: storeId, scope, page: String(page), page_size: "100" })));
}

export async function listAllQuickReplyGroups(storeId: string, scope: ReceptionScope): Promise<QuickReplyGroup[]> {
  const groups: QuickReplyGroup[] = [];
  for (let page = 1; ; page += 1) {
    const result = await listQuickReplyGroups(storeId, scope, page);
    groups.push(...result.items);
    if (groups.length >= result.total || result.items.length === 0) return groups;
  }
}

export function createQuickReplyGroup(payload: NewQuickReplyGroup) {
  return requestApi<QuickReplyGroup>(`${base}/groups`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateQuickReplyGroup(id: string, payload: Partial<Pick<QuickReplyGroup, "name" | "enabled" | "sort_order">>) {
  return requestApi<QuickReplyGroup>(itemPath("groups", id), { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteQuickReplyGroup(id: string) {
  return requestApi<void>(itemPath("groups", id), { method: "DELETE" });
}

export function listQuickReplies(storeId: string, scope: ReceptionScope, options: { groupId?: string; q?: string; shortcut?: string; page?: number; pageSize?: number; includeDisabled?: boolean } = {}) {
  const params = new URLSearchParams({ store_id: storeId, scope, page: String(options.page ?? 1), page_size: String(options.pageSize ?? 100) });
  if (options.groupId) params.set("group_id", options.groupId);
  if (options.q?.trim()) params.set("q", options.q.trim());
  if (options.shortcut) params.set("shortcut", options.shortcut);
  if (options.includeDisabled) params.set("include_disabled", "true");
  return requestApi<ReceptionPage<QuickReply>>(listPath("replies", params));
}

export async function resolveQuickReplyShortcut(storeId: string, shortcut: string): Promise<QuickReply | null> {
  const normalized = shortcut.trim().toLowerCase();
  if (!/^[a-z0-9]{1,8}$/.test(normalized)) return null;
  for (const scope of ["personal", "team"] as const) {
    const page = await listQuickReplies(storeId, scope, { shortcut: normalized, pageSize: 1 });
    if (page.items[0]) return page.items[0];
  }
  return null;
}

export function createQuickReply(payload: NewQuickReply) {
  return requestApi<QuickReply>(`${base}/replies`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateQuickReply(id: string, payload: Partial<Pick<QuickReply, "group_id" | "shortcut" | "tags" | "site_code" | "messages" | "sort_order">>) {
  return requestApi<QuickReply>(itemPath("replies", id), { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteQuickReply(id: string) {
  return requestApi<void>(itemPath("replies", id), { method: "DELETE" });
}

export function listReceptionPolicies(storeId: string, kind: ReceptionKind, page = 1) {
  return requestApi<ReceptionPage<ReceptionPolicy>>(listPath("policies", new URLSearchParams({ store_id: storeId, kind, page: String(page), page_size: "100" })));
}

export function createReceptionPolicy(payload: NewReceptionPolicy) {
  return requestApi<ReceptionPolicy>(`${base}/policies`, { method: "POST", body: JSON.stringify(payload) });
}

export function updateReceptionPolicy(id: string, payload: Partial<Omit<NewReceptionPolicy, "kind">>) {
  return requestApi<ReceptionPolicy>(itemPath("policies", id), { method: "PATCH", body: JSON.stringify(payload) });
}

export function deleteReceptionPolicy(id: string) {
  return requestApi<void>(itemPath("policies", id), { method: "DELETE" });
}
