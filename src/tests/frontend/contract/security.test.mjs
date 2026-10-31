import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { frontendRoot } from "../helpers/paths.mjs";

test("browser authentication never stores JWT in localStorage", async () => {
  const sources = await Promise.all([
    readFile(new URL("lib/api.ts", frontendRoot), "utf8"),
    readFile(new URL("app/login/page.tsx", frontendRoot), "utf8"),
  ]);
  const code = sources.join("\n");
  assert.equal(code.includes('localStorage.setItem("crm_access_token"'), false);
  assert.equal(code.includes('localStorage.setItem("crm_refresh_token"'), false);
  assert.equal(code.includes('credentials: "include"'), true);
});

test("workspace SSE suggestion fills the composer without automatic sending", async () => {
  const source = await readFile(new URL("app/workspace/page.tsx", frontendRoot), "utf8");
  const replyReview = await readFile(new URL("components/ReplyReviewPanel.tsx", frontendRoot), "utf8");
  const api = await readFile(new URL("lib/api.ts", frontendRoot), "utf8");
  assert.equal(api.includes('streamApiQuery("/chat/query"'), true);
  assert.equal(api.includes("ReadableStream"), false);
  assert.equal(api.includes("response.body.getReader()"), true);
  assert.equal(source.includes("<ReplyReviewPanel"), true);
  assert.equal(source.includes("setDraft(text)"), true);
  assert.equal(replyReview.includes("latest.current.onUse(verified[0])"), true);
  assert.equal(source.includes("建议已填入输入框，确认后再发送"), true);
  assert.equal(source.includes("submitMessage(suggestionDraft"), false);
  assert.equal(replyReview.includes("submitMessage("), false);
});

test("manual platform messages require confirmation and expose uncertain delivery", async () => {
  const source = await readFile(new URL("app/workspace/page.tsx", frontendRoot), "utf8");
  const api = await readFile(new URL("lib/api.ts", frontendRoot), "utf8");
  assert.equal(api.includes("JSON.stringify({ content, confirmed: true })"), true);
  assert.equal(source.includes('aria-label={en ? "Review outgoing message" : "审阅外发消息"}'), true);
  assert.equal(source.includes("onClick={() => void submitMessage(review.content, review.key, review.sessionId)}"), true);
  assert.equal(source.includes("真实 TikTok 客户"), true);
  assert.equal(source.includes("发送结果未知，请勿重试并前往 TikTok 人工对账"), true);
  assert.equal(source.includes("detail.send_mode === \"disabled\""), true);
});
