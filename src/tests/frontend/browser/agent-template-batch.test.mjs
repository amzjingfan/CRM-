import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");
const base = process.env.UI_BASE_URL ?? "http://127.0.0.1:3146";
if (!["127.0.0.1", "localhost", "::1"].includes(new URL(base).hostname)) throw new Error("local browser only");
const config = { default_agent_name: "客服", suggested_code: "service_01", agent_type: "service", description: null, model_provider: "openai", model_name: "model::name", prompt_sections: {}, tool_names: [], knowledge_slots: [] };
const pagination = (page, total = 2) => ({ page, page_size: 20, total, total_pages: total });
const store = (n) => ({ id: `s${n}`, name: `店 ${n}`, code: `store${n}`, can_view_knowledge: true, agents: n === 2 ? [{ id: "unlinked", name: "未关联", code: "existing", template_id: null, draft_revision: 7, published_version: 1, status: "enabled" }] : [] });

async function chooseStore(page, name) {
  const picker = page.getByRole("combobox", { name: "选择店铺", exact: true });
  if (await picker.getAttribute("aria-expanded") !== "true") await picker.click();
  const menu = page.getByRole("dialog", { name: "选择授权店铺", exact: true });
  const option = menu.getByRole("checkbox", { name, exact: true });
  if (!await option.count()) await menu.locator(".store-options-scroll").evaluate((node) => { node.scrollTop = node.scrollHeight; });
  await option.check();
  await menu.getByRole("button", { name: "完成选择", exact: true }).click();
}

async function openStoreDropdown({ failMore = false } = {}) {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext({ viewport: { width: 1440, height: 980 } });
  let releaseSlow; let slowStarted; const slowGate = new Promise((resolve) => { releaseSlow = resolve; }); const requestedSlow = new Promise((resolve) => { slowStarted = resolve; });
  await context.route("**/v1/**", async (route) => {
    const req = route.request(); const url = new URL(req.url()); const path = url.pathname; let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/templates/t") data = { id: "t", name: "售后模板", published_version: 1, archived_at: null };
    else if (path.endsWith("/versions")) data = [{ version: 1, config, content_sha256: "x", published_at: "now" }];
    else if (path.endsWith("/catalog")) data = { model_options: [], prompt_sections: [], groups: [], tools: [] };
    else if (path === "/v1/agents/templates/application-stores") {
      const query = url.searchParams.get("search"); const page = Number(url.searchParams.get("page"));
      if (query === "slow") { slowStarted(); await slowGate; }
      if (!query && page === 2 && failMore) { failMore = false; return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ code: 503, message: "店铺加载暂不可用" }) }); }
      data = { items: query || page === 2 ? [store(query === "slow" ? 4 : query ? 3 : 2)] : [store(1), ...Array.from({ length: 19 }, (_, i) => store(i + 10))], pagination: query ? pagination(1, 1) : pagination(page) };
    } else if (path.endsWith("/knowledge-files")) data = { items: [], pagination: pagination(1, 0) };
    else if (path.endsWith("/application-previews")) { const body = req.postDataJSON(); data = { preview_id: "p", items: body.items.map((item) => ({ id: item.store_id, store_id: item.store_id, store_name: item.store_id, action: item.action, agent_id: null, valid: true, issues: [], warnings: [], diffs: [], full_target: {}, knowledge_slots: [], mappings: {}, field_choices: {}, flags: {}, request: item })) }; }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) });
  });
  const page = await context.newPage(); page.setDefaultTimeout(5000); await page.goto(`${base}/agents/templates/t/apply`);
  return { browser, context, page, releaseSlow, requestedSlow };
}

test("store dropdown starts collapsed, keeps loaded/search selections and invalidates preview on removal", async () => {
  const { browser, context, page, releaseSlow } = await openStoreDropdown();
  try {
    const picker = page.getByRole("combobox", { name: "选择店铺", exact: true }); await picker.waitFor();
    await page.waitForFunction(() => !document.querySelector('button[role="combobox"][aria-label="选择店铺"]')?.disabled);
    assert.equal(await picker.getAttribute("aria-expanded"), "false");
    assert.equal(await page.getByRole("searchbox", { name: "搜索店铺", exact: true }).count(), 0);
    assert.equal(await page.getByRole("checkbox", { name: "店 1 · store1", exact: true }).count(), 0);
    await picker.focus(); await page.keyboard.press("ArrowDown");
    const menu = page.getByRole("dialog", { name: "选择授权店铺", exact: true }); await menu.waitFor();
    assert.equal(await menu.getByRole("searchbox", { name: "搜索店铺", exact: true }).evaluate((node) => node === document.activeElement), true);
    await menu.getByRole("checkbox", { name: "店 1 · store1", exact: true }).check();
    if (process.env.AGENT_TEMPLATE_UI_CAPTURE) {
      await page.screenshot({ path: fileURLToPath(new URL("../../.artifacts/agent-template-ui-20261031/frontend-store-dropdown-open-desktop.png", import.meta.url)) });
      await page.keyboard.press("Escape"); await page.setViewportSize({ width: 390, height: 844 }); await picker.click();
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
      await page.screenshot({ path: fileURLToPath(new URL("../../.artifacts/agent-template-ui-20261031/frontend-store-dropdown-open-mobile.png", import.meta.url)) });
      await page.keyboard.press("Escape"); await page.setViewportSize({ width: 1440, height: 980 }); await picker.click();
    }
    assert.equal(await menu.getByRole("button", { name: /上一页|下一页/ }).count(), 0);
    await menu.locator(".store-options-scroll").evaluate((node) => { node.scrollTop = node.scrollHeight; });
    await menu.getByRole("checkbox", { name: "店 2 · store2", exact: true }).check();
    await menu.getByRole("searchbox", { name: "搜索店铺", exact: true }).fill("第三店");
    await menu.getByRole("checkbox", { name: "店 3 · store3", exact: true }).check();
    await menu.getByRole("searchbox", { name: "搜索店铺", exact: true }).fill("");
    assert.equal(await menu.getByRole("checkbox", { name: "店 1 · store1", exact: true }).isChecked(), true);
    await menu.getByRole("button", { name: "移除已选店铺 店 2", exact: true }).click();
    await page.keyboard.press("Escape");
    assert.equal(await picker.getAttribute("aria-expanded"), "false");
    assert.equal(await picker.evaluate((node) => node === document.activeElement), true);
    assert.match(await picker.textContent(), /已选 2 店/);
    await page.getByRole("button", { name: "生成预览", exact: true }).click();
    await page.getByText("确认冻结计划", { exact: true }).waitFor();
    await picker.click(); await menu.getByRole("button", { name: "移除已选店铺 店 1", exact: true }).click();
    assert.equal(await page.getByText("确认冻结计划", { exact: true }).count(), 0);
    await page.getByRole("heading", { name: "批量应用 / 差异更新", exact: true }).click();
    assert.equal(await picker.getAttribute("aria-expanded"), "false");
    assert.match(await picker.textContent(), /店 3/);
  } finally { releaseSlow(); await context.close(); await browser.close(); }
});

test("store dropdown ignores late searches and supports checkbox navigation with keyboard", async () => {
  const { browser, context, page, releaseSlow, requestedSlow } = await openStoreDropdown();
  try {
    const picker = page.getByRole("combobox", { name: "选择店铺", exact: true }); await picker.click();
    const menu = page.getByRole("dialog", { name: "选择授权店铺", exact: true }); const search = menu.getByRole("searchbox", { name: "搜索店铺", exact: true });
    await search.fill("slow"); await requestedSlow;
    await search.fill("third"); await menu.getByRole("checkbox", { name: "店 3 · store3", exact: true }).waitFor();
    const response = page.waitForResponse((reply) => new URL(reply.url()).searchParams.get("search") === "slow"); releaseSlow(); await (await response).finished();
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await menu.getByRole("checkbox", { name: "店 4 · store4", exact: true }).count(), 0);
    await search.focus(); await page.keyboard.press("ArrowDown"); await page.keyboard.press("Space");
    assert.equal(await menu.getByRole("checkbox", { name: "店 3 · store3", exact: true }).isChecked(), true);
    await page.keyboard.press("Escape"); assert.equal(await picker.evaluate((node) => node === document.activeElement), true);
  } finally { releaseSlow(); await context.close(); await browser.close(); }
});

test("store dropdown retries a failed continuation without losing existing choices", async () => {
  const { browser, context, page, releaseSlow } = await openStoreDropdown({ failMore: true });
  try {
    await page.getByRole("combobox", { name: "选择店铺", exact: true }).click();
    const menu = page.getByRole("dialog", { name: "选择授权店铺", exact: true });
    await menu.getByRole("checkbox", { name: "店 1 · store1", exact: true }).check();
    await menu.locator(".store-options-scroll").evaluate((node) => { node.scrollTop = node.scrollHeight; });
    await menu.getByRole("button", { name: "重试加载店铺", exact: true }).click();
    await menu.getByRole("checkbox", { name: "店 2 · store2", exact: true }).waitFor();
    assert.equal(await menu.getByRole("checkbox", { name: "店 1 · store1", exact: true }).isChecked(), true);
  } finally { releaseSlow(); await context.close(); await browser.close(); }
});

test("store dropdown option text clicks select without closing, while Tab can leave the popup", async () => {
  const { browser, context, page, releaseSlow } = await openStoreDropdown();
  try {
    const picker = page.getByRole("combobox", { name: "选择店铺", exact: true }); await picker.click();
    const menu = page.getByRole("dialog", { name: "选择授权店铺", exact: true });
    await menu.getByText("店 1 · store1", { exact: true }).click();
    assert.equal(await menu.getByRole("checkbox", { name: "店 1 · store1", exact: true }).isChecked(), true);
    assert.equal(await picker.getAttribute("aria-expanded"), "true");
    await menu.getByRole("searchbox", { name: "搜索店铺", exact: true }).focus();
    await page.keyboard.press("Shift+Tab"); await page.keyboard.press("Shift+Tab");
    assert.equal(await picker.getAttribute("aria-expanded"), "false");
  } finally { releaseSlow(); await context.close(); await browser.close(); }
});

test("store dropdown focused mobile controls stay within the main area without horizontal scrolling", async () => {
  const { browser, context, page, releaseSlow } = await openStoreDropdown();
  try {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole("combobox", { name: "选择店铺", exact: true }).click();
    await page.getByRole("dialog", { name: "选择授权店铺", exact: true }).getByText("店 1 · store1", { exact: true }).click();
    await page.getByRole("dialog", { name: "选择授权店铺", exact: true }).getByRole("searchbox", { name: "搜索店铺", exact: true }).fill("third");
    await page.getByRole("checkbox", { name: "店 3 · store3", exact: true }).waitFor();
    const bounds = await page.evaluate(() => {
      const rect = (selector) => { const node = document.querySelector(selector); const r = node.getBoundingClientRect(); const css = getComputedStyle(node); return { left: r.left, right: r.right, width: r.width, scrollWidth: node.scrollWidth, clientWidth: node.clientWidth, scrollLeft: node.scrollLeft, cssWidth: css.width, minWidth: css.minWidth, flexBasis: css.flexBasis }; };
      return { width: innerWidth, scrollX, document: rect("html"), app: rect(".app-main"), body: rect(".application-store-picker .config-body"), toolbar: rect(".application-toolbar"), picker: rect(".application-store-select"), trigger: rect(".store-select-trigger"), menu: rect(".store-select-menu"), target: rect(".application-target-toolbar"), remove: rect(".application-store-config .batch-result-head button") };
    });
    console.log("mobile store dropdown bounds", JSON.stringify(bounds));
    assert.equal(bounds.scrollX, 0);
    assert.ok(bounds.document.scrollWidth <= bounds.document.clientWidth);
    assert.equal(bounds.app.scrollLeft, 0);
    assert.ok(bounds.app.scrollWidth <= bounds.app.clientWidth);
    assert.ok(bounds.trigger.right <= bounds.width - 16);
    assert.ok(bounds.menu.right <= bounds.width - 16);
    assert.ok(bounds.target.right <= bounds.width - 16);
    assert.ok(bounds.remove.right <= bounds.width - 16);
  } finally { releaseSlow(); await context.close(); await browser.close(); }
});

test("batch dropdown preserves deep link, page selection and browser history without exposing task IDs", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext({ viewport: { width: 1440, height: 980 } });
  const summary = (id) => ({ id, template_id: "t", template_version: id === "b" ? 1 : 2, status: "completed", counts: { succeeded: 1, skipped: 1 }, created_at: "2026-10-31T08:00:00Z", processor_enabled: true });
  await context.route("**/v1/**", async (route) => {
    const url = new URL(route.request().url()); const path = url.pathname; let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/template-batches") data = { items: [summary(url.searchParams.get("page") === "2" ? "c" : "b")], pagination: pagination(Number(url.searchParams.get("page"))) };
    else if (path.startsWith("/v1/agents/template-batches/")) data = { ...summary(path.split("/").at(-1)), items: [{ id: "item", store_name: "完成店铺", status: "succeeded", attempt_count: 1, preview: null }], pagination: pagination(1, 1) };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) });
  });
  try {
    const page = await context.newPage(); await page.goto(`${base}/agents/template-batches?batch_id=b`);
    await page.getByLabel("选择批量任务", { exact: true }).waitFor();
    const taskBounds = await page.getByLabel("选择批量任务", { exact: true }).boundingBox();
    const taskPageBounds = await page.getByRole("button", { name: "下一页任务", exact: true }).boundingBox();
    assert.ok(taskBounds.width <= 520);
    assert.ok(Math.abs(taskBounds.y - taskPageBounds.y) <= 2);
    assert.equal(await page.getByLabel("选择批量任务", { exact: true }).inputValue(), "b");
    assert.equal((await page.getByLabel("选择批量任务", { exact: true }).textContent()).includes("T08:00:00Z"), false);
    await page.getByRole("button", { name: "下一页任务", exact: true }).click();
    await page.getByLabel("选择批量任务", { exact: true }).selectOption("c");
    await page.waitForURL((url) => url.searchParams.get("batch_id") === "c");
    await page.getByRole("heading", { name: "全部成功 · 模板 v2", exact: true }).waitFor();
    if (process.env.AGENT_TEMPLATE_UI_CAPTURE) await page.screenshot({ path: fileURLToPath(new URL("../../.artifacts/agent-template-ui-20261031/frontend-batches-desktop.png", import.meta.url)), fullPage: true });
    assert.equal(await page.getByRole("progressbar", { name: "店铺处理进度" }).getAttribute("value"), "2");
    assert.equal(await page.getByRole("button", { name: "取消任务", exact: true }).count(), 0);
    assert.equal(await page.getByRole("button", { name: "重试可重试失败项", exact: true }).count(), 0);
    await page.goBack(); await page.getByRole("heading", { name: "全部成功 · 模板 v1", exact: true }).waitFor();
    assert.equal(await page.getByLabel("选择批量任务", { exact: true }).inputValue(), "b");
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
    if (process.env.AGENT_TEMPLATE_UI_CAPTURE) await page.screenshot({ path: fileURLToPath(new URL("../../.artifacts/agent-template-ui-20261031/frontend-batches-mobile.png", import.meta.url)), fullPage: true });
  } finally { await context.close(); await browser.close(); }
});

test("apply review steps keep conflicts visible while unchanged full values stay collapsed", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext({ viewport: { width: 1440, height: 980 } }); const requests = [];
  await context.route("**/v1/**", async (route) => {
    const req = route.request(); const path = new URL(req.url()).pathname; let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/templates/t") data = { id: "t", name: "售后模板", published_version: 1, archived_at: null };
    else if (path.endsWith("/versions")) data = [{ version: 1, config, content_sha256: "x", published_at: "now" }];
    else if (path.endsWith("/catalog")) data = { model_options: [], prompt_sections: [], groups: [], tools: [] };
    else if (path === "/v1/agents/templates/application-stores") data = { items: [{ ...store(1), agents: [{ id: "a", name: "售后助手", code: "service", template_id: "t", draft_revision: 3, published_version: 1 }] }], pagination: pagination(1, 1) };
    else if (path.endsWith("/knowledge-files")) data = { items: [], pagination: pagination(1, 0) };
    else if (path.endsWith("/application-previews")) {
      const body = req.postDataJSON(); requests.push(body); const resolved = body.items[0].fields?.description?.choice === "local";
      data = { preview_id: "p", preview_hash: "h", template_id: "t", template_version: 1, items: [{ id: "i", store_id: "s1", store_name: "店 1", agent_id: "a", action: "update", valid: resolved, issues: resolved ? [] : [{ code: "field_conflict", message: "职责存在未解决冲突", field: "description" }], warnings: [], diffs: [{ field: "description", baseline: "旧职责", local: "本店职责", target: "模板职责", status: "conflict", default_choice: "resolve" }, { field: "agent_type", baseline: "service", local: "service", target: "service", status: "unchanged", default_choice: "skip" }], full_target: { description: "本店职责", agent_type: "service" }, published_snapshot: {}, knowledge_slots: [], mappings: {}, field_choices: body.items[0].fields ?? {}, flags: {}, request: body.items[0] }] };
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) });
  });
  try {
    const page = await context.newPage(); page.setDefaultTimeout(5000); await page.goto(`${base}/agents/templates/t/apply`);
    await page.getByRole("list", { name: "应用步骤", exact: true }).waitFor();
    await page.locator('select[aria-label="模板版本"] option[value="1"]').waitFor({ state: "attached" });
    const versionBounds = await page.getByLabel("模板版本").boundingBox();
    const searchBounds = await page.getByRole("combobox", { name: "选择店铺", exact: true }).boundingBox();
    assert.ok(Math.abs(versionBounds.y - searchBounds.y) <= 2, "version and store dropdown share the compact toolbar row");
    assert.ok(searchBounds.width <= 400, "store dropdown does not stretch across the wide page");
    if (process.env.AGENT_TEMPLATE_UI_CAPTURE) {
      await page.screenshot({ path: fileURLToPath(new URL("../../.artifacts/agent-template-ui-20261031/frontend-apply-compact-desktop.png", import.meta.url)) });
      await page.setViewportSize({ width: 390, height: 844 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
      await page.screenshot({ path: fileURLToPath(new URL("../../.artifacts/agent-template-ui-20261031/frontend-apply-compact-mobile.png", import.meta.url)) });
      await page.setViewportSize({ width: 1440, height: 980 });
    }
    await chooseStore(page, "店 1 · store1");
    await page.getByRole("button", { name: "生成预览", exact: true }).click();
    await page.getByText("阻止确认：职责存在未解决冲突", { exact: true }).waitFor();
    assert.equal(await page.getByRole("button", { name: "确认批量任务", exact: true }).isDisabled(), true);
    assert.equal(await page.getByLabel("本次选择").filter({ visible: true }).count(), 1);
    if (process.env.AGENT_TEMPLATE_UI_CAPTURE) {
      await page.screenshot({ path: fileURLToPath(new URL("../../.artifacts/agent-template-ui-20261031/frontend-apply-review-desktop.png", import.meta.url)), fullPage: true });
      await page.setViewportSize({ width: 390, height: 844 });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
      await page.locator(".application-store-config").evaluate((element) => element.scrollIntoView({ block: "start" }));
      await page.screenshot({ path: fileURLToPath(new URL("../../.artifacts/agent-template-ui-20261031/frontend-apply-review-mobile.png", import.meta.url)), fullPage: true });
      await page.setViewportSize({ width: 1440, height: 980 });
    }
    await page.getByLabel("本次选择").filter({ visible: true }).selectOption("local");
    await page.getByRole("button", { name: "生成预览", exact: true }).click();
    await page.getByRole("button", { name: "确认批量任务", exact: true }).waitFor();
    assert.equal(await page.getByRole("button", { name: "确认批量任务", exact: true }).isEnabled(), true);
    assert.equal(requests[1].items[0].fields.description.choice, "local");
  } finally { await context.close(); await browser.close(); }
});

test("unconfirmed preview return restores selected store, field choice, knowledge and publication flags", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext();
  const summary = { id: "p", template_id: "t", template_version: 1, status: "preview", counts: { pending: 1 }, created_at: "2026-10-31T08:00:00Z", processor_enabled: true };
  const request = { store_id: "s1", action: "create", name: "保留的店铺助手", code: "saved_agent", fields: { description: { choice: "local" } }, knowledge_mappings: { faq: ["file-1"] }, unbind_removed_file_ids: [], include_existing_draft: false, publish: true, enable_after_publish: true };
  const preview = { id: "item", store_id: "s1", store_name: "店 1", agent_id: null, action: "create", valid: true, issues: [], warnings: [], diffs: [{ field: "description", baseline: "旧职责", local: "本店职责", target: "模板职责", status: "template_changed", default_choice: "template" }], full_target: { name: request.name }, published_snapshot: null, knowledge_slots: [{ key: "faq", name: "FAQ", purpose: "政策", required: true }], mappings: request.knowledge_mappings, field_choices: request.fields, flags: { publish: true }, request };
  await context.route("**/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname; let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/template-batches") data = { items: [summary], pagination: pagination(1, 1) };
    else if (path === "/v1/agents/template-batches/p") data = { ...summary, items: [{ id: "item", store_id: "s1", store_name: "店 1", status: "pending", attempt_count: 0, preview }], pagination: pagination(1, 1) };
    else if (path === "/v1/agents/templates/t") data = { id: "t", name: "模板", published_version: 1, archived_at: null };
    else if (path.endsWith("/versions")) data = [{ version: 1, config, content_sha256: "x", published_at: "now" }];
    else if (path.endsWith("/catalog")) data = { model_options: [], prompt_sections: [], groups: [], tools: [] };
    else if (path === "/v1/agents/templates/application-stores") data = { items: [store(1)], pagination: pagination(1, 1) };
    else if (path.endsWith("/knowledge-files")) data = { items: [{ id: "file-1", name: "保留知识", active_version_number: 1, can_publish: true }], pagination: pagination(1, 1) };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) });
  });
  try {
    const page = await context.newPage(); page.setDefaultTimeout(5000); await page.goto(`${base}/agents/template-batches?batch_id=p`);
    const back = page.getByRole("link", { name: "返回应用页", exact: true }); await back.waitFor();
    assert.match(await back.getAttribute("href"), /parent_batch_id=p/);
    await back.click(); await page.getByLabel("名称", { exact: true }).waitFor();
    assert.equal(await page.getByLabel("名称", { exact: true }).inputValue(), "保留的店铺助手");
    assert.match(await page.getByRole("combobox", { name: "选择店铺", exact: true }).textContent(), /已选 1 店.*店 1/);
    await chooseStore(page, "店 1 · store1");
    assert.equal(await page.getByLabel("本次选择").inputValue(), "local");
    assert.equal(await page.getByLabel("保留知识 · 有效版本 1 · 可发布", { exact: true }).isChecked(), true);
    assert.equal(await page.getByLabel("发布目标版本（未选则只保存草稿）").isChecked(), true);
    assert.equal(await page.getByLabel("发布后启用新 Agent").isChecked(), true);
  } finally { await context.close(); await browser.close(); }
});

// final-fix：需合法可用的本地 production 服务；本轮服务启动被策略阻断，未执行这些浏览器用例。
test("final-fix 批次成功文案区分实际发布、草稿及相同运行快照", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext();
  const summary = { id: "b", template_id: "t", template_version: 1, status: "completed", counts: { succeeded: 4 }, created_at: "now", processor_enabled: true };
  const items = [[null, 1, true], [1, 1, false], [1, 2, true], [1, 1, true]].map(([oldVersion, resultVersion, publish], n) => ({ id: `i${n}`, store_id: `s${n}`, store_name: `店 ${n}`, status: "succeeded", action: n ? "update" : "create", agent_id: null, result_agent_id: null, old_published_version: oldVersion, result_version: resultVersion, attempt_count: 1, preview: { flags: { publish } } }));
  await context.route("**/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname; let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    if (path === "/v1/agents/template-batches") data = { items: [summary], pagination: pagination(1, 1) };
    if (path === "/v1/agents/template-batches/b") data = { ...summary, items, pagination: pagination(1, 1) };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) });
  });
  try {
    const page = await context.newPage(); await page.goto(`${base}/agents/template-batches?batch_id=b`);
    await page.getByText("已与运行版本一致，未新增发布", { exact: true }).waitFor();
    assert.equal(await page.getByText("新版本已发布", { exact: true }).count(), 2);
    assert.equal(await page.getByText("草稿已保存，运行版本未改变", { exact: true }).count(), 1);
  } finally { await context.close(); await browser.close(); }
});

for (const kind of ["cancel", "retry-failed"]) test(`final-fix ${kind} POST 等待中站内离页后不续发列表 GET`, async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext();
  let release; let started; let listGets = 0; let postCompleted = false;
  const gate = new Promise((resolve) => { release = resolve; }); const requested = new Promise((resolve) => { started = resolve; });
  const summary = { id: "b", template_id: "t", template_version: 1, status: "queued", counts: { failed: 1 }, created_at: "now", processor_enabled: true };
  const detail = { ...summary, items: [{ id: "i", store_name: "店", status: "failed", retryable: true, error_code: "review_unavailable", attempt_count: 1, preview: null }], pagination: pagination(1, 1) };
  await context.route("**/v1/**", async (route) => {
    const request = route.request(); const path = new URL(request.url()).pathname; let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/template-batches") { listGets++; data = { items: [summary], pagination: pagination(1, 1) }; }
    else if (path === "/v1/agents/template-batches/b") data = detail;
    else if (path === `/v1/agents/template-batches/b/${kind}` && request.method() === "POST") { started(); await gate; postCompleted = true; data = { ...detail, status: kind === "cancel" ? "cancelled" : "queued" }; }
    else if (path === "/v1/agents/templates") data = { items: [], can_manage: false };
    else if (path.endsWith("/catalog")) data = { model_options: [], prompt_sections: [], groups: [], tools: [] };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) });
  });
  try {
    const page = await context.newPage(); await page.goto(`${base}/agents/templates`);
    await page.getByRole("heading", { name: "Agent 模板", exact: true }).waitFor();
    const documentTimeOrigin = await page.evaluate(() => performance.timeOrigin);
    await page.getByRole("link", { name: "批量任务", exact: true }).click();
    await page.getByLabel("选择批量任务", { exact: true }).selectOption("b");
    if (kind === "cancel") { await page.getByRole("button", { name: "取消任务", exact: true }).click(); await page.getByRole("button", { name: "确认取消", exact: true }).click(); }
    else await page.getByRole("button", { name: "重试可重试失败项", exact: true }).click();
    await requested;
    if (kind === "cancel") {
      // 选择任务本身增加一条 Next Link 历史；返回两步可离开 busy 遮罩且不取消同文档 POST。
      await page.goBack();
      await page.waitForURL((url) => url.pathname === "/agents/template-batches" && !url.searchParams.has("batch_id"));
      await page.goBack();
    } else await page.getByRole("link", { name: "Agent 模板", exact: true }).click();
    await page.getByRole("heading", { name: "Agent 模板", exact: true }).waitFor(); const before = listGets;
    assert.equal(await page.evaluate(() => performance.timeOrigin), documentTimeOrigin, "navigation must preserve the SPA document and in-flight POST");
    const response = page.waitForResponse((result) => new URL(result.url()).pathname.endsWith(`/${kind}`) && result.request().method() === "POST");
    release(); await response; await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(postCompleted, true); assert.equal(listGets, before);
    assert.equal(await page.getByRole("heading", { name: "Agent 模板", exact: true }).count(), 1);
  } finally { release(); await context.close(); await browser.close(); }
});

test("跨页选择、预览失效和稳定确认请求", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const context = await browser.newContext(); const writes = []; const calls = []; let releasePreview; let signalPreview;
  const previewGate = new Promise((resolve) => { releasePreview = resolve; }); const previewStarted = new Promise((resolve) => { signalPreview = resolve; });
  await context.route("**/v1/**", async (route) => {
    const request = route.request(); const url = new URL(request.url()); const path = url.pathname; calls.push(`${request.method()} ${path}`);
    let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: ["agent.view"], store_ids: [] };
    else if (path === "/v1/agents/templates/t") data = { id: "t", name: "模板", published_version: 1, archived_at: null };
    else if (path === "/v1/agents/templates/t/versions") data = [{ version: 1, config, content_sha256: "x", published_at: "now" }];
    else if (path === "/v1/agents/templates/catalog") data = { model_options: [], prompt_sections: [], groups: [], tools: [] };
    else if (path === "/v1/agents/templates/application-stores") { const page = Number(url.searchParams.get("page")); data = { items: [store(page)], pagination: pagination(page) }; }
    else if (path.endsWith("/knowledge-files")) data = { items: [], pagination: pagination(1, 0) };
    else if (path.endsWith("/application-previews")) {
      const body = request.postDataJSON(); writes.push({ path, body }); if (writes.length === 1) { signalPreview(); await previewGate; }
      data = { preview_id: `p${writes.length}`, preview_hash: "hash", template_id: "t", template_version: 1, items: body.items.map((item) => ({ id: item.store_id, store_id: item.store_id, store_name: item.store_id, agent_id: null, action: item.action, valid: true, issues: [], warnings: [], diffs: [], published_snapshot: null, full_target: {}, knowledge_slots: [], mappings: {}, has_existing_draft: false, field_choices: {}, flags: { publish: item.publish }, request: item })) };
    } else if (path === "/v1/agents/template-batches" && request.method() === "POST") { writes.push({ path, body: request.postDataJSON(), key: request.headers()["idempotency-key"] }); if (writes.filter((item) => item.path === path).length === 1) return route.abort("failed"); data = { id: "p2" }; }
    else if (path === "/v1/agents/template-batches/p3") data = { id: "p3", status: "preview", items: [], pagination: pagination(1, 0) };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) });
  });
  try {
    const page = await context.newPage(); await page.goto(`${base}/agents/templates/t/apply`);
    await chooseStore(page, "店 1 · store1"); await chooseStore(page, "店 2 · store2");
    await page.getByLabel("操作与目标").nth(1).selectOption("adopt:unlinked");
    await page.getByRole("button", { name: "生成预览" }).click(); await previewStarted;
    await page.getByLabel("名称", { exact: true }).first().fill("新客服"); releasePreview();
    await page.getByRole("button", { name: "生成预览" }).waitFor(); assert.equal(await page.getByText("确认冻结计划").count(), 0);
    await page.getByRole("button", { name: "生成预览" }).click(); await page.getByText("确认冻结计划").waitFor();
    await page.getByRole("link", { name: "店铺 Agent" }).click(); await page.getByText("当前未确认的编辑将丢失。").waitFor(); await page.getByRole("button", { name: "继续编辑" }).click(); assert.equal(await page.getByLabel("名称", { exact: true }).first().inputValue(), "新客服");
    await page.screenshot({ path: fileURLToPath(new URL("../../.artifacts/agent-template-ui-20261031/frontend-apply-desktop.png", import.meta.url)), fullPage: true });
    assert.deepEqual(writes[0].body.items.map((item) => item.store_id), ["s1", "s2"]);
    assert.equal(writes[0].body.items[0].fields, null); assert.equal(writes[0].body.items[0].publish, false);
    assert.equal(writes[0].body.items[1].action, "adopt"); assert.equal(writes[0].body.items[1].expected_revision, 7); assert.equal("name" in writes[0].body.items[1], false);
    await page.getByLabel("发布目标版本（未选则只保存草稿）").first().check();
    assert.equal(await page.getByText("确认冻结计划").count(), 0);
    await page.getByLabel("发布后启用新 Agent").check(); await page.getByLabel("发布目标版本（未选则只保存草稿）").first().uncheck();
    await page.getByLabel("发布目标版本（未选则只保存草稿）").first().check(); assert.equal(await page.getByLabel("发布后启用新 Agent").isChecked(), false);
    await page.getByRole("button", { name: "生成预览" }).click(); await page.getByRole("button", { name: "确认批量任务" }).click();
    await page.getByText(/确认结果未完成/).waitFor(); await page.reload();
    await page.getByRole("button", { name: "查询原任务" }).click(); await page.getByText(/服务端仍是未确认预览/).waitFor();
    const retryResponse = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/agents/template-batches" && response.request().method() === "POST");
    await page.getByRole("button", { name: "使用原确认重试" }).click(); await retryResponse;
    assert.deepEqual(writes[3].body, { preview_id: "p3", confirmation: true }); assert.ok(writes[3].key);
    assert.equal(writes[4].key, writes[3].key); assert.deepEqual(writes[4].body, writes[3].body);
    assert.ok(calls.filter((call) => call === "GET /v1/agents/template-batches/p3").length >= 2);
  } finally { await context.close(); await browser.close(); }
});

test("冲突须明确选择，本店构造器槽与完整草稿确认", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext(); const previews = [];
  await context.route("**/v1/**", async (route) => {
    const req = route.request(); const url = new URL(req.url()); const path = url.pathname; let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/templates/t") data = { id: "t", name: "模板", published_version: 1, archived_at: null };
    else if (path.endsWith("/versions")) data = [{ version: 1, config, content_sha256: "x", published_at: "now" }, { version: 2, config, content_sha256: "y", published_at: "now" }];
    else if (path.endsWith("/catalog")) data = { model_options: [{ provider: "openai", model_name: "model::name" }], prompt_sections: [], groups: [{ key: "orders", title: "订单", description: "查询" }], tools: [{ name: "query_order", title: "查询订单", description: "查询", category: "orders", operation: "read", requires_context: true }] };
    else if (path === "/v1/agents/templates/application-stores") data = { items: [{ ...store(1), agents: [{ id: "a", name: "客服", code: "code", template_id: "t", draft_revision: 3, published_version: 1, status: "enabled" }] }], pagination: pagination(1, 1) };
    else if (path.endsWith("/knowledge-files")) data = { items: [{ id: "f1", name: "有效 FAQ", active_version_number: 1, status: "ready", publication_approval: "approved_for_internal_review", can_publish: true }, { id: "f2", name: "旧需求文件", active_version_number: 1, status: "ready", publication_approval: "approved_for_internal_review", can_publish: true }, { id: "f3", name: "尚未批准", active_version_number: null, status: null, publication_approval: null, can_publish: false }], pagination: pagination(1, 1) };
    else if (path.endsWith("/application-previews")) {
      const body = req.postDataJSON(); previews.push(body); const item = body.items[0];
      const unresolved = item.fields === null; const draftIssue = item.publish && !item.include_existing_draft; const missing = item.publish && (!Object.hasOwn(item.knowledge_mappings, "constructor") || !item.knowledge_mappings.constructor.length);
      const fields = ["agent_type", "description", "model", "tool_names", "knowledge_slots", ...["identity", "service_scope", "tool_rules", "escalation", "language_format", "compliance", "clarification"].map((s) => `prompt_sections.${s}`)];
      data = { preview_id: `p${previews.length}`, preview_hash: "hash", template_id: "t", template_version: 1, items: [{ id: "i", store_id: "s1", store_name: "店 1", agent_id: "a", action: "update", valid: !unresolved && !draftIssue && !missing, issues: [...(unresolved ? [{ code: "field_conflict", message: "字段存在未解决冲突", field: "description" }] : []), ...(draftIssue ? [{ code: "draft", message: "确认已有草稿", field: null }] : []), ...(missing ? [{ code: "required_slot_missing", message: "必需知识槽尚未映射", field: "constructor" }] : [])], warnings: [], diffs: fields.map((field) => ({ field, baseline: "A", local: field === "model" ? { provider: "openai", name: "model::name" } : "B", target: "C", status: field === "description" ? "conflict" : "unchanged", default_choice: field === "description" ? "resolve" : "skip" })), published_snapshot: { description: "运行" }, full_target: { description: null, knowledge_file_ids: ["f2"] }, knowledge_slots: [{ key: "constructor", name: "FAQ", purpose: "问答", required: true }], mappings: { constructor: [] }, has_existing_draft: true, field_choices: item.fields ?? {}, flags: { publish: item.publish }, request: item }] };
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) });
  });
  try {
    const page = await context.newPage(); await page.goto(`${base}/agents/templates/t/apply`); await chooseStore(page, "店 1 · store1");
    await page.getByLabel("发布目标版本（未选则只保存草稿）").check(); await page.getByRole("button", { name: "生成预览" }).click();
    await page.getByText("字段存在未解决冲突", { exact: false }).waitFor();
    await page.getByText("阻止确认：必需知识槽尚未映射").waitFor(); await page.getByText("尚未批准 · 有效版本 无 · 不可发布").waitFor(); assert.equal(await page.getByRole("button", { name: "确认批量任务" }).isDisabled(), true);
    await page.getByRole("button", { name: "生成预览" }).click(); await page.getByText("请逐项选择冲突处理方式或明确跳过。").waitFor(); assert.equal(previews.length, 1);
    assert.equal(await page.getByLabel("本次选择").filter({ visible: true }).count(), 1);
    await page.getByText("未变化字段", { exact: true }).click();
    assert.equal(await page.getByLabel("本次选择").count(), 12);
    await page.getByLabel("本次选择").nth(0).selectOption("skip"); await page.getByRole("button", { name: "生成预览" }).click(); await page.getByText("确认冻结计划").waitFor(); assert.deepEqual(previews[1].items[0].fields, {});
    await page.getByLabel("发布目标版本（未选则只保存草稿）").uncheck(); await page.getByRole("button", { name: "生成预览" }).click(); await page.getByText("确认冻结计划").waitFor(); assert.equal(await page.getByRole("button", { name: "确认批量任务" }).isEnabled(), true); await page.getByLabel("发布目标版本（未选则只保存草稿）").check();
    await page.getByLabel("本次选择").nth(5).selectOption("template"); await page.getByLabel("本次选择").nth(5).selectOption("skip");
    await page.getByLabel("本次选择").nth(0).selectOption("manual"); await page.getByLabel("手工内容（留空清除）").fill("");
    await page.getByLabel("本次选择").nth(2).selectOption("manual");
    await page.getByLabel("本次选择").nth(3).selectOption("manual"); await page.getByLabel("启用查询订单").check();
    await page.getByLabel("本次选择").nth(4).selectOption("manual"); await page.getByRole("button", { name: "添加知识需求" }).click();
    await page.getByLabel("需求键 1").fill("constructor"); await page.getByLabel("需求名称 1").fill("FAQ"); await page.getByLabel("需求用途 1").fill("问答"); await page.getByLabel("应用时必须映射本店文件").check();
    await page.getByText("有效 FAQ · 有效版本 1 · 可发布").click(); await page.getByLabel("我确认同时发布此 Agent 原有的全部未发布草稿").check();
    await page.getByText("额外文件与解绑设置", { exact: true }).click();
    await page.getByLabel("解绑已移除槽的模板来源：旧需求文件").check();
    await page.getByRole("button", { name: "生成预览" }).click(); await page.getByRole("button", { name: "确认批量任务" }).waitFor();
    assert.deepEqual(previews[3].items[0].fields.description, { choice: "manual", value: null });
    assert.deepEqual(previews[3].items[0].fields.model, { choice: "manual", value: { provider: "openai", name: "model::name" } });
    assert.deepEqual(previews[3].items[0].fields.tool_names, { choice: "manual", value: ["query_order"] });
    assert.deepEqual(previews[3].items[0].fields.knowledge_slots, { choice: "manual", value: [{ key: "constructor", name: "FAQ", purpose: "问答", required: true }] });
    assert.equal(Object.hasOwn(previews[3].items[0].fields, "prompt_sections.identity"), false);
    assert.deepEqual(previews[3].items[0].knowledge_mappings, { constructor: ["f1"] }); assert.equal(previews[3].items[0].include_existing_draft, true);
    assert.deepEqual(previews[3].items[0].unbind_removed_file_ids, ["f2"]);
    await page.setViewportSize({ width: 390, height: 844 }); await page.screenshot({ path: fileURLToPath(new URL("../../.artifacts/agent-template-ui-20261031/frontend-apply-mobile.png", import.meta.url)), fullPage: true });
  } finally { await context.close(); await browser.close(); }
});

test("批次页使用真实状态，跨页发现可重试项且不调用 advance", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext(); const requests = [];
  const summary = { id: "b", template_id: "t", template_version: 1, parent_batch_id: null, status: "partial_failed", cancel_requested: false, counts: { succeeded: 1, failed: 1 }, created_at: "now", confirmed_at: "now", finished_at: "now", processor_enabled: false };
  const failed = { ...summary, id: "b2", counts: { failed: 2 } };
  await context.route("**/v1/**", async (route) => {
    const req = route.request(); const url = new URL(req.url()); requests.push(`${req.method()} ${url.pathname}`); let data = {};
    if (url.pathname === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (url.pathname === "/v1/agents/template-batches") data = { items: [summary, failed], pagination: pagination(1, 1) };
    else if (url.pathname === "/v1/agents/template-batches/b2") data = { ...failed, items: [], pagination: pagination(1, 0) };
    else if (url.pathname === "/v1/agents/template-batches/b" || url.pathname.endsWith("/retry-failed")) {
      const page = Number(url.searchParams.get("page") ?? 1); data = { ...summary, items: [{ id: `i${page}`, store_id: page === 1 ? "s1" : null, store_name: page === 1 ? "店 1" : "无权查看店铺", status: page === 1 ? "succeeded" : "failed", action: page === 1 ? "update" : null, agent_id: null, old_published_version: page === 1 ? 1 : null, result_agent_id: null, result_version: page === 1 ? 1 : null, error_code: page === 1 ? null : "review_unavailable", retryable: page === 2, attempt_count: 1, preview: page === 1 ? { flags: { publish: false } } : null }], pagination: { page, page_size: 50, total: 2, total_pages: 2 } };
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) });
  });
  try {
    const page = await context.newPage(); await page.goto(`${base}/agents/template-batches?batch_id=b`);
    await page.getByText("后台处理器未启用，任务不会自动推进。").waitFor(); await page.getByRole("button", { name: "重试可重试失败项" }).waitFor({ state: "visible" });
    await page.getByText("处理详情", { exact: true }).first().click(); await page.getByText(/预览时已发布版本 1 → 结果版本 1/).waitFor(); await page.getByText("草稿已保存，运行版本未改变").waitFor();
    await page.getByRole("button", { name: "重试可重试失败项" }).click();
    assert.ok(requests.includes("POST /v1/agents/template-batches/b/retry-failed")); assert.ok(requests.every((request) => !request.includes("advance")));
    assert.match(await page.getByRole("link", { name: "重新预览未成功项" }).getAttribute("href"), /parent_batch_id=b/);
    await page.getByLabel("选择批量任务", { exact: true }).selectOption("b2"); await page.getByRole("heading", { name: /全部失败/ }).waitFor();
    await page.goto("about:blank"); const countAfterClose = requests.length; await new Promise((resolve) => setTimeout(resolve, 5500)); assert.equal(requests.length, countAfterClose);
  } finally { await context.close(); await browser.close(); }
});

test("fixround1 站内离开后迟到的详情不再请求其他分页", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext(); const pages = []; let release; let started;
  const gate = new Promise((resolve) => { release = resolve; }); const requested = new Promise((resolve) => { started = resolve; });
  const summary = { id: "b", template_id: "t", template_version: 1, parent_batch_id: null, status: "partial_failed", cancel_requested: false, counts: { failed: 2 }, created_at: "now", confirmed_at: "now", finished_at: "now", processor_enabled: false };
  await context.route("**/v1/**", async (route) => { const url = new URL(route.request().url()); const path = url.pathname; let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/template-batches") data = { items: [summary], pagination: pagination(1, 1) };
    else if (path === "/v1/agents/template-batches/b") { const p = Number(url.searchParams.get("page")); pages.push(p); if (p === 1) { started(); await gate; } data = { ...summary, items: [], pagination: { page: p, page_size: 50, total: 3, total_pages: 3 } }; }
    else if (path === "/v1/agents/templates") data = { items: [], can_manage: false };
    else if (path.endsWith("/catalog")) data = { model_options: [], prompt_sections: [], groups: [], tools: [] };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) }); });
  try { const page = await context.newPage(); await page.goto(`${base}/agents/template-batches?batch_id=b`); await requested;
    await page.getByRole("link", { name: "Agent 模板", exact: true }).click(); await page.getByRole("heading", { name: "Agent 模板" }).waitFor();
    release(); await new Promise((resolve) => setTimeout(resolve, 750)); assert.deepEqual(pages, [1]);
  } finally { release(); await context.close(); await browser.close(); }
});

test("续接读取所有批次页并排除已成功店铺", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext(); const previews = [];
  const original = { store_id: "s2", action: "adopt", agent_id: "unlinked", expected_revision: 6, fields: {}, knowledge_mappings: {}, unbind_removed_file_ids: [], include_existing_draft: false, publish: false, enable_after_publish: false };
  await context.route("**/v1/**", async (route) => {
    const req = route.request(); const url = new URL(req.url()); const path = url.pathname; let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/templates/t") data = { id: "t", name: "模板", published_version: 2, archived_at: null };
    else if (path.endsWith("/versions")) data = [{ version: 1, config, content_sha256: "x", published_at: "now" }, { version: 2, config, content_sha256: "y", published_at: "now" }];
    else if (path.endsWith("/catalog")) data = { model_options: [], prompt_sections: [], groups: [], tools: [] };
    else if (path === "/v1/agents/templates/application-stores") { const page = Number(url.searchParams.get("page")); data = { items: [store(page)], pagination: pagination(page) }; }
    else if (path.endsWith("/knowledge-files")) data = { items: [], pagination: pagination(1, 0) };
    else if (path === "/v1/agents/template-batches/b") { const page = Number(url.searchParams.get("page")); data = { items: [{ id: `i${page}`, store_id: `s${page}`, status: page === 1 ? "succeeded" : "failed", preview: { request: page === 1 ? { ...original, store_id: "s1" } : original, diffs: [], issues: [], warnings: [], knowledge_slots: [], mappings: {}, full_target: {}, flags: {} } }], pagination: pagination(page) }; }
    else if (path.endsWith("/application-previews")) { const body = req.postDataJSON(); previews.push(body); data = { preview_id: "p", preview_hash: "h", template_id: "t", template_version: 1, items: [] }; }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) });
  });
  try {
    const page = await context.newPage(); await page.goto(`${base}/agents/templates/t/apply?version=2&parent_batch_id=b`);
    await page.getByRole("heading", { name: "店 2" }).waitFor(); assert.equal(await page.getByRole("heading", { name: "店 1" }).count(), 0);
    await page.getByRole("button", { name: "生成预览" }).click(); await page.getByText("确认冻结计划").waitFor();
    assert.equal(previews[0].parent_batch_id, "b"); assert.deepEqual(previews[0].items, [{ ...original, expected_revision: 7 }]);
    await page.getByLabel("模板版本").selectOption("1"); await page.getByRole("button", { name: "切换并重新预览" }).click();
    await page.getByRole("button", { name: "生成预览" }).click(); await page.getByText("确认冻结计划").waitFor();
    assert.equal(previews[1].parent_batch_id, "b"); assert.equal(previews[1].template_version, 1); assert.equal(previews[1].items[0].store_id, "s2");
  } finally { await context.close(); await browser.close(); }
});

test("fixround1 续接目标关联改变时要求重选且不猜其他 Agent", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext(); const writes = [];
  const old = { store_id: "s1", action: "update", agent_id: "a", expected_revision: 1, fields: {}, knowledge_mappings: {}, unbind_removed_file_ids: [], include_existing_draft: false, publish: false, enable_after_publish: false };
  await context.route("**/v1/**", async (route) => { const req = route.request(); const url = new URL(req.url()); const path = url.pathname; let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/templates/t") data = { id: "t", name: "模板", published_version: 1, archived_at: null };
    else if (path.endsWith("/versions")) data = [{ version: 1, config, content_sha256: "x", published_at: "now" }];
    else if (path.endsWith("/catalog")) data = { model_options: [], prompt_sections: [], groups: [], tools: [] };
    else if (path === "/v1/agents/templates/application-stores") data = { items: [{ ...store(1), agents: [{ id: "a", name: "原目标", code: "old", template_id: "other", draft_revision: 2, published_version: 1, status: "enabled" }, { id: "b", name: "另一目标", code: "new", template_id: null, draft_revision: 4, published_version: 1, status: "enabled" }] }], pagination: pagination(1, 1) };
    else if (path.endsWith("/knowledge-files")) data = { items: [], pagination: pagination(1, 0) };
    else if (path === "/v1/agents/template-batches/batch") data = { items: [{ id: "i", store_id: "s1", status: "needs_repreview", preview: { request: old, diffs: [], issues: [], warnings: [], knowledge_slots: [], mappings: {}, full_target: {}, flags: {} } }], pagination: pagination(1, 1) };
    else if (path.endsWith("/application-previews")) { writes.push(req.postDataJSON()); }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) }); });
  try { const page = await context.newPage(); await page.goto(`${base}/agents/templates/t/apply?version=1&parent_batch_id=batch`);
    await page.getByText("原目标已不可用或关联已变化，请重新选择目标。").waitFor({ timeout: 3000 }); assert.equal(await page.getByRole("button", { name: "生成预览" }).isDisabled(), true); assert.equal(writes.length, 0);
    await page.getByLabel("操作与目标").selectOption("adopt:b"); assert.equal(await page.getByRole("button", { name: "生成预览" }).isEnabled(), true);
  } finally { await context.close(); await browser.close(); }
});

test("取消任务明确提示成功项不回滚并调用取消接口", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext(); const calls = [];
  const summary = { id: "b", template_id: "t", template_version: 1, parent_batch_id: null, status: "running", cancel_requested: false, counts: { succeeded: 1, pending: 1 }, created_at: "now", confirmed_at: "now", finished_at: null, processor_enabled: true };
  await context.route("**/v1/**", async (route) => { const req = route.request(); const path = new URL(req.url()).pathname; calls.push(`${req.method()} ${path}`); let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/template-batches") data = { items: [summary], pagination: pagination(1, 1) };
    else if (path === "/v1/agents/template-batches/b" || path.endsWith("/cancel")) { if (path.endsWith("/cancel")) { summary.status = "cancelled"; summary.cancel_requested = true; } data = { ...summary, items: [], pagination: pagination(1, 0) }; }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) }); });
  try { const page = await context.newPage(); await page.goto(`${base}/agents/template-batches?batch_id=b`); await page.getByRole("button", { name: "取消任务" }).click(); await page.getByText("已成功的店铺不会回滚，尚未处理的项目将停止。").waitFor(); await page.getByRole("button", { name: "确认取消" }).click(); await page.getByRole("heading", { name: /已取消/ }).waitFor(); assert.ok(calls.includes("POST /v1/agents/template-batches/b/cancel")); }
  finally { await context.close(); await browser.close(); }
});

test("无知识查看权限不请求候选文件，仍可预览其他字段", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext(); const calls = []; let sent; let first = true;
  await context.route("**/v1/**", async (route) => { const req = route.request(); const path = new URL(req.url()).pathname; calls.push(path); let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/templates/t") data = { id: "t", name: "模板", published_version: 1, archived_at: null };
    else if (path.endsWith("/versions")) data = [{ version: 1, config, content_sha256: "x", published_at: "now" }];
    else if (path.endsWith("/catalog")) data = { model_options: [], prompt_sections: [], groups: [], tools: [] };
    else if (path === "/v1/agents/templates/application-stores") data = { items: [{ ...store(1), can_view_knowledge: false, agents: [{ id: "a", name: "客服", code: "x", template_id: "t", draft_revision: 1, published_version: 1, status: "enabled" }] }], pagination: pagination(1, 1) };
    else if (path.endsWith("/application-previews")) { sent = req.postDataJSON(); if (first) { first = false; assert.equal(sent.items[0].fields, null); return route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ code: 403, message: "没有本店知识绑定权限" }) }); } data = { preview_id: "p", preview_hash: "h", template_id: "t", template_version: 1, items: [{ id: "i", store_id: "s1", store_name: "店 1", agent_id: "a", action: "update", valid: true, issues: [], warnings: [{ code: "warn", message: "工具不可用", field: null }], diffs: [], published_snapshot: {}, full_target: {}, knowledge_slots: [], mappings: {}, has_existing_draft: false, field_choices: {}, flags: {}, request: sent.items[0] }] }; }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) }); });
  try { const page = await context.newPage(); await page.goto(`${base}/agents/templates/t/apply`); await chooseStore(page, "店 1 · store1"); await page.getByRole("button", { name: "生成预览" }).click(); await page.getByText("没有本店知识绑定权限").waitFor(); await page.getByRole("button", { name: "保留绑定并手工审阅" }).click(); await page.getByRole("button", { name: "生成预览" }).click(); await page.getByText("无知识查看权限；保留原绑定，可继续审阅其他字段。").waitFor(); await page.getByText("提示：工具不可用").waitFor(); assert.deepEqual(sent.items[0].fields, {}); assert.deepEqual(sent.items[0].knowledge_mappings, {}); assert.ok(!calls.some((path) => path.endsWith("/knowledge-files"))); }
  finally { await context.close(); await browser.close(); }
});

test("确认明确 409 且原计划未确认时保留编辑并允许重新预览", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext();
  await context.route("**/v1/**", async (route) => { const req = route.request(); const path = new URL(req.url()).pathname; let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/templates/t") data = { id: "t", name: "模板", published_version: 1, archived_at: null };
    else if (path.endsWith("/versions")) data = [{ version: 1, config, content_sha256: "x", published_at: "now" }];
    else if (path.endsWith("/catalog")) data = { model_options: [], prompt_sections: [], groups: [], tools: [] };
    else if (path === "/v1/agents/templates/application-stores") data = { items: [store(1)], pagination: pagination(1, 1) };
    else if (path.endsWith("/knowledge-files")) data = { items: [], pagination: pagination(1, 0) };
    else if (path.endsWith("/application-previews")) { const body = req.postDataJSON(); data = { preview_id: "p", preview_hash: "h", template_id: "t", template_version: 1, items: [{ id: "i", store_id: "s1", store_name: "店 1", agent_id: null, action: "create", valid: true, issues: [], warnings: [], diffs: [], published_snapshot: null, full_target: {}, knowledge_slots: [], mappings: {}, has_existing_draft: false, field_choices: {}, flags: {}, request: body.items[0] }] }; }
    else if (path === "/v1/agents/template-batches" && req.method() === "POST") return route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ code: 409, message: "预览已失效" }) });
    else if (path === "/v1/agents/template-batches/p") data = { id: "p", status: "preview", items: [], pagination: pagination(1, 0) };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) }); });
  try { const page = await context.newPage(); await page.goto(`${base}/agents/templates/t/apply`); await chooseStore(page, "店 1 · store1"); await page.getByLabel("名称", { exact: true }).fill("保留编辑"); await page.getByRole("button", { name: "生成预览" }).click(); await page.getByRole("button", { name: "确认批量任务" }).click(); await page.getByText(/确认被拒绝，请检查并重新预览/).waitFor(); assert.equal(await page.getByLabel("名称", { exact: true }).inputValue(), "保留编辑"); assert.equal(await page.getByRole("button", { name: "生成预览" }).isEnabled(), true); }
  finally { await context.close(); await browser.close(); }
});

test("fixround1 刷新后未知恢复保留 key，明确409再次查 preview 才释放", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext(); const calls = []; let attempts = 0; let failRecheck = false;
  await context.addInitScript(() => { sessionStorage.setItem("template-pending:t", "p"); sessionStorage.setItem("template-batch:p", "original-key"); });
  await context.route("**/v1/**", async (route) => { const req = route.request(); const path = new URL(req.url()).pathname; calls.push(`${req.method()} ${path}`); let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/templates/t") data = { id: "t", name: "模板", published_version: 1, archived_at: null };
    else if (path.endsWith("/versions")) data = [{ version: 1, config, content_sha256: "x", published_at: "now" }];
    else if (path.endsWith("/catalog")) data = { model_options: [], prompt_sections: [], groups: [], tools: [] };
    else if (path === "/v1/agents/templates/application-stores") data = { items: [store(1)], pagination: pagination(1, 1) };
    else if (path.endsWith("/knowledge-files")) data = { items: [], pagination: pagination(1, 0) };
    else if (path === "/v1/agents/template-batches/p") { if (failRecheck) { failRecheck = false; return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ code: 503, message: "查询不可用" }) }); } data = { id: "p", status: "preview", items: [], pagination: pagination(1, 0) }; }
    else if (path === "/v1/agents/template-batches" && req.method() === "POST") { assert.equal(req.headers()["idempotency-key"], "original-key"); attempts++; if (attempts === 2) failRecheck = true; const status = attempts === 1 ? 503 : 409; return route.fulfill({ status, contentType: "application/json", body: JSON.stringify({ code: status, message: `拒绝 ${status}` }) }); }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) }); });
  try {
    const page = await context.newPage(); await page.goto(`${base}/agents/templates/t/apply`); await chooseStore(page, "店 1 · store1");
    await page.getByRole("button", { name: "查询原任务" }).click(); await page.getByText(/服务端仍是未确认预览/).waitFor();
    await page.getByRole("button", { name: "使用原确认重试" }).click(); await page.getByText(/拒绝 503/).waitFor(); assert.equal(await page.getByRole("button", { name: "生成预览" }).isDisabled(), true);
    await page.getByRole("button", { name: "使用原确认重试" }).click(); await page.getByText(/确认结果未知/).waitFor(); assert.equal(await page.getByRole("button", { name: "生成预览" }).isDisabled(), true); assert.equal(await page.evaluate(() => sessionStorage.getItem("template-pending:t")), "p");
    await page.getByRole("button", { name: "使用原确认重试" }).click(); await page.getByText(/确认被拒绝，请检查并重新预览/).waitFor({ timeout: 3000 });
    assert.equal(await page.getByRole("button", { name: "生成预览" }).isEnabled(), true); assert.equal(await page.evaluate(() => sessionStorage.getItem("template-pending:t")), null);
    assert.ok(calls.filter((call) => call === "GET /v1/agents/template-batches/p").length >= 4);
  } finally { await context.close(); await browser.close(); }
});

test("归档模板与不存在的版本不会自动回退并创建计划", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext(); const calls = [];
  await context.route("**/v1/**", async (route) => { const path = new URL(route.request().url()).pathname; calls.push(path); let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/templates/t") data = { id: "t", name: "模板", published_version: 1, archived_at: "now" };
    else if (path.endsWith("/versions")) data = [{ version: 1, config, content_sha256: "x", published_at: "now" }];
    else if (path.endsWith("/catalog")) data = { model_options: [], prompt_sections: [], groups: [], tools: [] };
    else if (path === "/v1/agents/templates/application-stores") data = { items: [store(1)], pagination: pagination(1, 1) };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) }); });
  try { const page = await context.newPage(); await page.goto(`${base}/agents/templates/t/apply?version=99`); await page.getByText("指定的模板发布版本不存在或不可用，请选择有效版本。").waitFor(); await page.getByText("模板已归档，不能新建应用。").waitFor(); assert.equal(await page.getByLabel("模板版本").inputValue(), "0"); assert.equal(await page.getByRole("button", { name: "生成预览" }).isDisabled(), true); assert.ok(!calls.some((path) => path.endsWith("/application-previews"))); }
  finally { await context.close(); await browser.close(); }
});

test("跨店知识候选与映射分别来自本店", async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext(); const previews = []; let confirmed;
  await context.route("**/v1/**", async (route) => { const req = route.request(); const url = new URL(req.url()); const path = url.pathname; let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/templates/t") data = { id: "t", name: "模板", published_version: 1, archived_at: null };
    else if (path.endsWith("/versions")) data = [{ version: 1, config, content_sha256: "x", published_at: "now" }];
    else if (path.endsWith("/catalog")) data = { model_options: [], prompt_sections: [], groups: [], tools: [] };
    else if (path === "/v1/agents/templates/application-stores") { const p = Number(url.searchParams.get("page")); data = { items: [store(p)], pagination: pagination(p) }; }
    else if (path.endsWith("/knowledge-files")) { const shop = path.split("/")[5]; data = { items: [{ id: `file-${shop}`, name: `知识 ${shop}`, active_version_number: 1, status: "ready", publication_approval: "approved_for_internal_review", can_publish: true }], pagination: pagination(1, 1) }; }
    else if (path.endsWith("/application-previews")) { const body = req.postDataJSON(); previews.push(body); data = { preview_id: `p${previews.length}`, preview_hash: "h", template_id: "t", template_version: 1, items: body.items.map((item) => ({ id: item.store_id, store_id: item.store_id, store_name: item.store_id, agent_id: null, action: item.action, valid: true, issues: [], warnings: [], diffs: [], published_snapshot: null, full_target: { knowledge_file_ids: [`file-${item.store_id}`] }, knowledge_slots: [{ key: "faq", name: "FAQ", purpose: "问答", required: false }], mappings: item.knowledge_mappings, has_existing_draft: false, field_choices: {}, flags: {}, request: item })) }; }
    else if (path === "/v1/agents/template-batches" && req.method() === "POST") { confirmed = req.postDataJSON(); data = { id: confirmed.preview_id }; }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) }); });
  try { const page = await context.newPage(); await page.goto(`${base}/agents/templates/t/apply`); await chooseStore(page, "店 1 · store1"); await chooseStore(page, "店 2 · store2"); await page.getByRole("button", { name: "生成预览" }).click(); await page.getByText("可选知识绑定", { exact: true }).first().click(); await page.getByText("知识 s1 · 有效版本 1 · 可发布").click(); await page.getByText("可选知识绑定", { exact: true }).nth(1).click(); await page.getByText("知识 s2 · 有效版本 1 · 可发布").click(); assert.equal(await page.getByLabel("解绑已移除槽的模板来源：知识 s1", { exact: true }).count(), 0); assert.equal(await page.getByLabel("解绑已移除槽的模板来源：知识 s2", { exact: true }).count(), 0); await page.getByRole("button", { name: "生成预览" }).click(); await page.getByText("确认冻结计划").waitFor(); assert.equal(await page.getByLabel("解绑已移除槽的模板来源：知识 s1", { exact: true }).count(), 0); assert.equal(await page.getByLabel("解绑已移除槽的模板来源：知识 s2", { exact: true }).count(), 0); assert.deepEqual(previews[1].items.map((item) => item.knowledge_mappings), [{ faq: ["file-s1"] }, { faq: ["file-s2"] }]); const response = page.waitForResponse((r) => new URL(r.url()).pathname === "/v1/agents/template-batches" && r.request().method() === "POST"); await page.getByRole("button", { name: "确认批量任务" }).click(); await response; assert.deepEqual(confirmed, { preview_id: "p2", confirmation: true }); }
  finally { await context.close(); await browser.close(); }
});

for (const status of [404, 503]) test(`预览 ${status} 保留未确认编辑`, async () => {
  const browser = await chromium.launch({ channel: "chrome", headless: true }); const context = await browser.newContext();
  await context.route("**/v1/**", async (route) => { const path = new URL(route.request().url()).pathname; let data = {};
    if (path === "/v1/auth/me") data = { id: "u", name: "测试", role: "admin", permissions: [], store_ids: [] };
    else if (path === "/v1/agents/templates/t") data = { id: "t", name: "模板", published_version: 1, archived_at: null };
    else if (path.endsWith("/versions")) data = [{ version: 1, config, content_sha256: "x", published_at: "now" }];
    else if (path.endsWith("/catalog")) data = { model_options: [], prompt_sections: [], groups: [], tools: [] };
    else if (path === "/v1/agents/templates/application-stores") data = { items: [store(1)], pagination: pagination(1, 1) };
    else if (path.endsWith("/knowledge-files")) data = { items: [], pagination: pagination(1, 0) };
    else if (path.endsWith("/application-previews")) return route.fulfill({ status, contentType: "application/json", body: JSON.stringify({ code: status, message: `预览失败 ${status}` }) });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) }); });
  try { const page = await context.newPage(); await page.goto(`${base}/agents/templates/t/apply`); await chooseStore(page, "店 1 · store1"); await page.getByLabel("名称", { exact: true }).fill("尚未保存"); await page.getByRole("button", { name: "生成预览" }).click(); await page.getByText(`预览失败 ${status}`).waitFor(); assert.equal(await page.getByLabel("名称", { exact: true }).inputValue(), "尚未保存"); assert.equal(await page.getByText("确认冻结计划").count(), 0); }
  finally { await context.close(); await browser.close(); }
});
