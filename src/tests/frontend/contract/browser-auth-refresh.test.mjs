import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const ts = require("typescript");
const source = readFileSync(new URL("../../../frontend/lib/api.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
let moduleNumber = 0;

async function loadApiWithBrowserFetch(fetch) {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  globalThis.fetch = fetch;
  globalThis.window = {};
  const api = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}#${++moduleNumber}`);
  return { api, restore: () => { globalThis.fetch = originalFetch; if (originalWindow === undefined) delete globalThis.window; else globalThis.window = originalWindow; } };
}

function jsonResponse(status, data = null) {
  return new Response(JSON.stringify({ code: status === 200 ? 0 : status, message: status === 200 ? "ok" : "expired", data }), {
    status, headers: { "content-type": "application/json" },
  });
}

test("a late 401 from a read does not start a second completed browser refresh", async () => {
  const attempts = new Map();
  let refreshCalls = 0;
  let releaseLateResponse;
  const storeRecovered = new Promise((resolve) => { releaseLateResponse = resolve; });
  const { api, restore } = await loadApiWithBrowserFetch(async (url) => {
    const path = new URL(url).pathname;
    if (path === "/v1/auth/browser/refresh") {
      refreshCalls += 1;
      return jsonResponse(200, {});
    }
    const attempt = (attempts.get(path) ?? 0) + 1;
    attempts.set(path, attempt);
    if (path === "/v1/settings/channels" && attempt === 1) await storeRecovered;
    if (path === "/v1/settings/stores" && attempt === 2) releaseLateResponse();
    return attempt === 1 ? jsonResponse(401) : jsonResponse(200, []);
  });
  try {
    const [stores, channels] = await Promise.all([
      api.requestApi("/settings/stores"), api.requestApi("/settings/channels"),
    ]);
    assert.deepEqual(stores, []);
    assert.deepEqual(channels, []);
    assert.equal(refreshCalls, 1);
    assert.equal(attempts.get("/v1/settings/stores"), 2);
    assert.equal(attempts.get("/v1/settings/channels"), 2);
  } finally {
    releaseLateResponse();
    restore();
  }
});

test("a late 401 from a read-only POST reuses the refreshed cookie and its idempotency key", async () => {
  const attempts = new Map();
  const keys = [];
  let refreshCalls = 0;
  let releaseLateResponse;
  const lateResponse = new Promise((resolve) => { releaseLateResponse = resolve; });
  const { api, restore } = await loadApiWithBrowserFetch(async (url, init) => {
    const path = new URL(url).pathname;
    if (path === "/v1/auth/browser/refresh") {
      refreshCalls += 1;
      return jsonResponse(200, {});
    }
    if (path.endsWith("/sidebar/orders/detail")) keys.push(init.headers.get("Idempotency-Key"));
    const attempt = (attempts.get(path) ?? 0) + 1;
    attempts.set(path, attempt);
    if (path.endsWith("/sidebar/orders/detail") && attempt === 1) await lateResponse;
    if (path === "/v1/settings/stores" && attempt === 2) releaseLateResponse();
    return attempt === 1 ? jsonResponse(401) : jsonResponse(200, {});
  });
  try {
    const [stores, detail] = await Promise.all([
      api.requestApi("/settings/stores"),
      api.getCustomerSidebarOrderDetail("session-1", "123", undefined, false),
    ]);
    assert.deepEqual(stores, {});
    assert.deepEqual(detail, {});
    assert.equal(refreshCalls, 1);
    assert.equal(attempts.get("/v1/workspace/sessions/session-1/sidebar/orders/detail"), 2);
    assert.equal(keys.length, 2);
    assert.ok(keys[0]);
    assert.equal(keys[0], keys[1]);
  } finally {
    releaseLateResponse();
    restore();
  }
});

test("failed shared refresh leaves concurrent reads unauthorized and does not retry them", async () => {
  const attempts = new Map();
  let refreshCalls = 0;
  const { api, restore } = await loadApiWithBrowserFetch(async (url) => {
    const path = new URL(url).pathname;
    if (path === "/v1/auth/browser/refresh") {
      refreshCalls += 1;
      await new Promise((resolve) => setTimeout(resolve, 20));
      return jsonResponse(401);
    }
    attempts.set(path, (attempts.get(path) ?? 0) + 1);
    return jsonResponse(401);
  });
  try {
    const results = await Promise.allSettled([
      api.requestApi("/settings/stores"), api.requestApi("/settings/channels"),
    ]);
    assert.equal(results.every((result) => result.status === "rejected" && result.reason.status === 401), true);
    assert.equal(refreshCalls, 1);
    assert.equal(attempts.get("/v1/settings/stores"), 1);
    assert.equal(attempts.get("/v1/settings/channels"), 1);
  } finally {
    restore();
  }
});


test("manual message send settles at its deadline without retrying an uncertain request", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const calls = [];
  const { api, restore } = await loadApiWithBrowserFetch(async (url, init) => {
    calls.push({ url, init });
    return new Promise(() => {});
  });
  try {
    let outcome;
    void api.sendMessage("synthetic-session", "Synthetic message", "stable-send-key").catch((error) => { outcome = error; });
    t.mock.timers.tick(45001);
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(outcome?.name, "MessageSendWaitError");
    assert.equal(calls.length, 1);
    assert.equal(calls[0].init.headers.get("Idempotency-Key"), "stable-send-key");
    assert.equal(calls[0].init.signal.aborted, true);
  } finally { restore(); t.mock.timers.reset(); }
});
