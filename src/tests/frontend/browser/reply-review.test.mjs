import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { after, before, test } from "node:test";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");
const baseUrl = process.env.UI_BASE_URL ?? "http://127.0.0.1:3124";
if (!["127.0.0.1", "localhost", "::1"].includes(new URL(baseUrl).hostname)) throw new Error("local browser only");
const sessionId = "00000000-0000-4000-8000-000000000101";
const otherId = "00000000-0000-4000-8000-000000000102";
let browser;
before(async () => { browser = await chromium.launch({ channel: "chrome", headless: true }); });
after(async () => { await browser?.close(); });

async function openReview(options = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const batches = [];
  const records = [sessionId, otherId].map((id, index) => ({ id, store_id: "store-1", platform: "tiktok", status: "active", is_starred: false, closed_at: null, unread_count: 0, assigned_user_id: null, last_message_at: "2026-10-29T01:00:00Z", last_message: "Where is my parcel?", customer: { id: `customer-${index}`, name: index ? "Bob" : "Alice", email: null, avatar: null, tags: [], buyer_stage_override: null } }));
  const card = { order_id: "order-1", package_id: "package-1", product_name: "Test parcel", image_url: null, sku_name: null, quantity: 1, unit_price: null, currency: null, tracking_number: "TRACK-1", carrier_name: "Test carrier", latest_description: "Arrived today", latest_at: "2026-10-29T01:00:00Z" };
  const notificationRequests = [];
  const state = { cardFailure: false, batchStatus: "completed", batchParts: null, orders: options.orders ?? [] };
  await context.route("**/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const headers = { "access-control-allow-origin": new URL(baseUrl).origin, "access-control-allow-credentials": "true", "access-control-allow-methods": "GET,POST,OPTIONS", "access-control-allow-headers": "content-type,idempotency-key,x-csrf-token" };
    if (req.method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    let data = [];
    if (path.endsWith("/auth/me")) data = { id: "agent-1", name: "Agent", permissions: ["workspace.view", "workspace.reply"], store_ids: ["store-1"], role: "agent", email: null, avatar: null };
    else if (path.endsWith("/settings/stores")) data = [{ id: "store-1", name: "Test store", alias: null, code: "test", status: "active", timezone: "UTC", currency: "USD", created_at: "2026-10-29T00:00:00Z" }];
    else if (path.endsWith("/workspace/sessions")) data = { items: records, pagination: { page: 1, page_size: 30, total: 2 }, unread_messages_total: 0 };
    else if (path.endsWith("/messages") && req.method() === "GET") { const record = records.find((item) => path.includes(item.id)); data = { session: record, customer: record.customer, messages: [{ id: "buyer-1", role: "user", content: "Where is my parcel?", status: "received", created_at: "2026-10-29T01:00:00Z", error_code: null, delivery_mode: "inbound" }], recent_orders: [], ai_suggestion: null, pagination: { page: 1, page_size: 100, total: 1 }, send_mode: "mock", requires_confirmation: true, draft_translation_enabled: true }; }
    else if (path.endsWith("/sidebar/search")) data = { items: state.orders, pagination: { page: 1, page_size: 20, total: state.orders.length } };
    else if (path.endsWith("/logistics-notifications/policy")) data = { store_id: "store-1", agent_id: "agent-1", enabled: true, mode: "preview", enabled_at: "2026-10-29T00:00:00Z", revision: 1, global_enabled: false, real_delivery_enabled: false, last_scan_at: null };
    else if (path.endsWith("/logistics-notifications/preview")) { notificationRequests.push(JSON.parse(req.postData())); data = { status: "previewed", preview_text: "Your parcel arrived today.", event_at: "2026-10-29T01:00:00Z", buyer_language: "en" }; }
    else if (path.endsWith("/logistics-notifications")) { assert.equal(url.searchParams.get("conversation_id"), sessionId); assert.equal(url.searchParams.get("store_id"), "store-1"); data = []; }
    else if (path.endsWith("/logistics-card-preview")) {
      assert.equal(url.searchParams.get("order_id"), "order-1");
      if (state.cardFailure) return route.fulfill({ status: 503, headers, contentType: "application/json", body: JSON.stringify({ code: 503, message: "Card temporarily unavailable", data: null }) });
      data = [{ card, packages: [], enhanced_available: false, selected: 0 }];
    } else if (path.endsWith("/reply-batches")) {
      const body = JSON.parse(req.postData());
      batches.push({ body, key: req.headers()["idempotency-key"] });
      data = { id: "batch-1", preview_only: body.preview_only, status: state.batchStatus, parts: state.batchParts ?? body.parts.map((part, index) => ({ index, kind: part.kind, status: body.preview_only ? "previewed" : "sent", message_id: null, error_code: null })), messages: [] };
    } else if (req.method() !== "GET" && !path.endsWith("/read")) throw new Error(`Unexpected write ${path}`);
    await route.fulfill({ status: 200, headers, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) });
  });
  await context.addInitScript(() => {
    const realFetch = window.fetch;
    window.replyEvents = [];
    window.fetch = (url, init) => {
      if (String(url).endsWith("/chat/query")) {
        window.replyRequest = JSON.parse(init.body);
        return Promise.resolve(new Response(new ReadableStream({ start(controller) { window.replyStream = controller; } }), { headers: { "content-type": "text/event-stream" } }));
      }
      return realFetch(url, init);
    };
    window.emitReply = (event, data) => window.replyStream.enqueue(new TextEncoder().encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
  });
  const page = await context.newPage();
  await page.goto(`${baseUrl}/workspace?session=${sessionId}`);
  await page.getByRole("heading", { name: "Alice", exact: true }).first().waitFor();
  const emit = (event, data) => page.evaluate(({ event, data }) => window.emitReply(event, data), { event, data });
  const finish = async (parts, orders = []) => { await emit("result", { content: parts[0] ?? null, reply_parts: parts, logistics_order_numbers: orders, trigger_message_id: "buyer-1", reason_codes: [] }); await emit("done", { reason: "completed" }); };
  return { context, page, emit, finish, batches, state, notificationRequests };
}

test("final stream operator translation stays internal and never enters the reply batch", async () => {
  const { context, page, emit, finish, batches } = await openReview();
  try {
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await emit("result", { content: "Your parcel arrives tomorrow.", reply_parts: ["Your parcel arrives tomorrow."], trigger_message_id: "buyer-1", translation: { trigger_message_id: "buyer-1", target_language: "zh-CN", message_translation: "包裹何时到？", draft_translation: "您的包裹明天送达。" } });
    await emit("done", { reason: "completed" });
    const panel = page.getByRole("region", { name: "回复审阅" });
    await panel.getByText("坐席译文 · 简体中文", { exact: true }).click({ timeout: 5000 });
    await panel.getByText("您的包裹明天送达。", { exact: true }).waitFor();
    assert.equal(await page.getByRole("textbox", { name: "回复内容", exact: true }).inputValue(), "Your parcel arrives tomorrow.");
    assert.equal(await panel.locator(".reply-review-parts").getByText("您的包裹明天送达。", { exact: true }).count(), 0);
    await panel.getByRole("button", { name: "审阅整组发送", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "审阅整组回复" });
    assert.equal(await dialog.getByText("您的包裹明天送达。", { exact: true }).count(), 0);
    await dialog.getByRole("button", { name: "确认发送整组", exact: true }).click();
    await page.getByText("交付完成", { exact: true }).waitFor();
    assert.deepEqual(batches[0].body.parts, [{ kind: "text", content: "Your parcel arrives tomorrow." }]);
    await panel.getByRole("button", { name: "刷新", exact: true }).click();
    await finish(["Another reviewed reply."]);
    assert.equal(await panel.getByText("您的包裹明天送达。", { exact: true }).count(), 0);
  } finally { await context.close(); }
});

test("translation failure keeps the reviewed customer reply usable without exposing technical errors", async () => {
  const { context, page, emit } = await openReview();
  try {
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await emit("result", { content: "Your parcel arrives tomorrow.", reply_parts: ["Your parcel arrives tomorrow."], trigger_message_id: "buyer-1", translation_error_code: "operator_translation_provider_error" });
    await emit("done", { reason: "completed" });
    const panel = page.getByRole("region", { name: "回复审阅" });
    await panel.getByText("坐席译文暂不可用，请复核客户正文。", { exact: true }).waitFor({ timeout: 5000 });
    assert.equal(await page.getByRole("textbox", { name: "回复内容", exact: true }).inputValue(), "Your parcel arrives tomorrow.");
    assert.equal(await panel.getByRole("button", { name: "审阅整组发送", exact: true }).isEnabled(), true);
    assert.equal(await page.getByText("operator_translation_provider_error", { exact: true }).count(), 0);
  } finally { await context.close(); }
});

test("a translation for another buyer message never appears beside the current reviewed reply", async () => {
  const { context, page, emit } = await openReview();
  try {
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await emit("result", { content: "Current reply.", reply_parts: ["Current reply."], trigger_message_id: "buyer-1", translation: { trigger_message_id: "other-buyer", target_language: "zh-CN", message_translation: "旧问题", draft_translation: "其他消息的译文" } });
    await emit("done", { reason: "completed" });
    await page.getByRole("region", { name: "回复审阅" }).getByText("Current reply.", { exact: true }).waitFor();
    assert.equal(await page.getByText("其他消息的译文", { exact: true }).count(), 0);
  } finally { await context.close(); }
});

test("unverified streamed drafts stay outside the composer until final review succeeds", async () => {
  const { context, page, emit, finish } = await openReview();
  try {
    const composer = page.getByRole("textbox", { name: "回复内容", exact: true });
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await emit("draft", { part_index: 0, text: "Your parcel", replace: true, unverified: true, sendable: false, trigger_message_id: "buyer-1" });
    await page.getByLabel("未复核生成草稿").getByText("Your parcel", { exact: true }).waitFor();
    if (process.env.REPLY_REVIEW_CAPTURE) await page.screenshot({ path: process.env.REPLY_REVIEW_CAPTURE, fullPage: true });
    assert.equal(await composer.inputValue(), "");
    assert.equal(await page.getByRole("button", { name: "使用", exact: true }).count(), 0);
    await emit("draft", { part_index: 0, text: "Your parcel arrived today.", replace: true, unverified: true, sendable: false, trigger_message_id: "buyer-1" });
    await finish(["Your parcel arrived today."]);
    await page.waitForFunction(() => document.querySelector('textarea[aria-label="回复内容"]')?.value === "Your parcel arrived today.");
    assert.equal(await page.getByLabel("未复核生成草稿").count(), 0);
    assert.deepEqual(await page.evaluate(() => window.replyRequest), { session_id: sessionId, trigger_message_id: "buyer-1", reply_mode: "review_plan" });
  } finally { await context.close(); }
});

test("temporary preview controls are absent while ordered review stays available", async () => {
  const { context, page, finish, batches, notificationRequests } = await openReview();
  try {
    assert.equal(await page.getByText("物流更新通知预演", { exact: true }).count(), 0);
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await finish(["Your parcel arrived today."], ["order-1"]);
    const panel = page.getByRole("region", { name: "回复审阅" });
    await panel.getByLabel("物流卡片", { exact: true }).waitFor();
    assert.equal(await panel.getByRole("button", { name: "预演交付顺序", exact: true }).count(), 0);
    await panel.getByRole("button", { name: "审阅整组发送", exact: true }).click();
    await page.getByRole("dialog", { name: "审阅整组回复" }).waitFor();
    assert.equal(batches.length, 0);
    assert.equal(notificationRequests.length, 0);
  } finally { await context.close(); }
});

test("multiple verified answers precede native cards and confirmation uses the actual composer edit", async () => {
  const { context, page, finish, batches } = await openReview();
  try {
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await finish(["Your parcel arrived today.", "Returns are accepted within 30 days."], ["order-1"]);
    const panel = page.getByRole("region", { name: "回复审阅" });
    await panel.getByLabel("物流卡片", { exact: true }).waitFor();
    await page.getByRole("textbox", { name: "回复内容", exact: true }).fill("Edited latest status.");
    await panel.getByRole("button", { name: "审阅整组发送", exact: true }).click();
    const review = page.getByRole("dialog", { name: "审阅整组回复" });
    await review.waitFor();
    assert.equal(batches.length, 0, "opening review never delivers");
    await review.getByRole("button", { name: "确认发送整组", exact: true }).click();
    await page.waitForFunction(() => !!document.querySelector(".reply-review-result"));
    assert.deepEqual(batches[0].body, { trigger_message_id: "buyer-1", parts: [{ kind: "text", content: "Edited latest status." }, { kind: "text", content: "Returns are accepted within 30 days." }, { kind: "logistics_card", order_id: "order-1", package_id: "package-1" }], preview_only: false, confirmed: true });
    assert.ok(batches[0].key);
    assert.deepEqual(await panel.locator("[data-reply-kind]").evaluateAll((nodes) => nodes.map((node) => node.dataset.replyKind)), ["text", "text", "logistics_card"]);
  } finally { await context.close(); }
});

test("failed review clears unverified text and never calls a batch", async () => {
  const { context, page, emit, batches } = await openReview();
  try {
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await emit("draft", { part_index: 0, text: "Private draft", replace: true, unverified: true, sendable: false, trigger_message_id: "buyer-1" });
    await emit("error", { message: "Safety review failed" });
    await emit("done", { reason: "completed" });
    await page.getByText("Safety review failed", { exact: true }).waitFor();
    assert.equal(await page.getByText("Private draft", { exact: true }).count(), 0);
    assert.equal(await page.getByRole("textbox", { name: "回复内容", exact: true }).inputValue(), "");
    assert.equal(batches.length, 0);
  } finally { await context.close(); }
});

test("an operator edit during generation survives the late verified result", async () => {
  const { context, page, finish } = await openReview();
  try {
    await page.getByRole("button", { name: "生成", exact: true }).click();
    const composer = page.getByRole("textbox", { name: "回复内容", exact: true });
    await composer.fill("人工正在编辑");
    await finish(["您的包裹今天已送达。"]);
    await page.getByRole("region", { name: "回复审阅" }).getByText("您的包裹今天已送达。", { exact: true }).waitFor();
    assert.equal(await composer.inputValue(), "人工正在编辑");
  } finally { await context.close(); }
});

test("cancelled and cross-conversation late results never replace an operator draft", async () => {
  const { context, page, emit, finish } = await openReview();
  try {
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await emit("draft", { part_index: 0, text: "Unverified", replace: true, unverified: true, sendable: false, trigger_message_id: "buyer-1" });
    await page.getByRole("button", { name: "取消", exact: true }).click();
    await finish(["Late after cancel"]);
    assert.equal(await page.getByText("Late after cancel", { exact: true }).count(), 0);
    assert.equal(await page.getByLabel("未复核生成草稿").count(), 0);
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await page.locator(".conversation-card").filter({ hasText: "Bob" }).click();
    await page.getByRole("heading", { name: "Bob", exact: true }).first().waitFor();
    await page.getByRole("textbox", { name: "回复内容", exact: true }).fill("Bob draft");
    await finish(["Late for Alice"]);
    assert.equal(await page.getByRole("textbox", { name: "回复内容", exact: true }).inputValue(), "Bob draft");
    assert.equal(await page.getByText("Late for Alice", { exact: true }).count(), 0);
  } finally { await context.close(); }
});

test("completed without a usable result reports review required and clears every draft", async () => {
  const { context, page, emit } = await openReview();
  try {
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await emit("draft", { part_index: 0, text: "Discard me", replace: true, unverified: true, sendable: false, trigger_message_id: "buyer-1" });
    await emit("result", { content: null, reply_parts: [], reason_codes: ["privacy_review_failed"], trigger_message_id: "buyer-1" });
    await emit("done", { reason: "completed" });
    await page.getByText(/未生成可用回复.*隐私复核未通过/).waitFor();
    assert.equal(await page.getByText("Discard me", { exact: true }).count(), 0);
    assert.equal(await page.getByRole("button", { name: "审阅整组发送", exact: true }).count(), 0);
    assert.equal(await page.getByRole("textbox", { name: "回复内容", exact: true }).inputValue(), "");
  } finally { await context.close(); }
});

test("logistics preview failure preserves verified text and can retry the card alone", async () => {
  const { context, page, finish, state, batches } = await openReview();
  try {
    state.cardFailure = true;
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await finish(["Your parcel arrived today."], ["order-1"]);
    const panel = page.getByRole("region", { name: "回复审阅" });
    await panel.getByRole("alert").filter({ hasText: "Card temporarily unavailable" }).waitFor();
    assert.equal(await page.getByRole("textbox", { name: "回复内容", exact: true }).inputValue(), "Your parcel arrived today.");
    assert.equal(await panel.getByRole("button", { name: "审阅整组发送", exact: true }).isDisabled(), true);
    state.cardFailure = false;
    await panel.getByRole("button", { name: "重试卡片预览", exact: true }).click();
    await panel.getByLabel("物流卡片", { exact: true }).waitFor();
    assert.equal(await panel.getByRole("button", { name: "审阅整组发送", exact: true }).isEnabled(), true);
    assert.equal(batches.length, 0);
  } finally { await context.close(); }
});

test("a failed card retry preserves the immutable confirmed plan and idempotency key", async () => {
  const { context, page, finish, state, batches } = await openReview();
  try {
    state.batchStatus = "partial";
    state.batchParts = [{ index: 0, kind: "text", status: "sent", message_id: "text-1", error_code: null }, { index: 1, kind: "logistics_card", status: "failed", message_id: null, error_code: "PLATFORM_REJECTED" }];
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await finish(["Your parcel arrived today."], ["order-1"]);
    const panel = page.getByRole("region", { name: "回复审阅" });
    await panel.getByLabel("物流卡片", { exact: true }).waitFor();
    await panel.getByRole("button", { name: "审阅整组发送", exact: true }).click();
    assert.equal(batches.length, 0, "opening review must not deliver");
    await page.getByRole("dialog", { name: "审阅整组回复" }).getByRole("button", { name: "确认发送整组", exact: true }).click();
    await panel.getByRole("button", { name: "仅重试失败卡片", exact: true }).waitFor();
    assert.equal(batches[0].body.confirmed, true);
    assert.equal(batches[0].body.preview_only, false);
    assert.ok(batches[0].key);
    state.batchStatus = "completed";
    state.batchParts = state.batchParts.map((part) => ({ ...part, status: "sent", error_code: null }));
    await page.getByRole("textbox", { name: "回复内容", exact: true }).fill("New unrelated edit");
    assert.equal(await panel.locator("[data-reply-kind=text]").innerText().then((text) => text.includes("New unrelated edit")), false, "a confirmed delivery must keep displaying its immutable text");
    await panel.getByRole("button", { name: "仅重试失败卡片", exact: true }).click();
    await panel.getByText("交付完成", { exact: true }).waitFor();
    assert.deepEqual(batches[1], batches[0], "retry must resume the same immutable plan; the server skips sent text");
  } finally { await context.close(); }
});

for (const status of ["unknown", "failed"]) test(`${status} text delivery offers no card retry or duplicate send`, async () => {
  const { context, page, finish, state } = await openReview();
  try {
    state.batchStatus = status;
    state.batchParts = [{ index: 0, kind: "text", status, message_id: null, error_code: "TEXT_RESULT" }, { index: 1, kind: "logistics_card", status: "failed", message_id: null, error_code: "BLOCKED" }];
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await finish(["Your parcel arrived today."], ["order-1"]);
    const panel = page.getByRole("region", { name: "回复审阅" });
    await panel.getByLabel("物流卡片", { exact: true }).waitFor();
    await panel.getByRole("button", { name: "审阅整组发送", exact: true }).click();
    await page.getByRole("dialog", { name: "审阅整组回复" }).getByRole("button", { name: "确认发送整组", exact: true }).click();
    await panel.getByRole("status").filter({ hasText: status === "unknown" ? "交付结果未知" : "交付失败" }).waitFor();
    assert.equal(await panel.getByRole("button", { name: "仅重试失败卡片", exact: true }).count(), 0);
    assert.equal(await panel.getByRole("button", { name: "审阅整组发送", exact: true }).isDisabled(), true);
  } finally { await context.close(); }
});

test("one Chinese question stays a single short reply without a logistics card", async () => {
  const { context, page, finish, batches } = await openReview();
  try {
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await finish(["您的包裹今天已送达。"]);
    const panel = page.getByRole("region", { name: "回复审阅" });
    await panel.getByText("您的包裹今天已送达。", { exact: true }).waitFor();
    assert.equal(await panel.locator("[data-reply-kind=text]").count(), 1);
    assert.equal(await panel.getByLabel("物流卡片", { exact: true }).count(), 0);
    await panel.getByRole("button", { name: "审阅整组发送", exact: true }).click();
    const review = page.getByRole("dialog", { name: "审阅整组回复" });
    await review.waitFor();
    assert.equal(batches.length, 0, "opening review never delivers");
    await review.getByRole("button", { name: "确认发送整组", exact: true }).click();
    await page.waitForFunction(() => !!document.querySelector(".reply-review-result"));
    assert.deepEqual(batches[0].body.parts, [{ kind: "text", content: "您的包裹今天已送达。" }]);
  } finally { await context.close(); }
});

test("the total delivery budget includes native card references after text", async () => {
  const { context, page, finish } = await openReview();
  try {
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await finish(Array.from({ length: 8 }, () => "R".repeat(2000)), ["order-1"]);
    const panel = page.getByRole("region", { name: "回复审阅" });
    await panel.getByLabel("物流卡片", { exact: true }).waitFor();
    assert.equal(await panel.getByRole("button", { name: "审阅整组发送", exact: true }).isDisabled(), true);
  } finally { await context.close(); }
});

test("batch review keeps keyboard focus inside and Escape cancels without delivery", async () => {
  const { context, page, finish, batches } = await openReview();
  try {
    await page.getByRole("button", { name: "生成", exact: true }).click();
    await finish(["Your parcel arrived today."]);
    await page.getByRole("button", { name: "审阅整组发送", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "审阅整组回复", exact: true });
    await dialog.waitFor();
    await page.keyboard.press("Tab");
    assert.equal(await dialog.evaluate((node) => node.contains(document.activeElement)), true);
    await page.keyboard.press("Escape");
    await dialog.waitFor({ state: "hidden", timeout: 1500 });
    assert.equal(batches.length, 0);
  } finally { await context.close(); }
});
