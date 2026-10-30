import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";
import vm from "node:vm";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const source = readFileSync(new URL("../../../frontend/app/agents/template-batches/page.tsx", import.meta.url), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
const flush = () => new Promise((resolve) => setImmediate(resolve));
const deferred = () => { let resolve; let reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const summary = { id: "b", template_id: "t", template_version: 1, status: "running", counts: { succeeded: 1 }, created_at: "now", processor_enabled: true };
const pagination = { page: 1, total_pages: 1, total: 1, page_size: 50 };

// 运行原始 TSX 的事件闭包与 effect；所有传输和计时器均为内存替身，不启动服务或出网。
function pageHarness(item, post = Promise.resolve({ ...summary, items: [], pagination }), listReply = null) {
  const detail = { ...summary, items: [item], pagination };
  const values = ["b", 1, 1, { items: [summary], pagination }, detail, "", false, true, true];
  const refs = []; const effects = []; const writes = []; const calls = [];
  let stateIndex = 0; let refIndex = 0; let effectIndex = 0;
  const api = {
    listTemplateBatches: async () => { const afterPost = calls.some((call) => call.startsWith("POST")); calls.push("GET list"); return afterPost && listReply ? listReply : { items: [summary], pagination }; },
    getTemplateBatch: async () => detail,
    cancelTemplateBatch: () => { calls.push("POST cancel"); return post; },
    retryFailedTemplateBatch: () => { calls.push("POST retry"); return post; },
  };
  const hooks = {
    ...React,
    useState: () => { const i = stateIndex++; return [values[i], (value) => { writes.push([i, value]); values[i] = value; }]; },
    useRef: (initial) => { const i = refIndex++; return refs[i] ??= { current: initial }; },
    useCallback: (fn) => fn,
    useEffect: (fn, deps) => {
      const i = effectIndex++; const old = effects[i];
      if (!old || deps.some((value, n) => value !== old.deps[n])) { old?.cleanup?.(); effects[i] = { fn, deps, pending: true }; }
    },
  };
  const fragment = ({ children }) => React.createElement(React.Fragment, null, children);
  const exports = {};
  const context = vm.createContext({ exports, URLSearchParams, window: { location: { search: "?batch_id=b" }, addEventListener() {}, removeEventListener() {}, setInterval: () => 1, clearInterval() {} }, require: (name) => {
    if (name === "react") return hooks;
    if (name === "react/jsx-runtime") return require(name);
    if (name === "next/link") return { __esModule: true, default: fragment };
    if (name.endsWith("/agent-templates")) return api;
    if (name.endsWith("AppShell")) return { AppShell: fragment };
    if (name.endsWith("AgentTemplateNav")) return { AgentTemplateNav: () => null };
    if (name.endsWith("TemplateModal")) return { TemplateModal: fragment };
    if (name.endsWith(".css")) return {};
    throw new Error(`Unexpected import: ${name}`);
  } });
  vm.runInContext(code, context);
  function render() {
    stateIndex = 0; refIndex = 0; effectIndex = 0;
    const tree = exports.default();
    for (const effect of effects) if (effect.pending) { effect.pending = false; effect.cleanup = effect.fn(); }
    return tree;
  }
  return { render, values, writes, calls, unmount: () => effects.forEach((effect) => effect.cleanup?.()) };
}

function findButton(node, name) {
  if (!node || typeof node !== "object") return null;
  if (node.type === "button" && node.props.children === name) return node;
  for (const child of React.Children.toArray(node.props?.children)) { const found = findButton(child, name); if (found) return found; }
  return null;
}

for (const [name, publish, oldVersion, resultVersion, expected] of [
  ["create and publish", true, null, 1, "新版本已发布"],
  ["save draft", false, 1, 1, "草稿已保存，运行版本未改变"],
  ["new version", true, 1, 2, "新版本已发布"],
  ["same snapshot or source metadata only", true, 1, 1, "已与运行版本一致，未新增发布"],
]) test(`batch outcome describes actual ${name}`, async () => {
  const harness = pageHarness({ id: "i", status: "succeeded", store_name: "店", old_published_version: oldVersion, result_version: resultVersion, preview: { flags: { publish } } });
  const html = renderToStaticMarkup(harness.render());
  harness.unmount();
  assert.ok(html.includes(expected), html);
  if (oldVersion === resultVersion && publish) assert.ok(!html.includes("新版本已发布"));
});

test("hidden result never claims a publication", () => {
  const harness = pageHarness({ id: "hidden", status: "succeeded", store_name: "无权查看店铺", old_published_version: null, result_version: null, preview: null });
  const html = renderToStaticMarkup(harness.render()); harness.unmount();
  assert.ok(!html.includes("新版本已发布") && !html.includes("未新增发布"));
});

for (const kind of ["cancel", "retry"]) for (const leave of ["unmount", "selection", "page", "current"]) {
  test(`${kind} late POST respects ${leave} action lifetime`, async () => {
    const gate = deferred(); const harness = pageHarness({ id: "i", retryable: true, status: "failed", store_name: "店" }, gate.promise);
    const tree = harness.render(); await flush(); harness.calls.length = 0; harness.writes.length = 0;
    findButton(tree, kind === "cancel" ? "确认取消" : "重试可重试失败项").props.onClick();
    assert.deepEqual(harness.calls, [`POST ${kind}`]);
    if (leave === "unmount") harness.unmount();
    if (leave === "selection") { harness.values[0] = "other-batch"; harness.render(); }
    if (leave === "page") { harness.values[1] = 2; harness.render(); }
    await flush(); harness.calls.length = 0; harness.writes.length = 0;
    gate.resolve({ ...summary, id: "b", items: [], pagination }); await flush(); await flush();
    if (leave === "current") {
      assert.deepEqual(harness.calls, ["GET list"]);
      assert.ok(harness.writes.some(([slot]) => slot === 4));
    } else {
      assert.deepEqual(harness.calls, [], "departed request must not start a list GET");
      assert.deepEqual(harness.writes, [], "departed request must not mutate another view");
    }
    harness.unmount();
  });
}

for (const kind of ["cancel", "retry"]) {
  test(`${kind} rejected POST after departure cannot set error or busy state`, async () => {
    const gate = deferred(); const harness = pageHarness({ id: "i", retryable: true }, gate.promise);
    const tree = harness.render(); await flush();
    findButton(tree, kind === "cancel" ? "确认取消" : "重试可重试失败项").props.onClick();
    harness.unmount(); harness.writes.length = 0; harness.calls.length = 0;
    gate.reject(new Error("synthetic failure")); await flush(); await flush();
    assert.deepEqual(harness.calls, []); assert.deepEqual(harness.writes, []);
  });
  test(`${kind} list already in flight cannot update a departed selection`, async () => {
    const gate = deferred(); const harness = pageHarness({ id: "i", retryable: true }, Promise.resolve({ ...summary, items: [], pagination }), gate.promise);
    const tree = harness.render(); await flush(); harness.calls.length = 0;
    findButton(tree, kind === "cancel" ? "确认取消" : "重试可重试失败项").props.onClick(); await flush();
    assert.deepEqual(harness.calls, [`POST ${kind}`, "GET list"]);
    harness.values[0] = "other-batch"; harness.render(); await flush(); harness.writes.length = 0;
    gate.resolve({ items: [summary], pagination }); await flush(); await flush();
    assert.deepEqual(harness.writes, []); harness.unmount();
  });
}
