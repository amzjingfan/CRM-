import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { after, before, test } from "node:test";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");

const baseUrl = process.env.UI_BASE_URL ?? "http://127.0.0.1:3101";
const target = new URL(baseUrl);
if (!["127.0.0.1", "localhost", "::1"].includes(target.hostname)) {
  throw new Error("UI regression tests only run against a local server");
}
const origin = target.origin;
const user = {
  id: "00000000-0000-4000-8000-000000000001",
  name: "Test Admin",
  email: "admin@example.invalid",
  role: "admin",
  avatar: null,
  permissions: ["marketing.manage"],
  store_ids: [],
};
const store = {
  id: "00000000-0000-4000-8000-0000000000f1",
  name: "US Demo Store",
  code: "us_demo",
  status: "active",
  timezone: "America/Los_Angeles",
  currency: "USD",
  created_at: "2026-09-01T00:00:00Z",
};
const storeChannel = {
  id: "00000000-0000-4000-8000-0000000000c1",
  store_id: store.id,
  platform: "tiktok",
  external_store_id: "7494319122518476618",
  display_name: store.name,
  status: "connected",
  scopes: [],
  last_sync_at: null,
  created_at: "2026-09-01T00:00:00Z",
  site: "US",
  authorization_expires_at: "2125-01-21T14:12:11Z",
  authorization_status: null,
  last_authorized_at: "2026-10-22T00:00:00Z",
};
const agent = {
  id: "00000000-0000-4000-8000-0000000000a1",
  store_id: store.id,
  name: "Service Agent",
  code: "service_agent",
  description: null,
  status: "enabled",
  enabled_tools: [],
  knowledge_scope: {},
  runtime: {
    available: true,
    llm_provider: "deepseek",
    llm_model: "test-model",
    embedding_provider: "local_bge",
    embedding_model: "BAAI/bge-m3",
    reranker_model: "test-reranker",
    prompt_versions: {},
    auto_reply_threshold: 0.85,
    human_review_threshold: 0.5,
    token_streaming: false,
  },
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
};

let browser;

before(async () => {
  browser = await chromium.launch({ channel: "chrome", headless: true });
});

after(async () => {
  await browser?.close();
});

async function openPage(path, responses = {}, setup = async () => {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.route("**/v1/**", async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    const headers = {
      "access-control-allow-origin": origin,
      "access-control-allow-credentials": "true",
      "access-control-allow-methods": "GET,POST,PATCH,DELETE,OPTIONS",
      "access-control-allow-headers": "content-type,idempotency-key,x-csrf-token",
    };
    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers });
      return;
    }
    const response = responses[`${request.method()} ${pathname}`] ??
      (pathname.endsWith("/sidebar/search")
        ? { items: [], pagination: { page: 1, page_size: 20, total: 0 } }
        : pathname === "/v1/auth/me" ? user : []);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers,
      body: JSON.stringify({ code: 0, message: "ok", data: response }),
    });
  });
  await setup(context);
  const page = await context.newPage();
  await page.goto(`${baseUrl}${path}`);
  await page.getByRole("link", { name: "数据看板" }).waitFor();
  return { context, page };
}

test("knowledge with no authorized store offers store setup instead of loading forever", async () => {
  const { context, page } = await openPage("/knowledge");
  try {
    await page.getByRole("link", { name: "创建店铺" }).waitFor({ state: "visible", timeout: 5000 });
    assert.equal(await page.getByRole("status", { name: /加载中/ }).count(), 0);
  } finally {
    await context.close();
  }
});

test("marketing with no authorized store offers store setup instead of loading forever", async () => {
  const { context, page } = await openPage("/marketing");
  try {
    await page.getByRole("link", { name: "创建店铺" }).waitFor({ state: "visible", timeout: 5000 });
    assert.equal(await page.getByText(/正在加载营销流程/).count(), 0);
  } finally {
    await context.close();
  }
});

test("stale store URL cannot bypass knowledge and marketing setup guidance", async () => {
  for (const path of ["/knowledge", "/marketing"]) {
    const { context, page } = await openPage(`${path}?store_id=stale-store`);
    try {
      await page.getByRole("link", { name: "创建店铺" }).waitFor({ state: "visible", timeout: 5000 });
      assert.equal(await page.getByRole("button", { name: path === "/knowledge" ? "新增知识" : "新建流程" }).isDisabled(), true);
    } finally {
      await context.close();
    }
  }
});

test("knowledge creation controls stay disabled until a store is available", async () => {
  const { context, page } = await openPage("/knowledge");
  try {
    await page.getByRole("link", { name: "创建店铺" }).waitFor();
    assert.equal(await page.getByRole("button", { name: "新增知识" }).isDisabled(), true);
    assert.equal(await page.getByRole("button", { name: "管理分类" }).isDisabled(), true);
    assert.equal(await page.locator('input[type="file"]').isDisabled(), true);
  } finally {
    await context.close();
  }
});

test("knowledge prototype keeps navigation, parameter drawer, and detail interaction coherent", async () => {
  const category = {
    id: "00000000-0000-4000-8000-0000000000c1",
    store_id: store.id,
    parent_id: null,
    name: "物流与仓储",
    code: "logistics",
    layer: "C",
    sort_order: 1,
    status: "active",
  };
  const entry = {
    id: "00000000-0000-4000-8000-0000000000e1",
    store_id: store.id,
    category_id: category.id,
    question: "美国订单物流时效说明",
    answer: "标准配送预计三到五个工作日。",
    source: null,
    tags: ["物流"],
    status: "published",
    vectorization_status: "ready",
    document_version: 3,
    usage_count: 2,
    satisfaction_rate: null,
    statement_type: "policy",
    customer_scope: "generic",
    publication_approval: "approved_for_internal_review",
    semantic_schema_version: 1,
    approved_by: null,
    approved_at: null,
    published_at: null,
    created_at: "2026-10-20T00:00:00Z",
    updated_at: "2026-10-21T00:00:00Z",
  };
  const { context, page } = await openPage("/knowledge", {
    "GET /v1/auth/me": { ...user, store_ids: [store.id] },
    "GET /v1/settings/stores": [store],
    "GET /v1/knowledge/categories": [category],
    "GET /v1/knowledge/entries": { items: [entry], page: 1, page_size: 20, total: 1 },
    "GET /v1/knowledge/vectorization/status": {
      store_id: store.id,
      worker_enabled: true,
      provider: "local_bge",
      model: "BAAI/bge-m3",
      dimensions: 1024,
      counts: { pending: 0, processing: 0, ready: 1, failed: 0 },
    },
  });
  try {
    await page.getByText("CRM 智能聊天系统").waitFor();
    await page.getByRole("button", { name: /流程参数/ }).click();
    const parameters = page.getByRole("dialog", { name: /知识库参数配置/ });
    await parameters.waitFor();
    await parameters.getByRole("spinbutton", { name: "分块大小" }).fill("700");
    await parameters.getByRole("slider", { name: /单次召回数量/ }).fill("12");
    await parameters.getByRole("button", { name: /保存并应用/ }).click();
    await page.getByText(/分块：700.*召回：12/).waitFor();
    assert.equal(await parameters.isVisible(), false);

    await page.getByRole("button", { name: "物流与仓储" }).click();
    await page.getByRole("heading", { name: "物流与仓储" }).waitFor();
    await page.getByRole("combobox", { name: "文件类型" }).selectOption("pdf");
    await page.getByText("当前条件下没有知识文档").waitFor();
    await page.getByRole("combobox", { name: "文件类型" }).selectOption("");

    await page.getByRole("button", { name: "查看", exact: true }).click();
    const detail = page.getByRole("dialog", { name: "知识详情" });
    await detail.getByText("美国订单物流时效说明").waitFor();
    await detail.getByText("标准配送预计三到五个工作日。").waitFor();
    await page.keyboard.press("Escape");
    assert.equal(await detail.isVisible(), false);
    assert.equal(await page.getByRole("link", { name: "Agent 管理" }).count(), 1);
    await page.reload();
    await page.getByText(/分块：500.*召回：20/).waitFor();
    await page.setViewportSize({ width: 760, height: 900 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  } finally {
    await context.close();
  }
});

test("knowledge demo upload stays in the page while CSV uses the existing import API", async () => {
  const importJob = { id: "demo-job", status: "succeeded", total_rows: 1, succeeded_rows: 1, failed_rows: 0 };
  const { context, page } = await openPage("/knowledge", {
    "GET /v1/auth/me": { ...user, store_ids: [store.id] },
    "GET /v1/settings/stores": [store],
    "GET /v1/knowledge/categories": [],
    "GET /v1/knowledge/entries": { items: [], page: 1, page_size: 20, total: 0 },
    "GET /v1/knowledge/vectorization/status": {
      store_id: store.id, worker_enabled: true, provider: "local_bge", model: "BAAI/bge-m3", dimensions: 1024,
      counts: { pending: 0, processing: 0, ready: 0, failed: 0 },
    },
    "POST /v1/knowledge/imports": { job_id: importJob.id, status: "pending" },
    "GET /v1/knowledge/imports/demo-job": importJob,
  });
  const importRequests = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && new URL(request.url()).pathname === "/v1/knowledge/imports") importRequests.push(request);
  });
  try {
    await page.getByRole("button", { name: "新增知识" }).click();
    await page.locator('input[type="file"]').setInputFiles({ name: "manual.pdf", mimeType: "application/pdf", buffer: Buffer.from("sample") });
    await page.getByRole("button", { name: "确认上传并解析" }).click();
    await page.getByText("manual.pdf").first().waitFor();
    assert.equal(importRequests.length, 0);
    await page.reload();
    await page.getByRole("button", { name: "新增知识" }).waitFor();
    assert.equal(await page.getByText("manual.pdf").count(), 0);

    await page.getByRole("button", { name: "新增知识" }).click();
    await page.locator('input[type="file"]').setInputFiles({ name: "facts.csv", mimeType: "text/csv", buffer: Buffer.from("question,answer\nQ,A\n") });
    await page.getByRole("button", { name: "确认上传并解析" }).click();
    await page.getByText(/CSV\/XLSX 已提交真实导入/).waitFor();
    assert.equal(importRequests.length, 1);
  } finally {
    await context.close();
  }
});

test("marketing workflow creation stays disabled until a store is available", async () => {
  const { context, page } = await openPage("/marketing");
  try {
    await page.getByRole("link", { name: "创建店铺" }).waitFor();
    assert.equal(await page.getByRole("button", { name: "新建流程" }).isDisabled(), true);
  } finally {
    await context.close();
  }
});

test("add store starts direct TikTok OAuth without a manual store form", async () => {
  const { context, page } = await openPage("/settings/stores");
  try {
    let starts = 0;
    await context.route("**/v1/settings/stores/tiktok/oauth/start", async (route) => {
      starts += 1;
      assert.equal(route.request().method(), "POST");
      await route.fulfill({ status: 503, contentType: "application/json", headers: {
        "access-control-allow-origin": origin, "access-control-allow-credentials": "true",
      }, body: JSON.stringify({ code: 503, message: "授权暂不可用", data: null }) });
    });
    await page.getByRole("button", { name: "添加店铺" }).click();
    await page.getByRole("status").getByText("授权暂不可用").waitFor();
    assert.equal(starts, 1);
    assert.equal(await page.locator('input[name="code"]').count(), 0);
  } finally {
    await context.close();
  }
});

test("store alias can be edited without changing its platform identity", async () => {
  const { context, page } = await openPage("/settings/stores", {
    "GET /v1/settings/stores": [store], "GET /v1/settings/channels": [storeChannel],
  });
  try {
    let alias = "";
    await context.route("**/v1/settings/stores/*/alias", async (route) => {
      alias = JSON.parse(route.request().postData()).alias;
      await route.fulfill({ status: 200, contentType: "application/json", headers: {
        "access-control-allow-origin": origin, "access-control-allow-credentials": "true",
      }, body: JSON.stringify({ code: 0, message: "ok", data: { ...store, alias } }) });
    });
    await page.getByRole("button", { name: "编辑US Demo Store的别名" }).click();
    await page.getByRole("textbox", { name: "店铺别名" }).fill("美国客服店");
    await page.getByRole("button", { name: "保存" }).click();
    await page.getByRole("status").getByText("别名已保存。").waitFor();
    assert.equal(alias, "美国客服店");
  } finally {
    await context.close();
  }
});

test("store settings filter actual authorization status and search aliases", async () => {
  const pausedStore = { ...store, id: "00000000-0000-4000-8000-0000000000f2", name: "Paused Store", code: "paused", status: "disabled" };
  const expiredChannel = { ...storeChannel, id: "00000000-0000-4000-8000-0000000000c2", store_id: pausedStore.id,
    display_name: pausedStore.name, authorization_expires_at: "2020-01-01T00:00:00Z" };
  const { context, page } = await openPage("/settings/stores", {
    "GET /v1/settings/stores": [{ ...store, alias: "客服店" }, pausedStore],
    "GET /v1/settings/channels": [storeChannel, expiredChannel],
  });
  try {
    await page.getByRole("row", { name: /US Demo Store/ }).waitFor();
    await page.getByRole("button", { name: "已失效 (1)" }).click();
    assert.equal(await page.getByRole("row", { name: /US Demo Store/ }).count(), 0);
    await page.getByRole("row", { name: /Paused Store/ }).waitFor();
    await page.getByRole("button", { name: "全部 (2)" }).click();
    await page.getByRole("textbox", { name: "搜索店铺" }).fill("客服店");
    assert.equal(await page.getByRole("row", { name: /Paused Store/ }).count(), 0);
    assert.equal(await page.getByRole("row", { name: /US Demo Store/ }).count(), 1);
  } finally {
    await context.close();
  }
});

test("store list hides local deletions but retains platform deauthorizations for re-add", async () => {
  const platformStore = { ...store, id: "00000000-0000-4000-8000-0000000000f3", name: "Platform revoked" };
  const deletedStore = { ...store, id: "00000000-0000-4000-8000-0000000000f4", name: "Locally deleted" };
  const mockStore = { ...store, id: "00000000-0000-4000-8000-0000000000f5", name: "Mock only" };
  const { context, page } = await openPage("/settings/stores", {
    "GET /v1/settings/stores": [store, platformStore, deletedStore, mockStore],
    "GET /v1/settings/channels": [storeChannel,
      { ...storeChannel, id: "00000000-0000-4000-8000-0000000000c3", store_id: platformStore.id,
        display_name: platformStore.name, status: "disconnected", authorization_status: "deauthorized" },
      { ...storeChannel, id: "00000000-0000-4000-8000-0000000000c4", store_id: deletedStore.id,
        display_name: deletedStore.name, status: "disconnected", authorization_status: "revoked" }],
  });
  try {
    await page.getByRole("row", { name: /Platform revoked/ }).waitFor();
    assert.equal(await page.getByRole("button", { name: "全部 (2)" }).count(), 1);
    assert.equal(await page.getByRole("row", { name: /Locally deleted/ }).count(), 0);
    assert.equal(await page.getByRole("row", { name: /Mock only/ }).count(), 0);
    await page.getByRole("button", { name: "异常 (1)" }).click();
    assert.equal(await page.getByRole("row", { name: /Platform revoked/ }).count(), 1);
  } finally {
    await context.close();
  }
});

test("store settings keep readable columns in a narrow desktop window", async () => {
  const { context, page } = await openPage("/settings/stores", {
    "GET /v1/settings/stores": [store], "GET /v1/settings/channels": [storeChannel],
  });
  try {
    await page.setViewportSize({ width: 820, height: 900 });
    await page.getByRole("row", { name: /US Demo Store/ }).waitFor();
    const dimensions = await page.locator(".settings-table-wrap").evaluate((wrapper) => ({
      viewportWidth: wrapper.clientWidth,
      contentWidth: wrapper.scrollWidth,
      statusWidth: wrapper.querySelector("tbody tr td:nth-child(6)")?.getBoundingClientRect().width ?? 0,
      statusText: wrapper.querySelector("tbody tr td:nth-child(6) .store-status")?.textContent ?? "",
      statusHeight: wrapper.querySelector("tbody tr td:nth-child(6) .store-status")?.getBoundingClientRect().height ?? 0,
    }));
    assert.ok(dimensions.contentWidth > dimensions.viewportWidth);
    assert.ok(dimensions.statusWidth >= 60);
    assert.equal(dimensions.statusText, "生效中");
    assert.ok(dimensions.statusHeight <= 32);
  } finally {
    await context.close();
  }
});

test("re-add uses the same store and deletion needs a second confirmation", async () => {
  const { context, page } = await openPage("/settings/stores", {
    "GET /v1/settings/stores": [store], "GET /v1/settings/channels": [storeChannel],
  });
  try {
    let oauthStoreId = "";
    let returnTo = "";
    let deletions = 0;
    await context.route("**/v1/settings/channels/tiktok/oauth/start?*", async (route) => {
      const params = new URL(route.request().url()).searchParams;
      oauthStoreId = params.get("store_id");
      returnTo = params.get("return_to");
      await route.fulfill({ status: 503, contentType: "application/json", headers: {
        "access-control-allow-origin": origin, "access-control-allow-credentials": "true",
      }, body: JSON.stringify({ code: 503, message: "重新授权暂不可用", data: null }) });
    });
    await context.route(`**/v1/settings/channels/${storeChannel.id}`, async (route) => {
      deletions += 1;
      await route.fulfill({ status: 204, headers: {
        "access-control-allow-origin": origin, "access-control-allow-credentials": "true",
      } });
    });
    await page.getByRole("button", { name: "重新添加" }).click();
    await page.getByRole("status").getByText("重新授权暂不可用").waitFor();
    assert.equal(oauthStoreId, store.id);
    assert.equal(returnTo, "/settings/stores");
    await page.getByRole("button", { name: "删除", exact: true }).click();
    await page.getByRole("dialog").getByText(/系统 ID 和历史数据保留/).waitFor();
    assert.equal(deletions, 0);
    await page.getByRole("button", { name: "取消" }).click();
    assert.equal(deletions, 0);
    await page.getByRole("button", { name: "删除", exact: true }).click();
    await page.getByRole("button", { name: "确认删除" }).click();
    await page.getByRole("status").getByText(/历史数据已保留/).waitFor();
    assert.equal(deletions, 1);
  } finally {
    await context.close();
  }
});

test("channel authorization without an internal store explains the prerequisite", async () => {
  const { context, page } = await openPage("/settings/channels");
  try {
    await page.getByRole("link", { name: "创建店铺" }).waitFor({ state: "visible", timeout: 5000 });
    assert.equal(await page.getByRole("button", { name: "授权 TikTok Shop" }).isDisabled(), true);
    assert.equal(await page.getByRole("button", { name: "添加 Mock 渠道" }).isDisabled(), true);
  } finally {
    await context.close();
  }
});

test("channel authorization failure is visibly announced", async () => {
  const { context, page } = await openPage("/settings/channels", {
    "GET /v1/auth/me": { ...user, store_ids: [store.id] },
    "GET /v1/settings/stores": [store],
  });
  try {
    await context.route("**/v1/settings/channels/tiktok/oauth/start*", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
        body: JSON.stringify({ code: 503, message: "授权服务暂不可用", data: null }),
      });
    });
    await page.getByRole("button", { name: "授权 TikTok Shop" }).click();
    const status = page.getByRole("status").filter({ hasText: "授权服务暂不可用" });
    await status.waitFor({ state: "visible", timeout: 5000 });
    assert.ok((await status.boundingBox()).y < 400, "OAuth error should be near the page header");
  } finally {
    await context.close();
  }
});

test("TikTok OAuth processing return polls and shows the verified result", async () => {
  const jobId = "00000000-0000-4000-8000-0000000000e1";
  let polls = 0;
  const { context, page } = await openPage(
    `/settings/channels?oauth=tiktok&status=processing&job=${jobId}`,
    { "GET /v1/settings/stores": [store] },
    async (browserContext) => {
      await browserContext.route(`**/v1/settings/channels/tiktok/oauth/jobs/${jobId}`, async (route) => {
        polls += 1;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
          body: JSON.stringify({ code: 0, message: "ok", data: { status: polls === 1 ? "processing" : "connected" } }),
        });
      });
    },
  );
  try {
    await page.getByRole("status").getByText("授权已完成").waitFor({ timeout: 8000 });
    assert.ok(polls >= 2);
    assert.equal(new URL(page.url()).search, "");
  } finally {
    await context.close();
  }
});

test("TikTok OAuth connected URL does not claim success without a verified job", async () => {
  const jobId = "00000000-0000-4000-8000-0000000000e2";
  const { context, page } = await openPage(
    `/settings/channels?oauth=tiktok&status=connected&job=${jobId}`,
    { "GET /v1/settings/stores": [store] },
    async (browserContext) => {
      await browserContext.route(`**/v1/settings/channels/tiktok/oauth/jobs/${jobId}`, async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
          body: JSON.stringify({ code: 0, message: "ok", data: { status: "failed" } }),
        });
      });
    },
  );
  try {
    await page.getByRole("status").getByText("授权未完成").waitFor({ timeout: 8000 });
    assert.equal(await page.getByRole("status").getByText("授权已完成").count(), 0);
  } finally {
    await context.close();
  }
});

test("TikTok OAuth connected URL without a job asks for a new authorization", async () => {
  const { context, page } = await openPage(
    "/settings/channels?oauth=tiktok&status=connected",
    { "GET /v1/settings/stores": [store] },
  );
  try {
    await page.getByRole("status").getByText("无法确认此次 TikTok Shop 授权").waitFor();
    assert.equal(await page.getByRole("status").getByText("授权已完成").count(), 0);
  } finally {
    await context.close();
  }
});

test("failed channel and team loads do not claim there are no stores", async () => {
  for (const [path, endpoint] of [["/settings/channels", "/v1/settings/channels"], ["/settings/team", "/v1/settings/team"]]) {
    const { context, page } = await openPage(path, {}, async (context) => {
      await context.route(`**${endpoint}`, async (route) => {
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
          body: JSON.stringify({ code: 503, message: "配置加载失败", data: null }),
        });
      });
    });
    try {
      await page.getByRole("alert").getByText("配置加载失败").waitFor();
      assert.equal(await page.getByRole("link", { name: "创建店铺" }).count(), 0);
    } finally {
      await context.close();
    }
  }
});

test("Agent code with punctuation is rejected by browser validation", async () => {
  const { context, page } = await openPage("/agents", {
    "GET /v1/agents": [],
    "GET /v1/settings/stores": [store],
  });
  try {
    const code = page.locator('input[name="code"]');
    await code.fill("c's");
    assert.equal(await code.evaluate((input) => input.validity.valid), false);
  } finally {
    await context.close();
  }
});

test("Agent save failure is visibly announced", async () => {
  const { context, page } = await openPage("/agents", {
    "GET /v1/agents": [],
    "GET /v1/settings/stores": [store],
  }, async (context) => {
    await context.route("**/v1/agents", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({
        status: 422,
        contentType: "application/json",
        headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
        body: JSON.stringify({ code: 422, message: "Agent 配置无效", data: null }),
      });
    });
  });
  try {
    await page.getByRole("button", { name: "保存运营配置" }).click();
    const status = page.getByRole("status").filter({ hasText: "Agent 配置无效" });
    await status.waitFor({ state: "visible", timeout: 5000 });
    assert.ok((await status.boundingBox()).y < 400, "Agent save error should be near the page header");
  } finally {
    await context.close();
  }
});

test("Agent log request failure is not shown as an empty log", async () => {
  const { context, page } = await openPage("/agents", {
    "GET /v1/agents": [agent],
    "GET /v1/settings/stores": [store],
  }, async (context) => {
    await context.route("**/v1/agents/*/logs*", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
        body: JSON.stringify({ code: 503, message: "日志服务不可用", data: null }),
      });
    });
  });
  try {
    await page.getByRole("alert").getByText("日志服务不可用").waitFor({ state: "visible", timeout: 5000 });
    assert.equal(await page.getByText("暂无运行日志").count(), 0);
  } finally {
    await context.close();
  }
});

test("late Agent log error cannot replace the newly selected Agent logs", async () => {
  const agentA = { ...agent, name: "Agent A" };
  const agentB = { ...agent, id: "00000000-0000-4000-8000-0000000000a2", name: "Agent B" };
  let releaseA;
  let startedA;
  const startedAPromise = new Promise((resolve) => { startedA = resolve; });
  const { context, page } = await openPage("/agents", {
    "GET /v1/agents": [agentA, agentB],
    "GET /v1/settings/stores": [store],
  }, async (context) => {
    await context.route("**/v1/agents/*/logs*", async (route) => {
      const isA = route.request().url().includes(agentA.id);
      if (isA) await new Promise((resolve) => { releaseA = resolve; startedA(); });
      await route.fulfill({
        status: isA ? 503 : 200,
        contentType: "application/json",
        headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
        body: JSON.stringify(isA ? { code: 503, message: "A 日志不可用", data: null } : { code: 0, message: "ok", data: {
          items: [{ id: "run-B", status: "success", action: "B ACTION", intent: "reply", model_provider: "test", model_name: "test-model", latency_ms: 10, trace_id: "trace-B" }],
          page: 1, page_size: 20, total: 1,
        } }),
      });
    });
  });
  try {
    await startedAPromise;
    await page.locator(".agent-summary-card").filter({ hasText: "Agent B" }).getByRole("button", { name: "配置" }).click();
    await page.getByText("B ACTION").waitFor();
    const oldResponse = page.waitForResponse((response) => response.url().includes(agentA.id) && response.url().includes("/logs"));
    releaseA();
    await oldResponse;
    await page.waitForTimeout(150);
    assert.equal(await page.getByText("B ACTION").isVisible(), true);
    assert.equal(await page.getByText("A 日志不可用").count(), 0);
  } finally {
    releaseA?.();
    await context.close();
  }
});

test("knowledge archive failure is visibly announced", async () => {
  const entry = {
    id: "00000000-0000-4000-8000-0000000000e1",
    store_id: store.id,
    category_id: null,
    question: "Shipping time?",
    answer: "Three days.",
    source: null,
    tags: [],
    status: "draft",
    vectorization_status: "ready",
    document_version: 1,
    usage_count: 0,
    satisfaction_rate: null,
    statement_type: "policy",
    customer_scope: "none",
    publication_approval: "draft",
    semantic_schema_version: 1,
    approved_by: null,
    approved_at: null,
    published_at: null,
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
  };
  const { context, page } = await openPage("/knowledge", {
    "GET /v1/auth/me": { ...user, store_ids: [store.id] },
    "GET /v1/knowledge/categories": [],
    "GET /v1/knowledge/entries": { items: [entry], page: 1, page_size: 20, total: 1 },
    "GET /v1/knowledge/vectorization/status": {
      store_id: store.id,
      worker_enabled: true,
      provider: "local_bge",
      model: "BAAI/bge-m3",
      dimensions: 1024,
      counts: { pending: 0, processing: 0, ready: 1, failed: 0 },
    },
  }, async (context) => {
    await context.route("**/v1/knowledge/entries/*/archive", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
        body: JSON.stringify({ code: 503, message: "归档服务不可用", data: null }),
      });
    });
  });
  try {
    await page.getByRole("button", { name: "查看", exact: true }).click();
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("dialog", { name: "知识详情" }).getByRole("button", { name: "归档" }).click();
    await page.getByRole("status").getByText("归档服务不可用").waitFor({ state: "visible", timeout: 5000 });
  } finally {
    await context.close();
  }
});

test("Agent form without a store disables save and points to store setup", async () => {
  const { context, page } = await openPage("/agents");
  try {
    await page.getByRole("link", { name: "创建店铺" }).waitFor({ state: "visible", timeout: 5000 });
    assert.equal(await page.getByRole("button", { name: "保存运营配置" }).isDisabled(), true);
  } finally {
    await context.close();
  }
});

test("team form without a store disables employee creation and points to setup", async () => {
  const { context, page } = await openPage("/settings/team");
  try {
    await page.getByRole("button", { name: "新建账号" }).click();
    await page.getByRole("link", { name: "创建店铺" }).waitFor({ state: "visible", timeout: 5000 });
    assert.equal(await page.getByRole("button", { name: "保存" }).isDisabled(), true);
  } finally {
    await context.close();
  }
});

test("team form permits system admin without store and resets to disabled agent role", async () => {
  const { context, page } = await openPage("/settings/team", {}, async (context) => {
    await context.route("**/v1/settings/team", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
        body: JSON.stringify({ code: 0, message: "ok", data: {
          id: "00000000-0000-4000-8000-0000000000c1",
          name: "Admin Two",
          email: "admin2@example.invalid",
          status: "active",
          assignments: [{ role: "admin", store_id: null }],
          last_login_at: null,
          created_at: "2026-09-23T00:00:00Z",
        } }),
      });
    });
  });
  try {
    await page.getByRole("button", { name: "新建账号" }).click();
    await page.locator('select[name="role"]').selectOption("admin");
    assert.equal(await page.getByRole("button", { name: "保存" }).isEnabled(), true);
    await page.locator('input[name="login_name"]').fill("admin_two");
    await page.locator('input[name="name"]').fill("Admin Two");
    await page.locator('input[name="email"]').fill("admin2@example.invalid");
    await page.locator('input[name="temporary_password"]').fill("ExamplePass123!");
    await page.getByRole("button", { name: "保存" }).click();
    await page.getByRole("status").getByText(/账号已创建/).waitFor();
    await page.getByRole("button", { name: "新建账号" }).click();
    assert.equal(await page.locator('select[name="role"]').inputValue(), "agent");
    assert.equal(await page.getByRole("button", { name: "保存" }).isDisabled(), true);
  } finally {
    await context.close();
  }
});

test("department members show deferred permission controls and removal uses only membership API", async () => {
  const departmentId = "00000000-0000-4000-8000-0000000000d1";
  const memberId = "00000000-0000-4000-8000-0000000000c1";
  const member = {
    id: memberId, login_name: "agent_one", name: "Agent One", email: null, phone: "13800000000",
    timezone: "Asia/Shanghai", max_concurrent_sessions: 50, status: "active",
    assignments: [{ role: "agent", store_id: store.id }], department_ids: [departmentId],
    last_login_at: null, created_at: "2026-10-22T00:00:00Z",
  };
  let removalPath = "";
  const { context, page } = await openPage("/settings/team/departments", {
    "GET /v1/settings/departments": [{ id: departmentId, name: "客服一部", store_ids: [store.id], created_at: "2026-10-22T00:00:00Z" }],
    "GET /v1/settings/stores": [store],
    "GET /v1/settings/team": [member],
    [`GET /v1/settings/departments/${departmentId}/members`]: [member],
  }, async (context) => {
    await context.route(`**/v1/settings/departments/${departmentId}/members/${memberId}`, async (route) => {
      removalPath = new URL(route.request().url()).pathname;
      await route.fulfill({ status: 204, headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" } });
    });
  });
  try {
    await page.getByRole("cell", { name: "agent_one" }).waitFor();
    assert.equal(await page.getByRole("button", { name: "切换角色" }).isDisabled(), true);
    assert.equal(await page.getByRole("button", { name: "修改权限" }).isDisabled(), true);
    await page.getByRole("button", { name: "移出部门" }).click();
    await page.getByRole("button", { name: "确认移出" }).click();
    await page.getByRole("status").getByText(/账号角色和店铺权限保持不变/).waitFor();
    assert.equal(removalPath, `/v1/settings/departments/${departmentId}/members/${memberId}`);
  } finally { await context.close(); }
});

test("conversation filter replaces a detail that is no longer in the list", async () => {
  const customer = (name) => ({ id: `customer-${name}`, name, email: null, avatar: null, tags: [] });
  const session = (name, unread) => ({
    id: `session-${name}`,
    store_id: "00000000-0000-4000-8000-0000000000f1",
    platform: "tiktok",
    status: "open",
    unread_count: unread,
    assigned_user_id: null,
    last_message_at: "2026-09-23T00:00:00Z",
    last_message: `Message from ${name}`,
    customer: customer(name),
  });
  const alice = session("Alice", 0);
  const bob = session("Bob", 2);
  const { context, page } = await openPage("/workspace", {}, async (context) => {
    await context.route("**/v1/workspace/sessions*", async (route) => {
      if (new URL(route.request().url()).pathname !== "/v1/workspace/sessions") return route.fallback();
      const filter = new URL(route.request().url()).searchParams.get("filter");
      const items = filter === "unread" ? [bob] : [alice, bob];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
        body: JSON.stringify({ code: 0, message: "ok", data: { items, pagination: { page: 1, page_size: 30, total: items.length } } }),
      });
    });
    await context.route("**/v1/workspace/sessions/*/messages*", async (route) => {
      const selected = route.request().url().includes("session-Bob") ? bob : alice;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
        body: JSON.stringify({ code: 0, message: "ok", data: {
          session: selected,
          messages: [],
          customer: selected.customer,
          recent_orders: [],
          ai_suggestion: null,
          pagination: { page: 1, page_size: 100, total: 0 },
          send_mode: "disabled",
          requires_confirmation: true,
        } }),
      });
    });
  });
  try {
    await page.getByLabel("聊天窗口").getByRole("heading", { name: "Alice" }).waitFor();
    await page.getByRole("button", { name: "未读", exact: true }).click();
    await page.locator(".conversation-card").filter({ hasText: "Bob" }).waitFor();
    assert.equal(await page.locator(".conversation-card").filter({ hasText: "Bob" }).getAttribute("aria-pressed"), "true");
    await page.getByLabel("聊天窗口").getByRole("heading", { name: "Bob" }).waitFor();
  } finally {
    await context.close();
  }
});

test("workspace store filter shows authorized names and keeps options after filtering", async () => {
  const otherStore = { ...store, id: "00000000-0000-4000-8000-0000000000f2", name: "Second Store", code: "second" };
  const conversation = {
    id: "session-store-filter", store_id: store.id, platform: "tiktok", status: "active", unread_count: 0,
    assigned_user_id: null, last_message_at: "2026-10-19T00:00:00Z", last_message: "Hello",
    customer: { id: "customer-store-filter", name: "Buyer", email: null, avatar: null, tags: [] },
  };
  const { context, page } = await openPage("/workspace", { "GET /v1/settings/stores": [store, otherStore] }, async (context) => {
    await context.route("**/v1/workspace/sessions*", async (route) => {
      if (new URL(route.request().url()).pathname !== "/v1/workspace/sessions") return route.fallback();
      const items = new URL(route.request().url()).searchParams.has("store_id") ? [] : [conversation];
      await route.fulfill({
        status: 200, contentType: "application/json",
        headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
        body: JSON.stringify({ code: 0, message: "ok", data: { items, pagination: { page: 1, page_size: 30, total: items.length } } }),
      });
    });
  });
  try {
    const filter = page.getByRole("combobox", { name: "店铺" });
    await page.locator(".conversation-card").waitFor();
    assert.deepEqual(await filter.locator("option").allTextContents(), ["全部店铺", "US Demo Store", "Second Store"]);
    await filter.selectOption(otherStore.id);
    await page.getByText("暂无会话，平台消息到达后会显示在这里").waitFor();
    assert.equal(await filter.inputValue(), otherStore.id);
    assert.deepEqual(await filter.locator("option").allTextContents(), ["全部店铺", "US Demo Store", "Second Store"]);
  } finally {
    await context.close();
  }
});

test("older conversation filter response cannot replace the latest list", async () => {
  const session = (name) => ({
    id: `session-${name}`,
    store_id: store.id,
    platform: "tiktok",
    status: "open",
    unread_count: name === "Bob" ? 1 : 0,
    assigned_user_id: null,
    last_message_at: "2026-09-23T00:00:00Z",
    last_message: `Message from ${name}`,
    customer: { id: `customer-${name}`, name, email: null, avatar: null, tags: [] },
  });
  const alice = session("Alice");
  const bob = session("Bob");
  let releaseUnread;
  let unreadStarted;
  const unreadStartedPromise = new Promise((resolve) => { unreadStarted = resolve; });
  let secondAll;
  const secondAllPromise = new Promise((resolve) => { secondAll = resolve; });
  let allCount = 0;
  const { context, page } = await openPage("/workspace", {}, async (context) => {
    await context.route("**/v1/workspace/sessions*", async (route) => {
      const url = new URL(route.request().url());
      if (url.pathname !== "/v1/workspace/sessions") return route.fallback();
      const unread = url.searchParams.get("filter") === "unread";
      if (unread) {
        await new Promise((resolve) => { releaseUnread = resolve; unreadStarted(); });
      } else {
        allCount += 1;
      }
      const items = unread ? [bob] : [alice];
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
        body: JSON.stringify({ code: 0, message: "ok", data: { items, pagination: { page: 1, page_size: 30, total: items.length } } }),
      });
      if (!unread && allCount === 2) secondAll();
    });
    await context.route("**/v1/workspace/sessions/*/messages*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" },
        body: JSON.stringify({ code: 0, message: "ok", data: {
          session: alice, messages: [], customer: alice.customer, recent_orders: [], ai_suggestion: null,
          pagination: { page: 1, page_size: 100, total: 0 }, send_mode: "disabled", requires_confirmation: true,
        } }),
      });
    });
  });
  try {
    await page.getByLabel("聊天窗口").getByRole("heading", { name: "Alice" }).waitFor();
    await page.getByRole("button", { name: "未读" }).click();
    await unreadStartedPromise;
    await page.getByText(/正在加载会话/).waitFor({ state: "visible" });
    await page.getByLabel("会话筛选").getByRole("button", { name: "全部" }).click();
    await secondAllPromise;
    await page.getByText(/正在加载会话/).waitFor({ state: "hidden" });
    const unreadResponse = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/workspace/sessions" && new URL(response.url()).searchParams.get("filter") === "unread");
    releaseUnread();
    await unreadResponse;
    await page.waitForTimeout(150);
    assert.equal(await page.locator(".conversation-card").filter({ hasText: "Bob" }).count(), 0);
    assert.equal(await page.locator(".conversation-card").filter({ hasText: "Alice" }).getAttribute("aria-pressed"), "true");
  } finally {
    releaseUnread?.();
    await context.close();
  }
});

test("buyer and seller bubbles stay on opposite sides and show Chinese beneath the original", async () => {
  const customer = { id: "customer-demo", name: "Buyer", email: null, avatar: null, tags: [] };
  const conversation = {
    id: "session-demo", store_id: store.id, platform: "tiktok", status: "active", unread_count: 0,
    assigned_user_id: null, last_message_at: "2026-10-16T00:00:00Z", last_message: "Available", customer,
  };
  const messages = [
    { id: "buyer-message", role: "user", content: "Is the black one available?", status: "received", created_at: "2026-10-16T00:00:00Z", error_code: null, delivery_mode: "inbound" },
    { id: "seller-message", role: "agent", content: "Yes, the black one is available.", status: "sent", created_at: "2026-10-16T00:01:00Z", error_code: null, delivery_mode: "real" },
  ];
  let translationCalls = 0;
  let sendCalls = 0;
  const cors = { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" };
  const { context, page } = await openPage("/workspace", {}, async (context) => {
    await context.route("**/v1/workspace/sessions**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/v1/workspace/sessions" && route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", headers: cors, body: JSON.stringify({ code: 0, message: "ok", data: { items: [conversation], pagination: { page: 1, page_size: 30, total: 1 } } }) });
      }
      if (path === "/v1/workspace/sessions/session-demo/messages" && route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", headers: cors, body: JSON.stringify({ code: 0, message: "ok", data: { session: conversation, messages, customer, recent_orders: [], ai_suggestion: null, pagination: { page: 1, page_size: 100, total: 2 }, send_mode: "disabled", requires_confirmation: true, translation_enabled: true } }) });
      }
      if (path.endsWith("/translation") && route.request().method() === "POST") {
        translationCalls += 1;
        const messageId = path.split("/").at(-2);
        return route.fulfill({ status: 200, contentType: "application/json", headers: cors, body: JSON.stringify({ code: 0, message: "ok", data: { message_id: messageId, target_language: "zh-CN", translated_text: messageId === "buyer-message" ? "请问黑色还有货吗？" : "有的，黑色还有货。" } }) });
      }
      if (path === "/v1/workspace/sessions/session-demo/messages" && route.request().method() === "POST") sendCalls += 1;
      return route.fallback();
    });
  });
  try {
    const buyer = page.locator(".message.incoming");
    const seller = page.locator(".message.outgoing");
    const listTime = page.locator(".conversation-time");
    await listTime.waitFor();
    assert.match(await listTime.innerText(), /^\d{2}-\d{2} \d{2}:\d{2}$/);
    assert.equal(await listTime.getAttribute("datetime"), conversation.last_message_at);
    await buyer.waitFor();
    assert.ok((await buyer.boundingBox()).x < (await seller.boundingBox()).x);
    await buyer.getByRole("button", { name: "译成中文" }).click();
    await seller.getByRole("button", { name: "译成中文" }).click();
    await buyer.locator(".message-translation").getByText("请问黑色还有货吗？").waitFor();
    await seller.locator(".message-translation").getByText("有的，黑色还有货。").waitFor();
    assert.equal(await buyer.locator(".message-original").textContent(), "Is the black one available?");
    assert.equal(translationCalls, 2);
    assert.equal(sendCalls, 0);
  } finally {
    await context.close();
  }
});

test("real-send reply composer stays visible with a long AI suggestion and accepts a draft", async () => {
  const customer = { id: "customer-draft", name: "Buyer", email: null, avatar: null, tags: [] };
  const session = {
    id: "session-draft", store_id: store.id, platform: "tiktok", status: "active", unread_count: 0,
    assigned_user_id: null, last_message_at: "2026-10-17T06:00:00Z", last_message: "Hello", customer,
  };
  const messages = Array.from({ length: 100 }, (_, index) => ({ id: `message-${index}`, role: "user", content: `Message ${index}`,
    status: "received", created_at: "2026-10-17T06:00:00Z", error_code: null, delivery_mode: "inbound" }));
  const cors = { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" };
  let sendCalls = 0;
  const { context, page } = await openPage("/workspace", {}, async (context) => {
    await context.route("**/v1/chat/query", async (route) => {
      const advice = "Review the buyer request and check the store policy before replying. ".repeat(50);
      await route.fulfill({ status: 200, contentType: "text/event-stream", headers: cors,
        body: `event: delta\ndata: ${JSON.stringify({ text: advice })}\n\nevent: result\ndata: ${JSON.stringify({ content: advice, confidence: 0.8, intent: "general", requires_human: false, demo_mode: false })}\n\nevent: done\ndata: {"reason":"completed"}\n\n` });
    });
    await context.route("**/v1/workspace/sessions**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/v1/workspace/sessions" && route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", headers: cors,
          body: JSON.stringify({ code: 0, message: "ok", data: { items: [session], pagination: { page: 1, page_size: 30, total: 1 } } }) });
      }
      if (path === "/v1/workspace/sessions/session-draft/messages" && route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", headers: cors,
          body: JSON.stringify({ code: 0, message: "ok", data: { session, messages, customer,
            recent_orders: [], ai_suggestion: null, pagination: { page: 1, page_size: 100, total: 100 },
            send_mode: "real", requires_confirmation: true } }) });
      }
      if (path === "/v1/workspace/sessions/session-draft/messages" && route.request().method() === "POST") sendCalls += 1;
      return route.fallback();
    });
  });
  try {
    await page.setViewportSize({ width: 903, height: 787 });
    await page.getByLabel("AI 建议").getByRole("button", { name: "生成" }).click();
    const reply = page.getByRole("textbox", { name: "回复内容" });
    await page.waitForFunction(() => document.querySelector('textarea[aria-label="回复内容"]')?.value.startsWith("Review the buyer request"));
    assert.equal(await reply.isEnabled(), true);
    const sendButton = page.getByRole("button", { name: "直接发送" });
    for (const viewport of [{ width: 903, height: 787 }, { width: 1440, height: 768 }, { width: 390, height: 768 }]) {
      await page.setViewportSize(viewport);
      const replyBounds = await reply.boundingBox();
      assert.ok(replyBounds && replyBounds.y >= 0 && replyBounds.y + replyBounds.height <= viewport.height,
        `Reply input must fit within ${JSON.stringify(viewport)}: ${JSON.stringify(replyBounds)}`);
      const buttonBounds = await sendButton.boundingBox();
      assert.ok(buttonBounds && buttonBounds.y >= 0 && buttonBounds.y + buttonBounds.height <= viewport.height,
        `Send button must fit within ${JSON.stringify(viewport)}: ${JSON.stringify(buttonBounds)}`);
    }
    await reply.fill("Draft only; do not send.");
    assert.equal(await reply.inputValue(), "Draft only; do not send.");
    assert.equal(await sendButton.isEnabled(), true);
    assert.equal(sendCalls, 0);
  } finally {
    await context.close();
  }
});

test("open workspace picks up a new buyer message without reloading or changing the selected conversation", async () => {
  const customer = { id: "customer-live", name: "Buyer", email: null, avatar: null, tags: [] };
  const session = { id: "session-live", store_id: store.id, platform: "tiktok", status: "active", unread_count: 0,
    assigned_user_id: null, last_message_at: "2026-10-17T06:00:00Z", last_message: "First", customer };
  const first = { id: "first", role: "user", content: "First", status: "received", created_at: "2026-10-17T06:00:00Z", error_code: null, delivery_mode: "inbound" };
  const second = { ...first, id: "second", content: "New buyer message", created_at: "2026-10-17T06:01:00Z" };
  let newest = [first];
  const cors = { "access-control-allow-origin": origin, "access-control-allow-credentials": "true" };
  const { context, page } = await openPage("/workspace", {}, async (context) => {
    await context.route("**/v1/workspace/sessions**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      if (path === "/v1/workspace/sessions" && route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", headers: cors,
          body: JSON.stringify({ code: 0, message: "ok", data: { items: [{ ...session, last_message: newest.at(-1).content }], pagination: { page: 1, page_size: 30, total: 1 } } }) });
      }
      if (path === "/v1/workspace/sessions/session-live/messages" && route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", headers: cors,
          body: JSON.stringify({ code: 0, message: "ok", data: { session, messages: newest, customer, recent_orders: [], ai_suggestion: null,
            pagination: { page: 1, page_size: 100, total: newest.length }, send_mode: "disabled", requires_confirmation: true } }) });
      }
      return route.fallback();
    });
  });
  try {
    await page.getByText("First", { exact: true }).last().waitFor();
    newest = [first, second];
    await page.getByText("New buyer message", { exact: true }).last().waitFor({ timeout: 9000 });
    assert.equal(await page.locator(".conversation-card.active").count(), 1);
    assert.equal(await page.locator(".message.incoming").count(), 2);
  } finally {
    await context.close();
  }
});
