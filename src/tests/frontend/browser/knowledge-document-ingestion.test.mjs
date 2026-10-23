import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { after, before, test } from "node:test";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const { chromium } = require("playwright-core");
const baseUrl = process.env.UI_BASE_URL ?? "http://127.0.0.1:3101";
const origin = new URL(baseUrl).origin;
if (!["127.0.0.1", "localhost", "::1"].includes(new URL(baseUrl).hostname)) throw new Error("UI tests require a local server");

const storeId = "00000000-0000-4000-8000-0000000000f1";
const fileId = "00000000-0000-4000-8000-0000000000f2";
const versionId = "00000000-0000-4000-8000-0000000000f3";
const timestamp = "2026-10-23T05:00:00Z";
const config = { strategy: "recursive", chunk_size: 500, overlap: 50, parser_mode: "auto", embedding_model: "BAAI/bge-m3" };
const user = { id: "00000000-0000-4000-8000-000000000001", name: "管理员", email: "admin@example.invalid", login_name: "admin", role: "admin", avatar: null, permissions: ["knowledge.view", "knowledge.manage"], store_ids: [storeId] };
const store = { id: storeId, name: "测试店铺", alias: null, code: "test", status: "active", timezone: "Asia/Shanghai", currency: "CNY", created_at: timestamp };
let browser;

before(async () => { browser = await chromium.launch({ channel: "chrome", headless: true }); });
after(async () => { await browser?.close(); });

async function open(status = "ready") {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const writes = [];
  let savedConfig = { ...config };
  let currentStatus = status;
  const version = () => ({ id: versionId, version_number: 1, status: currentStatus, error_code: null, retry_count: 0, created_at: timestamp, completed_at: null, is_active: status === "ready", chunk_count: currentStatus === "review_required" ? 0 : 1 });
  const file = () => ({ id: fileId, store_id: storeId, category_id: null, filename: "policy.txt", active_version_number: status === "ready" ? 1 : null, latest_version: version() });
  const detail = () => ({ ...version(), file_id: fileId, filename: "policy.txt", file_sha256: "a".repeat(64), config: savedConfig, parser_version: "native-text-v1", cleaning_version: "clean-v1", units: [{ unit_index: 0, unit_kind: "document_unit", source_locator: { source_unit: 0 }, raw_text: "原始政策文本", cleaned_text: "原始政策文本", issue_codes: currentStatus === "review_required" ? ["TEXT_CORRUPTED"] : [], needs_review: currentStatus === "review_required", parse_mode: "native_text", reviewed_by: null, reviewed_at: null }] });
  await context.route("**/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const headers = { "access-control-allow-origin": origin, "access-control-allow-credentials": "true", "access-control-allow-methods": "GET,POST,PUT,OPTIONS", "access-control-allow-headers": "content-type,idempotency-key,x-csrf-token" };
    if (method === "OPTIONS") return route.fulfill({ status: 204, headers });
    if (!["GET", "HEAD"].includes(method)) writes.push({ method, path, body: request.postData() });
    if (path === "/v1/knowledge/file-settings" && method === "PUT") savedConfig = JSON.parse(request.postData());
    if (path.endsWith("/review") && method === "POST") currentStatus = "queued";
    const data = path === "/v1/auth/me" ? user
      : path === "/v1/settings/stores" ? [store]
      : path === "/v1/knowledge/categories" ? []
      : path === "/v1/knowledge/entries" ? { items: [], page: 1, page_size: 20, total: 0 }
      : path === "/v1/knowledge/files" ? { items: [file()], page: Number(url.searchParams.get("page") ?? 1), page_size: 20, total: 1 }
      : path === "/v1/knowledge/file-settings" ? savedConfig
      : path === "/v1/knowledge/vectorization/status" ? { store_id: storeId, worker_enabled: true, provider: "local_bge", model: "BAAI/bge-m3", dimensions: 1024, counts: { pending: 0, processing: 0, ready: 0, failed: 0 } }
      : path === `/v1/knowledge/files/${fileId}` ? { ...file(), versions: [version()] }
      : path === `/v1/knowledge/files/${fileId}/versions/1` || path.endsWith("/review") ? detail()
      : path === "/v1/knowledge/files/imports" ? { file_id: fileId, version_id: versionId, version_number: 2, status: "queued" }
      : [];
    await route.fulfill({ status: path === "/v1/knowledge/files/imports" ? 202 : 200, headers, contentType: "application/json", body: JSON.stringify({ code: 0, message: "ok", data }) });
  });
  const tab = await context.newPage();
  await tab.goto(`${baseUrl}/knowledge?store_id=${storeId}`);
  await tab.getByRole("button", { name: "查看" }).waitFor();
  return { context, tab, writes };
}

test("selected chunk settings reach document upload and same-name replacement is explicit", async () => {
  const { context, tab, writes } = await open();
  try {
    await tab.getByRole("button", { name: /流程参数/ }).click();
    const settings = tab.getByRole("dialog", { name: "知识库参数配置" });
    await settings.getByRole("combobox", { name: "默认分段策略" }).selectOption("fixed_token");
    await settings.getByLabel("分块大小").fill("80");
    await settings.getByLabel("重叠大小").fill("8");
    await settings.getByRole("button", { name: "保存并应用" }).click();
    await tab.getByRole("button", { name: "新增知识" }).click();
    await tab.getByLabel("选择知识文件").setInputFiles({ name: "policy.txt", mimeType: "text/plain", buffer: Buffer.from("新政策文本") });
    await tab.getByRole("button", { name: "确认上传并解析" }).click();
    const replacement = tab.getByRole("dialog", { name: "替换同名文件" });
    await replacement.waitFor();
    assert.match(await replacement.innerText(), /旧有效版本/);
    await replacement.getByRole("button", { name: "替换旧文件" }).click();
    await tab.getByText("文件 v2 已进入解析队列", { exact: false }).waitFor();
    const upload = writes.find((item) => item.path === "/v1/knowledge/files/imports");
    assert.ok(upload);
    assert.match(upload.body, /"strategy":"fixed_token"/);
    assert.match(upload.body, /"chunk_size":80/);
    assert.match(upload.body, /"overlap":8/);
    assert.match(upload.body, new RegExp(fileId));
  } finally { await context.close(); }
});

test("whole-version review shows zero vectors and sends explicit corrected content", async () => {
  const { context, tab, writes } = await open("review_required");
  try {
    await tab.getByRole("button", { name: "查看" }).click();
    const detail = tab.getByRole("dialog", { name: "知识详情" });
    await detail.getByText("整个新版本保持待复核", { exact: false }).waitFor();
    assert.match(await detail.innerText(), /0 向量/);
    await detail.getByRole("textbox", { name: "修订单元 1" }).fill("已核对：不允许退款。");
    await detail.getByRole("button", { name: "确认此单元" }).click();
    await tab.getByText("全部问题单元已确认", { exact: false }).waitFor();
    const review = writes.find((item) => item.path.endsWith("/review"));
    assert.ok(review);
    assert.deepEqual(JSON.parse(review.body), { corrected_text: "已核对：不允许退款。", confirmed: true });
  } finally { await context.close(); }
});
