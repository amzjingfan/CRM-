import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const ts = require("typescript");
const dataModule = (source) => `data:text/javascript;base64,${Buffer.from(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText).toString("base64")}`;

test("template transport uses shared CSRF, idempotency and precise revision/source bodies", async () => {
  const apiUrl = dataModule(readFileSync(new URL("../../../frontend/lib/api.ts", import.meta.url), "utf8"));
  const file = new URL("../../../frontend/lib/agent-templates.ts", import.meta.url);
  assert.equal(require("node:fs").existsSync(file), true, "template transport is implemented");
  const source = readFileSync(file, "utf8").replace('"./api"', JSON.stringify(apiUrl));
  const calls = []; const originalFetch = globalThis.fetch; const originalDocument = globalThis.document;
  globalThis.document = { cookie: "crm_csrf_token=synthetic-csrf" };
  globalThis.fetch = async (url, init) => { calls.push({ url, init }); return new Response(JSON.stringify({ code: 0, message: "ok", data: { items: [], can_manage: true } }), { status: 200 }); };
  try {
    const api = await import(dataModule(source));
    await api.listAgentTemplates(true);
    await api.publishAgentTemplate("a/b", 7);
    await api.createAgentTemplateFromAgent({ name: "source", code: "source_code", description: null, source_agent_id: "agent", source_version: null, source_draft_revision: 9, knowledge_slots: [] });
    assert.equal(new URL(calls[0].url).searchParams.get("include_archived"), "true");
    assert.equal(new URL(calls[1].url).pathname, "/v1/agents/templates/a%2Fb/publish");
    assert.deepEqual(JSON.parse(calls[1].init.body), { expected_revision: 7 });
    assert.equal(calls[1].init.credentials, "include");
    assert.ok(calls[1].init.headers.get("Idempotency-Key"));
    assert.equal(calls[1].init.headers.get("X-CSRF-Token"), "synthetic-csrf");
    assert.equal(JSON.parse(calls[2].init.body).source_draft_revision, 9);
    assert.equal(JSON.parse(calls[2].init.body).source_version, null);
  } finally { globalThis.fetch = originalFetch; if (originalDocument === undefined) delete globalThis.document; else globalThis.document = originalDocument; }
});

test("batch transport preserves stable confirmation key and exact selection queries", async () => {
  const apiUrl = dataModule(readFileSync(new URL("../../../frontend/lib/api.ts", import.meta.url), "utf8"));
  const source = readFileSync(new URL("../../../frontend/lib/agent-templates.ts", import.meta.url), "utf8").replace('"./api"', JSON.stringify(apiUrl));
  const calls = []; const oldFetch = globalThis.fetch; const oldDocument = globalThis.document;
  globalThis.document = { cookie: "crm_csrf_token=synthetic-csrf" };
  globalThis.fetch = async (url, init) => { calls.push({ url: new URL(url), init }); return new Response(JSON.stringify({ code: 0, message: "ok", data: {} }), { status: 200 }); };
  try {
    const api = await import(dataModule(source));
    await api.listApplicationStores(2, 20, "A B");
    await api.listApplicationKnowledgeFiles("store/1", 3, 10, "faq");
    await api.previewTemplateApplication("template/1", { template_version: 2, items: [] });
    await api.confirmTemplateBatch("preview-1", "stable-key");
    await api.confirmTemplateBatch("preview-1", "stable-key");
    await api.getTemplateBatch("batch/1", 2, 50);
    await api.detachAgentTemplate("agent/1", 4);
    assert.equal(calls[0].url.searchParams.get("page"), "2");
    assert.equal(calls[0].url.searchParams.get("search"), "A B");
    assert.equal(calls[1].url.pathname, "/v1/agents/templates/application-stores/store%2F1/knowledge-files");
    assert.equal(calls[1].url.searchParams.get("page_size"), "10");
    assert.deepEqual(JSON.parse(calls[2].init.body), { template_version: 2, items: [] });
    for (const call of calls.slice(3, 5)) {
      assert.deepEqual(JSON.parse(call.init.body), { preview_id: "preview-1", confirmation: true });
      assert.equal(call.init.headers.get("Idempotency-Key"), "stable-key");
      assert.equal(call.init.headers.get("X-CSRF-Token"), "synthetic-csrf");
    }
    assert.equal(calls[5].url.searchParams.get("page"), "2");
    assert.deepEqual(JSON.parse(calls[6].init.body), { expected_revision: 4 });
  } finally { globalThis.fetch = oldFetch; if (oldDocument === undefined) delete globalThis.document; else globalThis.document = oldDocument; }
});
