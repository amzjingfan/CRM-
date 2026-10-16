import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";

const moduleUrl = new URL("../../../frontend/lib/message-display.ts", import.meta.url);
const require = createRequire(moduleUrl);
const ts = require("typescript");
const compiled = ts.transpileModule(readFileSync(moduleUrl, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { messageSide, senderLabel } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);

test("TikTok history distinguishes buyer, human agent, robot, and system", () => {
  assert.deepEqual(
    ["user", "agent", "assistant", "system"].map((role) => [senderLabel(role, false), messageSide(role)]),
    [["买家", "incoming"], ["客服", "outgoing"], ["机器人", "outgoing"], ["系统", "system"]],
  );
});
