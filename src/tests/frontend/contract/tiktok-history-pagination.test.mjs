import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";

const frontendApi = new URL("../../../frontend/lib/api.ts", import.meta.url);
const require = createRequire(frontendApi);
const ts = require("typescript");
const compiled = ts.transpileModule(readFileSync(frontendApi, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { getSessionMessages } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);

test("opening a long conversation shows its newest history page", async () => {
  const originalFetch = globalThis.fetch;
  const pages = [];
  globalThis.fetch = async (input) => {
    const page = Number(new URL(String(input)).searchParams.get("page"));
    pages.push(page);
    return new Response(JSON.stringify({ code: 0, message: "ok", data: {
      session: { id: "one" }, messages: [{ id: page === 1 ? "old" : "new" }],
      pagination: { page, page_size: 100, total: 125 },
    } }), { status: 200, headers: { "Content-Type": "application/json" } });
  };
  try {
    const result = await getSessionMessages("one");
    assert.deepEqual(pages, [1, 2]);
    assert.equal(result.messages[0].id, "new");
    assert.equal(result.pagination.page, 2);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
