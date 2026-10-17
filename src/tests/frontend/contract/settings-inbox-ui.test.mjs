import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";

import { frontendRoot } from "../helpers/paths.mjs";

const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const ts = require("typescript");

test("conversation list formats the real last-message timestamp and omits invalid dates", async () => {
  const source = await readFile(new URL("lib/conversationTime.ts", frontendRoot), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  const { formatConversationTime } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);
  const timestamp = "2026-10-17T05:08:00Z";
  const actual = formatConversationTime(timestamp, "zh-CN");
  const local = new Date(timestamp);
  const expected = `${String(local.getMonth() + 1).padStart(2, "0")}-${String(local.getDate()).padStart(2, "0")} ${String(local.getHours()).padStart(2, "0")}:${String(local.getMinutes()).padStart(2, "0")}`;
  assert.equal(actual, expected);
  assert.equal(formatConversationTime(null, "zh-CN"), null);
  assert.equal(formatConversationTime("invalid", "zh-CN"), null);

  const page = await readFile(new URL("app/workspace/page.tsx", frontendRoot), "utf8");
  assert.match(page, /formatConversationTime\(item\.last_message_at/);
  assert.match(page, /<time className="conversation-time"/);
});

test("settings navigation links only to supported pages", async () => {
  const nav = await readFile(new URL("components/SettingsNav.tsx", frontendRoot), "utf8");
  assert.match(nav, /\/settings\/stores/);
  assert.match(nav, /\/settings\/channels/);
  assert.match(nav, /\/settings\/team/);
  assert.doesNotMatch(nav, /\/settings\/(departments|blacklist|sensitive-words)/);
});
