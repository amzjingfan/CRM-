export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

export type UserView = { id: string; name: string; email: string; role: string; avatar: string | null; permissions: string[]; store_ids: string[] };
export type ApiResponse<T> = { code: number; message: string; data: T };
export type CustomerSummary = { id: string; name: string | null; email: string | null; avatar: string | null; tags: string[] };
export type SessionSummary = { id: string; store_id: string; platform: string; status: string; is_starred: boolean; closed_at: string | null; unread_count: number; assigned_user_id: string | null; last_message_at: string | null; last_message: string | null; customer: CustomerSummary };
export type SessionActionResult = Pick<SessionSummary, "status" | "is_starred" | "closed_at">;
export type SessionAssignee = { id: string; name: string };
export type MessageView = { id: string; role: "user" | "agent" | "assistant" | "system"; content: string; status: "received" | "processing" | "sent" | "delivered" | "failed" | "unknown"; created_at: string; error_code: string | null; delivery_mode: "inbound" | "mock" | "real" | "unknown" };
export type MessageTranslationView = { message_id: string; target_language: "zh-CN"; translated_text: string };
export type DraftTargetLanguage = "en" | "id" | "fil" | "ms" | "th" | "my" | "vi" | "pt" | "es" | "pl" | "fr" | "zh-TW" | "zh-CN";
export type DraftTranslationView = { source_text_sha256: string; target_language: DraftTargetLanguage; translated_text: string };
export type OrderSummary = { id: string; external_order_id: string; platform: string; status: string; currency: string; total_amount: string; tracking_number: string | null; tracking_status: string | null };
export type SidebarOrderItem = { name: string; product_id: string | null; sku: string | null; sku_id: string | null; sku_name: string | null; image_url: string | null; quantity: number; unit_price: string | null; total_amount: string | null };
export type SidebarOrder = { id: string; external_order_id: string; status: string; payment_status: string | null; currency: string; total_amount: string | null; payment_breakdown: Record<string, string>; ordered_at: string | null; tracking_number: string | null; tracking_status: string | null; items: SidebarOrderItem[]; live_detail_available: boolean };
export type SidebarOrderDetail = { payment_method_name: string | null; shipping_provider: string | null; latest_tracking_description: string | null; latest_tracking_at: string | null };
export type SidebarOrders = { items: SidebarOrder[]; pagination: { page: number; page_size: number; total: number } };
export type SidebarSku = { id: string; seller_sku: string | null; name: string | null; currency: string | null; sale_price: string | null; quantity: number | null };
export type SidebarProduct = { id: string; title: string; status: string | null; image_url: string | null; skus: SidebarSku[] };
export type SidebarProducts = { items: SidebarProduct[]; next_page_token: string | null; total_count: number | null; partial_search: boolean };
export type SidebarCoupon = { id: string; title: string; status: string | null; display_type: string | null; promo_code: string | null; discount_type: string | null; discount_value: string | null; claim_end_time: number | null; chat_shareable: boolean };
export type SidebarCoupons = { items: SidebarCoupon[]; next_page_token: string | null; total_count: number | null; partial_search: boolean };
export type SidebarSearch = { section: "orders" | "products" | "coupons"; field: string; query: string; status?: "all" | "unpaid" | "ship" | "transit" | "done" | "cancel"; page?: number; page_token?: string | null };
export type SessionListData = { items: SessionSummary[]; pagination: { page: number; page_size: number; total: number } };
export type SessionMessagesData = { session: SessionSummary; messages: MessageView[]; customer: CustomerSummary; recent_orders: OrderSummary[]; ai_suggestion: null; pagination: { page: number; page_size: number; total: number }; send_mode: "disabled" | "mock" | "real"; requires_confirmation: true; translation_enabled?: boolean; draft_translation_enabled?: boolean };
export type KnowledgeCategory = { id: string; store_id: string; parent_id: string | null; name: string; code: string; layer: string; sort_order: number; status: string };
export type KnowledgeStatementType = "policy" | "technical_artifact" | "customer_instance_fact" | "non_assertive_proposition" | "unknown";
export type KnowledgeCustomerScope = "none" | "generic" | "specific_customer";
export type KnowledgePublicationApproval = "draft" | "approved_for_internal_review" | "approved_for_public_reply";
export type KnowledgeEntry = { id: string; store_id: string; category_id: string | null; question: string; answer: string; source: string | null; tags: string[]; status: string; vectorization_status: string; document_version: number; usage_count: number; satisfaction_rate: number | null; statement_type: KnowledgeStatementType; customer_scope: KnowledgeCustomerScope; publication_approval: KnowledgePublicationApproval; semantic_schema_version: 1; approved_by: string | null; approved_at: string | null; published_at: string | null; created_at: string; updated_at: string };
export type KnowledgePage = { items: KnowledgeEntry[]; page: number; page_size: number; total: number };
export type KnowledgeVectorizationStatus = { store_id: string; worker_enabled: boolean; provider: "local_bge"; model: string; dimensions: 1024; counts: { pending: number; processing: number; ready: number; failed: number } };
export type ImportJob = { id: string; store_id: string; original_filename: string; status: string; total_rows: number; succeeded_rows: number; failed_rows: number; error_summary: Array<Record<string, unknown>>; created_at: string; completed_at: string | null };
export type Campaign = { id: string; store_id: string; name: string; trigger_type: string; action_type: string; content_mode: string; template_content: string | null; coupon_code: string | null; trigger_delay_minutes: number; cooldown_hours: number; max_contacts_30d: number; status: string; created_at: string; updated_at: string };
export type CampaignPage = { items: Campaign[]; page: number; page_size: number; total: number };
export type MarketingEvent = { id: string; store_id: string; campaign_id: string; customer_id: string | null; source_type: string; source_id: string; status: string; attempt_count: number; error_code: string | null; ai_draft_content: string | null; ai_draft_agent_run_id: string | null; ai_review_status: "pending" | "approved" | "rejected" | null; ai_reviewed_by: string | null; ai_reviewed_at: string | null; triggered_at: string; completed_at: string | null; converted_at: string | null };
export type MarketingEventPage = { items: MarketingEvent[]; page: number; page_size: number; total: number };
export type Logistics = { order_id: string; external_order_id: string; tracking_number: string | null; tracking_status: string | null; shipped_at: string | null; delivered_at: string | null };
export type StoreView = { id: string; name: string; code: string; status: string; timezone: string; currency: string; created_at: string };
export type ChannelView = { id: string; store_id: string; platform: string; external_store_id: string; display_name: string; status: string; scopes: string[]; last_sync_at: string | null; created_at: string };
export type TikTokOAuthStart = { authorization_url: string; expires_in: number };
export type TikTokOAuthJobStatus = { status: "pending" | "processing" | "connected" | "denied" | "failed" };
export type DashboardMetrics = { total_sessions: number; transfer_rate: number; avg_response_time: number | null; recovered_gmv: string; currency: string; period: "today" | "7d" | "30d"; updated_at: string | null };
export type DashboardTrend = { items: Array<{ date: string; sessions: number }> };
export type DashboardChannels = { items: Array<{ platform: string; count: number; percentage: number }> };
export type DashboardAlerts = { refund_requests: { total: number }; bad_reviews: { total: number; golden_window: boolean }; abandoned_carts: { total: number; potential_gmv: string } };
export type TopQuery = { rank: number; intent: string; count: number };
export type AgentRuntime = { available: boolean; llm_provider: string; llm_model: string | null; embedding_provider: string; embedding_model: string; reranker_model: string; prompt_versions: Record<string, string>; auto_reply_threshold: number; human_review_threshold: number; token_streaming: false };
export type AgentConfig = { id: string; store_id: string; name: string; code: string; description: string | null; status: "enabled" | "disabled"; enabled_tools: string[]; knowledge_scope: Record<string, unknown>; runtime: AgentRuntime; created_at: string; updated_at: string };
export type AgentRunLog = { id: string; status: string; action: string; intent: string | null; final_confidence: number | null; model_provider: string; model_name: string; prompt_version: string | null; latency_ms: number | null; input_tokens: number | null; output_tokens: number | null; error_code: string | null; trace_id: string | null; tool_calls: Array<{ id: string; tool_name: string; status: string; error_code: string | null; latency_ms: number | null; mocked: boolean }>; created_at: string };
export type AgentRunLogPage = { items: AgentRunLog[]; page: number; page_size: number; total: number };
export type TeamAssignment = { role: "admin" | "supervisor" | "agent"; store_id: string | null };
export type TeamMember = { id: string; name: string; email: string; status: "active" | "disabled"; assignments: TeamAssignment[]; last_login_at: string | null; created_at: string };
export type Suggestion = { agent_run_id: string; content: string | null; intent: string | null; confidence: number; action: string; terminal_state: string; requires_human: boolean; transfer_performed: boolean; send_performed: false; citations: Array<{ document_id: string; chunk_id: string; score: number; source_label: string }>; trace_id: string; demo_mode: boolean; demo_scenario: string | null };
export type ChatEvent = { event: "accepted" | "status" | "delta" | "result" | "error" | "done"; data: Record<string, unknown> };

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function isAuthenticationError(error: unknown): error is ApiError {
  return error instanceof ApiError && error.status === 401;
}

function getCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;
  const prefix = `${encodeURIComponent(name)}=`;
  return document.cookie.split(";").map((value) => value.trim()).find((value) => value.startsWith(prefix))?.slice(prefix.length);
}

export function createIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function withStableIdempotencyKey(init: RequestInit): RequestInit {
  const method = (init.method ?? "GET").toUpperCase();
  if (["GET", "HEAD", "OPTIONS"].includes(method)) return init;
  const headers = new Headers(init.headers);
  if (!headers.has("Idempotency-Key")) headers.set("Idempotency-Key", createIdempotencyKey());
  return { ...init, headers };
}

async function rawRequest(path: string, init: RequestInit = {}): Promise<Response> {
  const method = (init.method ?? "GET").toUpperCase();
  const csrf = !["GET", "HEAD", "OPTIONS"].includes(method) ? getCookie("crm_csrf_token") : undefined;
  const isForm = typeof FormData !== "undefined" && init.body instanceof FormData;
  const headers = new Headers(init.headers);
  if (!isForm && init.body !== undefined && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (csrf && !headers.has("X-CSRF-Token")) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  return fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });
}

export async function requestApi<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  // 同一次业务请求的 401 刷新重试必须复用原键，避免首个响应丢失后重复写入。
  const stableInit = withStableIdempotencyKey(init);
  let response = await rawRequest(path, stableInit);
  if (response.status === 401 && retry && path !== "/auth/browser/refresh") {
    const refreshed = await rawRequest("/auth/browser/refresh", { method: "POST" });
    if (refreshed.ok) response = await rawRequest(path, stableInit);
  }
  if (response.status === 204) return undefined as T;
  const body = (await response.json().catch(() => null)) as ApiResponse<T> | null;
  if (!response.ok || !body) {
    throw new ApiError(body?.message ?? "请求失败，请稍后重试", response.status, body?.code);
  }
  return body.data;
}

export const browserLogin = (email: string, password: string) => requestApi<{ expires_in: number; user: UserView }>("/auth/browser/login", { method: "POST", body: JSON.stringify({ email, password }) }, false);
export const currentUser = () => requestApi<UserView>("/auth/me");
export const logout = () => requestApi<{ logged_out: boolean }>("/auth/browser/logout", { method: "POST" }, false);
export const listSessions = (query: URLSearchParams) => {
  const terms = query.getAll("term");
  const search = query.get("q");
  if (!search && !terms.length) return requestApi<SessionListData>(`/workspace/sessions?${query.toString()}`);
  // 买家昵称和订单号留在请求体中，避免进入代理及浏览器的 URL 访问记录。
  return requestApi<SessionListData>("/workspace/sessions/search", {
    method: "POST",
    body: JSON.stringify({
      filter: query.get("filter") ?? "all",
      platform: query.get("platform"),
      store_id: query.get("store_id"),
      page: Number(query.get("page") ?? "1"),
      page_size: Number(query.get("page_size") ?? "30"),
      search_scope: query.get("search_scope") ?? "all",
      q: search,
      terms,
    }),
  });
};
export const getSessionMessagesPage = (sessionId: string, page: number) => requestApi<SessionMessagesData>(`/workspace/sessions/${sessionId}/messages?page=${page}&page_size=100`);
export const searchCustomerSidebar = <T extends SidebarOrders | SidebarProducts | SidebarCoupons>(sessionId: string, payload: SidebarSearch) => requestApi<T>(`/workspace/sessions/${encodeURIComponent(sessionId)}/sidebar/search`, { method: "POST", body: JSON.stringify(payload) });
export const getCustomerSidebarOrderDetail = (sessionId: string, orderId: string) => requestApi<SidebarOrderDetail>(`/workspace/sessions/${encodeURIComponent(sessionId)}/sidebar/orders/detail`, { method: "POST", body: JSON.stringify({ order_id: orderId }) });
export const getCustomerSidebarProduct = (sessionId: string, productId: string) => requestApi<SidebarProduct>(`/workspace/sessions/${encodeURIComponent(sessionId)}/sidebar/products/${encodeURIComponent(productId)}`);
export const getSessionMessages = async (sessionId: string): Promise<SessionMessagesData> => {
  const first = await getSessionMessagesPage(sessionId, 1);
  const newestPage = Math.ceil(first.pagination.total / first.pagination.page_size);
  return newestPage > 1 ? getSessionMessagesPage(sessionId, newestPage) : first;
};
export const sendMessage = (sessionId: string, content: string, idempotencyKey: string) => requestApi<MessageView>(`/workspace/sessions/${sessionId}/messages`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify({ content, confirmed: true }) });
export const translateMessage = (sessionId: string, messageId: string) => requestApi<MessageTranslationView>(`/workspace/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(messageId)}/translation`, { method: "POST" });
export const translateDraft = (sessionId: string, sourceText: string, targetLanguage: DraftTargetLanguage) => requestApi<DraftTranslationView>(`/workspace/sessions/${encodeURIComponent(sessionId)}/draft/translation`, { method: "POST", body: JSON.stringify({ source_text: sourceText, target_language: targetLanguage }) });
export const markSessionRead = (sessionId: string) => requestApi<{ unread_count: number }>(`/workspace/sessions/${sessionId}/read`, { method: "POST" });
export const setSessionStar = (sessionId: string, starred: boolean) => requestApi<SessionActionResult>(`/workspace/sessions/${sessionId}/star`, { method: "PATCH", body: JSON.stringify({ starred }) });
export const setSessionClosed = (sessionId: string, closed: boolean) => requestApi<SessionActionResult>(`/workspace/sessions/${sessionId}/closed`, { method: "PATCH", body: JSON.stringify({ closed }) });
export const listSessionAssignees = (sessionId: string) => requestApi<SessionAssignee[]>(`/workspace/sessions/${sessionId}/assignees`);
export const transferSession = (sessionId: string, reason: string, idempotencyKey: string, assignTo?: string) => requestApi<{ transfer_id: string; status: "transferred" }>(`/workspace/sessions/${sessionId}/transfer`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify({ reason, assign_to: assignTo ?? null }) });
export const listKnowledgeCategories = (storeId = "") => requestApi<KnowledgeCategory[]>(`/knowledge/categories${storeId ? `?store_id=${encodeURIComponent(storeId)}` : ""}`);
export const createKnowledgeCategory = (payload: { store_id: string; parent_id: string | null; name: string; code: string }) => requestApi<KnowledgeCategory>("/knowledge/categories", { method: "POST", body: JSON.stringify(payload) });
export const updateKnowledgeCategory = (categoryId: string, payload: Partial<{ name: string; parent_id: string | null; sort_order: number; status: string }>) => requestApi<KnowledgeCategory>(`/knowledge/categories/${categoryId}`, { method: "PATCH", body: JSON.stringify(payload) });
export const deleteKnowledgeCategory = (categoryId: string) => requestApi<void>(`/knowledge/categories/${categoryId}`, { method: "DELETE" });
export const listKnowledgeEntries = (query: URLSearchParams) => requestApi<KnowledgePage>(`/knowledge/entries?${query.toString()}`);
export const createKnowledgeEntry = (payload: { store_id: string; category_id: string | null; question: string; answer: string; tags: string[]; statement_type: KnowledgeStatementType; customer_scope: KnowledgeCustomerScope }) => requestApi<KnowledgeEntry>("/knowledge/entries", { method: "POST", body: JSON.stringify(payload) });
export const updateKnowledgeEntry = (entryId: string, payload: Partial<{ category_id: string | null; question: string; answer: string; tags: string[]; source: string | null; statement_type: KnowledgeStatementType; customer_scope: KnowledgeCustomerScope }>) => requestApi<KnowledgeEntry>(`/knowledge/entries/${entryId}`, { method: "PATCH", body: JSON.stringify(payload) });
export const deleteKnowledgeEntry = (entryId: string) => requestApi<void>(`/knowledge/entries/${entryId}`, { method: "DELETE" });
export const publishKnowledgeEntry = (entryId: string) => requestApi<KnowledgeEntry>(`/knowledge/entries/${entryId}/publish`, { method: "POST" });
export const archiveKnowledgeEntry = (entryId: string) => requestApi<KnowledgeEntry>(`/knowledge/entries/${entryId}/archive`, { method: "POST" });
export const getKnowledgeVectorizationStatus = (storeId: string) => requestApi<KnowledgeVectorizationStatus>(`/knowledge/vectorization/status?store_id=${encodeURIComponent(storeId)}`);
export const retryKnowledgeVectorization = (entryId: string) => requestApi<KnowledgeEntry>(`/knowledge/entries/${entryId}/vectorization/retry`, { method: "POST" });
export const importKnowledge = (storeId: string, file: File) => { const body = new FormData(); body.set("store_id", storeId); body.set("file", file); return requestApi<{ job_id: string; status: "pending" }>("/knowledge/imports", { method: "POST", body }); };
export const getImportJob = (jobId: string) => requestApi<ImportJob>(`/knowledge/imports/${jobId}`);
export const listCampaigns = (storeId = "", page = 1) => requestApi<CampaignPage>(`/marketing/campaigns?page=${page}&page_size=20${storeId ? `&store_id=${encodeURIComponent(storeId)}` : ""}`);
export const createCampaign = (payload: Record<string, unknown>) => requestApi<Campaign>("/marketing/campaigns", { method: "POST", body: JSON.stringify(payload) });
export const updateCampaign = (campaignId: string, payload: Record<string, unknown>) => requestApi<Campaign>(`/marketing/campaigns/${campaignId}`, { method: "PATCH", body: JSON.stringify(payload) });
export const deleteCampaign = (campaignId: string) => requestApi<void>(`/marketing/campaigns/${campaignId}`, { method: "DELETE" });
export const setCampaignEnabled = (campaignId: string, enabled: boolean) => requestApi<Campaign>(`/marketing/campaigns/${campaignId}/${enabled ? "enable" : "disable"}`, { method: "POST" });
export const listMarketingEvents = (storeId = "", page = 1) => requestApi<MarketingEventPage>(`/marketing/events?page=${page}&page_size=20${storeId ? `&store_id=${encodeURIComponent(storeId)}` : ""}`);
export const reviewMarketingDraft = (eventId: string, decision: "approve" | "reject", idempotencyKey: string) => requestApi<MarketingEvent>(`/marketing/events/${eventId}/review`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify({ decision }) });
export const getLogistics = (orderId: string) => requestApi<Logistics>(`/workspace/actions/order/${encodeURIComponent(orderId)}/logistics`);
export const updateShippingAddress = (orderId: string, payload: Record<string, string>, idempotencyKey: string) => requestApi<{ tool_call_id: string; status: "pending_confirmation"; mocked: true; replayed: boolean }>(`/workspace/actions/order/${encodeURIComponent(orderId)}/shipping-address`, { method: "PATCH", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(payload) });
export const issueCoupon = (customerId: string, couponCode: string, idempotencyKey: string) => requestApi<{ issuance_id: string; tool_call_id: string; coupon_code: string; status: string; mocked: boolean; replayed: boolean }>(`/workspace/actions/customer/${customerId}/coupon`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify({ coupon_code: couponCode }) });
export const listStores = () => requestApi<StoreView[]>("/settings/stores");
export const createStore = (payload: { name: string; code: string; timezone: string; currency: string }) => requestApi<StoreView>("/settings/stores", { method: "POST", body: JSON.stringify(payload) });
export const listChannels = () => requestApi<ChannelView[]>("/settings/channels");
export const startTikTokOAuth = (storeId: string) => requestApi<TikTokOAuthStart>(`/settings/channels/tiktok/oauth/start?store_id=${encodeURIComponent(storeId)}`);
export const getTikTokOAuthJobStatus = (jobId: string) => requestApi<TikTokOAuthJobStatus>(`/settings/channels/tiktok/oauth/jobs/${encodeURIComponent(jobId)}`);
export const createChannel = (payload: { store_id: string; platform: string; external_store_id: string; display_name: string; access_token_ref: string; scopes: string[] }) => requestApi<ChannelView>("/settings/channels", { method: "POST", body: JSON.stringify(payload) });
export const deleteChannel = (channelId: string) => requestApi<void>(`/settings/channels/${channelId}`, { method: "DELETE" });
export const getDashboardMetrics = (storeId: string, period: string) => requestApi<DashboardMetrics>(`/dashboard/metrics?store_id=${encodeURIComponent(storeId)}&period=${period}`);
export const getDashboardTrend = (storeId: string, days: number) => requestApi<DashboardTrend>(`/dashboard/trend?store_id=${encodeURIComponent(storeId)}&days=${days}`);
export const getDashboardChannels = (storeId: string, period: string) => requestApi<DashboardChannels>(`/dashboard/channels?store_id=${encodeURIComponent(storeId)}&period=${period}`);
export const getDashboardAlerts = (storeId: string) => requestApi<DashboardAlerts>(`/dashboard/alerts?store_id=${encodeURIComponent(storeId)}`);
export const getTopQueries = (storeId: string, period: string) => requestApi<TopQuery[]>(`/dashboard/top-queries?store_id=${encodeURIComponent(storeId)}&period=${period}&limit=5`);
export const listAgents = () => requestApi<AgentConfig[]>("/agents");
export const createAgent = (payload: { store_id: string; name: string; code: string; description: string | null; enabled_tools: string[] }) => requestApi<AgentConfig>("/agents", { method: "POST", body: JSON.stringify(payload) });
export const updateAgent = (agentId: string, payload: Partial<{ name: string; description: string | null; enabled_tools: string[] }>) => requestApi<AgentConfig>(`/agents/${agentId}`, { method: "PATCH", body: JSON.stringify(payload) });
export const setAgentEnabled = (agentId: string, enabled: boolean) => requestApi<AgentConfig>(`/agents/${agentId}/${enabled ? "enable" : "disable"}`, { method: "POST" });
export const getAgentLogs = (agentId: string) => requestApi<AgentRunLogPage>(`/agents/${agentId}/logs?page=1&page_size=20`);
export const listTeam = () => requestApi<TeamMember[]>("/settings/team");
export const createTeamMember = (payload: { name: string; email: string; temporary_password: string; assignments: TeamAssignment[] }) => requestApi<TeamMember>("/settings/team", { method: "POST", body: JSON.stringify(payload) });
export const updateTeamMember = (userId: string, payload: Partial<{ name: string; assignments: TeamAssignment[] }>) => requestApi<TeamMember>(`/settings/team/${userId}`, { method: "PATCH", body: JSON.stringify(payload) });
export const disableTeamMember = (userId: string) => requestApi<void>(`/settings/team/${userId}`, { method: "DELETE" });
export const deleteTeamMember = (userId: string) => requestApi<void>(`/settings/team/${userId}/permanent`, { method: "DELETE" });
export const getSuggestion = (sessionId: string, triggerMessageId?: string) => requestApi<Suggestion>(`/workspace/sessions/${sessionId}/suggest`, { method: "POST", body: JSON.stringify({ trigger_message_id: triggerMessageId ?? null }) });

export async function streamChatQuery(
  sessionId: string,
  onEvent: (event: ChatEvent) => void,
  signal: AbortSignal,
  triggerMessageId?: string,
): Promise<void> {
  const init: RequestInit = { method: "POST", body: JSON.stringify({ session_id: sessionId, trigger_message_id: triggerMessageId ?? null }), signal };
  let response = await rawRequest("/chat/query", init);
  if (response.status === 401) {
    const refreshed = await rawRequest("/auth/browser/refresh", { method: "POST" });
    if (refreshed.ok) response = await rawRequest("/chat/query", init);
  }
  if (!response.ok || !response.body) {
    const body = (await response.json().catch(() => null)) as ApiResponse<unknown> | null;
    throw new ApiError(body?.message ?? "AI 建议连接失败", response.status, body?.code);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let terminalReceived = false;
  try {
    while (!terminalReceived) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replaceAll("\r\n", "\n");
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const lines = block.split("\n");
        const event = lines.find((line) => line.startsWith("event:"))?.slice(6).trim() as ChatEvent["event"] | undefined;
        const dataText = lines.filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart()).join("\n");
        if (event && dataText) {
          let data: Record<string, unknown>;
          try { data = JSON.parse(dataText) as Record<string, unknown>; }
          catch { throw new ApiError("AI 建议响应格式无效，请重试", 0, 50003); }
          onEvent({ event, data });
          terminalReceived ||= event === "done";
        }
      }
      if (done) break;
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
  if (!terminalReceived && !signal.aborted) throw new ApiError("AI 建议连接意外中断，请重试", 0, 50003);
}
