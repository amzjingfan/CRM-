import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const workspace = new URL("../../../frontend/app/workspace/page.tsx", import.meta.url);

test("workspace can reach conversations beyond the first API page", async () => {
  const source = await readFile(workspace, "utf8");
  assert.match(source, /async function loadMoreConversations\(/);
  assert.match(source, /const page = list\.pagination\.page \+ 1;/);
  assert.match(source, /const query = buildListQuery\(page\)/);
  assert.match(source, /requestId !== listRequestId\.current/);
  assert.match(source, /list\.items\.length < list\.pagination\.total/);
  assert.match(source, /加载更多会话/);
});
