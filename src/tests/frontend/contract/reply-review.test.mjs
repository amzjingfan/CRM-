import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const ts = require("typescript");
const source = readFileSync(new URL("../../../frontend/lib/api.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;

test("review stream binds the original message and preserves draft snapshots without changing old callers", async () => {
  const original = globalThis.fetch;
  const payloads = [];
  globalThis.fetch = async (_url, init) => {
    payloads.push(JSON.parse(init.body));
    return new Response('event: draft\ndata: {"part_index":0,"text":"Ready","replace":true,"unverified":true,"sendable":false,"trigger_message_id":"buyer-1"}\n\nevent: done\ndata: {"reason":"completed"}\n\n', { headers: { "content-type": "text/event-stream" } });
  };
  try {
    const api = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}#reply-review-stream`);
    const events = [];
    await api.streamChatQuery("session-1", (event) => events.push(event), new AbortController().signal, "buyer-1", "review_plan");
    await api.streamChatQuery("session-1", () => {}, new AbortController().signal);
    assert.deepEqual(payloads, [{ session_id: "session-1", trigger_message_id: "buyer-1", reply_mode: "review_plan" }, { session_id: "session-1", trigger_message_id: null }]);
    assert.equal(events[0].event, "draft");
    assert.equal(events[0].data.sendable, false);
  } finally { globalThis.fetch = original; }
});

test("batch preview keeps exact edited text, confirmation and stable idempotency through the API boundary", async () => {
  const original = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, init) => {
    requests.push({ url, init });
    return new Response(JSON.stringify({ code: 0, message: "ok", data: { id: "batch-1", status: "previewed", preview_only: true, parts: [], messages: [] } }), { headers: { "content-type": "application/json" } });
  };
  try {
    const api = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}#reply-review-batch`);
    const parts = [{ kind: "text", content: "Edited reply" }, { kind: "logistics_card", order_id: "order-1", package_id: null }];
    await api.submitReplyBatch("session-1", { trigger_message_id: "buyer-1", parts, preview_only: true, confirmed: false }, "key-1");
    assert.equal(requests[0].url, "http://localhost:8000/v1/workspace/sessions/session-1/reply-batches");
    assert.equal(new Headers(requests[0].init.headers).get("Idempotency-Key"), "key-1");
    assert.deepEqual(JSON.parse(requests[0].init.body), { trigger_message_id: "buyer-1", parts, preview_only: true, confirmed: false });
  } finally { globalThis.fetch = original; }
});

test("logistics notification preview keeps CRM order IDs and cannot enable delivery", async () => {
  const original = globalThis.fetch;
  const requests = [];
  globalThis.fetch = async (url, init) => {
    requests.push({ url, init });
    return new Response(JSON.stringify({ code: 0, message: "ok", data: { status: "previewed", preview_text: "Your parcel arrived." } }), { headers: { "content-type": "application/json" } });
  };
  try {
    const api = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}#notification-preview`);
    await api.previewLogisticsNotification({ store_id: "store-1", conversation_id: "session-1", order_id: "00000000-0000-4000-8000-000000000501" });
    assert.equal(requests[0].url, "http://localhost:8000/v1/agents/logistics-notifications/preview");
    assert.deepEqual(JSON.parse(requests[0].init.body), { store_id: "store-1", conversation_id: "session-1", order_id: "00000000-0000-4000-8000-000000000501" });
    assert.ok(new Headers(requests[0].init.headers).get("Idempotency-Key"));
  } finally { globalThis.fetch = original; }
});
