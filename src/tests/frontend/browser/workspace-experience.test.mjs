import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { after, before, test } from "node:test";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");
const baseUrl = process.env.UI_BASE_URL ?? "http://127.0.0.1:3101";
const origin = new URL(baseUrl).origin;
const firstId = "00000000-0000-4000-8000-000000000101";
const secondId = "00000000-0000-4000-8000-000000000102";
const storeId = "00000000-0000-4000-8000-000000000201";
const assigneeId = "00000000-0000-4000-8000-000000000301";
let browser;

before(async () => { browser = await chromium.launch({ channel: "chrome", headless: true }); });
after(async () => { await browser?.close(); });

async function openWorkspace(messageCount = 70) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const records = [
    { id: firstId, store_id: storeId, platform: "tiktok", status: "active", is_starred: false, closed_at: null, unread_count: 2, assigned_user_id: null, last_message_at: "2026-10-20T10:00:00Z", last_message: "Latest message", customer: { id: "00000000-0000-4000-8000-000000000401", name: "Alice", email: null, avatar: null, tags: [] } },
    { id: secondId, store_id: storeId, platform: "tiktok", status: "active", is_starred: false, closed_at: null, unread_count: 3, assigned_user_id: null, last_message_at: "2026-10-20T09:00:00Z", last_message: "Another message", customer: { id: "00000000-0000-4000-8000-000000000402", name: "Bob", email: null, avatar: null, tags: [] } },
  ];
  const messages = Array.from({ length: messageCount }, (_, index) => ({ id: `message-${index}`, role: index % 2 ? "agent" : "user", content: `Message ${index}`, status: "received", created_at: new Date(Date.UTC(2026, 9, 20, 0, index)).toISOString(), error_code: null, delivery_mode: "inbound" }));
  const calls = { send: 0, transfer: 0 };
  await context.route("**/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const headers = { "access-control-allow-origin": origin, "access-control-allow-credentials": "true", "access-control-allow-methods": "GET,POST,PATCH,OPTIONS", "access-control-allow-headers": "content-type,idempotency-key,x-csrf-token" };
    if (method === "OPTIONS") return route.fulfill({ status: 204, headers });
    if (path === "/v1/chat/query") {
      const body = ["event: result", 'data: {"content":"AI draft ready","confidence":0.8,"intent":"general","requires_human":false,"demo_mode":false}', "", "event: done", 'data: {"reason":"completed"}', ""].join("\n");
      return route.fulfill({ status: 200, headers: { ...headers, "content-type": "text/event-stream" }, body });
    }
    let data;
    if (path === "/v1/auth/me") data = { id: assigneeId, name: "Agent", email: "agent@example.invalid", role: "agent", avatar: null, permissions: ["workspace.view", "workspace.reply", "workspace.transfer"], store_ids: [storeId] };
    else if (path === "/v1/settings/stores") data = [{ id: storeId, name: "TKW FITNESS", code: "tkw", status: "active", timezone: "America/Los_Angeles", currency: "USD", created_at: "2026-10-01T00:00:00Z" }];
    else if (path === "/v1/workspace/sessions" && method === "GET") {
      const filter = url.searchParams.get("filter");
      const items = records.filter((item) => filter === "closed" ? item.status === "closed" : item.status !== "closed" && (filter !== "starred" || item.is_starred));
      data = { items, pagination: { page: 1, page_size: 30, total: items.length } };
    } else if (path.endsWith("/messages") && method === "GET") {
      const record = records.find((item) => path.includes(item.id));
      const page = Number(url.searchParams.get("page") ?? "1");
      data = { session: record, customer: record.customer, messages: messages.slice((page - 1) * 100, page * 100), recent_orders: [], ai_suggestion: null, pagination: { page, page_size: 100, total: messages.length }, send_mode: record.status === "closed" ? "disabled" : "real", requires_confirmation: true, translation_enabled: false };
    } else if (path.endsWith("/read")) { records.find((item) => path.includes(item.id)).unread_count = 0; data = { unread_count: 0 }; }
    else if (path.endsWith("/star")) { const record = records.find((item) => path.includes(item.id)); record.is_starred = JSON.parse(request.postData()).starred; data = { status: record.status, is_starred: record.is_starred, closed_at: record.closed_at }; }
    else if (path.endsWith("/closed")) { const record = records.find((item) => path.includes(item.id)); record.status = JSON.parse(request.postData()).closed ? "closed" : "active"; data = { status: record.status, is_starred: record.is_starred, closed_at: record.status === "closed" ? "2026-10-20T11:00:00Z" : null }; }
    else if (path.endsWith("/assignees")) data = [{ id: assigneeId, name: "Agent A" }];
    else if (path.endsWith("/transfer")) { calls.transfer++; const record = records.find((item) => path.includes(item.id)); record.status = "transferred"; record.assigned_user_id = JSON.parse(request.postData()).assign_to; data = { status: "transferred", transfer_id: "00000000-0000-4000-8000-000000000501" }; }
    else if (path.endsWith("/messages") && method === "POST") { calls.send++; data = messages.at(-1); }
    else data = [];
    await route.fulfill({ status: 200, contentType: "application/json", headers, body: JSON.stringify({ code: 0, message: "ok", data }) });
  });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/workspace?session=${firstId}`);
  await page.getByRole("heading", { name: "Alice" }).first().waitFor();
  return { context, page, messages, records, calls };
}

test("conversation opens at newest message and offers a return button while reading history", async () => {
  const { context, page, messages, records } = await openWorkspace();
  try {
    const scroll = page.locator(".message-scroll");
    await page.getByText("Message 69").waitFor();
    await page.waitForFunction(() => { const node = document.querySelector(".message-scroll"); return node && node.scrollHeight - node.scrollTop - node.clientHeight < 5; });
    await scroll.evaluate((node) => { node.scrollTop = 0; });
    await page.getByRole("button", { name: "到最新消息" }).waitFor({ state: "visible" });
    records[0].unread_count = 1;
    messages.push({ id: "message-70", role: "user", content: "New incoming", status: "received", created_at: "2026-10-20T02:00:00Z", error_code: null, delivery_mode: "inbound" });
    await page.getByText("New incoming").waitFor({ timeout: 8000 });
    assert.equal(await scroll.evaluate((node) => node.scrollTop), 0);
    await page.getByRole("button", { name: "到最新消息" }).click();
    await page.locator(".conversation-card.active .unread").waitFor({ state: "hidden" });
    await page.waitForFunction(() => { const node = document.querySelector(".message-scroll"); return node && node.scrollHeight - node.scrollTop - node.clientHeight < 5; });
    assert.match(await page.getByRole("button", { name: /Bob/ }).textContent(), /3/);
  } finally { await context.close(); }
});

test("loading older messages preserves the current reading position", async () => {
  const { context, page } = await openWorkspace(130);
  try {
    const scroll = page.locator(".message-scroll");
    await page.getByText("Message 129").waitFor();
    await scroll.evaluate((node) => { node.scrollTop = 0; });
    const before = await page.getByText("Message 100", { exact: true }).boundingBox();
    await page.getByRole("button", { name: "加载更早消息" }).click();
    await page.getByText("Message 0", { exact: true }).waitFor();
    const after = await page.getByText("Message 100", { exact: true }).boundingBox();
    assert.ok(before && after && Math.abs(before.y - after.y) < 5, `reading position moved from ${before?.y} to ${after?.y}`);
  } finally { await context.close(); }
});

test("AI result fills editable draft without sending; star, transfer and close persist in CRM", async () => {
  const { context, page, calls } = await openWorkspace();
  try {
    await page.getByRole("button", { name: "生成" }).click();
    const draft = page.getByRole("textbox", { name: "回复内容" });
    await page.waitForFunction(() => document.querySelector('textarea[aria-label="回复内容"]')?.value === "AI draft ready");
    assert.equal(await draft.inputValue(), "AI draft ready");
    assert.equal(calls.send, 0);
    await page.getByRole("button", { name: "标记差评风险" }).click();
    await page.getByRole("button", { name: "取消差评风险标记" }).waitFor();
    await page.getByRole("button", { name: "转交会话" }).click();
    await page.getByRole("combobox", { name: "目标坐席" }).selectOption(assigneeId);
    await page.getByRole("button", { name: "确认转交" }).click();
    assert.equal(calls.transfer, 1);
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "关闭会话" }).click();
    await page.getByRole("button", { name: "已关闭" }).click();
    await page.getByRole("button", { name: "重新打开会话" }).waitFor();
    assert.equal(await draft.isDisabled(), true);
    await page.getByRole("button", { name: "重新打开会话" }).click();
    await page.getByRole("button", { name: "全部" }).first().click();
    await page.getByRole("button", { name: "关闭会话" }).waitFor();
    assert.equal(calls.send, 0);
  } finally { await context.close(); }
});
