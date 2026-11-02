import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { frontendRoot } from "../helpers/paths.mjs";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const ts = require("typescript");

function handler(overrides = {}) {
  const source = readFileSync(new URL("app/agents/page.tsx", frontendRoot), "utf8");
  const start = source.indexOf("  async function previewLogistics() {");
  assert.ok(start >= 0, "selected logistics Agent needs the dedicated verified event handler");
  const code = source.slice(start, source.indexOf("\n  async function preview()", start));
  const calls = [];
  const rendered = [];
  const bindings = {
    selected: { id: "selected-event-agent" }, conversationId: "authorized-conversation", eventOrderId: "771100",
    eventPackageId: "123", previewBusy: false, dirty: false, eventOrdersBusy: false, eventPackagesBusy: false,
    previewRequestId: { current: 0 }, previewAbort: { current: null },
    setPreviewBusy: () => {}, setPreviewError: () => {}, setPreviewResult: () => {}, setPreviewDrafts: () => {},
    setEventPreview: (value) => rendered.push(value), setPreviewLines: () => {},
    previewAgentLogisticsEvent: async (...args) => { calls.push(args); return { status: "previewed", preview_text: "Verified latest node.", citations: ["chunk"], tool_calls: [{ name: "query_logistics", status: "succeeded" }] }; },
    message: (error) => error.message,
    ...overrides,
  };
  const compiled = ts.transpileModule(code, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText;
  const run = new Function(...Object.keys(bindings), `${compiled}; return previewLogistics;`)(...Object.values(bindings));
  return { run, calls, rendered, bindings };
}

test("logistics preview binds selected Agent and real order context without supplying event facts", async () => {
  const probe = handler();
  await probe.run();
  assert.equal(probe.calls.length, 1);
  assert.equal(probe.calls[0][0], "selected-event-agent");
  assert.deepEqual(probe.calls[0][1], { conversation_id: "authorized-conversation", external_order_id: "771100", package_id: "123" });
  assert.equal(probe.rendered.at(-1).tool_calls[0].status, "succeeded");
  assert.deepEqual(probe.rendered.at(-1).citations, ["chunk"]);
});

test("logistics preview needs selected order and ignores a late response after context changes", async () => {
  const missing = handler({ eventOrderId: "" });
  await missing.run();
  assert.equal(missing.calls.length, 0);
  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  const late = handler({ previewAgentLogisticsEvent: async () => pending });
  const operation = late.run();
  late.bindings.previewRequestId.current += 1;
  release({ status: "previewed", preview_text: "Old context" });
  await operation;
  assert.equal(late.rendered.some((row) => row?.preview_text === "Old context"), false);
});
