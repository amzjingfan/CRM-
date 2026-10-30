import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { after, before, test } from "node:test";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");
const baseUrl = process.env.UI_BASE_URL ?? "http://localhost:3146";
if (!["127.0.0.1", "localhost", "::1"].includes(new URL(baseUrl).hostname)) throw new Error("local browser only");
const catalog = JSON.parse(readFileSync(new URL("./fixtures/agent-tool-catalog.json", import.meta.url), "utf8"));
const sections = ["identity", "service_scope", "tool_rules", "escalation", "language_format", "compliance", "clarification"];
const config = (name = "默认客服") => ({ default_agent_name: name, suggested_code: "service_default", agent_type: "service", description: "职责描述", model_provider: "openai", model_name: "alias::model:2026", prompt_sections: Object.fromEntries(sections.map((key) => [key, `${key} 完整说明`])), tool_names: [], knowledge_slots: [] });
const template = (id, name, manager = true) => ({ id, code: `template_${id}`, name, description: "模板职责", draft_revision: manager ? 2 : null, published_version: 1, archived_at: null, config: config(manager ? "私有草稿" : "已发布客服"), published_config: config("已发布客服"), can_manage: manager, linked_store_count: 2, update_count: 1, created_at: "2026-10-30T00:00:00Z", updated_at: "2026-10-30T00:00:00Z" });
let browser;
before(async () => { browser = await chromium.launch({ channel: "chrome", headless: true }); });
after(async () => { await browser?.close(); });

async function open(options = {}) {
  const manager = options.manager ?? true;
  const context = await browser.newContext({ viewport: options.mobile ? { width: 390, height: 844 } : { width: 1440, height: 980 } });
  const items = options.empty ? [] : [template("one", "售后模板", manager), template("two", "物流模板", manager)];
  const writes = [];
  const histories = new Map(items.map((item) => [item.id, [{ version: 1, config: config("已发布客服"), content_sha256: "test", published_at: "2026-10-30T00:00:00Z" }]]));
  let releaseHistory;
  let historyStarted;
  const oldHistoryGate = new Promise((resolve) => { releaseHistory = resolve; });
  const oldHistoryStarted = new Promise((resolve) => { historyStarted = resolve; });
  let releaseSave;
  let saveStarted;
  const saveGate = new Promise((resolve) => { releaseSave = resolve; });
  const pendingSaveStarted = new Promise((resolve) => { saveStarted = resolve; });
  let heldHistory = false;
  let conflict = options.conflict;
  const headers = { "access-control-allow-origin": new URL(baseUrl).origin, "access-control-allow-credentials": "true", "access-control-allow-headers": "content-type,x-csrf-token,idempotency-key" };
  await context.route("**/v1/**", async (route) => {
    const request = route.request(); const url = new URL(request.url()); const path = url.pathname; const method = request.method();
    if (method === "OPTIONS") return route.fulfill({ status: 204, headers });
    let data = []; let status = 200; let message = "ok";
    if (path === "/v1/auth/me") data = { id: "reader", name: "测试维护者", role: "admin", permissions: ["agent.view"], store_ids: [] };
    else if (path === "/v1/agents/templates/catalog") data = { groups: catalog.groups, tools: catalog.tools.map((tool) => ({ name: tool.name, title: tool.title, description: tool.description, category: tool.category, operation: tool.operation, requires_context: tool.requires_context })), model_options: [{ provider: "openai", model_name: "alias::model:2026" }, { provider: "deepseek", model_name: "deepseek-v4" }], prompt_sections: sections.map((key, i) => ({ key, title: `${i + 1} ${key}` })) };
    else if (path === "/v1/agents/templates" && method === "GET") data = { items: items.filter((item) => !item.archived_at || url.searchParams.get("include_archived") === "true"), can_manage: manager };
    else if ((path === "/v1/agents/templates" || path === "/v1/agents/templates/from-agent") && method === "POST") {
      const body = request.postDataJSON(); writes.push({ path, body });
      data = { ...template("new", body.name), code: body.code, published_version: null, published_config: null, draft_revision: 1, config: body.config ?? config(body.name) }; items.push(data);
    } else if (path.startsWith("/v1/agents/templates/")) {
      const id = path.split("/")[4]; const item = items.find((row) => row.id === id);
      if (options.delayed && id === "one" && method === "GET") await new Promise((resolve) => setTimeout(resolve, 650));
      if (path.endsWith("/versions")) {
        data = options.reversedHistory ? structuredClone(histories.get(id)) : [{ version: 1, config: config(options.delayedHistory ? `${id} 已发布客服` : "已发布客服"), content_sha256: "test", published_at: "2026-10-30T00:00:00Z" }];
        if (options.reversedHistory && id === "one" && item.published_version === 2 && !heldHistory) {
          heldHistory = true;
          historyStarted(); await oldHistoryGate;
          if (options.rejectOldHistory) { status = 503; message = "旧历史读取失败"; }
        } else if (options.rejectRecoveryHistory && id === "one" && item.published_version === 2) {
          status = 503; message = "恢复历史读取失败";
        } else if (options.delayedHistory && id === "one" && writes.some((write) => write.path.endsWith("/publish"))) await new Promise((resolve) => setTimeout(resolve, 650));
      }
      else if (method === "GET") data = item;
      else {
        const body = request.postDataJSON(); writes.push({ path, body });
        if (options.delayedSave && method === "PATCH") { saveStarted(); await saveGate; }
        if (options.failLaterPublication && path.endsWith("/publish") && item.published_version === 2) { status = options.failLaterPublication; message = "后次发布被拒绝"; }
        else if (conflict) { conflict = false; status = 409; message = "模板已被更新，请重新加载后重试"; }
        else {
          if (method === "PATCH") Object.assign(item, body);
          if (path.endsWith("/publish")) Object.assign(item, { published_version: (item.published_version ?? 0) + 1, published_config: structuredClone(item.config) });
          if (options.reversedHistory && path.endsWith("/publish")) histories.get(id).push({ version: item.published_version, config: structuredClone(item.config), content_sha256: "test", published_at: "2026-10-30T01:00:00Z" });
          if (path.endsWith("/archive")) item.archived_at = "2026-10-30T01:00:00Z";
          if (path.endsWith("/restore")) item.archived_at = null;
          item.draft_revision++; data = item;
        }
      }
    } else if (path === "/v1/settings/stores") data = [{ id: "store", name: "合成店铺" }];
    else if (path.endsWith("/template-source")) data = { agent_id: "agent", store_id: "store", draft: null, published: { version: 3, template_source_json: null } };
    else if (path === "/v1/agents") data = [{ id: "agent", store_id: "store", name: "源客服", code: "service_source", description: "源职责", agent_type: "service", status: "disabled", published_version: 3, draft_revision: 8, model_provider: "openai", model_name: "alias::model:2026", prompt_sections: config().prompt_sections, enabled_tools: [], knowledge_file_ids: ["private-file"], reply_profile: { tone: "friendly", reply_language: "auto", operator_language: "zh-CN", brand_name: null }, runtime: { model_options: [{ provider: "openai", model_name: "alias::model:2026" }] } }];
    else if (path === "/v1/knowledge/files" || path.endsWith("/logs") || path === "/v1/workspace/sessions") data = { items: [], total: 0 };
    await route.fulfill({ status, headers, contentType: "application/json", body: JSON.stringify({ code: status === 200 ? 0 : 40901, message, data }) });
  });
  const page = await context.newPage(); page.setDefaultTimeout(8000);
  await page.goto(`${baseUrl}${options.agents ? "/agents" : "/agents/templates"}`);
  await page.getByRole("heading", { name: options.agents ? "选择 Agent" : "Agent 模板", exact: true }).waitFor();
  return { page, context, writes, items, releaseHistory, oldHistoryStarted, releaseSave, pendingSaveStarted };
}

test("empty global library can be created by server-authorized manager with no shop", async () => {
  const { page, context, writes } = await open({ empty: true });
  try {
    assert.equal(await page.getByLabel("当前店铺", { exact: true }).count(), 0);
    await page.getByRole("button", { name: "新建模板", exact: true }).click();
    await page.getByLabel("模板名称", { exact: true }).fill("新模板");
    await page.getByLabel("模板编码", { exact: true }).fill("template_new");
    await page.getByRole("button", { name: "创建草稿", exact: true }).click();
    await page.getByText("草稿已创建，尚未发布", { exact: true }).waitFor();
    assert.equal(writes[0].body.name, "新模板");
    assert.equal(writes.some((write) => write.path.endsWith("/publish")), false);
  } finally { await context.close(); }
});

test("shared model pair and seven sections save draft independently from immutable publication", async () => {
  const { page, context, writes, items } = await open();
  try {
    await page.getByLabel("默认 Agent 名称").fill("新草稿客服");
    await page.getByLabel("驱动模型 · 已接入").selectOption({ label: "deepseek / deepseek-v4" });
    await page.getByLabel("驱动模型 · 已接入").selectOption({ label: "openai / alias::model:2026" });
    assert.equal(await page.locator(".prompt-section textarea").count(), 7);
    assert.equal(await page.locator(".capability-card").count(), catalog.tools.length);
    await page.getByLabel("搜索工具", { exact: true }).fill(catalog.tools[0].name);
    assert.equal(await page.locator(".capability-card").count(), 1);
    await page.getByLabel("搜索工具", { exact: true }).fill("");
    await page.getByRole("checkbox", { name: `启用${catalog.tools[0].title}`, exact: true }).check();
    await page.getByLabel("展示范围", { exact: true }).selectOption("selected");
    assert.equal(await page.locator(".capability-card").count(), 1);
    await page.getByLabel("展示范围", { exact: true }).selectOption("all");
    await page.getByRole("button", { name: "添加知识需求" }).click();
    await page.getByLabel("需求键 1", { exact: true }).fill("shipping_policy");
    await page.getByLabel("需求名称 1", { exact: true }).fill("物流政策");
    await page.getByLabel("需求用途 1", { exact: true }).fill("核实物流时效");
    await page.getByRole("button", { name: "保存草稿", exact: true }).click();
    await page.getByText("草稿已保存；已发布版本和店铺运行保持原样", { exact: true }).waitFor();
    assert.equal(items[0].published_config.default_agent_name, "已发布客服");
    assert.equal(writes[0].body.config.model_name, "alias::model:2026");
    assert.equal(writes[0].body.config.model_provider, "openai");
    assert.deepEqual(writes[0].body.config.tool_names, [catalog.tools[0].name]);
    assert.deepEqual(writes[0].body.config.knowledge_slots, [{ key: "shipping_policy", name: "物流政策", purpose: "核实物流时效", required: false }]);
    assert.equal("reply_profile" in writes[0].body.config, false);
    await page.getByLabel("查看版本").selectOption("1");
    assert.equal(await page.getByLabel("默认 Agent 名称").inputValue(), "已发布客服");
    assert.equal(await page.getByLabel("默认 Agent 名称").isDisabled(), true);
    await page.getByLabel("查看版本").selectOption("draft");
    await page.getByRole("button", { name: "发布模板", exact: true }).click();
    await page.getByText("模板已发布；关联店铺须另行审阅应用", { exact: true }).waitFor();
    assert.deepEqual(writes.at(-1).body, { expected_revision: 3 });
  } finally { await context.close(); }
});

test("409 keeps unsaved form and lets user explicitly reload", async () => {
  const { page, context } = await open({ conflict: true });
  try {
    await page.getByLabel("默认 Agent 名称").fill("不要丢失的编辑");
    await page.getByRole("button", { name: "保存草稿", exact: true }).click();
    await page.getByRole("alert").filter({ hasText: "模板已被更新" }).waitFor();
    assert.equal(await page.getByLabel("默认 Agent 名称").inputValue(), "不要丢失的编辑");
    await page.getByRole("button", { name: "重新加载此模板" }).click();
    await page.getByRole("button", { name: "放弃编辑并重新加载" }).click();
    await page.waitForFunction(() => document.querySelector('input[aria-label="默认 Agent 名称"]')?.value === "私有草稿");
  } finally { await context.close(); }
});

test("archive and restore use keyboard-accessible modal with focus restored", async () => {
  const { page, context, writes } = await open();
  try {
    const archive = page.getByRole("button", { name: "归档模板", exact: true });
    await archive.click();
    const dialog = page.getByRole("dialog", { name: "归档模板", exact: true }); await dialog.waitFor();
    await page.keyboard.press("Escape"); await dialog.waitFor({ state: "hidden" });
    assert.equal(await archive.evaluate((element) => element === document.activeElement), true);
    await archive.click();
    await page.keyboard.press("Shift+Tab");
    assert.equal(await dialog.getByRole("button", { name: "确认归档" }).evaluate((element) => element === document.activeElement), true);
    await dialog.getByRole("button", { name: "确认归档" }).click();
    await page.getByRole("button", { name: "恢复模板", exact: true }).click();
    await page.getByRole("dialog", { name: "恢复模板", exact: true }).getByRole("button", { name: "确认恢复" }).click();
    await page.getByText("模板已恢复", { exact: true }).waitFor();
    assert.deepEqual(writes.map((write) => write.body), [{ expected_revision: 2 }, { expected_revision: 3 }]);
  } finally { await context.close(); }
});

test("reader sees only published config with no manager actions even if role claims admin", async () => {
  const { page, context } = await open({ manager: false, mobile: true });
  try {
    await page.getByLabel("默认 Agent 名称").waitFor();
    assert.equal(await page.getByLabel("默认 Agent 名称").inputValue(), "已发布客服");
    assert.equal(await page.getByLabel("默认 Agent 名称").isDisabled(), true);
    for (const name of ["新建模板", "保存草稿", "发布模板", "归档模板", "恢复模板"]) assert.equal(await page.getByRole("button", { name, exact: true }).count(), 0);
    assert.equal(await page.getByText("私有草稿", { exact: true }).count(), 0);
    assert.equal(await page.locator('option[value="draft"]').count(), 0);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    if (process.env.TEMPLATE_CAPTURE) await page.screenshot({ path: process.env.TEMPLATE_CAPTURE, fullPage: true });
  } finally { await context.close(); }
});

test("late detail response cannot replace the newly selected template", async () => {
  const { page, context } = await open({ delayed: true });
  try {
    await page.getByRole("button", { name: /物流模板.*服务类/ }).click();
    await page.getByRole("heading", { name: "物流模板", exact: true }).waitFor();
    await page.waitForTimeout(800);
    assert.equal(await page.getByRole("heading", { name: "物流模板", exact: true }).count(), 1);
    assert.equal(await page.getByRole("heading", { name: "售后模板", exact: true }).count(), 0);
  } finally { await context.close(); }
});

test("Agent extraction requires exact saved source and never copies file bindings or reply settings", async () => {
  const { page, context, writes } = await open({ agents: true });
  try {
    await page.getByRole("button", { name: "保存为模板", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "保存为模板", exact: true });
    await dialog.getByLabel("模板名称", { exact: true }).fill("源版本模板");
    await dialog.getByLabel("模板编码", { exact: true }).fill("source_template");
    await dialog.getByLabel("提取来源").selectOption("published");
    await dialog.getByRole("button", { name: "创建模板草稿" }).click();
    await page.getByText("模板草稿已创建，尚未发布", { exact: true }).waitFor();
    assert.deepEqual(writes.at(-1).body, { name: "源版本模板", code: "source_template", description: null, source_agent_id: "agent", source_version: 3, source_draft_revision: null, knowledge_slots: [] });
    assert.equal(JSON.stringify(writes).includes("private-file"), false);
  } finally { await context.close(); }
});

test("late publication history cannot replace a different template history", async () => {
  const { page, context } = await open({ delayedHistory: true });
  try {
    await page.getByLabel("默认 Agent 名称").waitFor();
    await page.getByRole("button", { name: "发布模板", exact: true }).click();
    await page.getByText("模板已发布；关联店铺须另行审阅应用", { exact: true }).waitFor();
    await page.getByRole("button", { name: /物流模板.*服务类/ }).click();
    await page.getByRole("heading", { name: "物流模板", exact: true }).waitFor();
    await page.getByLabel("查看版本").selectOption("1");
    await page.waitForTimeout(850);
    assert.equal(await page.getByLabel("默认 Agent 名称").inputValue(), "two 已发布客服");
  } finally { await context.close(); }
});

test("empty reader library hides create action and remains read-only", async () => {
  const { page, context } = await open({ empty: true, manager: false });
  try {
    await page.getByText("模板库为空", { exact: true }).waitFor();
    assert.equal(await page.getByRole("button", { name: "新建模板", exact: true }).count(), 0);
    assert.equal(await page.getByRole("checkbox", { name: /归档/ }).count(), 0);
  } finally { await context.close(); }
});

test("template search filters rows and archive filter retrieves archived library", async () => {
  const { page, context } = await open();
  try {
    await page.getByLabel("默认 Agent 名称").waitFor();
    await page.getByRole("button", { name: "归档模板", exact: true }).click();
    await page.getByRole("button", { name: "确认归档" }).click();
    await page.getByText("模板已归档", { exact: true }).waitFor();
    assert.equal(await page.locator(".template-list-item").count(), 1);
    await page.getByRole("checkbox", { name: "包含已归档模板" }).check();
    await page.locator(".template-list-item").filter({ hasText: "已归档" }).waitFor();
    await page.getByLabel("搜索模板", { exact: true }).fill("物流");
    assert.equal(await page.locator(".template-list-item").count(), 1);
    await page.getByLabel("搜索模板", { exact: true }).fill("无匹配需求");
    await page.getByText("没有符合搜索条件的模板", { exact: true }).waitFor();
  } finally { await context.close(); }
});

test("saved Agent draft source preserves exact revision separately from published version", async () => {
  const { page, context, writes } = await open({ agents: true });
  try {
    await page.getByRole("button", { name: "保存为模板", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "保存为模板", exact: true });
    assert.equal(await dialog.getByRole("button", { name: "创建模板草稿" }).isDisabled(), true);
    await dialog.getByLabel("模板名称", { exact: true }).fill("草稿提取");
    await dialog.getByLabel("模板编码", { exact: true }).fill("draft_source");
    await dialog.getByLabel("提取来源").selectOption("draft");
    await dialog.getByRole("button", { name: "添加知识需求" }).click();
    await dialog.getByLabel("需求键 1", { exact: true }).fill("returns");
    await dialog.getByLabel("需求名称 1", { exact: true }).fill("售后规则");
    await dialog.getByLabel("需求用途 1", { exact: true }).fill("核实售后范围");
    await dialog.getByRole("button", { name: "创建模板草稿" }).click();
    await page.getByText("模板草稿已创建，尚未发布", { exact: true }).waitFor();
    assert.deepEqual(writes.at(-1).body, { name: "草稿提取", code: "draft_source", description: null, source_agent_id: "agent", source_version: null, source_draft_revision: 8, knowledge_slots: [{ key: "returns", name: "售后规则", purpose: "核实售后范围", required: false }] });
  } finally { await context.close(); }
});

test("switching away from unsaved template requires explicit discard", async () => {
  const { page, context, writes } = await open();
  try {
    await page.getByLabel("默认 Agent 名称").fill("待保存的编辑");
    await page.getByRole("button", { name: /物流模板.*服务类/ }).click();
    await page.getByRole("dialog", { name: "放弃当前编辑" }).getByRole("button", { name: "取消", exact: true }).click();
    assert.equal(await page.getByLabel("默认 Agent 名称").inputValue(), "待保存的编辑");
    await page.getByRole("button", { name: /物流模板.*服务类/ }).click();
    await page.getByRole("button", { name: "放弃编辑并继续" }).click();
    await page.getByRole("heading", { name: "物流模板", exact: true }).waitFor();
    assert.equal(writes.length, 0);
  } finally { await context.close(); }
});

test("template editor desktop layout remains usable with all shared controls", async () => {
  const { page, context } = await open();
  try {
    await page.getByLabel("默认 Agent 名称").waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    const editor = page.locator(".template-editor .config-body");
    assert.equal(await editor.evaluate((element) => element.scrollHeight > element.clientHeight), true);
    if (process.env.TEMPLATE_DESKTOP_CAPTURE) await page.screenshot({ path: process.env.TEMPLATE_DESKTOP_CAPTURE, fullPage: true });
  } finally { await context.close(); }
});

for (const rejectOldHistory of [false, true]) test(`same-template publication ignores older ${rejectOldHistory ? "failed" : "successful"} history after a newer publication`, async () => {
  const { page, context, releaseHistory, oldHistoryStarted } = await open({ reversedHistory: true, rejectOldHistory });
  try {
    await page.getByLabel("默认 Agent 名称").waitFor();
    await page.getByRole("button", { name: "发布模板", exact: true }).click();
    await oldHistoryStarted;
    await page.getByLabel("默认 Agent 名称").fill("第三版客服");
    await page.getByRole("button", { name: "保存草稿", exact: true }).click();
    await page.getByText("草稿已保存；已发布版本和店铺运行保持原样", { exact: true }).waitFor();
    await page.getByRole("button", { name: "发布模板", exact: true }).click();
    await page.locator('option[value="3"]').waitFor({ state: "attached" });
    await page.getByLabel("查看版本").selectOption("3");
    const oldResponse = page.waitForResponse(async (response) => response.url().endsWith("/templates/one/versions") && (rejectOldHistory ? response.status() === 503 : (await response.json()).data.length === 2));
    releaseHistory(); await (await oldResponse).finished();
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await page.locator('option[value="3"]').count(), 1);
    assert.equal(await page.getByLabel("查看版本").inputValue(), "3");
    assert.equal(await page.getByLabel("默认 Agent 名称").inputValue(), "第三版客服");
    assert.equal(await page.getByRole("alert").filter({ hasText: "旧历史读取失败" }).count(), 0);
  } finally { releaseHistory(); await context.close(); }
});

for (const sidebar of [false, true]) test(`dirty ${sidebar ? "sidebar" : "tab"} navigation preserves input on cancel and navigates only after explicit discard`, async () => {
  const { page, context, writes } = await open();
  try {
    await page.getByLabel("默认 Agent 名称").fill("离页前未保存编辑");
    const link = sidebar ? page.locator('.main-nav a[href="/agents"]') : page.getByRole("navigation", { name: "Agent 管理导航" }).getByRole("link", { name: "店铺 Agent", exact: true });
    await link.click();
    const dialog = page.getByRole("dialog", { name: "放弃当前编辑", exact: true });
    await dialog.getByRole("button", { name: "取消", exact: true }).click();
    assert.equal(new URL(page.url()).pathname, "/agents/templates");
    assert.equal(await page.getByLabel("默认 Agent 名称").inputValue(), "离页前未保存编辑");
    assert.equal(writes.length, 0);
    assert.equal(await link.evaluate((element) => element === document.activeElement), true);
    await link.focus(); await page.keyboard.press("Enter"); await dialog.getByRole("button", { name: "放弃编辑并继续" }).click();
    await page.waitForURL((url) => url.pathname === "/agents");
    await page.getByRole("heading", { name: "选择 Agent", exact: true }).waitFor();
    await page.goBack(); await page.getByLabel("默认 Agent 名称").waitFor();
    assert.equal(await page.getByLabel("默认 Agent 名称").inputValue(), "私有草稿");
    assert.equal(writes.length, 0);
  } finally { await context.close(); }
});

test("dirty navigation guard leaves same-page anchors, new tabs and modified clicks alone", async () => {
  const { page, context, writes } = await open();
  try {
    await page.getByLabel("默认 Agent 名称").fill("仍在当前页的编辑");
    await page.evaluate(() => {
      const anchor = document.createElement("a"); anchor.href = "#template-editor-form"; anchor.textContent = "同页锚点";
      anchor.style.cssText = "position:fixed;top:0;right:0;z-index:100"; document.body.appendChild(anchor);
    });
    await page.getByRole("link", { name: "同页锚点", exact: true }).click();
    assert.equal(new URL(page.url()).hash, "#template-editor-form");
    assert.equal(await page.getByRole("dialog").count(), 0);
    const link = page.getByRole("navigation", { name: "Agent 管理导航" }).getByRole("link", { name: "店铺 Agent", exact: true });
    const allowedModifiers = await link.evaluate((anchor) => ["ctrlKey", "metaKey", "shiftKey", "altKey"].map((key) => {
      let reachedAnchor = false;
      const cancelNativeNavigation = (event) => { reachedAnchor = true; event.preventDefault(); };
      anchor.addEventListener("click", cancelNativeNavigation);
      anchor.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, button: 0, [key]: true }));
      anchor.removeEventListener("click", cancelNativeNavigation);
      return reachedAnchor;
    }));
    assert.deepEqual(allowedModifiers, [true, true, true, true]);
    await link.evaluate((anchor) => { anchor.target = "_blank"; });
    const [popup] = await Promise.all([page.waitForEvent("popup"), link.click()]);
    await popup.close();
    assert.equal(new URL(page.url()).pathname, "/agents/templates");
    assert.equal(await page.getByRole("dialog").count(), 0);
    assert.equal(await page.getByLabel("默认 Agent 名称").inputValue(), "仍在当前页的编辑");
    assert.equal(writes.length, 0);
  } finally { await context.close(); }
});

test("navigation during a pending save waits for its result without treating the request as cancelled", async () => {
  const { page, context, writes, releaseSave, pendingSaveStarted } = await open({ delayedSave: true });
  try {
    await page.getByLabel("默认 Agent 名称").fill("正在保存的编辑");
    await page.getByRole("button", { name: "保存草稿", exact: true }).click();
    await pendingSaveStarted;
    const link = page.getByRole("navigation", { name: "Agent 管理导航" }).getByRole("link", { name: "店铺 Agent", exact: true });
    await link.click();
    assert.equal(new URL(page.url()).pathname, "/agents/templates");
    assert.equal(await page.getByRole("dialog").count(), 0);
    await page.getByText("操作正在处理，请等待结果后离开页面。", { exact: true }).waitFor();
    releaseSave();
    await page.getByText("草稿已保存；已发布版本和店铺运行保持原样", { exact: true }).waitFor();
    assert.equal(writes.length, 1);
    assert.equal(writes[0].body.config.default_agent_name, "正在保存的编辑");
    await link.click(); await page.waitForURL((url) => url.pathname === "/agents");
    assert.equal(await page.getByRole("dialog").count(), 0);
  } finally { releaseSave(); await context.close(); }
});

for (const failureStatus of [422, 503]) test(`rejected later publication ${failureStatus} recovers actual published history without replacing draft edits or its failure`, async () => {
  const rejectOldHistory = failureStatus === 503;
  const { page, context, releaseHistory, oldHistoryStarted } = await open({ reversedHistory: true, failLaterPublication: failureStatus, rejectOldHistory });
  try {
    await page.getByLabel("默认 Agent 名称").waitFor();
    await page.getByRole("button", { name: "发布模板", exact: true }).click(); await oldHistoryStarted;
    await page.getByLabel("默认 Agent 名称").fill("下一版已保存草稿");
    await page.getByRole("button", { name: "保存草稿", exact: true }).click();
    await page.getByText("草稿已保存；已发布版本和店铺运行保持原样", { exact: true }).waitFor();
    await page.getByRole("button", { name: "发布模板", exact: true }).click();
    await page.getByRole("alert").filter({ hasText: "后次发布被拒绝" }).waitFor();
    await page.getByLabel("默认 Agent 名称").fill("失败后尚未保存的编辑");
    const oldResponse = page.waitForResponse((response) => response.url().endsWith("/templates/one/versions") && (rejectOldHistory ? response.status() === 503 : response.status() === 200));
    releaseHistory(); await (await oldResponse).finished();
    await page.locator('option[value="2"]').waitFor({ state: "attached" });
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await page.getByRole("alert").filter({ hasText: "后次发布被拒绝" }).count(), 1);
    assert.equal(await page.getByRole("alert").filter({ hasText: "旧历史读取失败" }).count(), 0);
    assert.equal(await page.getByLabel("默认 Agent 名称").inputValue(), "失败后尚未保存的编辑");
    assert.equal(await page.locator('option[value="3"]').count(), 0);
    await page.getByLabel("查看版本").selectOption("2");
    assert.equal(await page.getByLabel("默认 Agent 名称").inputValue(), "私有草稿");
    await page.getByLabel("查看版本").selectOption("draft");
    assert.equal(await page.getByLabel("默认 Agent 名称").inputValue(), "失败后尚未保存的编辑");
  } finally { releaseHistory(); await context.close(); }
});

test("a failed history recovery preserves the publication failure and unsaved input", async () => {
  const { page, context, releaseHistory, oldHistoryStarted } = await open({ reversedHistory: true, failLaterPublication: 422, rejectRecoveryHistory: true });
  try {
    await page.getByLabel("默认 Agent 名称").waitFor();
    await page.getByRole("button", { name: "发布模板", exact: true }).click(); await oldHistoryStarted;
    const recoveryResponse = page.waitForResponse((response) => response.url().endsWith("/templates/one/versions") && response.status() === 503);
    await page.getByRole("button", { name: "发布模板", exact: true }).click();
    await page.getByRole("alert").filter({ hasText: "后次发布被拒绝" }).waitFor();
    await (await recoveryResponse).finished();
    await page.getByLabel("默认 Agent 名称").fill("历史读取失败仍保留的编辑");
    releaseHistory();
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await page.getByRole("alert").filter({ hasText: "后次发布被拒绝" }).count(), 1);
    assert.equal(await page.getByRole("alert").filter({ hasText: "恢复历史读取失败" }).count(), 1);
    assert.equal(await page.getByLabel("默认 Agent 名称").inputValue(), "历史读取失败仍保留的编辑");
    assert.equal(await page.locator('option[value="3"]').count(), 0);
  } finally { releaseHistory(); await context.close(); }
});
