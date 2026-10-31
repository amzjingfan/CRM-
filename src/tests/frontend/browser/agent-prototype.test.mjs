import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { after, before, test } from "node:test";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");
const baseUrl = process.env.UI_BASE_URL ?? "http://localhost:3101";
const toolCatalog = JSON.parse(readFileSync(new URL("./fixtures/agent-tool-catalog.json", import.meta.url), "utf8"));
if (!["127.0.0.1", "localhost", "::1"].includes(new URL(baseUrl).hostname)) throw new Error("local browser only");

const us = { id: "00000000-0000-4000-8000-0000000000f1", name: "US 店铺" };
const uk = { id: "00000000-0000-4000-8000-0000000000f2", name: "UK 店铺" };
const file = { id: "00000000-0000-4000-8000-0000000000d1", store_id: us.id, filename: "物流说明.pdf", active_version_number: 1, archived_at: null, latest_version: { id: "00000000-0000-4000-8000-0000000000d2", version_number: 1, status: "ready", approval_status: "draft", is_active: true, chunk_count: 2 } };
const promptSections = Object.fromEntries(["identity", "service_scope", "tool_rules", "escalation", "language_format", "compliance", "clarification"].map((key) => [key, `测试 ${key} 的完整说明` ]));
const agent = (id, store_id, name) => ({
  id, store_id, name, code: `service_${name}`, description: "客服建议", agent_type: "service", status: "disabled",
  draft_revision: 1, published_version: null, model_provider: "deepseek", model_name: "deepseek-v4-flash", prompt_sections: promptSections,
  enabled_tools: ["transfer_to_human"], knowledge_file_ids: [], knowledge_scope: {},
  reply_profile: { tone: "friendly", reply_language: "auto", operator_language: "zh-CN", brand_name: null },
  runtime: { available: true, llm_provider: "deepseek", llm_model: "deepseek-v4-flash", available_models: ["deepseek-v4-flash", "deepseek-v4-pro"], model_options: [{ provider: "deepseek", model_name: "deepseek-v4-flash" }, { provider: "deepseek", model_name: "deepseek-v4-pro" }, { provider: "openai", model_name: "agent::alias:2026" }], embedding_provider: "local_bge", embedding_model: "BAAI/bge-m3", reranker_model: "BAAI/bge-reranker-large", prompt_versions: {}, auto_reply_threshold: 0.85, human_review_threshold: 0.5, token_streaming: false },
  created_at: "2026-10-26T00:00:00Z", updated_at: "2026-10-26T00:00:00Z",
});
let browser;
before(async () => { browser = await chromium.launch({ channel: "chrome", headless: true }); });
after(async () => { await browser?.close(); });

async function openAgentPage(options = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const agents = [agent("00000000-0000-4000-8000-0000000000a1", us.id, "美国客服"), agent("00000000-0000-4000-8000-0000000000a2", uk.id, "英国客服")];
  if (options.templateSource) agents[0].published_version = 1;
  if (options.notificationAgent) Object.assign(agents[0], { status: "enabled", published_version: 1, enabled_tools: ["notify_logistics_update"] });
  const writes = [];
  let detached = false;
  const previewPolicies = new Map();
  await context.route("**/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: { "access-control-allow-origin": new URL(baseUrl).origin, "access-control-allow-credentials": "true" } });
    let data = [];
    if (url.pathname === "/v1/auth/me") data = { id: "00000000-0000-4000-8000-000000000001", name: "测试管理员", role: "admin", permissions: ["agent.view", "agent.manage", "knowledge.view"], store_ids: [us.id, uk.id] };
    else if (url.pathname === "/v1/settings/stores") data = [us, uk];
    else if (url.pathname.endsWith("/template-source")) {
      if (options.sourceGate && agents[0].draft_revision > 1 && !detached) await options.sourceGate();
      data = options.templateSource ? { agent_id: agents[0].id, store_id: us.id, draft: detached ? null : { template_id: "template", name: "共享模板", archived: false, target_template_version: 2, draft_revision: agents[0].draft_revision, fields: [{ field: "description", local_override: true, applied_template_version: 1, last_reviewed_template_version: 1, aligned: false, pending_review: true }], aligned_count: 0, local_override_count: agents[0].draft_revision, pending_review_count: 1 }, published: { version: agents[0].published_version ?? 1, template_source_json: { template_id: "template", fields: { description: { applied_template_version: 1, baseline_value: "不应展示的基线正文" } } } } } : { agent_id: agents[0].id, store_id: us.id, draft: null, published: null };
    }
    else if (url.pathname.endsWith("/detach-template") && options.templateSource) { writes.push({ detach: request.postDataJSON() }); detached = true; data = agents[0]; }
    else if (url.pathname === "/v1/agents/tool-catalog") data = toolCatalog;
    else if (url.pathname === "/v1/agents/templates") data = { items: [], can_manage: true };
    else if (url.pathname === "/v1/agents/collaboration") data = [];
    else if (url.pathname === "/v1/agents/logistics-notifications/policy") {
      const policy = { store_id: url.searchParams.get("store_id"), agent_id: null, enabled: false, mode: "preview", enabled_at: null, revision: 0, global_enabled: false, real_delivery_enabled: false, last_scan_at: null };
      if (request.method() === "PATCH") { const payload = JSON.parse(request.postData()); writes.push({ policy: payload, store_id: policy.store_id }); Object.assign(policy, payload, { revision: 1 }); }
      data = policy;
    }
    else if (url.pathname === "/v1/agents/auto-reply-preview") {
      const storeId = url.searchParams.get("store_id");
      const current = previewPolicies.get(storeId) ?? { store_id: storeId, enabled: false, revision: 0, mode: "review_preview", send_performed: false };
      if (request.method() === "PUT") {
        const payload = request.postDataJSON();
        writes.push({ auto_preview: payload, store_id: storeId });
        Object.assign(current, { enabled: payload.enabled, revision: current.revision + 1 });
        previewPolicies.set(storeId, current);
      }
      data = current;
    }
    else if (url.pathname === "/v1/agents" && request.method() === "GET") data = agents;
    else if (url.pathname === "/v1/agents" && request.method() === "POST") {
      const payload = JSON.parse(request.postData() ?? "{}"); writes.push(payload);
      data = { ...agent("00000000-0000-4000-8000-0000000000a3", payload.store_id, payload.name), ...payload };
      agents.push(data);
    } else if (url.pathname.startsWith("/v1/agents/") && request.method() === "PATCH") {
      const payload = JSON.parse(request.postData() ?? "{}"); writes.push(payload);
      const current = agents.find((item) => url.pathname.includes(item.id)); Object.assign(current, payload, { draft_revision: current.draft_revision + 1 }); data = current;
    } else if (url.pathname.endsWith("/publish") && request.method() === "POST") {
      const current = agents.find((item) => url.pathname.includes(item.id));
      writes.push({ publish: JSON.parse(request.postData() ?? "{}") });
      current.published_version = (current.published_version ?? 0) + 1;
      data = current;
    } else if ((url.pathname.endsWith("/debug") || url.pathname.endsWith("/debug/stream")) && request.method() === "POST") {
      const payload = JSON.parse(request.postData() ?? "{}");
      writes.push({ debug: payload, path: url.pathname });
      data = { agent_run_id: "00000000-0000-4000-8000-0000000000b1", content: "已查询绑定知识，订单信息需要关联会话。", action: "human_review", terminal_state: "HUMAN_REVIEW", citations: [], tool_calls: [], tool_events: payload.mode === "store" ? [{ agent_id: agents[0].id, tool_name: "query_order", status: "succeeded", call_id: "call-1" }] : [], routed_agents: payload.mode === "store" ? [{ id: agents[0].id, name: agents[0].name }] : [], trace_id: "debug-trace", send_performed: false };
      if (options.operatorTranslation) Object.assign(data, { content: "Your parcel arrives tomorrow.", customer_translation: { trigger_message_id: "synthetic", source_text_sha256: "0".repeat(64), source_language: "en", target_language: "zh-CN", message_translation: "包裹何时到？", draft_translation: "您的包裹明天送达。", prompt_version: "test", provider: "test", model: "test", input_tokens: 1, output_tokens: 1, latency_ms: 1 } });
      if (url.pathname.endsWith("/stream")) {
        if (options.debugGate) await options.debugGate();
        return route.fulfill({ status: 200, contentType: "text/event-stream", body: `event: accepted\ndata: {}\n\nevent: result\ndata: ${JSON.stringify(data)}\n\nevent: done\ndata: {}\n\n` });
      }
    } else if (url.pathname.endsWith("/logs")) data = { items: [], page: 1, page_size: 20, total: 0 };
    else if (url.pathname.endsWith("/approve") && request.method() === "POST") { writes.push(JSON.parse(request.postData() ?? "{}")); data = { ...file.latest_version, approval_status: "approved_for_internal_review" }; }
    else if (url.pathname.endsWith("/revoke") && request.method() === "POST") { writes.push({ revoked: true }); data = { ...file.latest_version, approval_status: "draft" }; }
    else if (url.pathname === "/v1/knowledge/files") data = { items: url.searchParams.get("store_id") === us.id ? [file] : [], page: 1, page_size: 100, total: url.searchParams.get("store_id") === us.id ? 1 : 0 };
    await route.fulfill({ status: 200, contentType: "application/json", headers: { "access-control-allow-origin": new URL(baseUrl).origin, "access-control-allow-credentials": "true" }, body: JSON.stringify({ code: 0, message: "ok", data }) });
  });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/agents?store_id=${us.id}`);
  await page.getByRole("heading", { name: "选择 Agent" }).waitFor({ timeout: 10000 }).catch(async (error) => {
    throw new Error(`${error.message}\nURL: ${page.url()}\nBODY: ${(await page.locator("body").innerText()).slice(0, 1200)}`);
  });
  if (process.env.AGENT_CAPTURE) await page.screenshot({ path: process.env.AGENT_CAPTURE, fullPage: true });
  return { context, page, writes };
}

async function openMore(page) {
  const menu = page.locator(".agent-more");
  if (await menu.getAttribute("open") === null) await page.getByText("更多", { exact: true }).click();
}

test("temporary preview auto-send switch is absent and real Agent settings remain", async () => {
  const { context, page, writes } = await openAgentPage();
  try {
    assert.equal(await page.getByRole("switch", { name: "自动发送原型演示", exact: true }).count(), 0);
    assert.equal(await page.getByText("模拟自动发送", { exact: true }).count(), 0);
    assert.equal(await page.getByRole("button", { name: "保存配置", exact: true }).isEnabled(), true);
    assert.equal(writes.length, 0);
  } finally { await context.close(); }
});

test("auto suggestion preview toggles only the selected store and never offers buyer delivery", async () => {
  const { context, page, writes } = await openAgentPage({ notificationAgent: true });
  try {
    const switchButton = page.getByRole("button", { name: "开启预演" });
    await switchButton.click();
    await page.getByRole("button", { name: "关闭预演" }).waitFor();
    assert.deepEqual(writes.at(-1), { auto_preview: { enabled: true, expected_revision: 0 }, store_id: us.id });
    await page.getByLabel("当前店铺", { exact: true }).selectOption(uk.id);
    await page.getByRole("button", { name: "开启预演" }).waitFor();
    assert.equal(await page.getByRole("button", { name: "开启预演" }).isDisabled(), true);
    assert.equal(await page.getByText("当前店铺收到新买家消息后自动生成待审阅建议；不会发送平台消息。").count(), 1);
  } finally { await context.close(); }
});

test("mobile Agent action toolbar keeps all actions reachable before and after editing", async () => {
  const { context, page, writes } = await openAgentPage();
  try {
    await page.setViewportSize({ width: 390, height: 844 });
    const header = page.locator(".config-head");
    await header.evaluate((element) => element.scrollIntoView({ block: "start", inline: "nearest" }));
    const actions = page.locator(".config-actions");
    await page.getByRole("button", { name: "保存为模板", exact: true }).waitFor({ state: "visible" });
    const buttons = actions.getByRole("button");
    assert.deepEqual(await buttons.allTextContents(), ["保存为模板", "启用", "发布版本", "保存配置"]);
    const assertActionsVisible = async () => {
      const bounds = await actions.evaluate((element) => {
        const card = element.closest(".config");
        const rect = (node) => { const { left, right, top, bottom } = node.getBoundingClientRect(); return { left, right, top, bottom }; };
        return { actions: rect(element), card: rect(card), viewport: { width: innerWidth, height: innerHeight }, buttons: [...element.querySelectorAll("button")].map(rect), scrollLeft: document.querySelector(".app-main")?.scrollLeft ?? 0 };
      });
      assert.equal(bounds.scrollLeft, 0);
      for (const rect of [bounds.actions, ...bounds.buttons]) {
        assert.ok(rect.left >= bounds.card.left && rect.right <= bounds.card.right, `action clipped by card: ${JSON.stringify({ rect, card: bounds.card })}`);
        assert.ok(rect.left >= 0 && rect.right <= bounds.viewport.width && rect.top >= 0 && rect.bottom <= bounds.viewport.height, `action outside viewport: ${JSON.stringify({ rect, viewport: bounds.viewport })}`);
      }
    };
    await assertActionsVisible();
    await page.getByLabel("Agent 名称", { exact: true }).fill("美国客服已编辑");
    await page.getByText("未保存", { exact: true }).waitFor();
    await assertActionsVisible();
    const saved = page.waitForResponse((response) => response.url().includes("/v1/agents/") && response.request().method() === "PATCH");
    await page.getByRole("button", { name: "保存配置", exact: true }).click();
    await saved;
    assert.equal(writes.at(-1).name, "美国客服已编辑");
  } finally { await context.close(); }
});

test("compact More menu keeps template update and exact-revision detach available without a source panel", async () => {
  const { context, page, writes } = await openAgentPage({ templateSource: true });
  try {
    assert.equal(await page.getByRole("heading", { name: "模板来源", exact: true }).count(), 0);
    assert.equal(await page.getByText("不应展示的基线正文").count(), 0);
    await openMore(page);
    await page.getByText("共享模板 · v2", { exact: true }).waitFor();
    assert.match(await page.getByRole("link", { name: "本店差异更新 / 恢复跟随" }).getAttribute("href"), /version=2&store_id=.+&agent_id=/);
    await page.getByRole("button", { name: "解除模板关联" }).click();
    await page.getByRole("button", { name: "确认解除" }).click();
    await openMore(page);
    await page.getByText("当前草稿为独立 Agent，未关联模板。").waitFor();
    assert.deepEqual(writes.at(-1), { detach: { expected_revision: 1 } });
    await page.locator(".config-head").getByText(/已发布 v1/).waitFor();
  } finally { await context.close(); }
});

test("template association refresh after saving and publishing cannot detach an old revision", async () => {
  let release; let started; const gate = new Promise((resolve) => { release = resolve; }); const requested = new Promise((resolve) => { started = resolve; });
  const { context, page, writes } = await openAgentPage({ templateSource: true, sourceGate: async () => { started(); await gate; } });
  try {
    await openMore(page);
    await page.getByText("共享模板 · v2", { exact: true }).waitFor();
    await page.getByLabel("用途描述").fill("新职责");
    assert.equal(await page.getByRole("button", { name: "解除模板关联" }).isDisabled(), true);
    await page.getByRole("button", { name: "保存配置", exact: true }).click();
    await page.getByText("配置已保存").waitFor();
    await Promise.race([requested, new Promise((_, reject) => setTimeout(() => reject(new Error("保存后未请求最新关联")), 3000))]);
    await openMore(page);
    assert.equal(await page.getByRole("button", { name: "解除模板关联" }).count(), 0);
    release(); await page.getByRole("button", { name: "解除模板关联" }).waitFor();
    await page.getByRole("button", { name: "发布版本" }).click();
    await page.locator(".config-head").getByText(/已发布 v2/).waitFor({ timeout: 3000 });
    await openMore(page);
    await page.getByRole("button", { name: "解除模板关联" }).click(); await page.getByRole("button", { name: "确认解除" }).click();
    await openMore(page);
    await page.getByText("当前草稿为独立 Agent，未关联模板。").waitFor(); assert.deepEqual(writes.at(-1), { detach: { expected_revision: 2 } });
  } finally { release(); await context.close(); }
});

test("shared Agent model selector keeps the full provider and colon-containing model name", async () => {
  const { context, page, writes } = await openAgentPage();
  try {
    await page.getByRole("tab", { name: /模型与提示词/ }).click();
    await page.getByLabel("驱动模型 · 已接入").selectOption({ label: "openai / agent::alias:2026" });
    const saved = page.waitForResponse((response) => response.url().includes("/v1/agents/") && response.request().method() === "PATCH");
    await page.getByRole("button", { name: "保存配置", exact: true }).click(); await saved;
    assert.equal(writes.at(-1).model_provider, "openai");
    assert.equal(writes.at(-1).model_name, "agent::alias:2026");
    assert.deepEqual(writes.at(-1).reply_profile, { tone: "friendly", reply_language: "auto", operator_language: "zh-CN", brand_name: null });
  } finally { await context.close(); }
});

test("Agent prototype tabs, store isolation and bound files", async () => {
  const { context, page, writes } = await openAgentPage();
  try {
    assert.equal(await page.getByRole("button", { name: /美国客服/ }).count(), 1);
    await page.getByRole("tab", { name: /模型与提示词/ }).click();
    await page.getByText("七段式系统提示词 · 可编辑").waitFor();
    await page.getByLabel("驱动模型 · 已接入").selectOption({ label: "deepseek / deepseek-v4-pro" });
    await page.getByRole("tab", { name: /知识库/ }).click();
    await page.getByLabel("选择已导入知识").selectOption(file.id);
    await page.getByRole("button", { name: /绑定知识/ }).click();
    const saved = page.waitForResponse((response) => response.url().includes("/v1/agents/") && response.request().method() === "PATCH");
    await page.getByRole("button", { name: "保存配置" }).click();
    await saved;
    assert.deepEqual(writes.at(-1).knowledge_file_ids, [file.id]);
    assert.equal(writes.at(-1).model_name, "deepseek-v4-pro");
    assert.deepEqual(writes.at(-1).prompt_sections, promptSections);
    assert.equal("llm_model" in writes.at(-1), false);
    await page.getByRole("button", { name: "发布版本" }).click();
    await page.getByText(/已发布 v1/).waitFor();
    await page.getByLabel("确认语义类型：物流说明.pdf").selectOption("policy");
    await page.getByRole("button", { name: "批准内部建议" }).click();
    await page.getByText("可用于内部建议").waitFor();
    assert.equal(writes.at(-1).statement_type, "policy");
    await page.getByRole("button", { name: "撤销审批" }).click();
    await page.getByText("暂不可检索").waitFor();
    assert.deepEqual(writes.at(-1), { revoked: true });
    await page.getByLabel("当前店铺", { exact: true }).selectOption(uk.id);
    await page.getByRole("heading", { name: "英国客服" }).waitFor();
    assert.equal(await page.getByText("物流说明.pdf").count(), 0);
  } finally { await context.close(); }
});

test("logistics notification policy saves only an explicit preview strategy while deployment switches remain off", async () => {
  const { context, page, writes } = await openAgentPage({ notificationAgent: true });
  try {
    await page.getByRole("tab", { name: /工具能力/ }).click();
    const section = page.getByRole("region", { name: "物流更新通知策略", exact: true });
    await section.getByText(/全局通知未启用/).waitFor();
    await section.getByRole("checkbox", { name: "启用本店预演策略", exact: true }).check();
    await section.getByRole("combobox", { name: "通知 Agent", exact: true }).selectOption("00000000-0000-4000-8000-0000000000a1");
    await section.getByRole("button", { name: "保存为预演策略", exact: true }).click();
    await section.getByText("预演策略已保存；未开启真实通知", { exact: true }).waitFor();
    assert.deepEqual(writes.at(-1), { store_id: us.id, policy: { enabled: true, agent_id: "00000000-0000-4000-8000-0000000000a1", mode: "preview", expected_revision: 0 } });
    await section.getByText(/真实外发未启用/).waitFor();
    assert.equal(writes.some((write) => write.policy?.mode === "external"), false);
  } finally { await context.close(); }
});

test("tool catalog shows six groups, searchable cards, operation labels and knowledge navigation", async () => {
  const { context, page, writes } = await openAgentPage();
  try {
    await page.getByRole("tab", { name: /工具能力/ }).click();
    for (const name of ["订单与物流", "商品与优惠", "售后服务", "客户与会话", "知识检索", "人工协作"]) {
      await page.getByRole("heading", { name, exact: true }).waitFor();
    }
    assert.equal(await page.locator(".capability-card").count(), 17);
    const notification = page.locator(".capability-card").filter({ hasText: "notify_logistics_update" });
    await notification.getByText("店铺策略通知", { exact: true }).waitFor({ timeout: 1500 });
    if (process.env.AGENT_TOOL_CAPTURE) {
      await page.locator(".capability-panel").evaluate((element) => element.scrollIntoView({ block: "start" }));
      await page.screenshot({ path: process.env.AGENT_TOOL_CAPTURE });
    }
    await page.getByLabel("搜索工具").fill("售后");
    assert.equal(await page.locator(".capability-card").count(), 1);
    await page.getByRole("checkbox", { name: "启用售后查询" }).check();
    await page.getByRole("button", { name: "保存配置" }).click();
    assert.ok(writes.at(-1).enabled_tools.includes("query_aftersales"));
    await page.getByLabel("搜索工具").fill("");
    await page.getByRole("button", { name: "配置知识文件" }).click();
    await page.getByLabel("选择已导入知识").waitFor();
    await page.getByLabel("选择已导入知识").selectOption(file.id);
    await page.getByRole("button", { name: /绑定知识/ }).click();
    await page.getByRole("tab", { name: /工具能力/ }).click();
    await page.getByText("已绑定文件", { exact: true }).waitFor();
    assert.equal(await page.getByRole("checkbox", { name: "启用知识检索" }).isChecked(), true);
    await page.getByRole("button", { name: "保存配置" }).click();
    await page.getByText("3 项工具", { exact: true }).waitFor();
    await page.setViewportSize({ width: 720, height: 900 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  } finally { await context.close(); }
});

test("switching stores ignores a late tool catalog response from the previous store", async () => {
  const { context, page } = await openAgentPage();
  let release;
  let requested;
  const started = new Promise((resolve) => { requested = resolve; });
  const hold = new Promise((resolve) => { release = resolve; });
  await context.route("**/v1/agents/tool-catalog?**", async (route) => {
    const oldStore = new URL(route.request().url()).searchParams.get("store_id") === us.id;
    if (oldStore) { requested(); await hold; }
    const data = structuredClone(toolCatalog);
    data.tools[0].title = oldStore ? "美国专属目录" : "英国专属目录";
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, data }) });
  });
  try {
    await page.getByRole("tab", { name: /工具能力/ }).click();
    await started;
    await page.getByLabel("当前店铺", { exact: true }).selectOption(uk.id);
    await page.getByRole("button", { name: /英国客服/ }).waitFor();
    await page.getByRole("tab", { name: /工具能力/ }).click();
    await page.getByText("英国专属目录", { exact: true }).waitFor();
    const response = page.waitForResponse((item) => item.url().includes("tool-catalog") && item.url().includes(us.id));
    release();
    await response;
    assert.equal(await page.getByText("美国专属目录", { exact: true }).count(), 0);
    assert.equal(await page.getByText("英国专属目录", { exact: true }).count(), 1);
  } finally { release(); await context.close(); }
});

test("internal collaboration records are labelled as AI suggestions and cleared on store change", async () => {
  const { context, page } = await openAgentPage();
  const conversation = "00000000-0000-4000-8000-0000000000e1";
  await context.route("**/v1/workspace/sessions?**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, data: { items: [{ id: conversation, store_id: us.id, customer: { name: "合成买家" } }], pagination: { page: 1, page_size: 50, total: 1 } } }) }));
  await context.route("**/v1/agents/collaboration?**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, data: [{ id: "note-1", kind: "handoff_request", content: "请核实退货进度，尚未完成会话转交。", created_at: "2026-10-28T00:00:00Z", agent_run_id: "run-1", is_ai_suggestion: true, send_performed: false, transfer_performed: false }] }) }));
  try {
    await page.reload();
    await page.getByLabel("只读工具上下文").selectOption(conversation);
    await page.getByRole("heading", { name: "内部协作记录" }).waitFor();
    await page.getByText("AI 建议", { exact: true }).waitFor();
    await page.getByText("请核实退货进度，尚未完成会话转交。", { exact: true }).waitFor();
    await page.getByLabel("当前店铺", { exact: true }).selectOption(uk.id);
    await page.getByRole("button", { name: /英国客服/ }).waitFor();
    assert.equal(await page.getByText("请核实退货进度，尚未完成会话转交。", { exact: true }).count(), 0);
  } finally { await context.close(); }
});

test("disabled Agent live debug calls backend without platform sending", async () => {
  const { context, page, writes } = await openAgentPage();
  const requests = [];
  page.on("request", (request) => requests.push(new URL(request.url()).pathname));
  try {
    await page.getByRole("button", { name: "新建 Agent" }).click();
    await page.getByRole("dialog", { name: "新建 Agent" }).getByLabel("Agent 编码").fill("service_us_new");
    await page.getByRole("dialog", { name: "新建 Agent" }).getByLabel("Agent 名称").fill("新客服");
    await page.getByRole("button", { name: "创建 Agent" }).click();
    await page.getByRole("dialog", { name: "新建 Agent" }).waitFor({ state: "hidden" });
    assert.equal(writes.at(-1).code, "service_us_new");
    await page.getByRole("tab", { name: /知识库/ }).click();
    await page.getByLabel("选择已导入知识").selectOption(file.id);
    await page.getByRole("button", { name: /绑定知识/ }).click();
    await page.getByRole("button", { name: "保存配置" }).click();
    assert.deepEqual(writes.at(-1).knowledge_file_ids, [file.id]);
    await page.getByPlaceholder(/试试/).fill("你好");
    await page.getByRole("button", { name: "运行调试" }).click();
    await page.getByText(/已查询绑定知识/).waitFor();
    assert.deepEqual(writes.at(-1), { debug: { message: "你好", conversation_id: null, mode: "single" }, path: "/v1/agents/00000000-0000-4000-8000-0000000000a3/debug/stream" });
    assert.equal(requests.some((path) => path.includes("/chat/query") || path.includes("/messages")), false);
  } finally { await context.close(); }
});

test("store debug sends multi-Agent mode and renders route and tool events", async () => {
  const { context, page, writes } = await openAgentPage();
  try {
    await page.getByLabel("调试范围").selectOption("store");
    await page.getByPlaceholder(/试试/).fill("请同时查订单和物流");
    await page.getByRole("button", { name: "运行调试" }).click();
    await page.getByText("路由：美国客服").waitFor();
    await page.getByText("工具：query_order（succeeded）").waitFor();
    assert.equal(writes.at(-1).debug.mode, "store");
  } finally { await context.close(); }
});


test("debug clears submitted input immediately and preserves next draft", async () => {
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  const { context, page } = await openAgentPage({ debugGate: () => gate });
  try {
    await page.getByPlaceholder(/试试/).fill("我的订单到哪了");
    await page.getByRole("button", { name: "运行调试" }).click();
    assert.equal(await page.getByPlaceholder(/试试/).inputValue(), "");
    await page.locator(".preview-bubble.user").getByText("我的订单到哪了", { exact: true }).waitFor();
    await page.getByPlaceholder(/试试/).fill("下一条问题");
    release();
    await page.getByText(/已查询绑定知识/).waitFor();
    assert.equal(await page.getByPlaceholder(/试试/).inputValue(), "下一条问题");
  } finally { release(); await context.close(); }
});


async function installDebugStream(page) {
  await page.evaluate(() => {
    const original = window.fetch;
    window.fetch = async (...args) => {
      if (!String(args[0]).endsWith("/debug/stream")) return original(...args);
      const encoder = new TextEncoder();
      const body = new ReadableStream({
        start(controller) {
          window.debugEmit = (event, data) => controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
          window.debugEmit("accepted", {});
          window.debugFinish = () => { window.debugEmit("done", {}); controller.close(); };
        },
      });
      return new Response(body, { headers: { "content-type": "text/event-stream" } });
    };
  });
}

test("operator translation remains separate from the customer reply in debug", async () => {
  const { context, page } = await openAgentPage({ operatorTranslation: true });
  try {
    await page.getByPlaceholder(/试试/).fill("When does my parcel arrive?");
    await page.getByRole("button", { name: "运行调试" }).click();
    await page.locator(".preview-bubble.assistant").getByText("Your parcel arrives tomorrow.", { exact: true }).waitFor();
    await page.getByText("坐席译文 · 简体中文", { exact: true }).click({ timeout: 5000 });
    await page.getByText("您的包裹明天送达。", { exact: true }).waitFor();
    assert.equal(await page.locator(".preview-bubble.assistant").getByText("您的包裹明天送达。", { exact: true }).count(), 0);
  } finally { await context.close(); }
});

test("reply preferences explain separate customer and operator languages and retain saved selections", async () => {
  const { context, page, writes } = await openAgentPage();
  try {
    await page.getByRole("tab", { name: /模型与提示词/ }).click();
    await page.getByRole("heading", { name: "回复偏好", exact: true }).waitFor();
    await page.getByText(/坐席语言用于内部说明或译文，不改变客户正文/).waitFor();
    await page.getByLabel("回复语气", { exact: true }).selectOption("empathetic");
    await page.getByLabel("客户回复语言", { exact: true }).selectOption("en");
    await page.getByLabel("坐席工作语言", { exact: true }).selectOption("zh-CN");
    await page.getByRole("button", { name: "保存配置", exact: true }).click();
    await page.getByText("配置已保存", { exact: true }).waitFor();
    assert.deepEqual(writes.at(-1).reply_profile, { tone: "empathetic", reply_language: "en", operator_language: "zh-CN", brand_name: null });
    await page.getByRole("button", { name: "发布版本", exact: true }).click();
    await page.getByText("Agent 已发布，后续运行将使用这个不可变版本", { exact: true }).waitFor();
    assert.equal(await page.getByLabel("回复语气", { exact: true }).inputValue(), "empathetic");
    assert.equal(await page.getByLabel("客户回复语言", { exact: true }).inputValue(), "en");
    assert.equal(await page.getByLabel("坐席工作语言", { exact: true }).inputValue(), "zh-CN");
    if (process.env.AGENT_TEMPLATE_UI_CAPTURE) {
      await page.locator(".policy-card").evaluate((element) => element.scrollIntoView({ block: "start" }));
      await page.screenshot({ path: fileURLToPath(new URL("../../.artifacts/agent-template-ui-20261031/frontend-preferences-desktop.png", import.meta.url)) });
      await page.setViewportSize({ width: 390, height: 844 });
      await page.locator(".policy-card").evaluate((element) => element.scrollIntoView({ block: "start" }));
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
      await page.screenshot({ path: fileURLToPath(new URL("../../.artifacts/agent-template-ui-20261031/frontend-preferences-mobile.png", import.meta.url)) });
    }
  } finally { await context.close(); }
});

test("debug renders progressive drafts then replaces with reviewed result", async () => {
  const { context, page } = await openAgentPage();
  try {
    await installDebugStream(page);
    await page.getByPlaceholder(/试试/).fill("Where is my order?");
    await page.getByRole("button", { name: "运行调试" }).click();
    await page.evaluate(() => window.debugEmit("draft", { part_index: 0, text: "Your parcel", unverified: true, sendable: false }));
    await page.getByLabel("待复核草稿").getByText("Your parcel", { exact: true }).waitFor();
    await page.evaluate(() => window.debugEmit("draft", { part_index: 0, text: "Your parcel arrived", unverified: true, sendable: false }));
    await page.getByLabel("待复核草稿").getByText("Your parcel arrived", { exact: true }).waitFor();
    await page.getByPlaceholder(/试试/).fill("Next question");
    await page.evaluate(() => {
      window.debugEmit("result", { agent_run_id: "run", content: "Delivered today.", terminal_state: "review_ready", routed_agents: [], tool_events: [{ tool_name: "query_logistics", status: "succeeded" }], tool_calls: [], citations: [{source_label:"delivery.md"}], trace_id: "stream-trace" });
      window.debugFinish();
    });
    await page.getByText("Delivered today.", { exact: true }).waitFor();
    assert.equal(await page.getByLabel("待复核草稿").count(), 0);
    assert.equal(await page.getByPlaceholder(/试试/).inputValue(), "Next question");
    await page.getByText("引用：delivery.md", { exact: true }).waitFor();
  } finally { await context.close(); }
});

test("debug error removes unreviewed drafts and preserves new input", async () => {
  const { context, page } = await openAgentPage();
  try {
    await installDebugStream(page);
    await page.getByPlaceholder(/试试/).fill("First question");
    await page.getByRole("button", { name: "运行调试" }).click();
    await page.evaluate(() => window.debugEmit("draft", { part_index: 0, text: "Unreviewed" }));
    await page.getByLabel("待复核草稿").waitFor();
    await page.getByPlaceholder(/试试/).fill("Keep this next question");
    await page.evaluate(() => { window.debugEmit("error", {message:"模型超时"}); window.debugFinish(); });
    await page.getByText("模型超时", {exact:true}).waitFor();
    assert.equal(await page.getByLabel("待复核草稿").count(),0);
    assert.equal(await page.getByPlaceholder(/试试/).inputValue(),"Keep this next question");
    assert.equal(await page.locator(".preview-bubble.user").innerText(),"First question");
  } finally { await context.close(); }
});

test("debug store switch ignores late draft and result", async () => {
  const { context, page } = await openAgentPage();
  try {
    await installDebugStream(page);
    await page.getByPlaceholder(/试试/).fill("US question");
    await page.getByRole("button", { name: "运行调试" }).click();
    await page.getByLabel("当前店铺", {exact:true}).selectOption(uk.id);
    await page.evaluate(() => {
      window.debugEmit("draft", { part_index: 0, text:"OLD-US-DRAFT" });
      window.debugEmit("result", {content:"OLD-US-RESULT"}); window.debugFinish();
    });
    assert.equal(await page.getByText("OLD-US-DRAFT",{exact:true}).count(),0);
    assert.equal(await page.getByText("OLD-US-RESULT",{exact:true}).count(),0);
    assert.equal(await page.locator(".preview-bubble").count(),0);
  } finally { await context.close(); }
});
