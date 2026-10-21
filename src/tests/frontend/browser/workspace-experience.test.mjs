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

async function openWorkspace(messageCount = 70, orderStatus = "IN_TRANSIT", conversationCount = 2, latestTrackingDescription = null, orderDetailDelay = 0) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const records = [
    { id: firstId, store_id: storeId, platform: "tiktok", status: "active", is_starred: false, closed_at: null, unread_count: 2, assigned_user_id: null, last_message_at: "2026-10-20T10:00:00Z", last_message: "Latest message", customer: { id: "00000000-0000-4000-8000-000000000401", name: "Alice", email: null, avatar: null, tags: [] } },
    { id: secondId, store_id: storeId, platform: "tiktok", status: "active", is_starred: false, closed_at: null, unread_count: 3, assigned_user_id: null, last_message_at: "2026-10-20T09:00:00Z", last_message: "Another message", customer: { id: "00000000-0000-4000-8000-000000000402", name: "Bob", email: null, avatar: null, tags: [] } },
  ];
  for (let index = 2; index < conversationCount; index++) records.push({ ...records[1], id: `00000000-0000-4000-8000-${String(index + 101).padStart(12, "0")}`, unread_count: 0, customer: { ...records[1].customer, name: `Customer ${index}` } });
  const messages = Array.from({ length: messageCount }, (_, index) => ({ id: `message-${index}`, role: index % 2 ? "agent" : "user", content: `Message ${index}`, status: "received", created_at: new Date(Date.UTC(2026, 9, 20, 0, index)).toISOString(), error_code: null, delivery_mode: "inbound" }));
  const calls = { send: 0, sendFailures: 0, sentContent: [], transfer: 0, translation: 0, translationDelay: 0, searchQueries: [], sidebarQueries: [], productDetails: 0, orderDetails: 0 };
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
    else if ((path === "/v1/workspace/sessions" && method === "GET") || (path === "/v1/workspace/sessions/search" && method === "POST")) {
      const payload = method === "POST" ? JSON.parse(request.postData()) : null;
      const filter = payload?.filter ?? url.searchParams.get("filter");
      if (payload) calls.searchQueries.push(payload);
      const scope = payload?.search_scope ?? "all";
      const terms = payload?.terms?.length ? payload.terms : [payload?.q].filter(Boolean);
      const searchable = { [firstId]: { buyer: "Alice", order: "ORDER-ALICE", tracking: "TRACK-A", product: "Walking pad" }, [secondId]: { buyer: "Bob", order: "ORDER-BOB", tracking: "TRACK-B", product: "Treadmill" } };
      const matches = (item) => !terms.length || terms.some((term) => {
        const fields = searchable[item.id] ?? { buyer: item.customer.name, order: "", tracking: "", product: "" };
        return (scope === "all" ? Object.values(fields) : [fields[scope]]).some((value) => value.toLowerCase().includes(term.toLowerCase()));
      });
      const items = records.filter((item) => (filter === "closed" ? item.status === "closed" : item.status !== "closed" && (filter !== "starred" || item.is_starred)) && matches(item));
      const pageNumber = Number(payload?.page ?? url.searchParams.get("page") ?? 1);
      data = { items: items.slice((pageNumber - 1) * 30, pageNumber * 30), unread_messages_total: records.filter((item) => item.status !== "closed").reduce((sum, item) => sum + item.unread_count, 0), pagination: { page: pageNumber, page_size: 30, total: items.length } };
    } else if (path.endsWith("/messages") && method === "GET") {
      const record = records.find((item) => path.includes(item.id));
      const page = Number(url.searchParams.get("page") ?? "1");
      data = { session: record, customer: record.customer, messages: messages.slice((page - 1) * 100, page * 100), recent_orders: [], ai_suggestion: null, pagination: { page, page_size: 100, total: messages.length }, send_mode: record.status === "closed" ? "disabled" : "real", requires_confirmation: true, translation_enabled: false, draft_translation_enabled: record.status !== "closed" };
    } else if (path.endsWith("/sidebar/search") && method === "POST") {
      const payload = JSON.parse(request.postData());
      calls.sidebarQueries.push(payload);
      const order = { id: "order-1", external_order_id: "577600000000000001", status: orderStatus, payment_status: orderStatus === "UNPAID" ? null : "paid", currency: "USD", total_amount: "97.90", payment_breakdown: { sub_total: "90.45", tax: "7.45" }, ordered_at: "2026-10-15T07:11:00Z", paid_at: orderStatus === "UNPAID" ? null : "2026-10-15T07:12:00Z", tracking_number: "878696895644", tracking_status: null, live_detail_available: true, items: [{ name: "Walking pad", product_id: "123", sku: "PAD-BLK", sku_id: "456", sku_name: "Black with handrail", image_url: null, quantity: 1, unit_price: "90.45", total_amount: "90.45" }] };
      const product = { id: "123", title: "Walking pad", status: "ACTIVATE", image_url: null, skus: [{ id: "456", seller_sku: "PAD-BLK", name: null, currency: "USD", sale_price: "90.45", quantity: 4 }] };
      const coupon = { id: "789", title: "Shop coupon", status: "EXPIRED", display_type: "REGULAR", promo_code: "SAVE5", discount_type: "AMOUNT_OFF", discount_value: "$5.00", claim_end_time: null, chat_shareable: false };
      if (payload.section === "orders") {
        const category = { UNPAID: "unpaid", AWAITING_SHIPMENT: "ship", IN_TRANSIT: "transit", DELIVERED: "done", CANCELLED: "cancel" }[orderStatus];
        data = { items: (payload.status === "all" || payload.status === category) && (!payload.query || [order.external_order_id, order.tracking_number, order.items[0].name, order.items[0].sku, order.items[0].sku_id, order.items[0].product_id].some((value) => value?.toLowerCase().includes(payload.query.toLowerCase()))) ? [order] : [], pagination: { page: payload.page, page_size: 20, total: 1 } };
      }
      else if (payload.section === "products") data = { items: !payload.query || product.title.toLowerCase().includes(payload.query.toLowerCase()) ? [product] : [], next_page_token: null, total_count: 1, partial_search: false };
      else data = { items: !payload.query || coupon.title.toLowerCase().includes(payload.query.toLowerCase()) || coupon.promo_code.toLowerCase().includes(payload.query.toLowerCase()) ? [coupon] : [], next_page_token: null, total_count: 1, partial_search: false };
    } else if (path.endsWith("/sidebar/orders/detail") && method === "POST") {
      calls.orderDetails++;
      assert.deepEqual(JSON.parse(request.postData()), { order_id: "577600000000000001" });
      if (orderDetailDelay) await new Promise((resolve) => setTimeout(resolve, orderDetailDelay));
      data = { payment_method_name: "Card", shipping_provider: "Carrier A", latest_tracking_description: latestTrackingDescription ?? (orderStatus === "COMPLETED" ? "Delivered" : "Package dispatched"), latest_tracking_at: "2026-10-16T23:26:48Z" };
    } else if (path.endsWith("/sidebar/products/123") && method === "GET") {
      calls.productDetails++;
      data = { id: "123", title: "Walking pad", status: "ACTIVATE", image_url: "https://example.invalid/product.png", skus: [{ id: "456", seller_sku: "PAD-BLK", name: "Black with handrail", currency: "USD", sale_price: "90.45", quantity: 4 }] };
    } else if (path.endsWith("/draft/translation") && method === "POST") {
      calls.translation++;
      if (calls.translationDelay) await new Promise((resolve) => setTimeout(resolve, calls.translationDelay));
      const payload = JSON.parse(request.postData());
      data = { source_text_sha256: "a".repeat(64), target_language: payload.target_language, translated_text: `Translated: ${payload.source_text}` };
    } else if (path.endsWith("/read")) { records.find((item) => path.includes(item.id)).unread_count = 0; data = { unread_count: 0 }; }
    else if (path.endsWith("/star")) { const record = records.find((item) => path.includes(item.id)); record.is_starred = JSON.parse(request.postData()).starred; data = { status: record.status, is_starred: record.is_starred, closed_at: record.closed_at }; }
    else if (path.endsWith("/closed")) { const record = records.find((item) => path.includes(item.id)); record.status = JSON.parse(request.postData()).closed ? "closed" : "active"; data = { status: record.status, is_starred: record.is_starred, closed_at: record.status === "closed" ? "2026-10-20T11:00:00Z" : null }; }
    else if (path.endsWith("/assignees")) data = [{ id: assigneeId, name: "Agent A" }];
    else if (path.endsWith("/transfer")) { calls.transfer++; const record = records.find((item) => path.includes(item.id)); record.status = "transferred"; record.assigned_user_id = JSON.parse(request.postData()).assign_to; data = { status: "transferred", transfer_id: "00000000-0000-4000-8000-000000000501" }; }
    else if (path.endsWith("/messages") && method === "POST") {
      calls.send++;
      calls.sentContent.push(JSON.parse(request.postData()).content);
      if (calls.sendFailures-- > 0) return route.fulfill({ status: 503, contentType: "application/json", headers, body: JSON.stringify({ code: 503, message: "temporary failure", data: null }) });
      data = messages.at(-1);
    }
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
    await page.waitForFunction(() => document.querySelector('[aria-label="新消息总数"]')?.textContent === "3");
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

test("scrolling to the end automatically loads the next conversation page", async () => {
  const { context, page } = await openWorkspace(2, "IN_TRANSIT", 35);
  try {
    await page.waitForFunction(() => document.querySelectorAll(".conversation-card").length === 30);
    await page.locator(".conversation-scroll").evaluate((node) => { node.scrollTop = node.scrollHeight; node.dispatchEvent(new Event("scroll", { bubbles: true })); });
    await page.waitForFunction(() => document.querySelectorAll(".conversation-card").length === 35);
    assert.equal(await page.getByRole("button", { name: "加载更多会话" }).count(), 0);
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
    await draft.fill("Earlier draft");
    await page.getByRole("button", { name: "刷新", exact: true }).click();
    await page.waitForFunction(() => document.querySelector('textarea[aria-label="回复内容"]')?.value === "AI draft ready");
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

test("single and multiple search terms share one input", async () => {
  const { context, page, calls } = await openWorkspace(2);
  try {
    await page.getByRole("combobox", { name: "搜索范围" }).selectOption("order");
    await page.getByRole("textbox", { name: "搜索会话" }).fill("ORDER-BOB");
    await page.waitForFunction(() => document.querySelectorAll(".conversation-card").length === 1);
    assert.equal(await page.locator(".conversation-card").count(), 1);
    assert.ok(calls.searchQueries.some((query) => query.search_scope === "order" && query.q === "ORDER-BOB"));
    assert.equal(await page.getByRole("button", { name: "批量搜索会话" }).count(), 0);
    await page.getByRole("textbox", { name: "搜索会话" }).fill("Alice,Bob,Walking pad");
    await page.getByText("3 个关键词 · 2 个会话").waitFor();
    assert.equal(await page.locator(".conversation-card").count(), 2);
    assert.ok(calls.searchQueries.some((query) => query.terms.includes("Alice") && query.terms.includes("Bob")));
  } finally { await context.close(); }
});

test("translation preview never sends and edit invalidates the reviewed translation", async () => {
  const { context, page, calls } = await openWorkspace(2);
  try {
    const draft = page.getByRole("textbox", { name: "回复内容" });
    await draft.fill("你好，欢迎光临");
    await page.getByRole("button", { name: "翻译", exact: true }).click();
    await page.getByLabel("译文预览").getByText("Translated: 你好，欢迎光临").waitFor();
    assert.equal(calls.send, 0);
    await draft.fill("你好，请问有什么需要？");
    await page.getByLabel("译文预览").waitFor({ state: "hidden" });
    await page.getByRole("button", { name: "翻译后发送", exact: true }).click();
    const review = page.getByRole("dialog", { name: "审阅外发消息" });
    await review.getByText("Translated: 你好，请问有什么需要？").waitFor();
    assert.equal(calls.send, 0);
    await review.getByRole("button", { name: "确认并发送" }).click();
    await page.waitForFunction(() => document.querySelector('textarea[aria-label="回复内容"]')?.value === "");
    assert.deepEqual(calls.sentContent, ["Translated: 你好，请问有什么需要？"]);
    assert.equal(calls.translation, 2);
  } finally { await context.close(); }
});

test("language and send menus keep direct text separate from translated review", async () => {
  const { context, page, calls } = await openWorkspace(2);
  try {
    const draft = page.getByRole("textbox", { name: "回复内容" });
    await draft.fill("您好，包裹已发出");
    await page.getByRole("button", { name: "目标语言" }).click();
    await page.getByRole("menuitem", { name: "更多" }).click();
    const languageMenu = page.getByRole("menu", { name: "目标语言选项" });
    assert.equal(await languageMenu.getByRole("menuitemradio").count(), 13);
    await languageMenu.getByRole("menuitemradio", { name: "越南语" }).click();
    assert.match(await page.getByRole("button", { name: "目标语言" }).textContent(), /越南语/);
    await page.getByRole("button", { name: "选择发送方式" }).click();
    await page.getByRole("menuitemradio", { name: "直接发送" }).click();
    await draft.press("Enter");
    const review = page.getByRole("dialog", { name: "审阅外发消息" });
    await review.getByText("您好，包裹已发出").waitFor();
    assert.equal(calls.translation, 0);
    assert.equal(calls.send, 0);
    await review.getByRole("button", { name: "返回修改" }).click();
    await page.getByRole("button", { name: "选择发送方式" }).click();
    await page.getByRole("menuitemradio", { name: "翻译后发送" }).click();
    await page.getByRole("button", { name: "翻译后发送", exact: true }).click();
    await review.getByText("Translated: 您好，包裹已发出").waitFor();
    await review.getByText("目标语言：越南语").waitFor();
    assert.equal(calls.translation, 1);
    assert.equal(calls.send, 0);
  } finally { await context.close(); }
});

test("composer keeps the count separate and opens more languages beside the short menu", async () => {
  const { context, page } = await openWorkspace(2);
  try {
    assert.equal((await page.locator(".workspace-composer-count").textContent()).trim(), "0/2000");
    await page.getByRole("button", { name: "目标语言" }).click();
    const menu = page.getByRole("menu", { name: "目标语言选项" });
    await menu.getByRole("menuitem", { name: "更多" }).click();
    const more = page.getByRole("menu", { name: "更多目标语言" });
    const menuBox = await menu.boundingBox();
    const moreBox = await more.boundingBox();
    assert.ok(menuBox && moreBox);
    assert.ok(moreBox.x >= menuBox.x + menuBox.width - 2, "language submenu should open beside the short menu");
    assert.ok(moreBox.x + moreBox.width <= 1440, "language submenu should stay in the viewport");
    assert.ok(moreBox.y >= 0, "language submenu should not extend above the viewport");
    await page.setViewportSize({ width: 375, height: 900 });
    await menu.getByRole("menuitem", { name: "更多" }).click();
    await menu.getByRole("menuitem", { name: "更多" }).click();
    const mobileMoreBox = await more.boundingBox();
    assert.ok(mobileMoreBox);
    assert.ok(mobileMoreBox.x >= 0 && mobileMoreBox.x + mobileMoreBox.width <= 375, "language submenu should stay visible on mobile");
  } finally { await context.close(); }
});

test("late translation response cannot restore a preview after the draft changed", async () => {
  const { context, page, calls } = await openWorkspace(2);
  try {
    calls.translationDelay = 450;
    const draft = page.getByRole("textbox", { name: "回复内容" });
    await draft.fill("旧草稿");
    await page.getByRole("button", { name: "翻译", exact: true }).click();
    await draft.fill("新草稿");
    await page.waitForTimeout(650);
    assert.equal(await page.getByLabel("译文预览").count(), 0);
    assert.equal(calls.send, 0);
  } finally { await context.close(); }
});

test("changing send mode while translating cannot open an outdated review", async () => {
  const { context, page, calls } = await openWorkspace(2);
  try {
    calls.translationDelay = 450;
    await page.getByRole("textbox", { name: "回复内容" }).fill("你好");
    await page.getByRole("button", { name: "翻译后发送", exact: true }).click();
    await page.getByRole("button", { name: "选择发送方式" }).click();
    await page.getByRole("menuitemradio", { name: "直接发送" }).click();
    await page.waitForTimeout(650);
    assert.equal(await page.getByRole("dialog", { name: "审阅外发消息" }).count(), 0);
    assert.equal(calls.send, 0);
    await page.getByRole("button", { name: "直接发送" }).click();
    await page.getByRole("dialog", { name: "审阅外发消息" }).getByText("你好").waitFor();
    assert.equal(calls.send, 0);
  } finally { await context.close(); }
});

test("an interrupted send retry stays bound to its original conversation", async () => {
  const { context, page, calls } = await openWorkspace(2);
  try {
    calls.sendFailures = 1;
    await page.getByRole("textbox", { name: "回复内容" }).fill("Alice's message");
    await page.getByRole("button", { name: "选择发送方式" }).click();
    await page.getByRole("menuitemradio", { name: "直接发送" }).click();
    await page.getByRole("button", { name: "直接发送" }).click();
    await page.getByRole("dialog", { name: "审阅外发消息" }).getByRole("button", { name: "确认并发送" }).click();
    await page.getByRole("button", { name: "请求中断，审阅原内容后重试" }).waitFor();
    await page.getByRole("button", { name: /Bob/ }).click();
    await page.getByRole("heading", { name: "Bob" }).first().waitFor();
    assert.equal(await page.getByRole("button", { name: "请求中断，审阅原内容后重试" }).count(), 0);
    assert.equal(calls.send, 1);
    await page.getByRole("button", { name: /Alice/ }).click();
    await page.getByRole("button", { name: "请求中断，审阅原内容后重试" }).click();
    await page.getByRole("dialog", { name: "审阅外发消息" }).getByText(/收件人：Alice/).waitFor();
    assert.equal(calls.send, 1);
  } finally { await context.close(); }
});

test("visible customer order card loads six real payment and logistics rows without a detail click", async () => {
  const { context, page, calls } = await openWorkspace(2);
  try {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    const card = page.getByTestId("customer-order-card");
    await card.getByText("577600000000000001").waitFor();
    assert.equal(await card.getByRole("button", { name: "复制订单编号" }).count(), 1);
    assert.equal(await card.getByRole("button", { name: "复制商品规格" }).count(), 1);
    assert.equal(await card.getByRole("button", { name: "复制SKU", exact: true }).count(), 1);
    await card.getByRole("button", { name: "复制订单编号" }).click();
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), "577600000000000001");
    await card.getByText("商品规格：").waitFor();
    await card.getByText("Carrier A").waitFor();
    await card.getByText("买家实付金额").first().waitFor();
    await card.getByText("物流状态").waitFor();
    await card.locator(".customer-info-line").filter({ hasText: "物流状态" }).getByText("运送中").waitFor();
    await card.getByText("物流单号").waitFor();
    await card.getByText("878696895644").waitFor();
    await card.getByText("最新物流描述").waitFor();
    await card.getByText("最新物流时间").waitFor();
    assert.equal(await card.getByText("Card").count(), 1);
    assert.equal(await card.getByText("Package dispatched").count(), 1);
    assert.equal(calls.orderDetails, 1);
    assert.equal(calls.send, 0);
  } finally { await context.close(); }
});

test("order card reveals payment and logistics fields together after detail arrives", async () => {
  const { context, page } = await openWorkspace(2, "IN_TRANSIT", 2, null, 400);
  try {
    const card = page.getByTestId("customer-order-card");
    await card.getByText("正在读取订单详情…").waitFor();
    assert.equal(await card.getByText("付款时间").count(), 0);
    assert.equal(await card.getByText("物流单号").count(), 0);
    await card.getByText("付款时间").waitFor();
    await card.getByText("物流单号").waitFor();
    await card.getByText("Card").waitFor();
  } finally { await context.close(); }
});

test("customer order states show their own fields and leave unavailable facts blank", async () => {
  for (const [state, expected, missing, logisticsLabel] of [
    ["UNPAID", "付款截止", "物流状态", null],
    ["AWAITING_SHIPMENT", "最晚发货", "物流状态", null],
    ["DELIVERED", "物流状态", "取消原因", "已送达"],
    ["COMPLETED", "物流状态", "取消原因", "Delivered"],
    ["CANCELLED", "取消原因", "物流状态", null],
  ]) {
    const { context, page } = await openWorkspace(2, state);
    try {
      const card = page.getByTestId("customer-order-card");
      await card.getByText(expected).waitFor();
      assert.equal(await card.getByText(missing).count(), 0);
      if (logisticsLabel) await card.locator(".customer-info-line").filter({ hasText: "物流状态" }).getByText(logisticsLabel).waitFor();
    } finally { await context.close(); }
  }
});

test("completed order shows the latest platform tracking text without inventing a stage", async () => {
  const { context, page } = await openWorkspace(2, "COMPLETED", 2, "Carrier custom event");
  try {
    const card = page.getByTestId("customer-order-card");
    await card.locator(".customer-info-line").filter({ hasText: "物流状态" }).getByText("Carrier custom event").waitFor();
  } finally { await context.close(); }
});

test("customer sidebar filters real order projections and keeps amount rows tied to returned data", async () => {
  const { context, page, calls } = await openWorkspace(2);
  try {
    const card = page.getByTestId("customer-order-card");
    await card.getByText("577600000000000001").waitFor();
    await page.getByRole("button", { name: "运送中" }).click();
    await page.getByLabel("搜索字段").selectOption("tracking");
    await page.getByLabel("客户信息搜索").fill("878696895644");
    await page.getByRole("button", { name: "搜索", exact: true }).click();
    await card.getByText("878696895644").waitFor();
    await card.locator("summary").click();
    await card.getByText("商品小计").waitFor();
    if (process.env.CAPTURE_SIDEBAR) await page.screenshot({ path: `${process.env.CAPTURE_SIDEBAR}/orders.png`, fullPage: true });
    assert.equal(calls.sidebarQueries.at(-1).field, "tracking");
    assert.equal(calls.sidebarQueries.at(-1).query, "878696895644");
    assert.equal(new URL(page.url()).searchParams.has("query"), false);
    assert.equal(calls.send, 0);
  } finally { await context.close(); }
});

test("product and coupon tabs load shop data, expand SKU, and only fill an editable draft", async () => {
  const { context, page, calls } = await openWorkspace(2);
  try {
    await page.getByRole("tab", { name: "商品" }).click();
    const product = page.getByTestId("customer-product-card");
    await product.getByText("Walking pad").waitFor();
    await product.getByText("上架中").waitFor();
    await product.locator("img.customer-product-image").waitFor();
    await page.getByLabel("搜索字段").selectOption("name");
    await page.getByLabel("客户信息搜索").fill("Walking");
    await page.getByRole("button", { name: "搜索", exact: true }).click();
    await product.getByText("Walking pad").waitFor();
    await product.locator("summary").click();
    await product.getByText("Black with handrail").waitFor();
    if (process.env.CAPTURE_SIDEBAR) await page.screenshot({ path: `${process.env.CAPTURE_SIDEBAR}/products.png`, fullPage: true });
    assert.equal(calls.productDetails, 2);
    assert.equal(await product.getByRole("button", { name: "复制商品规格" }).count(), 1);
    assert.equal(await product.getByRole("button", { name: "复制SKU 货号" }).count(), 1);
    await product.getByRole("button", { name: "填入回复草稿" }).click();
    assert.match(await page.getByRole("textbox", { name: "回复内容" }).inputValue(), /Walking pad/);
    assert.equal(calls.send, 0);

    await page.getByRole("tab", { name: "优惠券" }).click();
    const coupon = page.getByTestId("customer-coupon-card");
    await coupon.getByText("Shop coupon").waitFor();
    await coupon.getByText("已过期").waitFor();
    await coupon.getByText("立减 $5.00").waitFor();
    await coupon.getByText("常规展示").waitFor();
    await page.getByLabel("搜索字段").selectOption("code");
    await page.getByLabel("客户信息搜索").fill("SAVE5");
    await page.getByRole("button", { name: "搜索", exact: true }).click();
    await coupon.getByText("SAVE5").waitFor();
    if (process.env.CAPTURE_SIDEBAR) await page.screenshot({ path: `${process.env.CAPTURE_SIDEBAR}/coupons.png`, fullPage: true });
    await coupon.getByRole("button", { name: "填入回复草稿" }).click();
    assert.match(await page.getByRole("textbox", { name: "回复内容" }).inputValue(), /SAVE5/);
    assert.equal(calls.send, 0);
  } finally { await context.close(); }
});

test("scrolling the product catalog to the bottom loads its next page", async () => {
  const { context, page } = await openWorkspace(2);
  try {
    const image = "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=";
    const makeProduct = (id) => ({ id: String(id), title: `Product ${id}`, status: "ACTIVATE", image_url: image, skus: [] });
    const productQueries = [];
    await page.route("**/v1/workspace/sessions/*/sidebar/search", async (route) => {
      const payload = JSON.parse(route.request().postData());
      if (payload.section !== "products") return route.fallback();
      productQueries.push(payload);
      const data = payload.page_token
        ? { items: [makeProduct(2000)], next_page_token: null, total_count: 13, partial_search: false }
        : { items: Array.from({ length: 12 }, (_, index) => makeProduct(1000 + index)), next_page_token: "next-1", total_count: 13, partial_search: false };
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) });
    });
    await page.getByRole("tab", { name: "商品" }).click();
    await page.waitForFunction(() => document.querySelectorAll(".customer-product-card").length === 12);
    await page.locator(".customer-side-body").evaluate((node) => { node.scrollTop = node.scrollHeight; node.dispatchEvent(new Event("scroll", { bubbles: true })); });
    await page.getByText("Product 2000").waitFor();
    assert.equal(productQueries.filter((query) => query.page_token === "next-1").length, 1);
    assert.equal(await page.getByRole("button", { name: "加载更多商品" }).count(), 0);
  } finally { await context.close(); }
});
