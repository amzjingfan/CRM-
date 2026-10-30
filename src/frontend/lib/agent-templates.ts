import { createIdempotencyKey, requestApi, type AgentToolMetadata } from "./api";

export type KnowledgeSlot = { key: string; name: string; purpose: string; required: boolean };
export type TemplateConfig = {
  default_agent_name: string; suggested_code: string; agent_type: "service" | "operations"; description: string | null;
  model_provider: string | null; model_name: string | null; prompt_sections: Record<string, string>;
  tool_names: string[]; knowledge_slots: KnowledgeSlot[];
};
export type AgentTemplate = {
  id: string; code: string; name: string; description: string | null; draft_revision: number | null;
  published_version: number | null; archived_at: string | null; config: TemplateConfig | null;
  published_config: TemplateConfig | null; can_manage: boolean; linked_store_count: number; update_count: number;
  created_at: string; updated_at: string;
};
export type TemplateVersion = { version: number; config: TemplateConfig; content_sha256: string; published_at: string };
export type TemplateCatalog = {
  model_options: { provider: string; model_name: string }[]; prompt_sections: { key: string; title: string }[];
  groups: { key: string; title: string; description: string }[];
  tools: Omit<AgentToolMetadata, "availability" | "reason" | "missing_scopes">[];
};
export type TemplateCreate = { code: string; name: string; description?: string | null; config?: TemplateConfig };
export type TemplateFromAgent = { code: string; name: string; description: string | null; source_agent_id: string; source_version: number | null; source_draft_revision: number | null; knowledge_slots: KnowledgeSlot[] };
const root = "/agents/templates";
const path = (id: string) => `${root}/${encodeURIComponent(id)}`;
const write = <T>(url: string, body: unknown, method = "POST") => requestApi<T>(url, { method, headers: { "Idempotency-Key": createIdempotencyKey() }, body: JSON.stringify(body) });
export const listAgentTemplates = (includeArchived = false) => requestApi<{ items: AgentTemplate[]; can_manage: boolean }>(`${root}?include_archived=${includeArchived}`);
export const getAgentTemplate = (id: string) => requestApi<AgentTemplate>(path(id));
export const getAgentTemplateCatalog = () => requestApi<TemplateCatalog>(`${root}/catalog`);
export const listAgentTemplateVersions = (id: string) => requestApi<TemplateVersion[]>(`${path(id)}/versions`);
export const createAgentTemplate = (payload: TemplateCreate) => write<AgentTemplate>(root, payload);
export const createAgentTemplateFromAgent = (payload: TemplateFromAgent) => write<AgentTemplate>(`${root}/from-agent`, payload);
export const updateAgentTemplate = (id: string, payload: { expected_revision: number; name: string; description: string | null; config: TemplateConfig }) => write<AgentTemplate>(path(id), payload, "PATCH");
export const publishAgentTemplate = (id: string, revision: number) => write<AgentTemplate>(`${path(id)}/publish`, { expected_revision: revision });
export const archiveAgentTemplate = (id: string, revision: number) => write<AgentTemplate>(`${path(id)}/archive`, { expected_revision: revision });
export const restoreAgentTemplate = (id: string, revision: number) => write<AgentTemplate>(`${path(id)}/restore`, { expected_revision: revision });

export type Pagination = { page: number; page_size: number; total: number; total_pages: number };
export type ApplicationAgentOption = { id: string; name: string; code: string; template_id: string | null; draft_revision: number; published_version: number | null; status: string };
export type ApplicationStoreOption = { id: string; name: string; code: string; can_view_knowledge: boolean; agents: ApplicationAgentOption[] };
export type KnowledgeFileOption = { id: string; name: string; active_version_number: number | null; status: string | null; publication_approval: string | null; can_publish: boolean };
export type Page<T> = { items: T[]; pagination: Pagination };
export type FieldValue = string | null | { provider: string | null; name: string | null } | string[] | KnowledgeSlot[];
export type FieldDecision = { choice: "template" | "local" } | { choice: "manual"; value: FieldValue };
export type ApplicationItemRequest = {
  store_id: string; action: "create" | "adopt" | "update"; agent_id?: string; expected_revision?: number;
  fields: Record<string, FieldDecision> | null; knowledge_mappings: Record<string, string[]>; unbind_removed_file_ids: string[];
  name?: string; code?: string; include_existing_draft: boolean; publish: boolean; enable_after_publish: boolean;
};
export type ApplicationPreviewRequest = { template_version: number; items: ApplicationItemRequest[]; parent_batch_id?: string };
export type ApplicationIssue = { code: string; message: string; field: string | null };
export type FieldDiff = { field: string; baseline: FieldValue; local: FieldValue; target: FieldValue; status: "unchanged" | "template_changed" | "local_changed" | "converged" | "conflict"; default_choice: "skip" | "template" | "local" | "resolve" };
export type ApplicationItemView = {
  id: string; store_id: string; store_name: string; agent_id: string | null; action: ApplicationItemRequest["action"];
  valid: boolean; issues: ApplicationIssue[]; warnings: ApplicationIssue[]; diffs: FieldDiff[];
  published_snapshot: Record<string, unknown> | null; full_target: Record<string, unknown>; knowledge_slots: KnowledgeSlot[];
  mappings: Record<string, string[]>; has_existing_draft: boolean; field_choices: Record<string, FieldDecision>;
  flags: Record<string, boolean>; request: ApplicationItemRequest | null;
};
export type ApplicationPreview = { preview_id: string; preview_hash: string; template_id: string; template_version: number; items: ApplicationItemView[] };
export type BatchItem = { id: string; store_id: string | null; store_name: string; status: string; action: string | null; agent_id: string | null; old_published_version: number | null; result_agent_id: string | null; result_version: number | null; error_code: string | null; retryable: boolean; started_at: string | null; finished_at: string | null; attempt_count: number; preview: ApplicationItemView | null };
export type BatchSummary = { id: string; template_id: string; template_version: number; parent_batch_id: string | null; status: string; cancel_requested: boolean; counts: Record<string, number>; created_at: string; confirmed_at: string | null; finished_at: string | null; processor_enabled: boolean };
export type BatchView = BatchSummary & Page<BatchItem>;
export type TemplateFieldSource = { field: string; local_override: boolean; applied_template_version: number | null; last_reviewed_template_version: number | null; aligned: boolean; pending_review: boolean };
export type AgentTemplateSource = { agent_id: string; store_id: string; draft: { template_id: string; name: string; archived: boolean; target_template_version: number; draft_revision: number; fields: TemplateFieldSource[]; aligned_count: number; local_override_count: number; pending_review_count: number } | null; published: { version: number; template_source_json: Record<string, unknown> | null } | null };

const query = (page: number, pageSize: number, search?: string) => new URLSearchParams({ page: String(page), page_size: String(pageSize), ...(search === undefined ? {} : { search }) }).toString();
const batchRoot = "/agents/template-batches";
export const listApplicationStores = (page = 1, pageSize = 20, search = "") => requestApi<Page<ApplicationStoreOption>>(`${root}/application-stores?${query(page, pageSize, search)}`);
export const listApplicationKnowledgeFiles = (storeId: string, page = 1, pageSize = 20, search = "") => requestApi<Page<KnowledgeFileOption>>(`${root}/application-stores/${encodeURIComponent(storeId)}/knowledge-files?${query(page, pageSize, search)}`);
export const previewTemplateApplication = (id: string, payload: ApplicationPreviewRequest) => write<ApplicationPreview>(`${path(id)}/application-previews`, payload);
export const confirmTemplateBatch = (previewId: string, key: string) => requestApi<BatchView>(batchRoot, { method: "POST", headers: { "Idempotency-Key": key }, body: JSON.stringify({ preview_id: previewId, confirmation: true }) });
export const listTemplateBatches = (page = 1, pageSize = 20) => requestApi<Page<BatchSummary>>(`${batchRoot}?${query(page, pageSize)}`);
export const getTemplateBatch = (id: string, page = 1, pageSize = 50) => requestApi<BatchView>(`${batchRoot}/${encodeURIComponent(id)}?${query(page, pageSize)}`);
export const cancelTemplateBatch = (id: string) => write<BatchView>(`${batchRoot}/${encodeURIComponent(id)}/cancel`, {});
export const retryFailedTemplateBatch = (id: string) => write<BatchView>(`${batchRoot}/${encodeURIComponent(id)}/retry-failed`, {});
export const getAgentTemplateSource = (id: string) => requestApi<AgentTemplateSource>(`/agents/${encodeURIComponent(id)}/template-source`);
export const detachAgentTemplate = (id: string, revision: number) => write<unknown>(`/agents/${encodeURIComponent(id)}/detach-template`, { expected_revision: revision });
