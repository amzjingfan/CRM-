import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { after, before, test } from "node:test";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");
const baseUrl = process.env.UI_BASE_URL ?? "http://127.0.0.1:3101";
const origin = new URL(baseUrl).origin;
if (!["127.0.0.1", "localhost", "::1"].includes(new URL(baseUrl).hostname)) throw new Error("UI tests require a local server");

const store = { id: "00000000-0000-4000-8000-0000000000f1", name: "演示店铺", alias: null, code: "demo", status: "active", timezone: "Asia/Shanghai", currency: "CNY", created_at: "2026-10-01T00:00:00Z" };
const user = { id: "00000000-0000-4000-8000-000000000001", name: "测试坐席", email: null, login_name: "test_agent", role: "admin", avatar: null, permissions: ["workspace.reply", "workspace.view", "marketing.manage", "marketing.view"], store_ids: [store.id] };
const group = { id: "00000000-0000-4000-8000-0000000000a1", store_id: store.id, scope: "personal", owner_user_id: user.id, name: "常用话术", enabled: true, reply_count: 1, sort_order: 0 };
const reply = { id: "00000000-0000-4000-8000-0000000000b1", store_id: store.id, scope: "personal", owner_user_id: user.id, group_id: group.id, shortcut: "hello", tags: ["欢迎"], site_code: "US", messages: ["您好，欢迎咨询。"], sort_order: 0 };
const policy = { id: "00000000-0000-4000-8000-0000000000c1", kind: "timeout", name: "夜间值守", content: "您好，我们稍后回复。", timeout_minutes: 30, valid_from: null, valid_to: null, enabled: true, sort_order: 0, store_ids: [store.id], delivery_enabled: false };
let browser;
before(async () => { browser = await chromium.launch({ channel: "chrome", headless: true }); });
after(async () => { await browser?.close(); });

async function open(path, initial = {}) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const writes = [];
  let groups = [...(initial.groups ?? [group])];
  let replies = [...(initial.replies ?? [reply])];
  let policies = [...(initial.policies ?? [policy])];
  await context.route("**/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const headers = { "access-control-allow-origin": origin, "access-control-allow-credentials": "true", "access-control-allow-methods": "GET,POST,PATCH,DELETE,OPTIONS", "access-control-allow-headers": "content-type,idempotency-key,x-csrf-token" };
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    const path = url.pathname;
    const body = !["GET", "DELETE"].includes(request.method()) ? request.postDataJSON() : null;
    if (request.method() !== "GET") writes.push({ method: request.method(), path, body });
    let changed = null;
    if (path.includes("/reception/groups")) {
      if (request.method() === "POST") { changed = { ...group, ...body, id: "00000000-0000-4000-8000-0000000000a2", reply_count: 0 }; groups.push(changed); }
      else if (request.method() === "PATCH") { groups = groups.map((item) => item.id === path.split("/").at(-1) ? changed = { ...item, ...body } : item); }
      else if (request.method() === "DELETE") groups = groups.filter((item) => item.id !== path.split("/").at(-1));
    }
    if (path.includes("/reception/replies")) {
      if (request.method() === "POST") { changed = { ...reply, ...body, id: "00000000-0000-4000-8000-0000000000b2" }; replies.push(changed); }
      else if (request.method() === "PATCH") replies = replies.map((item) => item.id === path.split("/").at(-1) ? changed = { ...item, ...body } : item);
      else if (request.method() === "DELETE") replies = replies.filter((item) => item.id !== path.split("/").at(-1));
    }
    if (path.includes("/reception/policies")) {
      if (request.method() === "POST") { changed = { ...policy, ...body, id: "00000000-0000-4000-8000-0000000000c2" }; policies.push(changed); }
      else if (request.method() === "PATCH") policies = policies.map((item) => item.id === path.split("/").at(-1) ? changed = { ...item, ...body } : item);
      else if (request.method() === "DELETE") policies = policies.filter((item) => item.id !== path.split("/").at(-1));
    }
    const list = (items) => {
      const pageNumber = Number(url.searchParams.get("page") ?? "1");
      const pageSize = Number(url.searchParams.get("page_size") ?? "100");
      return { items: items.slice((pageNumber - 1) * pageSize, pageNumber * pageSize), total: items.length, page: pageNumber, page_size: pageSize };
    };
    const data = path === "/v1/auth/me" ? user
      : path === "/v1/settings/stores" ? [store]
      : changed ? changed
      : path.endsWith("/groups") ? list(groups.filter((item) => item.scope === url.searchParams.get("scope")).map((item) => ({ ...item, reply_count: replies.filter((entry) => entry.group_id === item.id).length })))
      : path.endsWith("/replies") ? list(replies.filter((item) => item.scope === url.searchParams.get("scope") && (url.searchParams.get("include_disabled") === "true" || groups.find((entry) => entry.id === item.group_id)?.enabled) && (!url.searchParams.get("group_id") || item.group_id === url.searchParams.get("group_id")) && (!url.searchParams.get("q") || `${item.shortcut} ${item.messages.join(" ")}`.includes(url.searchParams.get("q")))))
      : path.endsWith("/policies") ? list(policies.filter((item) => item.kind === url.searchParams.get("kind")).sort((left, right) => left.sort_order - right.sort_order || left.id.localeCompare(right.id)))
      : [];
    await route.fulfill({ status: request.method() === "DELETE" ? 204 : 200, headers, contentType: "application/json", body: request.method() === "DELETE" ? "" : JSON.stringify({ code: 0, message: "ok", data }) });
  });
  const tab = await context.newPage();
  await tab.goto(`${baseUrl}${path}`);
  await tab.getByRole("complementary", { name: "主导航" }).getByRole("button", { name: "智能营销" }).waitFor();
  return { context, tab, writes };
}

test("basic reception navigation preserves marketing and opens all three pages", async () => {
  const { context, tab } = await open("/marketing/reception/quick-replies");
  try {
    const sideNav = tab.getByRole("complementary", { name: "主导航" });
    const marketing = sideNav.getByRole("button", { name: "智能营销" });
    assert.equal(await marketing.getAttribute("aria-expanded"), "false");
    assert.equal(await sideNav.getByRole("link", { name: "营销流程", exact: true }).isVisible(), false);
    await marketing.click();
    assert.equal(await marketing.getAttribute("aria-expanded"), "true");
    const reception = sideNav.getByRole("button", { name: "基础接待" });
    assert.equal(await reception.getAttribute("aria-expanded"), "false");
    await reception.click();
    for (const [name, href] of [["营销流程", "/marketing"], ["快捷回复", "/marketing/reception/quick-replies"], ["超时自动回复", "/marketing/reception/timeout"], ["进店欢迎语", "/marketing/reception/welcome"]]) {
      assert.equal(await sideNav.getByRole("link", { name, exact: true }).getAttribute("href"), href);
    }
    for (const [name, href] of [["超时自动回复", "/marketing/reception/timeout"], ["进店欢迎语", "/marketing/reception/welcome"], ["快捷回复", "/marketing/reception/quick-replies"]]) {
      await sideNav.getByRole("link", { name, exact: true }).click();
      await tab.waitForURL(`${baseUrl}${href}`);
      assert.equal(await sideNav.getByRole("link", { name, exact: true }).getAttribute("aria-current"), "page");
    }
    await marketing.click();
    assert.equal(await marketing.getAttribute("aria-expanded"), "false");
  } finally { await context.close(); }
});

test("quick reply editor validates text and previews before save", async () => {
  const { context, tab, writes } = await open("/marketing/reception/quick-replies");
  try {
    await tab.getByRole("button", { name: "团队", exact: true }).click();
    await tab.getByRole("button", { name: "个人", exact: true }).click();
    await tab.getByRole("button", { name: "管理分组" }).click();
    await tab.getByRole("dialog", { name: "管理分组" }).getByText("常用话术").waitFor();
    await tab.getByRole("button", { name: "关闭管理分组" }).click();
    await tab.getByRole("button", { name: "新增快捷回复" }).click();
    const dialog = tab.getByRole("dialog", { name: "新增快捷回复" });
    await dialog.getByLabel("分组").selectOption(group.id);
    await dialog.getByLabel("快捷键").fill("/welcome");
    await dialog.getByLabel("选择站点").selectOption("US");
    await dialog.getByLabel("消息 1").fill("您好，感谢您的咨询。");
    await dialog.locator(".reception-preview-bubble").getByText("您好，感谢您的咨询。").waitFor();
    await dialog.getByRole("button", { name: "保存快捷回复" }).click();
    assert.equal(writes.some((write) => write.path.endsWith("/replies") && write.body.shortcut === "welcome" && write.body.site_code === "US" && write.body.messages[0] === "您好，感谢您的咨询。"), true);
    assert.equal(writes.some((write) => write.path.includes("/workspace/") || write.path.includes("/messages")), false);
  } finally { await context.close(); }
});

test("policy editor saves configuration only", async () => {
  const { context, tab, writes } = await open("/marketing/reception/timeout");
  try {
    await tab.getByText("仅保存配置，自动发送未启用").waitFor();
    await tab.getByRole("button", { name: "新增超时自动回复" }).click();
    const dialog = tab.getByRole("dialog", { name: "新增超时自动回复" });
    await dialog.getByLabel("策略名称").fill("午间接待");
    await dialog.getByLabel("超时分钟").fill("15");
    await dialog.getByLabel("回复内容").fill("您好，客服稍后回复。\n请稍候。");
    await dialog.getByRole("button", { name: "保存配置" }).click();
    assert.equal(writes.some((write) => write.path.endsWith("/policies") && write.body.kind === "timeout" && write.body.store_ids.includes(store.id)), true);
    assert.equal(writes.some((write) => write.path.includes("/messages") || write.path.includes("/campaigns")), false);
  } finally { await context.close(); }
});

test("group creation and deletion update visible groups", async () => {
  const { context, tab, writes } = await open("/marketing/reception/quick-replies");
  try {
    await tab.getByRole("button", { name: "添加分组" }).click();
    const dialog = tab.getByRole("dialog", { name: "添加分组" });
    await dialog.getByPlaceholder("输入分组名称").fill("售后回复");
    await dialog.getByRole("button", { name: "保存" }).click();
    await tab.getByRole("button", { name: "售后回复", exact: true }).waitFor();
    await tab.getByRole("button", { name: "管理分组" }).click();
    const drawer = tab.getByRole("dialog", { name: "管理分组" });
    await drawer.getByRole("row", { name: /售后回复/ }).getByRole("button", { name: "删除" }).click();
    await tab.getByRole("alertdialog", { name: "删除分组" }).getByRole("button", { name: "确认删除" }).click();
    await drawer.getByRole("row", { name: /售后回复/ }).waitFor({ state: "hidden" });
    assert.equal(writes.some((write) => write.method === "POST" && write.path.endsWith("/groups") && write.body.name === "售后回复"), true);
    assert.equal(writes.some((write) => write.method === "DELETE" && write.path.endsWith("/groups/00000000-0000-4000-8000-0000000000a2")), true);
  } finally { await context.close(); }
});

test("group management loads groups beyond the first API page", async () => {
  const groups = Array.from({ length: 101 }, (_, index) => ({
    ...group,
    id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
    name: `分组 ${index + 1}`,
  }));
  const { context, tab } = await open("/marketing/reception/quick-replies", { groups, replies: [] });
  try {
    await tab.getByRole("button", { name: "管理分组" }).click();
    await tab.getByRole("dialog", { name: "管理分组" }).getByRole("row", { name: /分组 101/ }).waitFor();
  } finally { await context.close(); }
});

test("disabled group stays in management while its replies remain editable", async () => {
  const { context, tab, writes } = await open("/marketing/reception/quick-replies");
  try {
    await tab.getByRole("button", { name: "管理分组" }).click();
    const drawer = tab.getByRole("dialog", { name: "管理分组" });
    await drawer.getByRole("switch", { name: "常用话术状态" }).click();
    await tab.getByText("分组已停用，工作台不再提供该组话术。").waitFor();
    assert.equal(await drawer.getByRole("switch", { name: "常用话术状态" }).getAttribute("aria-checked"), "false");
    await drawer.getByRole("button", { name: "关闭管理分组" }).click();
    await tab.getByText("/hello").waitFor();
    assert.equal(writes.some((write) => write.method === "PATCH" && write.path.endsWith(`/groups/${group.id}`) && write.body.enabled === false), true);
  } finally { await context.close(); }
});

test("new reply can choose team ownership without changing the list tab", async () => {
  const teamGroup = { ...group, id: "00000000-0000-4000-8000-0000000000a3", scope: "team", owner_user_id: null, name: "团队话术" };
  const { context, tab, writes } = await open("/marketing/reception/quick-replies", { groups: [group, teamGroup] });
  try {
    await tab.getByRole("button", { name: "新增快捷回复" }).click();
    const dialog = tab.getByRole("dialog", { name: "新增快捷回复" });
    await dialog.getByLabel("归属").selectOption("team");
    await dialog.getByLabel("分组").selectOption(teamGroup.id);
    await dialog.getByLabel("快捷键").fill("/team1");
    await dialog.getByLabel("消息 1").fill("团队标准回复");
    await dialog.getByRole("button", { name: "保存快捷回复" }).click();
    assert.equal(writes.some((write) => write.path.endsWith("/replies") && write.body.scope === "team" && write.body.group_id === teamGroup.id), true);
  } finally { await context.close(); }
});

test("policy more menu moves a strategy down one place", async () => {
  const policies = [
    { ...policy, name: "第一条", sort_order: 1 },
    { ...policy, id: "00000000-0000-4000-8000-0000000000c2", name: "第二条", sort_order: 2 },
    { ...policy, id: "00000000-0000-4000-8000-0000000000c3", name: "第三条", sort_order: 3 },
  ];
  const { context, tab, writes } = await open("/marketing/reception/timeout", { policies });
  try {
    await tab.getByRole("button", { name: "第一条更多操作" }).click();
    await tab.getByRole("button", { name: "下移" }).click();
    await tab.getByText("策略顺序已保存。").waitFor();
    assert.deepEqual(
      writes.filter((write) => write.method === "PATCH" && write.path.includes("/policies/")).map((write) => [write.path.split("/").at(-1), write.body.sort_order]),
      [[policies[1].id, 1], [policies[0].id, 2], [policies[2].id, 3]],
    );
  } finally { await context.close(); }
});

test("quick reply search and pagination use the scoped list API", async () => {
  const many = Array.from({ length: 23 }, (_, index) => ({ ...reply, id: `00000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`, shortcut: `r${index + 1}`, messages: [`回复 ${index + 1}`] }));
  const { context, tab } = await open("/marketing/reception/quick-replies", { replies: many });
  try {
    await tab.getByText("共 23 条 · 第 1 页").waitFor();
    await tab.getByRole("button", { name: "下一页" }).click();
    await tab.getByText("共 23 条 · 第 2 页").waitFor();
    await tab.waitForFunction(() => document.querySelectorAll(".reception-table tbody tr").length === 3);
    assert.equal(await tab.locator(".reception-table tbody tr").count(), 3);
    await tab.getByRole("textbox", { name: "搜索快捷回复" }).fill("r23");
    await tab.getByRole("button", { name: "搜索" }).click();
    await tab.waitForFunction(() => document.querySelectorAll(".reception-table tbody tr").length === 1);
    await tab.getByText("/r23").waitFor();
    assert.equal(await tab.locator(".reception-table tbody tr").count(), 1);
  } finally { await context.close(); }
});

test("policy configuration switch never reports delivery enabled", async () => {
  const { context, tab, writes } = await open("/marketing/reception/timeout");
  try {
    await tab.getByRole("button", { name: "夜间值守配置开关" }).click();
    await tab.getByText("配置开关已关闭，自动发送仍未启用。").waitFor();
    assert.equal(writes.some((write) => write.method === "PATCH" && write.path.endsWith(`/policies/${policy.id}`) && write.body.enabled === false), true);
    assert.equal(writes.some((write) => write.path.includes("/messages") || write.path.includes("/campaigns")), false);
  } finally { await context.close(); }
});
