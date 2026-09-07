import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const composeSource = await readFile(
  new URL("../../docker-compose.yml", import.meta.url),
  "utf8",
);
const aiComposeSource = await readFile(
  new URL("../../docker-compose.ai.yml", import.meta.url),
  "utf8",
);
const modelDockerfile = await readFile(
  new URL("../../Dockerfile.model-service", import.meta.url),
  "utf8",
);

test("frontend container isolates the Next.js build directory from the host", () => {
  assert.match(composeSource, /frontend_next_cache:\/app\/\.next/);
  assert.match(composeSource, /^\s{2}frontend_next_cache:\s*$/m);
});

test("BGE jobs wait for the single model service and model container is non-root", () => {
  assert.match(aiComposeSource, /jobs:[\s\S]*retrieval-model-service:[\s\S]*condition: service_healthy/);
  assert.match(aiComposeSource, /EMBEDDING_ENABLED: "true"/);
  assert.match(modelDockerfile, /USER app/);
});
