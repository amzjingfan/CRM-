import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { after, before, test } from "node:test";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");
const baseUrl = process.env.UI_BASE_URL ?? "http://127.0.0.1:3101";
const origin = new URL(baseUrl).origin;
if (!["127.0.0.1", "localhost", "::1"].includes(new URL(baseUrl).hostname)) throw new Error("UI tests require a local server");

const store = { id: "00000000-0000-4000-8000-0000000000f1", name: "演示店铺", alias: null, code: "demo", status: "active", timezone: "Asia/Shanghai", currency: "CNY", created_at: "2026-10-01T00:00:00Z" };
const secondStore = { ...store, id: "00000000-0000-4000-8000-0000000000f2", name: "第二店铺", code: "second" };
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
  const availableStores = initial.stores ?? [store];
  const signedInUser = { ...user, store_ids: availableStores.map((item) => item.id) };
  await context.route("**/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const headers = { "access-control-allow-origin": origin, "access-control-allow-credentials": "true", "access-control-allow-methods": "GET,POST,PATCH,DELETE,OPTIONS", "access-control-allow-headers": "content-type,idempotency-key,x-csrf-token" };
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    const path = url.pathname;
    if (initial.beforeResponse) await initial.beforeResponse(path);
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
    const data = path === "/v1/auth/me" ? signedInUser
      : path === "/v1/settings/stores" ? availableStores
      : changed ? changed
      : path.endsWith("/groups") ? list(groups.filter((item) => item.scope === url.searchParams.get("scope")).map((item) => ({ ...item, reply_count: replies.filter((entry) => entry.group_id === item.id).length })))
      : path.endsWith("/replies") ? list(replies.filter((item) => item.scope === url.searchParams.get("scope") && (url.searchParams.get("include_disabled") === "true" || groups.find((entry) => entry.id === item.group_id)?.enabled) && (!url.searchParams.get("group_id") || item.group_id === url.searchParams.get("group_id")) && (!url.searchParams.get("q") || `${item.shortcut} ${item.messages.join(" ")}`.includes(url.searchParams.get("q")))))
      : path.endsWith("/policies") ? list(policies.filter((item) => item.kind === url.searchParams.get("kind") && (!url.searchParams.get("store_id") || item.store_ids.includes(url.searchParams.get("store_id")))).sort((left, right) => left.sort_order - right.sort_order || left.id.localeCompare(right.id)))
      : [];
    await route.fulfill({ status: request.method() === "DELETE" ? 204 : 200, headers, contentType: "application/json", body: request.method() === "DELETE" ? "" : JSON.stringify({ code: 0, message: "ok", data }) });
  });
  const tab = await context.newPage();
  await tab.goto(`${baseUrl}${path}`);
  if (!initial.skipNavWait) await tab.getByRole("complementary", { name: "主导航" }).getByRole("button", { name: "智能营销" }).waitFor();
  return { context, tab, writes };
}

test("reception pages request store names while identity is pending", async () => {
  for (const path of ["/marketing/reception/quick-replies", "/marketing/reception/timeout"]) {
    let releaseIdentity = () => {};
    let storeRequested = () => {};
    const identityGate = new Promise((resolve) => { releaseIdentity = resolve; });
    const storeRequest = new Promise((resolve) => { storeRequested = resolve; });
    const { context } = await open(path, { skipNavWait: true, beforeResponse: async (requestPath) => {
      if (requestPath === "/v1/auth/me") await identityGate;
      if (requestPath === "/v1/settings/stores") storeRequested();
    } });
    try {
      await Promise.race([storeRequest, new Promise((_, reject) => setTimeout(() => reject(new Error(`Store request waited for identity on ${path}`)), 1500))]);
    } finally {
      releaseIdentity();
      await context.close();
    }
  }
});

test("marketing sidebar has two entries and reception pages use in-page tabs", async () => {
  const { context, tab } = await open("/marketing/reception/quick-replies");
  try {
    const sideNav = tab.getByRole("complementary", { name: "主导航" });
    const marketing = sideNav.getByRole("button", { name: "智能营销" });
    assert.equal(await marketing.getAttribute("aria-expanded"), "false");
    assert.equal(await sideNav.getByRole("link", { name: "营销流程", exact: true }).isVisible(), false);
    await marketing.click();
    assert.equal(await marketing.getAttribute("aria-expanded"), "true");
    assert.equal(await sideNav.getByRole("link", { name: "营销流程" }).getAttribute("href"), "/marketing");
    assert.equal(await sideNav.getByRole("link", { name: "基础接待" }).getAttribute("href"), "/marketing/reception");
    for (const name of ["快捷回复", "超时自动回复", "进店欢迎语"]) assert.equal(await sideNav.getByRole("link", { name }).count(), 0);
    for (const [name, href] of [["超时自动回复", "/marketing/reception/timeout"], ["进店欢迎语", "/marketing/reception/welcome"], ["快捷回复", "/marketing/reception/quick-replies"]]) {
      await tab.locator(".reception-page-tabs").getByRole("link", { name, exact: true }).click();
      await tab.waitForURL(`${baseUrl}${href}`);
      assert.equal(await marketing.getAttribute("aria-expanded"), "false");
      assert.match(await tab.locator(".reception-crumb").textContent(), new RegExp(name));
      assert.equal(await tab.locator(".reception-head h1").textContent(), name);
      assert.equal(await tab.locator(".reception-card").count(), 1);
    }
    await marketing.click();
    assert.equal(await marketing.getAttribute("aria-expanded"), "true");
    await marketing.click();
    assert.equal(await marketing.getAttribute("aria-expanded"), "false");
  } finally { await context.close(); }
});

test("compact marketing flyout closes on outside click and does not persist across pages", async () => {
  const { context, tab } = await open("/marketing/reception/quick-replies");
  try {
    await tab.setViewportSize({ width: 1010, height: 800 });
    const marketing = tab.getByRole("complementary", { name: "主导航" }).getByRole("button", { name: "智能营销" });
    await marketing.click();
    assert.equal(await marketing.getAttribute("aria-expanded"), "true");
    await tab.locator(".reception-page h1").click();
    assert.equal(await marketing.getAttribute("aria-expanded"), "false");
    await marketing.click();
    await tab.reload();
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
    await tab.getByText("管理适用店铺、有效期及策略状态；自动发送尚未启用。").waitFor();
    await tab.getByRole("button", { name: "新增策略" }).click();
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

for (const [kind, label] of [["timeout", "超时自动回复"], ["welcome", "进店欢迎语"]]) {
  test(`${kind} policy remains visible after saving for a different authorized store`, async () => {
    const { context, tab, writes } = await open(`/marketing/reception/${kind}`, { stores: [store, secondStore], policies: [] });
    try {
      await tab.getByRole("button", { name: "新增策略" }).click();
      const dialog = tab.getByRole("dialog", { name: `新增${label}` });
      await dialog.getByLabel("策略名称").fill("第二店铺策略");
      await dialog.getByLabel("回复内容").fill("稍后人工处理。");
      await dialog.getByRole("button", { name: "适用店铺" }).click();
      await dialog.getByRole("checkbox", { name: "演示店铺" }).uncheck();
      await dialog.getByRole("checkbox", { name: "第二店铺" }).check();
      await dialog.getByRole("button", { name: "保存配置" }).click();
      await tab.getByText("配置已保存。自动发送仍未启用。").waitFor();
      assert.equal(writes.some((write) => write.method === "POST" && write.path.endsWith("/policies") && write.body.store_ids.length === 1 && write.body.store_ids[0] === secondStore.id), true);
      await tab.getByRole("row", { name: /第二店铺策略/ }).waitFor({ timeout: 3000 });
    } finally { await context.close(); }
  });

  test(`${kind} saves and reloads a fixed daily validity window`, async () => {
    const { context, tab, writes } = await open(`/marketing/reception/${kind}`, { policies: [] });
    try {
      await tab.getByRole("button", { name: "新增策略" }).click();
      const dialog = tab.getByRole("dialog", { name: `新增${label}` });
      await dialog.getByLabel("策略名称").fill("固定时段策略");
      await dialog.getByLabel("回复内容").fill("人工稍后处理");
      assert.equal(await dialog.getByRole("radio", { name: "长期" }).isChecked(), true);
      await dialog.getByRole("radio", { name: "起止", exact: true }).check();
      assert.equal(await dialog.getByLabel("开始日期").isVisible(), true);
      assert.equal(await dialog.getByLabel("每天开始时间").count(), 0);
      await dialog.getByRole("radio", { name: "固定时段" }).check();
      await dialog.getByLabel("开始日期").fill("2026-10-23");
      await dialog.getByLabel("结束日期").fill("2026-10-30");
      await dialog.getByLabel("每天开始时间").fill("09:00");
      await dialog.getByLabel("每天结束时间").fill("18:00");
      await dialog.getByRole("button", { name: "保存配置" }).click();
      await tab.getByRole("row", { name: /固定时段策略/ }).waitFor();
      const created = writes.find((write) => write.method === "POST" && write.path.endsWith("/policies"));
      assert.deepEqual(created.body.schedule, { mode: "fixed_hours", start_date: "2026-10-23", end_date: "2026-10-30", daily_start_time: "09:00", daily_end_time: "18:00" });
      assert.equal(created.body.valid_from, null);
      await tab.getByRole("row", { name: /固定时段策略/ }).getByRole("button", { name: "编辑" }).click();
      const editor = tab.getByRole("dialog", { name: `编辑${label}` });
      assert.equal(await editor.getByRole("radio", { name: "固定时段" }).isChecked(), true);
      assert.equal(await editor.getByLabel("每天开始时间").inputValue(), "09:00");
      assert.equal(await editor.getByLabel("每天结束时间").inputValue(), "18:00");
    } finally { await context.close(); }
  });
}

test("policy table filters by store alias and effective status", async () => {
  const future = new Date(Date.now() + 7 * 86_400_000).toISOString().slice(0, 10);
  const later = new Date(Date.now() + 14 * 86_400_000).toISOString().slice(0, 10);
  const entries = [
    { ...policy, name: "当前生效", schedule: { mode: "long_term", start_date: null, end_date: null, daily_start_time: null, daily_end_time: null } },
    { ...policy, id: "00000000-0000-4000-8000-0000000000c2", name: "未来开始", store_ids: [secondStore.id], schedule: { mode: "date_range", start_date: future, end_date: later, daily_start_time: null, daily_end_time: null } },
    { ...policy, id: "00000000-0000-4000-8000-0000000000c3", name: "开关关闭", store_ids: [secondStore.id], enabled: false },
  ];
  const { context, tab } = await open("/marketing/reception/timeout", { stores: [store, { ...secondStore, alias: "第二别名" }], policies: entries });
  try {
    await tab.getByRole("row", { name: /未来开始/ }).getByText("未开始").waitFor();
    await tab.getByRole("button", { name: "有效策略" }).click();
    assert.equal(await tab.locator(".reception-policy-table tbody tr").count(), 1);
    await tab.getByRole("button", { name: "失效策略" }).click();
    assert.equal(await tab.locator(".reception-policy-table tbody tr").count(), 2);
    await tab.getByRole("button", { name: "全部策略" }).click();
    await tab.getByRole("textbox", { name: "按店铺名称或别名搜索" }).fill("第二别名");
    assert.equal(await tab.locator(".reception-policy-table tbody tr").count(), 2);
  } finally { await context.close(); }
});

test("policy actions remain reachable in the narrow workspace", async () => {
  const { context, tab } = await open("/marketing/reception/welcome", { policies: [{ ...policy, kind: "welcome", timeout_minutes: null }] });
  try {
    await tab.setViewportSize({ width: 1120, height: 892 });
    await tab.getByRole("button", { name: "夜间值守更多操作" }).click();
    await tab.getByRole("button", { name: "删除", exact: true }).click();
    await tab.getByRole("alertdialog", { name: "删除策略" }).waitFor();
  } finally { await context.close(); }
});

test("editing an old policy preserves its UTC validity until the user changes it", async () => {
  const old = { ...policy, valid_from: "2026-10-20T08:00:00Z", valid_to: "2026-11-20T08:00:00Z", schedule: null };
  const { context, tab, writes } = await open("/marketing/reception/timeout", { policies: [old] });
  try {
    await tab.getByRole("row", { name: /夜间值守/ }).getByRole("button", { name: "编辑" }).click();
    const dialog = tab.getByRole("dialog", { name: "编辑超时自动回复" });
    await dialog.getByLabel("回复内容").fill("更新文本，不改时间");
    await dialog.getByRole("button", { name: "保存配置" }).click();
    const updated = writes.find((write) => write.method === "PATCH" && write.path.endsWith(`/policies/${old.id}`));
    assert.equal(updated.body.valid_from, old.valid_from);
    assert.equal(updated.body.valid_to, old.valid_to);
    assert.equal(updated.body.schedule, null);
  } finally { await context.close(); }
});

test("batch settings add only unassigned stores to an existing welcome policy", async () => {
  const welcome = { ...policy, kind: "welcome", timeout_minutes: null };
  const { context, tab, writes } = await open("/marketing/reception/welcome", { stores: [store, secondStore], policies: [welcome] });
  try {
    await tab.getByText("未加入策略的店铺：1").waitFor();
    await tab.getByRole("button", { name: "批量设置" }).click();
    const dialog = tab.getByRole("dialog", { name: "批量设置店铺" });
    await dialog.getByRole("button", { name: "保存设置" }).click();
    await tab.getByText("未加入策略的店铺：0").waitFor();
    assert.equal(writes.some((write) => write.method === "PATCH" && write.path.endsWith(`/policies/${welcome.id}`) && write.body.store_ids.includes(store.id) && write.body.store_ids.includes(secondStore.id)), true);
  } finally { await context.close(); }
});
