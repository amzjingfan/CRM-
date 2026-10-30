import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { frontendRoot } from "../helpers/paths.mjs";

test("TikTok authorization has one add-store entry and no standalone OAuth card", async () => {
  const page = await readFile(new URL("app/settings/channels/page.tsx", frontendRoot), "utf8");
  const storesPage = await readFile(new URL("app/settings/stores/page.tsx", frontendRoot), "utf8");
  const api = await readFile(new URL("lib/api.ts", frontendRoot), "utf8");

  assert.equal(api.includes("/settings/channels/tiktok/oauth/start?store_id="), true);
  assert.equal(page.includes("startTikTokOAuth(channel.store_id, \"/settings/stores\")"), true);
  assert.equal(page.includes("window.location.assign(result.authorization_url)"), true);
  assert.equal(page.includes("TikTok Shop OAuth</h2>"), false);
  assert.equal(page.includes("selectedStoreId"), false);
  assert.equal(storesPage.includes("startNewTikTokStoreOAuth()"), true);
});

test("TikTok channel page displays only low-sensitive authorization state", async () => {
  const page = await readFile(new URL("app/settings/channels/page.tsx", frontendRoot), "utf8");

  assert.equal(page.includes("channel.scopes"), true);
  assert.equal(page.includes("channel.last_sync_at"), true);
  assert.equal(page.includes('status === "connected"'), true);
  assert.equal(page.includes("/settings/stores?${params.toString()}"), true);
  assert.equal(page.includes("localStorage"), false);
});

test("TikTok store list starts direct OAuth and keeps deletion as revocation", async () => {
  const page = await readFile(new URL("app/settings/stores/page.tsx", frontendRoot), "utf8");
  const api = await readFile(new URL("lib/api.ts", frontendRoot), "utf8");

  assert.match(api, /\/settings\/stores\/tiktok\/oauth\/start/);
  assert.match(page, /startNewTikTokStoreOAuth\(\)/);
  assert.match(page, /startTikTokOAuth\(storeId, "\/settings\/stores"\)/);
  assert.match(page, /deleteChannel\(deleteRow\.channel\.id\)/);
  assert.match(page, /updateStoreAlias\(storeId, aliasDraft\.trim\(\) \|\| null\)/);
  assert.match(page, /authorization_expires_at/);
  assert.match(page, /external_store_id/);
  assert.doesNotMatch(page, /createStore/);
});

test("multi-shop OAuth asks for explicit shop selection and sends only selected IDs", async () => {
  const page = await readFile(new URL("app/settings/stores/page.tsx", frontendRoot), "utf8");
  const api = await readFile(new URL("lib/api.ts", frontendRoot), "utf8");

  assert.match(page, /result\.status === "selection_required"/);
  assert.match(page, /selectTikTokOAuthShops\(selection\.jobId, selectedShopIds\)/);
  assert.match(page, /type="checkbox"/);
  assert.match(page, /aria-modal="true"/);
  assert.match(api, /\/settings\/channels\/tiktok\/oauth\/jobs\/\$\{encodeURIComponent\(jobId\)\}\/shops/);
  assert.doesNotMatch(page, /selection_token_cipher|shop_cipher|refresh_token/);
});
