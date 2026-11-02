import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const ts = require("typescript");
const source = readFileSync(new URL("../../../frontend/lib/api.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
test("automation controls preserve mode revision and per-conversation pause through authenticated API", async () => {
 const original = globalThis.fetch; const requests = [];
 globalThis.fetch = async (url, init) => { requests.push({ url, init }); return new Response(JSON.stringify({ code: 0, data: {} }), { headers: { "content-type": "application/json" } }); };
 try {
  const api = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}#automation`);
  await api.setAutomationPolicy("shop-1", { mode: "auto", expected_revision: 2 });
  await api.setConversationAutomation("chat-1", { paused: true, expected_revision: 3 });
  assert.match(requests[0].url, /agents\/automation\?store_id=shop-1$/);
  assert.deepEqual(JSON.parse(requests[0].init.body), { mode: "auto", expected_revision: 2 });
  assert.deepEqual(JSON.parse(requests[1].init.body), { paused: true, expected_revision: 3 });
  assert.equal(requests[1].init.method, "PUT");
 } finally { globalThis.fetch = original; }
});
test("customer reply approval is explicit and internal approval remains default", async () => {
 const original = globalThis.fetch; const payloads = [];
 globalThis.fetch = async (_url, init) => { payloads.push(JSON.parse(init.body)); return new Response(JSON.stringify({ code: 0, data: {} }), { headers: { "content-type": "application/json" } }); };
 try {
  const api = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}#approval-purpose`);
  await api.approveDocumentVersion("file-1", 1, "policy");
  await api.approveDocumentVersion("file-1", 1, "policy", "public_reply");
  assert.equal(payloads[0].purpose, "internal_review");
  assert.equal(payloads[1].purpose, "public_reply");
 } finally { globalThis.fetch = original; }
});
