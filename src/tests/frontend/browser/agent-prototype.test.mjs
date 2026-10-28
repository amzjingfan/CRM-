import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
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
  runtime: { available: true, llm_provider: "deepseek", llm_model: "deepseek-v4-flash", available_models: ["deepseek-v4-flash", "deepseek-v4-pro"], model_options: [{ provider: "deepseek", model_name: "deepseek-v4-flash" }, { provider: "deepseek", model_name: "deepseek-v4-pro" }], embedding_provider: "local_bge", embedding_model: "BAAI/bge-m3", reranker_model: "BAAI/bge-reranker-large", prompt_versions: {}, auto_reply_threshold: 0.85, human_review_threshold: 0.5, token_streaming: false },
  created_at: "2026-10-26T00:00:00Z", updated_at: "2026-10-26T00:00:00Z",
});
let browser;
before(async () => { browser = await chromium.launch({ channel: "chrome", headless: true }); });
after(async () => { await browser?.close(); });

async function openAgentPage() {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const agents = [agent("00000000-0000-4000-8000-0000000000a1", us.id, "美国客服"), agent("00000000-0000-4000-8000-0000000000a2", uk.id, "英国客服")];
  const writes = [];
  await context.route("**/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: { "access-control-allow-origin": new URL(baseUrl).origin, "access-control-allow-credentials": "true" } });
    let data = [];
    if (url.pathname === "/v1/auth/me") data = { id: "00000000-0000-4000-8000-000000000001", name: "测试管理员", role: "admin", permissions: ["agent.view", "agent.manage", "knowledge.view"], store_ids: [us.id, uk.id] };
    else if (url.pathname === "/v1/settings/stores") data = [us, uk];
    else if (url.pathname === "/v1/agents/tool-catalog") data = toolCatalog;
    else if (url.pathname === "/v1/agents/collaboration") data = [];
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
    } else if (url.pathname.endsWith("/debug") && request.method() === "POST") {
      const payload = JSON.parse(request.postData() ?? "{}");
      writes.push({ debug: payload, path: url.pathname });
      data = { agent_run_id: "00000000-0000-4000-8000-0000000000b1", content: "已查询绑定知识，订单信息需要关联会话。", action: "human_review", terminal_state: "HUMAN_REVIEW", citations: [], tool_calls: [], tool_events: payload.mode === "store" ? [{ agent_id: agents[0].id, tool_name: "query_order", status: "succeeded", call_id: "call-1" }] : [], routed_agents: payload.mode === "store" ? [{ id: agents[0].id, name: agents[0].name }] : [], trace_id: "debug-trace", send_performed: false };
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

test("Agent prototype tabs, store isolation and bound files", async () => {
  const { context, page, writes } = await openAgentPage();
  try {
    assert.equal(await page.getByRole("button", { name: /美国客服/ }).count(), 1);
    await page.getByRole("tab", { name: /模型与提示词/ }).click();
    await page.getByText("七段式系统提示词 · 可编辑").waitFor();
    await page.getByLabel("驱动模型 · 已接入").selectOption("deepseek::deepseek-v4-pro");
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

test("tool catalog shows six groups, searchable cards, operation labels and knowledge navigation", async () => {
  const { context, page, writes } = await openAgentPage();
  try {
    await page.getByRole("tab", { name: /工具能力/ }).click();
    for (const name of ["订单与物流", "商品与优惠", "售后服务", "客户与会话", "知识检索", "人工协作"]) {
      await page.getByRole("heading", { name, exact: true }).waitFor();
    }
    assert.equal(await page.locator(".capability-card").count(), 16);
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
    assert.deepEqual(writes.at(-1), { debug: { message: "你好", conversation_id: null, mode: "single" }, path: "/v1/agents/00000000-0000-4000-8000-0000000000a3/debug" });
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
