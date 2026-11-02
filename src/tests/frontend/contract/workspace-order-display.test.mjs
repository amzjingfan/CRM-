import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";

import { frontendRoot } from "../helpers/paths.mjs";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const ts = require("typescript");

async function displayRules() {
  const source = await readFile(new URL("lib/order-display.ts", frontendRoot), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);
}

test("delivered and completed orders share one completed label, distinct from parcel delivery", async () => {
  const { orderStatusLabel, orderLogisticsStage } = await displayRules();
  for (const status of ["DELIVERED", "COMPLETED"]) {
    assert.equal(orderStatusLabel(status, false), "已完成");
    assert.equal(orderStatusLabel(status, true), "Completed");
  }
  assert.equal(orderLogisticsStage("COMPLETED", null, "Package has been delivered!"), "DELIVERED");
  assert.equal(orderLogisticsStage("COMPLETED", null, "Carrier custom event"), null);
  assert.equal(orderLogisticsStage("IN_TRANSIT", null, "Package has been delivered!"), "IN_TRANSIT");
});

test("carrier follows the matching package rather than the marketplace shipping label", async () => {
  const { orderCarrierLabel } = await displayRules();
  const order = { tracking_number: "TRACK-2", items: [{ package_id: "PKG-2", tracking_number: "TRACK-2" }] };
  const detail = { shipping_provider: "Collections by TikTok", tracking_packages: [
    { package_id: "PKG-1", tracking_number: "TRACK-1", carrier_name: "USPS", events: [] },
    { package_id: "PKG-2", tracking_number: "TRACK-2", carrier_name: "SwiftX", events: [] },
  ] };
  assert.equal(orderCarrierLabel(order, detail, false), "SwiftX");
  assert.equal(orderCarrierLabel({ ...order, items: [...order.items, { package_id: "PKG-1", tracking_number: "TRACK-1" }] }, detail, false), "多家物流商");
  assert.equal(orderCarrierLabel(order, { ...detail, tracking_packages: [] }, false), "—");
  assert.equal(orderCarrierLabel(order, { ...detail, shipping_provider: "FedEx", tracking_packages: [] }, false), "FedEx");
});
