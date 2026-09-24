import assert from "node:assert/strict";
import { test } from "node:test";

const baseUrl = process.env.UI_BASE_URL ?? "http://127.0.0.1:3101";
const target = new URL(baseUrl);
if (!["127.0.0.1", "localhost", "::1"].includes(target.hostname)) {
  throw new Error("HTML cache regression only runs against a local server");
}

test("CRM HTML documents cannot retain an obsolete build", async () => {
  for (const path of ["/login", "/marketing", "/settings/stores"]) {
    const response = await fetch(new URL(path, baseUrl), { headers: { Accept: "text/html" } });
    assert.equal(response.status, 200, path);
    assert.match(response.headers.get("content-type") ?? "", /text\/html/i, path);
    assert.match(response.headers.get("cache-control") ?? "", /(?:^|,)\s*no-store(?:,|$)/i, path);
  }
});

test("fingerprinted Next.js chunks remain immutable in production", {
  skip: process.env.UI_CACHE_EXPECT_PRODUCTION === "1" ? false : "Set UI_CACHE_EXPECT_PRODUCTION=1 against a production build",
}, async () => {
  const document = await fetch(new URL("/marketing", baseUrl));
  const html = await document.text();
  const scriptPath = html.match(/src="(\/_next\/static\/chunks\/[^"?]+\.js)"/)?.[1];
  assert.ok(scriptPath, "marketing HTML must reference a versioned JavaScript chunk");
  const script = await fetch(new URL(scriptPath, baseUrl));
  assert.equal(script.status, 200);
  assert.match(script.headers.get("cache-control") ?? "", /immutable/i);
});
