import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { frontendRoot } from "../helpers/paths.mjs";

test("TikTok channel uses server OAuth instead of browser credential input", async () => {
  const page = await readFile(new URL("app/settings/channels/page.tsx", frontendRoot), "utf8");
  const api = await readFile(new URL("lib/api.ts", frontendRoot), "utf8");

  assert.equal(api.includes("/settings/channels/tiktok/oauth/start?store_id="), true);
  assert.equal(page.includes("startTikTokOAuth(selectedStoreId)"), true);
  assert.equal(page.includes("window.location.assign(result.authorization_url)"), true);
  assert.equal(page.includes('value="tiktok"'), false);
  const oauthCard = page.split("<h3>TikTok Shop OAuth</h3>")[1].split("</article>")[0];
  assert.equal(oauthCard.includes("access_token_ref"), false);
  assert.equal(oauthCard.includes("refresh_token"), false);
});

test("TikTok channel page displays only low-sensitive authorization state", async () => {
  const page = await readFile(new URL("app/settings/channels/page.tsx", frontendRoot), "utf8");

  assert.equal(page.includes("channel.scopes"), true);
  assert.equal(page.includes("channel.last_sync_at"), true);
  assert.equal(page.includes('status === "connected"'), true);
  assert.equal(page.includes("getTikTokOAuthJobStatus(jobId)"), true);
  assert.equal(page.includes("window.history.replaceState"), true);
  assert.equal(page.includes("localStorage"), false);
});
