export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

export type UserView = { id: string; name: string; email: string | null; login_name: string | null; role: string; avatar: string | null; permissions: string[]; store_ids: string[] };
export type ApiResponse<T> = { code: number; message: string; data: T };
export type BuyerStage = "pre" | "during" | "after";
export type CustomerSummary = { id: string; name: string | null; email: string | null; avatar: string | null; tags: string[]; buyer_stage_override?: BuyerStage | null };
export type SessionSummary = { id: string; store_id: string; platform: string; status: string; is_starred: boolean; closed_at: string | null; unread_count: number; assigned_user_id: string | null; can_manage?: boolean; can_claim?: boolean; needs_takeover?: boolean; last_message_at: string | null; last_message: string | null; customer: CustomerSummary };
export type SessionActionResult = Pick<SessionSummary, "status" | "is_starred" | "closed_at">;
export type SessionAssignee = { id: string; name: string };
export type LogisticsCardView = { order_id: string; package_id: string | null; product_name: string | null; image_url: string | null; sku_name: string | null; quantity: number | null; unit_price: string | null; currency: string | null; tracking_number: string | null; carrier_name: string | null; latest_description: string | null; latest_at: string | null };
export type RichMessagePackageView = { title?: string | null; image_url?: string | null; package_id?: string | null; paid_price?: string | null; quantity?: string | null; tracking_number?: string | null; carrier_name?: string | null; latest_description?: string | null };
export type RichMessageCardView = { kind: string; title?: string | null; image_url?: string | null; price?: string | null; paid_price?: string | null; status?: string | null; product_id?: string | null; order_id?: string | null; coupon_id?: string | null; sku_id?: string | null; package_id?: string | null; tracking_number?: string | null; carrier_name?: string | null; latest_description?: string | null; sold_quantity?: string | null; quantity?: string | null; url?: string | null; packages?: RichMessagePackageView[] };
export type MessageView = { id: string; role: "user" | "agent" | "assistant" | "system"; content: string; status: "received" | "processing" | "sent" | "delivered" | "failed" | "unknown"; created_at: string; error_code: string | null; delivery_mode: "inbound" | "mock" | "real" | "unknown"; message_type?: string; logistics_card?: LogisticsCardView | null; media?: { url?: string | null; cover?: string | null; vid?: string | null; width?: number | null; height?: number | null; duration?: string | null; expire_time?: string | null } | null; rich_card?: RichMessageCardView | null };
export type MessageTranslationView = { message_id: string; target_language: "zh-CN"; translated_text: string };
export type DraftTargetLanguage = "en" | "id" | "fil" | "ms" | "th" | "my" | "vi" | "pt" | "es" | "pl" | "fr" | "zh-TW" | "zh-CN";
export type DraftTranslationView = { source_text_sha256: string; target_language: DraftTargetLanguage; translated_text: string };
export type OrderSummary = { id: string; external_order_id: string; platform: string; status: string; currency: string; total_amount: string; tracking_number: string | null; tracking_status: string | null };
export type SidebarOrderItem = { name: string; product_id: string | null; sku: string | null; sku_id: string | null; sku_name: string | null; image_url: string | null; quantity: number; unit_price: string | null; total_amount: string | null; package_id?: string | null; tracking_number?: string | null };
export type SidebarOrder = { id: string; external_order_id: string; status: string; payment_status: string | null; currency: string; total_amount: string | null; payment_breakdown: Record<string, string>; ordered_at: string | null; paid_at: string | null; tracking_number: string | null; tracking_status: string | null; items: SidebarOrderItem[]; live_detail_available: boolean };
export type SidebarTrackingEvent = { description: string; occurred_at: string; tracking_number: string | null; action_code: number; action_code_name: string | null };
export type SidebarTrackingPackage = { package_id?: string | null; tracking_number: string | null; carrier_name: string | null; events: SidebarTrackingEvent[] };
export type LogisticsCardDraft = { card: LogisticsCardView; packages: SidebarTrackingPackage[]; enhancedAvailable: boolean; selected: number };
export type ReplyBatchPart = { kind: "text"; content: string } | { kind: "logistics_card"; order_id: string; package_id: string | null };
export type ReplyBatchRequest = { trigger_message_id: string | null; parts: ReplyBatchPart[]; preview_only: boolean; confirmed: boolean };
export type ReplyBatchResult = { id: string; preview_only: boolean; status: "previewed" | "completed" | "partial" | "failed" | "unknown"; parts: Array<{ index: number; kind: ReplyBatchPart["kind"]; status: string; message_id: string | null; error_code: string | null }>; messages: MessageView[] };
export type LogisticsNotificationPolicy = { store_id: string; agent_id: string | null; enabled: boolean; mode: "preview" | "external"; enabled_at: string | null; revision: number; global_enabled: boolean; real_delivery_enabled: boolean; last_scan_at: string | null };
export type LogisticsNotificationView = { notification_key: string; conversation_id: string; state: string; reason: string | null; mode: "preview" | "external"; event_at: string; buyer_language: string; preview_text: string | null; created_at: string };
export type LogisticsNotificationPreview = { status: "previewed" | "blocked" | "rejected"; reason?: string | null; preview_text?: string | null; event_at?: string | null; buyer_language?: string | null };
export type SidebarTrackingTimeline = { packages: SidebarTrackingPackage[] };
export type SidebarTrackingTimelineTranslation = { events: Array<{ source_description: string; translated_text: string; occurred_at: string; tracking_number: string | null }> };
export type SidebarOrderDetail = { payment_method_name: string | null; recipient_address: { name: string | null; phone_number: string | null; full_address: string | null } | null; shipping_provider: string | null; latest_tracking_description: string | null; latest_tracking_at: string | null; tracking_packages: SidebarTrackingPackage[]; enhanced_tracking_available: boolean; tracking_loaded?: boolean };
export type SidebarStandardTracking = { latest_tracking_description: string | null; latest_tracking_at: string | null; packages: SidebarTrackingPackage[] };
export type SidebarTrackingTranslation = { source_description: string; translated_text: string };
export type SidebarOrders = { items: SidebarOrder[]; pagination: { page: number; page_size: number; total: number } };
export type SidebarSku = { id: string; seller_sku: string | null; name: string | null; currency: string | null; sale_price: string | null; quantity: number | null };
export type SidebarProduct = { id: string; title: string; status: string | null; image_url: string | null; skus: SidebarSku[] };
export type SidebarProducts = { items: SidebarProduct[]; next_page_token: string | null; total_count: number | null; partial_search: boolean };
export type SidebarCoupon = { id: string; title: string; status: string | null; display_type: string | null; promo_code: string | null; discount_type: string | null; discount_value: string | null; claim_start_time?: number | null; claim_end_time: number | null; chat_shareable: boolean };
export type SidebarCoupons = { items: SidebarCoupon[]; next_page_token: string | null; total_count: number | null; partial_search: boolean };
export type SidebarSearch = { section: "orders" | "products" | "coupons"; field: string; query: string; status?: "all" | "unpaid" | "ship" | "transit" | "done" | "cancel"; page?: number; page_token?: string | null; refresh?: boolean };
export type SessionListData = { items: SessionSummary[]; pagination: { page: number; page_size: number; total: number }; unread_messages_total: number };
export type SessionMessagesData = { session: SessionSummary; messages: MessageView[]; customer: CustomerSummary; recent_orders: OrderSummary[]; assignment_events?: Array<{ action: string; actor_type: string; assigned_user_id: string | null; reason: string | null; created_at: string }>; ai_suggestion: null; pagination: { page: number; page_size: number; total: number }; send_mode: "disabled" | "mock" | "real"; requires_confirmation: true; translation_enabled?: boolean; draft_translation_enabled?: boolean };
export type KnowledgeCategory = { id: string; store_id: string; parent_id: string | null; name: string; code: string; layer: string; sort_order: number; status: string };
export type KnowledgeStatementType = "policy" | "technical_artifact" | "customer_instance_fact" | "non_assertive_proposition" | "unknown";
export type KnowledgeCustomerScope = "none" | "generic" | "specific_customer";
export type KnowledgePublicationApproval = "draft" | "approved_for_internal_review" | "approved_for_public_reply";
export type KnowledgeEntry = { id: string; store_id: string; category_id: string | null; question: string; answer: string; source: string | null; tags: string[]; status: string; vectorization_status: string; document_version: number; usage_count: number; satisfaction_rate: number | null; statement_type: KnowledgeStatementType; customer_scope: KnowledgeCustomerScope; publication_approval: KnowledgePublicationApproval; semantic_schema_version: 1; approved_by: string | null; approved_at: string | null; published_at: string | null; created_at: string; updated_at: string };
export type KnowledgePage = { items: KnowledgeEntry[]; page: number; page_size: number; total: number };
export type KnowledgeVectorizationStatus = { store_id: string; worker_enabled: boolean; provider: "local_bge"; model: string; dimensions: 1024; counts: { pending: number; processing: number; ready: number; failed: number } };
export type ImportJob = { id: string; store_id: string; original_filename: string; status: string; total_rows: number; succeeded_rows: number; failed_rows: number; error_summary: Array<Record<string, unknown>>; created_at: string; completed_at: string | null };
export type DocumentStrategy = "recursive" | "heading_paragraph" | "sentence" | "fixed_token" | "fixed_char" | "semantic_similarity" | "page_slide" | "ocr_layout" | "table_rows";
export type DocumentIndexConfig = { strategy: DocumentStrategy; chunk_size: number; overlap: number; parser_mode: "auto" | "flash" | "basic"; embedding_model: "BAAI/bge-m3" };
export type DocumentVersionSummary = { id: string; version_number: number; status: "queued" | "parsing" | "review_required" | "indexing" | "ready" | "failed_retryable" | "failed_final"; error_code: string | null; retry_count: number; created_at: string; completed_at: string | null; is_active: boolean; chunk_count: number; approval_status: "draft" | "approved_for_internal_review"; statement_type: string; customer_scope: string };
export type DocumentFileSummary = { id: string; store_id: string; category_id: string | null; filename: string; active_version_number: number | null; archived_at: string | null; latest_version: DocumentVersionSummary };
export type DocumentFilePage = { items: DocumentFileSummary[]; total: number; page: number; page_size: number };
export type DocumentFileDetail = DocumentFileSummary & { versions: DocumentVersionSummary[] };
export type DocumentUnit = { unit_index: number; unit_kind: string; source_locator: Record<string, number>; raw_text: string; cleaned_text: string; issue_codes: string[]; needs_review: boolean; parse_mode: string; reviewed_by: string | null; reviewed_at: string | null };
export type DocumentVersionDetail = DocumentVersionSummary & { file_id: string; filename: string; file_sha256: string; config: DocumentIndexConfig; parser_version: string | null; cleaning_version: string; units: DocumentUnit[] };
export type DocumentImportAccepted = { file_id: string; version_id: string; version_number: number; status: string };
export type Campaign = { id: string; store_id: string; name: string; trigger_type: string; action_type: string; content_mode: string; template_content: string | null; coupon_code: string | null; trigger_delay_minutes: number; cooldown_hours: number; max_contacts_30d: number; status: string; created_at: string; updated_at: string };
export type CampaignPage = { items: Campaign[]; page: number; page_size: number; total: number };
export type MarketingEvent = { id: string; store_id: string; campaign_id: string; customer_id: string | null; source_type: string; source_id: string; status: string; attempt_count: number; error_code: string | null; ai_draft_content: string | null; ai_draft_agent_run_id: string | null; ai_review_status: "pending" | "approved" | "rejected" | null; ai_reviewed_by: string | null; ai_reviewed_at: string | null; triggered_at: string; completed_at: string | null; converted_at: string | null };
export type MarketingEventPage = { items: MarketingEvent[]; page: number; page_size: number; total: number };
export type Logistics = { order_id: string; external_order_id: string; tracking_number: string | null; tracking_status: string | null; shipped_at: string | null; delivered_at: string | null };
export type StoreView = { id: string; name: string; alias: string | null; code: string; status: string; timezone: string; currency: string; created_at: string };
export type ChannelView = { id: string; store_id: string; platform: string; external_store_id: string; display_name: string; status: string; scopes: string[]; last_sync_at: string | null; created_at: string; site: string | null; authorization_expires_at: string | null; authorization_status: string | null; last_authorized_at: string | null };
export type StoreAuthorizationView = { store: StoreView; channel: ChannelView };
export type TikTokOAuthStart = { authorization_url: string; expires_in: number };
export type TikTokOAuthShopChoice = { id: string; code: string; name: string; region: string; seller_type: string };
export type TikTokOAuthJobStatus = { status: "pending" | "processing" | "selection_required" | "connected" | "denied" | "failed"; shops: TikTokOAuthShopChoice[]; selection_expires_at: string | null; error_code: string | null; store_id: string | null };
export type DashboardMetrics = { total_sessions: number; transfer_rate: number; avg_response_time: number | null; recovered_gmv: string; currency: string; period: "today" | "7d" | "30d"; updated_at: string | null };
export type DashboardTrend = { items: Array<{ date: string; sessions: number }> };
export type DashboardChannels = { items: Array<{ platform: string; count: number; percentage: number }> };
export type DashboardAlerts = { refund_requests: { total: number }; bad_reviews: { total: number; golden_window: boolean }; abandoned_carts: { total: number; potential_gmv: string } };
export type TopQuery = { rank: number; intent: string; count: number };
export type AgentRuntime = { available: boolean; llm_provider: string; llm_model: string | null; available_models?: string[]; model_options?: Array<{ provider: string; model_name: string }>; embedding_provider: string; embedding_model: string; reranker_model: string; prompt_versions: Record<string, string>; auto_reply_threshold: number; human_review_threshold: number; token_streaming: boolean };
export type AgentReplyProfile = { tone: "friendly" | "professional" | "concise" | "empathetic"; reply_language: "auto" | "zh-CN" | "en"; operator_language: "zh-CN" | "en"; brand_name: string | null };
export type AgentConfig = { id: string; store_id: string; name: string; code: string; description: string | null; agent_type: "service" | "operations"; status: "enabled" | "disabled"; draft_revision: number; published_version: number | null; model_provider: string | null; model_name: string | null; prompt_sections: Record<string, string>; enabled_tools: string[]; knowledge_file_ids: string[]; knowledge_scope: Record<string, unknown>; reply_profile: AgentReplyProfile; runtime: AgentRuntime; created_at: string; updated_at: string };
export type AgentRunLog = { id: string; parent_run_id?: string | null; config_version?: number | null; phase?: string | null; status: string; action: string; intent: string | null; final_confidence: number | null; model_provider: string; model_name: string; prompt_version: string | null; latency_ms: number | null; input_tokens: number | null; output_tokens: number | null; error_code: string | null; trace_id: string | null; tool_calls: Array<{ id: string; tool_name: string; status: string; error_code: string | null; latency_ms: number | null; mocked: boolean }>; created_at: string };
export type AgentRunLogPage = { items: AgentRunLog[]; page: number; page_size: number; total: number };
export type AgentOperatorTranslation = { target_language: "zh-CN" | "en"; message_translation: string; draft_translation: string | null };
export type AgentDebugResult = { customer_translation?: AgentOperatorTranslation | null; customer_translation_error_code?: string | null; agent_run_id: string; content: string | null; action: string; terminal_state: string; citations: Array<{ document_id: string; chunk_id: string; score: number; source_label: string }>; tool_calls: Array<{ tool_call_id: string; tool_name: string; status: string; error_code: string | null }>; routed_agents?: Array<{ id: string; name: string }>; tool_events?: Array<{ agent_id: string; tool_name: string; status: string; call_id: string }>; reason_code?: string | null; trace_id: string; send_performed: false };
export type TeamAssignment = { role: "admin" | "supervisor" | "agent"; store_id: string | null };
export type TeamRoleView = { role: string; store_id: string | null };
export type TeamMember = { id: string; login_name: string | null; name: string; email: string | null; phone: string | null; timezone: string; max_concurrent_sessions: number; status: "active" | "disabled"; assignments: TeamRoleView[]; department_ids: string[]; last_login_at: string | null; created_at: string };
export type Department = { id: string; name: string; store_ids: string[]; created_at: string };
export type ReceptionDepartmentAgent = { user_id: string; name: string; active: boolean; eligible_store_ids: string[]; auto_enabled: boolean; online: boolean };
export type ReceptionDepartment = { department_id: string; store_ids: string[]; enabled: boolean; queue_count: number; queue_reasons: Record<string, number>; agents: ReceptionDepartmentAgent[] };
export type TeamMemberCreate = { login_name: string; name: string; email: string | null; phone: string | null; timezone: string; max_concurrent_sessions: number; temporary_password: string; assignments: TeamAssignment[]; department_id: string | null };
export type SuggestionTranslation = AgentOperatorTranslation & { trigger_message_id: string };
export type Suggestion = { translation?: SuggestionTranslation | null; translation_error_code?: string | null; agent_run_id: string; content: string | null; reply_parts?: string[]; logistics_order_numbers?: string[]; trigger_message_id?: string | null; reason_codes?: string[]; intent: string | null; confidence: number; action: string; terminal_state: string; requires_human: boolean; transfer_performed: boolean; send_performed: false; citations: Array<{ document_id: string; chunk_id: string; score: number; source_label: string }>; trace_id: string; demo_mode: boolean; demo_scenario: string | null };
export type ChatEvent = { event: "accepted" | "status" | "draft" | "delta" | "result" | "error" | "done"; data: Record<string, unknown> };

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
  const started = typeof window === "undefined" ? 0 : performance.now();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });
  if (started) {
    const elapsedMs = Math.round(performance.now() - started);
    if (elapsedMs >= 1500) {
      // 不输出路径参数、查询、请求体或买家资料；耗时可与入口日志和服务端 Trace ID 对照。
      const group = path.startsWith("/workspace/sessions/") ? "workspace-session"
        : path.startsWith("/workspace/") ? "workspace"
        : path.startsWith("/auth/") ? "auth"
        : path.startsWith("/integrations/") ? "integrations"
        : path.split("/")[1] || "api";
      console.warn("Slow API response", { group, elapsedMs, status: response.status, serverTiming: response.headers.get("Server-Timing"), traceId: response.headers.get("X-Trace-Id") });
    }
  }
  return response;
}

let browserRefreshInFlight: Promise<boolean> | null = null;
let browserRefreshVersion = 0;

function isReadOnlyRequest(path: string, method: string): boolean {
  if (method === "GET" || method === "HEAD") return true;
  if (method !== "POST") return false;
  // 搜索与订单详情使用 POST 隐藏买家查询条件，但服务端只读取授权店铺数据。
  return path === "/workspace/sessions/search"
    || /^\/workspace\/sessions\/[^/]+\/sidebar\/(search|orders\/(detail|standard-tracking|enhanced-tracking))$/.test(path);
}

function refreshBrowserSession(): Promise<boolean> {
  if (typeof window === "undefined") return rawRequest("/auth/browser/refresh", { method: "POST" }).then((response) => response.ok);
  if (!browserRefreshInFlight) {
    // 同页并发 401 共用一次 Cookie 刷新，避免弱网下重复往返和旧响应竞争。
    const refresh = rawRequest("/auth/browser/refresh", { method: "POST" }).then((response) => {
      if (response.ok) browserRefreshVersion += 1;
      return response.ok;
    });
    browserRefreshInFlight = refresh;
    void refresh.then(
      () => { if (browserRefreshInFlight === refresh) browserRefreshInFlight = null; },
      () => { if (browserRefreshInFlight === refresh) browserRefreshInFlight = null; },
    );
  }
  return browserRefreshInFlight;
}

export async function requestApi<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  // 同一次业务请求的 401 刷新重试必须复用原键，避免首个响应丢失后重复写入。
  const stableInit = withStableIdempotencyKey(init);
  const refreshVersionAtStart = browserRefreshVersion;
  let response = await rawRequest(path, stableInit);
  if (response.status === 401 && retry && path !== "/auth/browser/refresh") {
    // 只读请求若晚于同批次 Cookie 刷新才返回 401，直接用新登录态重试一次。
    const alreadyRefreshed = typeof window !== "undefined"
      && isReadOnlyRequest(path, (stableInit.method ?? "GET").toUpperCase())
      && browserRefreshVersion !== refreshVersionAtStart;
    if (alreadyRefreshed || await refreshBrowserSession()) response = await rawRequest(path, stableInit);
  }
  if (response.status === 204) return undefined as T;
  const body = (await response.json().catch(() => null)) as ApiResponse<T> | null;
  if (!response.ok || !body) {
    throw new ApiError(body?.message ?? "请求失败，请稍后重试", response.status, body?.code);
  }
  return body.data;
}

export const browserLogin = (identifier: string, password: string) => requestApi<{ expires_in: number; user: UserView }>("/auth/browser/login", { method: "POST", body: JSON.stringify({ identifier, password }) }, false);
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
export const getCustomerSidebarOrderDetail = (sessionId: string, orderId: string, signal?: AbortSignal, includeTracking = true) => requestApi<SidebarOrderDetail>(`/workspace/sessions/${encodeURIComponent(sessionId)}/sidebar/orders/detail`, { method: "POST", body: JSON.stringify({ order_id: orderId, include_tracking: includeTracking }), signal });
export const getCustomerSidebarStandardTracking = (sessionId: string, orderId: string, signal?: AbortSignal) => requestApi<SidebarStandardTracking>(`/workspace/sessions/${encodeURIComponent(sessionId)}/sidebar/orders/standard-tracking`, { method: "POST", body: JSON.stringify({ order_id: orderId }), signal });
export const getCustomerSidebarEnhancedTracking = (sessionId: string, orderId: string) => requestApi<SidebarTrackingTimeline>(`/workspace/sessions/${encodeURIComponent(sessionId)}/sidebar/orders/enhanced-tracking`, { method: "POST", body: JSON.stringify({ order_id: orderId }) });
export const getCustomerSidebarProduct = (sessionId: string, productId: string) => requestApi<SidebarProduct>(`/workspace/sessions/${encodeURIComponent(sessionId)}/sidebar/products/${encodeURIComponent(productId)}`);
export const getSessionMessages = async (sessionId: string): Promise<SessionMessagesData> => {
  const first = await getSessionMessagesPage(sessionId, 1);
  const newestPage = Math.ceil(first.pagination.total / first.pagination.page_size);
  return newestPage > 1 ? getSessionMessagesPage(sessionId, newestPage) : first;
};
export const sendMessage = (sessionId: string, content: string, idempotencyKey: string) => requestApi<MessageView>(`/workspace/sessions/${sessionId}/messages`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify({ content, confirmed: true }) });
export type MediaUpload = { kind: "image" | "video"; file_name: string; upload_token: string };
export const uploadMessageMedia = (sessionId: string, file: File, idempotencyKey: string) => { const body = new FormData(); body.set("file", file); return requestApi<MediaUpload>(`/workspace/sessions/${encodeURIComponent(sessionId)}/messages/media/upload`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body }); };
export const sendMessageMedia = (sessionId: string, kind: "image" | "video", uploadToken: string, idempotencyKey: string) => requestApi<MessageView>(`/workspace/sessions/${encodeURIComponent(sessionId)}/messages/media`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify({ kind, upload_token: uploadToken, confirmed: true }) });
export const sendLogisticsCard = (sessionId: string, orderId: string, packageId: string | null, idempotencyKey: string) => requestApi<MessageView>(`/workspace/sessions/${sessionId}/messages/logistics-card`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify({ order_id: orderId, package_id: packageId, confirmed: true }) });
export const getReplyLogisticsPreview = (sessionId: string, orderId: string) => requestApi<Array<{ card: LogisticsCardView; packages: SidebarTrackingPackage[]; enhanced_available: boolean; selected: number }>>(`/workspace/sessions/${encodeURIComponent(sessionId)}/logistics-card-preview?order_id=${encodeURIComponent(orderId)}`);
export const submitReplyBatch = (sessionId: string, plan: ReplyBatchRequest, idempotencyKey: string) => requestApi<ReplyBatchResult>(`/workspace/sessions/${encodeURIComponent(sessionId)}/reply-batches`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(plan) });
export const getLogisticsNotificationPolicy = (storeId: string) => requestApi<LogisticsNotificationPolicy>(`/agents/logistics-notifications/policy?store_id=${encodeURIComponent(storeId)}`);
export const saveLogisticsNotificationPolicy = (storeId: string, policy: { enabled: boolean; agent_id: string | null; mode: "preview"; expected_revision: number }) => requestApi<LogisticsNotificationPolicy>(`/agents/logistics-notifications/policy?store_id=${encodeURIComponent(storeId)}`, { method: "PATCH", body: JSON.stringify(policy) });
export const listLogisticsNotifications = (storeId: string, conversationId: string) => requestApi<LogisticsNotificationView[]>(`/agents/logistics-notifications?${new URLSearchParams({ store_id: storeId, conversation_id: conversationId, offset: "0" })}`);
export const previewLogisticsNotification = (input: { store_id: string; conversation_id: string; order_id: string; package_id?: string }) => requestApi<LogisticsNotificationPreview>("/agents/logistics-notifications/preview", { method: "POST", body: JSON.stringify(input) });
export const translateMessage = (sessionId: string, messageId: string) => requestApi<MessageTranslationView>(`/workspace/sessions/${encodeURIComponent(sessionId)}/messages/${encodeURIComponent(messageId)}/translation`, { method: "POST" });
export const translateDraft = (sessionId: string, sourceText: string, targetLanguage: DraftTargetLanguage) => requestApi<DraftTranslationView>(`/workspace/sessions/${encodeURIComponent(sessionId)}/draft/translation`, { method: "POST", body: JSON.stringify({ source_text: sourceText, target_language: targetLanguage }) });
export const translateSidebarTracking = (sessionId: string, orderId: string, event?: SidebarTrackingEvent & { enhanced: boolean }) => requestApi<SidebarTrackingTranslation>(`/workspace/sessions/${encodeURIComponent(sessionId)}/sidebar/orders/tracking-translation`, { method: "POST", body: JSON.stringify({ order_id: orderId, ...(event ? { event_description: event.description, event_at: event.occurred_at, event_tracking_number: event.tracking_number, enhanced: event.enhanced } : {}) }) });
export const translateSidebarTrackingTimeline = (sessionId: string, orderId: string, enhanced: boolean) => requestApi<SidebarTrackingTimelineTranslation>(`/workspace/sessions/${encodeURIComponent(sessionId)}/sidebar/orders/tracking-timeline-translation`, { method: "POST", body: JSON.stringify({ order_id: orderId, enhanced }) });
export const markSessionRead = (sessionId: string) => requestApi<{ unread_count: number }>(`/workspace/sessions/${sessionId}/read`, { method: "POST" });
export const setSessionStar = (sessionId: string, starred: boolean) => requestApi<SessionActionResult>(`/workspace/sessions/${sessionId}/star`, { method: "PATCH", body: JSON.stringify({ starred }) });
export const setSessionClosed = (sessionId: string, closed: boolean) => requestApi<SessionActionResult>(`/workspace/sessions/${sessionId}/closed`, { method: "PATCH", body: JSON.stringify({ closed }) });
export const setBuyerStage = (sessionId: string, stage: BuyerStage | null) => requestApi<CustomerSummary>(`/workspace/sessions/${sessionId}/buyer-stage`, { method: "PATCH", body: JSON.stringify({ stage }) });
export const listSessionAssignees = (sessionId: string) => requestApi<SessionAssignee[]>(`/workspace/sessions/${sessionId}/assignees`);
export const assignSession = (sessionId: string, userId: string) => requestApi<SessionSummary>(`/workspace/sessions/${sessionId}/assign`, { method: "POST", body: JSON.stringify({ user_id: userId }) });
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
export const listDocumentFiles = (query: URLSearchParams) => requestApi<DocumentFilePage>(`/knowledge/files?${query.toString()}`);
export const getDocumentFile = (fileId: string) => requestApi<DocumentFileDetail>(`/knowledge/files/${encodeURIComponent(fileId)}`);
export const updateDocumentFileCategory = (fileId: string, categoryId: string) => requestApi<DocumentFileDetail>(`/knowledge/files/${encodeURIComponent(fileId)}`, { method: "PATCH", body: JSON.stringify({ category_id: categoryId }) });
export const archiveDocumentFile = (fileId: string) => requestApi<DocumentFileDetail>(`/knowledge/files/${encodeURIComponent(fileId)}/archive`, { method: "POST" });
export const restoreDocumentFile = (fileId: string) => requestApi<DocumentFileDetail>(`/knowledge/files/${encodeURIComponent(fileId)}/restore`, { method: "POST" });
export const deleteDocumentFile = (fileId: string) => requestApi<void>(`/knowledge/files/${encodeURIComponent(fileId)}`, { method: "DELETE" });
export const getDocumentVersion = (fileId: string, versionNumber: number) => requestApi<DocumentVersionDetail>(`/knowledge/files/${encodeURIComponent(fileId)}/versions/${versionNumber}`);
export const approveDocumentVersion = (fileId: string, versionNumber: number, statementType: "policy" | "technical_artifact" | "non_assertive_proposition") => requestApi<DocumentVersionDetail>(`/knowledge/files/${encodeURIComponent(fileId)}/versions/${versionNumber}/approve`, { method: "POST", body: JSON.stringify({ statement_type: statementType, customer_scope: statementType === "technical_artifact" ? "none" : "generic" }) });
export const revokeDocumentVersion = (fileId: string, versionNumber: number) => requestApi<DocumentVersionDetail>(`/knowledge/files/${encodeURIComponent(fileId)}/versions/${versionNumber}/revoke`, { method: "POST" });
export const getDocumentSettings = (storeId: string) => requestApi<DocumentIndexConfig>(`/knowledge/file-settings?store_id=${encodeURIComponent(storeId)}`);
export const saveDocumentSettings = (storeId: string, config: DocumentIndexConfig) => requestApi<DocumentIndexConfig>(`/knowledge/file-settings?store_id=${encodeURIComponent(storeId)}`, { method: "PUT", body: JSON.stringify(config) });
export const importDocumentFile = (storeId: string, file: File, config: DocumentIndexConfig, categoryId: string | null, replaceFileId: string | null) => {
  const body = new FormData();
  body.set("store_id", storeId);
  body.set("file", file);
  body.set("config_json", JSON.stringify(config));
  if (categoryId) body.set("category_id", categoryId);
  if (replaceFileId) body.set("replace_file_id", replaceFileId);
  return requestApi<DocumentImportAccepted>("/knowledge/files/imports", { method: "POST", body });
};
export const reviewDocumentUnit = (fileId: string, versionNumber: number, unitIndex: number, correctedText: string) => requestApi<DocumentVersionDetail>(`/knowledge/files/${encodeURIComponent(fileId)}/versions/${versionNumber}/units/${unitIndex}/review`, { method: "POST", body: JSON.stringify({ corrected_text: correctedText, confirmed: true }) });
export const retryDocumentVersion = (fileId: string, versionNumber: number) => requestApi<DocumentVersionDetail>(`/knowledge/files/${encodeURIComponent(fileId)}/versions/${versionNumber}/retry`, { method: "POST" });
export async function downloadDocumentSource(fileId: string, versionNumber: number): Promise<Blob> {
  const path = `/knowledge/files/${encodeURIComponent(fileId)}/versions/${versionNumber}/source`;
  let response = await rawRequest(path);
  if (response.status === 401) {
    const refreshed = await rawRequest("/auth/browser/refresh", { method: "POST" });
    if (refreshed.ok) response = await rawRequest(path);
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiResponse<unknown> | null;
    throw new ApiError(body?.message ?? "原文件下载失败", response.status, body?.code);
  }
  return response.blob();
}
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
export const listStoreAuthorizations = () => requestApi<StoreAuthorizationView[]>("/settings/store-authorizations");
export const updateStoreAlias = (storeId: string, alias: string | null) => requestApi<StoreView>(`/settings/stores/${encodeURIComponent(storeId)}/alias`, { method: "PATCH", body: JSON.stringify({ alias }) });
export const createStore = (payload: { name: string; code: string; timezone: string; currency: string }) => requestApi<StoreView>("/settings/stores", { method: "POST", body: JSON.stringify(payload) });
export const listChannels = () => requestApi<ChannelView[]>("/settings/channels");
export const startTikTokOAuth = (storeId: string, returnTo?: "/settings/stores") => requestApi<TikTokOAuthStart>(`/settings/channels/tiktok/oauth/start?store_id=${encodeURIComponent(storeId)}${returnTo ? `&return_to=${encodeURIComponent(returnTo)}` : ""}`);
export const startNewTikTokStoreOAuth = () => requestApi<TikTokOAuthStart>("/settings/stores/tiktok/oauth/start", { method: "POST" });
export const getTikTokOAuthJobStatus = (jobId: string) => requestApi<TikTokOAuthJobStatus>(`/settings/channels/tiktok/oauth/jobs/${encodeURIComponent(jobId)}`);
export const selectTikTokOAuthShops = (jobId: string, shopIds: string[]) => requestApi<TikTokOAuthJobStatus>(`/settings/channels/tiktok/oauth/jobs/${encodeURIComponent(jobId)}/shops`, { method: "POST", body: JSON.stringify({ shop_ids: shopIds }) });
export const createChannel = (payload: { store_id: string; platform: string; external_store_id: string; display_name: string; access_token_ref: string; scopes: string[] }) => requestApi<ChannelView>("/settings/channels", { method: "POST", body: JSON.stringify(payload) });
export const deleteChannel = (channelId: string) => requestApi<void>(`/settings/channels/${channelId}`, { method: "DELETE" });
export const getDashboardMetrics = (storeId: string, period: string) => requestApi<DashboardMetrics>(`/dashboard/metrics?store_id=${encodeURIComponent(storeId)}&period=${period}`);
export const getDashboardTrend = (storeId: string, days: number) => requestApi<DashboardTrend>(`/dashboard/trend?store_id=${encodeURIComponent(storeId)}&days=${days}`);
export const getDashboardChannels = (storeId: string, period: string) => requestApi<DashboardChannels>(`/dashboard/channels?store_id=${encodeURIComponent(storeId)}&period=${period}`);
export const getDashboardAlerts = (storeId: string) => requestApi<DashboardAlerts>(`/dashboard/alerts?store_id=${encodeURIComponent(storeId)}`);
export const getTopQueries = (storeId: string, period: string) => requestApi<TopQuery[]>(`/dashboard/top-queries?store_id=${encodeURIComponent(storeId)}&period=${period}&limit=5`);
export const listAgents = () => requestApi<AgentConfig[]>("/agents");
export type AgentToolMetadata = { name: string; title: string; description: string; category: string; operation: "read" | "internal_write" | "confirmation" | "notification"; requires_context: boolean; availability: "available" | "unavailable" | "requires_context" | "requires_knowledge" | "confirmation"; reason: string; missing_scopes: string[] };
export type AgentToolCatalogView = { groups: { key: string; title: string; description: string }[]; tools: AgentToolMetadata[] };
export type AgentCollaborationEntry = { id: string; kind: string; content: string; created_at: string; agent_run_id: string; is_ai_suggestion: true; send_performed: false; transfer_performed: false };
export const getAgentToolCatalog = (storeId: string) => requestApi<AgentToolCatalogView>(`/agents/tool-catalog?store_id=${encodeURIComponent(storeId)}`);
export const getAgentCollaboration = (conversationId: string, offset = 0) => requestApi<AgentCollaborationEntry[]>(`/agents/collaboration?conversation_id=${encodeURIComponent(conversationId)}&offset=${offset}`);
export const createAgent = (payload: { store_id: string; name: string; code: string; description: string | null; agent_type: "service" | "operations"; enabled_tools: string[]; knowledge_file_ids: string[] }) => requestApi<AgentConfig>("/agents", { method: "POST", body: JSON.stringify(payload) });
export const updateAgent = (agentId: string, payload: Partial<Pick<AgentConfig, "name" | "description" | "agent_type" | "enabled_tools" | "knowledge_file_ids" | "reply_profile" | "model_provider" | "model_name" | "prompt_sections">> & { expected_revision?: number }) => requestApi<AgentConfig>(`/agents/${agentId}`, { method: "PATCH", body: JSON.stringify(payload) });
export const publishAgent = (agentId: string, expectedRevision: number) => requestApi<AgentConfig>(`/agents/${agentId}/publish`, { method: "POST", body: JSON.stringify({ expected_revision: expectedRevision }) });
export const setAgentEnabled = (agentId: string, enabled: boolean) => requestApi<AgentConfig>(`/agents/${agentId}/${enabled ? "enable" : "disable"}`, { method: "POST" });
export const getAgentLogs = (agentId: string) => requestApi<AgentRunLogPage>(`/agents/${agentId}/logs?page=1&page_size=20`);
export const debugAgent = (agentId: string, message: string, conversationId: string | null, mode: "single" | "store" = "single") => requestApi<AgentDebugResult>(`/agents/${agentId}/debug`, { method: "POST", body: JSON.stringify({ message, conversation_id: conversationId, mode }) });
export const listTeam = () => requestApi<TeamMember[]>("/settings/team");
export const createTeamMember = (payload: TeamMemberCreate) => requestApi<TeamMember>("/settings/team", { method: "POST", body: JSON.stringify(payload) });
export const updateTeamMember = (userId: string, payload: Partial<Pick<TeamMember, "name" | "email" | "phone" | "timezone" | "max_concurrent_sessions" | "assignments">>) => requestApi<TeamMember>(`/settings/team/${userId}`, { method: "PATCH", body: JSON.stringify(payload) });
export const changeTeamMemberPassword = (userId: string, password: string) => requestApi<void>(`/settings/team/${userId}/password`, { method: "PATCH", body: JSON.stringify({ password }) });
export const listDepartments = () => requestApi<Department[]>("/settings/departments");
export const createDepartment = (payload: { name: string; store_ids: string[] }) => requestApi<Department>("/settings/departments", { method: "POST", body: JSON.stringify(payload) });
export const updateDepartment = (id: string, payload: { name?: string; store_ids?: string[] }) => requestApi<Department>(`/settings/departments/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
export const listDepartmentMembers = (id: string) => requestApi<TeamMember[]>(`/settings/departments/${id}/members`);
export const addDepartmentMember = (id: string, userId: string) => requestApi<void>(`/settings/departments/${id}/members`, { method: "POST", body: JSON.stringify({ user_id: userId }) });
export const removeDepartmentMember = (id: string, userId: string) => requestApi<void>(`/settings/departments/${id}/members/${userId}`, { method: "DELETE" });
export const getDepartmentReception = (departmentId: string) => requestApi<ReceptionDepartment>(`/settings/departments/${departmentId}/reception`);
export const putDepartmentReception = (departmentId: string, payload: { enabled: boolean; agents: Array<{ user_id: string; auto_enabled: boolean }> }) => requestApi<ReceptionDepartment>(`/settings/departments/${departmentId}/reception`, { method: "PUT", body: JSON.stringify(payload) });
export const disableTeamMember = (userId: string) => requestApi<void>(`/settings/team/${userId}`, { method: "DELETE" });
export const deleteTeamMember = (userId: string) => requestApi<void>(`/settings/team/${userId}/permanent`, { method: "DELETE" });
export const getSuggestion = (sessionId: string, triggerMessageId?: string) => requestApi<Suggestion>(`/workspace/sessions/${sessionId}/suggest`, { method: "POST", body: JSON.stringify({ trigger_message_id: triggerMessageId ?? null }) });

export async function streamChatQuery(
  sessionId: string,
  onEvent: (event: ChatEvent) => void,
  signal: AbortSignal,
  triggerMessageId?: string,
  replyMode: "single" | "review_plan" = "single",
): Promise<void> {
  const init: RequestInit = { method: "POST", body: JSON.stringify({ session_id: sessionId, trigger_message_id: triggerMessageId ?? null, ...(replyMode === "review_plan" ? { reply_mode: replyMode } : {}) }), signal };
  return streamApiQuery("/chat/query", init, onEvent, signal);
}

export function streamAgentDebug(
  agentId: string, message: string, conversationId: string | null, mode: "single" | "store",
  onEvent: (event: ChatEvent) => void, signal: AbortSignal,
): Promise<void> {
  return streamApiQuery(`/agents/${agentId}/debug/stream`, {
    method: "POST", body: JSON.stringify({ message, conversation_id: conversationId, mode }), signal,
  }, onEvent, signal);
}

async function streamApiQuery(path: string, init: RequestInit, onEvent: (event: ChatEvent) => void, signal: AbortSignal): Promise<void> {
  let response = await rawRequest(path, init);
  if (response.status === 401) {
    const refreshed = await rawRequest("/auth/browser/refresh", { method: "POST" });
    if (refreshed.ok) response = await rawRequest(path, init);
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
