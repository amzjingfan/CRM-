import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { frontendRoot, repositoryRoot, sourceRoot } from "../helpers/paths.mjs";

const composeSource = await readFile(
  new URL("compose/docker-compose.yml", sourceRoot),
  "utf8",
);
const productionComposeSource = await readFile(
  new URL("compose/docker-compose.prod.yml", sourceRoot),
  "utf8",
);
const tiktokEgressComposeSource = await readFile(
  new URL("compose/docker-compose.tiktok-egress.yml", sourceRoot),
  "utf8",
);
const aiComposeSource = await readFile(
  new URL("compose/docker-compose.ai.yml", sourceRoot),
  "utf8",
);
const modelDockerfile = await readFile(
  new URL("docker/Dockerfile.model-service", sourceRoot),
  "utf8",
);
const productionFrontendDockerfile = await readFile(
  new URL("docker/Dockerfile.frontend.prod", sourceRoot),
  "utf8",
);
const productionReadmeSource = await readFile(
  new URL("deploy/production/README.md", sourceRoot),
  "utf8",
);
const packageJson = JSON.parse(
  await readFile(new URL("package.json", frontendRoot), "utf8"),
);

function composeServiceBlock(composeText, serviceName) {
  const lines = composeText.split(/\r?\n/);
  const start = lines.indexOf(`  ${serviceName}:`);
  assert.notEqual(start, -1, `missing Compose service: ${serviceName}`);

  const block = [lines[start]];
  for (const line of lines.slice(start + 1)) {
    if (/^  [^ ].*:$/.test(line)) {
      break;
    }
    block.push(line);
  }
  return block.join("\n");
}

test("frontend container isolates the Next.js build directory from the host", () => {
  assert.match(composeSource, /frontend_next_cache:\/app\/\.next/);
  assert.match(composeSource, /^\s{2}frontend_next_cache:\s*$/m);
});

test("BGE jobs wait for the single model service and model container is non-root", () => {
  assert.match(aiComposeSource, /jobs:[\s\S]*retrieval-model-service:[\s\S]*condition: service_healthy/);
  assert.match(aiComposeSource, /EMBEDDING_ENABLED: "true"/);
  assert.match(modelDockerfile, /USER app/);
});

test("frontend uses the supported Next.js security release", () => {
  assert.equal(packageJson.dependencies.next, "16.3.4");
  assert.equal(packageJson.devDependencies["eslint-config-next"], "16.3.4");
});

test("production frontend build pins the Node image manifest digest", () => {
  assert.match(
    productionFrontendDockerfile,
    /^ARG NODE_IMAGE=node:20\.19\.4-alpine3\.22@sha256:[0-9a-f]{64}$/m,
  );
});

test("retrieval model build pins the uv base image manifest digest", () => {
  assert.match(
    modelDockerfile,
    /^FROM ghcr\.io\/astral-sh\/uv:python3\.11-bookworm-slim@sha256:[0-9a-f]{64}$/m,
  );
});

test("production infrastructure images use immutable registry digests", () => {
  const expectedReferences = [
    "pgvector/pgvector:0.8.0-pg16@sha256:a132765ec351c65111b5b675928a3a0515a466a40f97277329db8b8209ad8bc9",
    "redis:7.4.2-alpine@sha256:02419de7eddf55aa5bcf49efb74e88fa8d931b4d77c07eff8a6b2144472b6952",
    "minio/minio:RELEASE.2025-04-22T22-12-26Z@sha256:a1ea29fa28355559ef137d71fc570e508a214ec84ff8083e39bc5428980b015e",
    "nginx:1.27.5-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10",
  ];

  for (const reference of expectedReferences) {
    assert.ok(
      productionComposeSource.includes(reference),
      `missing immutable image reference: ${reference}`,
    );
  }
});

test("production application services consume published images without local builds", () => {
  for (const serviceName of ["backend", "worker", "jobs", "agent-worker"]) {
    const block = composeServiceBlock(productionComposeSource, serviceName);
    assert.match(block, /image: \$\{BACKEND_IMAGE:\?/);
    assert.match(block, /build: !reset null/);
  }

  const frontendBlock = composeServiceBlock(productionComposeSource, "frontend");
  assert.match(frontendBlock, /image: \$\{FRONTEND_IMAGE:\?/);
  assert.match(frontendBlock, /build: !reset null/);

  const retrievalBlock = composeServiceBlock(
    productionComposeSource,
    "retrieval-model-service",
  );
  assert.match(retrievalBlock, /image: \$\{RETRIEVAL_MODEL_SERVICE_IMAGE:\?/);
  assert.match(retrievalBlock, /build: !reset null/);
  assert.doesNotMatch(productionReadmeSource, /up -d --build/);
});

test("TikTok-capable services wait for fixed egress without receiving SSH secrets", () => {
  for (const serviceName of ["backend", "worker", "jobs"]) {
    const block = composeServiceBlock(tiktokEgressComposeSource, serviceName);
    assert.match(block, /TIKTOK_EGRESS_PROXY_URL: socks5h:\/\/tiktok-egress:1080/);
    assert.match(block, /networks:\s+\- default\s+\- tiktok-egress/);
    assert.match(block, /tiktok-egress:\s+condition: service_healthy/);
    assert.doesNotMatch(block, /\/run\/secrets\/tiktok-egress/);
    assert.doesNotMatch(block, /TIKTOK_EGRESS_SECRET_DIR/);
  }
});

test("GHCR publisher uses least privilege and immutable GitHub Actions", async () => {
  const workflow = await readFile(
    new URL(".github/workflows/publish-images.yml", repositoryRoot),
    "utf8",
  );

  assert.match(workflow, /packages: write/);
  assert.match(workflow, /contents: read/);
  assert.match(workflow, /ghcr\.io\/cp11-gh\/crm-backend/);
  assert.match(workflow, /ghcr\.io\/cp11-gh\/crm-frontend/);
  assert.match(workflow, /ghcr\.io\/cp11-gh\/crm-retrieval-model-service/);
  assert.match(workflow, /github\.ref == 'refs\/heads\/main'/);
  assert.match(workflow, /environment:\s+image-publishing/);
  assert.doesNotMatch(workflow, /^permissions:[\s\S]{0,80}packages: write/m);
  assert.match(workflow, /git fetch --no-tags --depth=1 origin main/);
  assert.match(workflow, /"\$SOURCE_SHA" != "\$main_sha"/);
  assert.doesNotMatch(workflow, /uses:\s+[^\s]+@(v\d+|main|master)\s*$/m);
  for (const line of workflow.match(/^\s*uses:\s+.*$/gm) ?? []) {
    assert.match(line, /@[0-9a-f]{40}(?:\s+#.*)?$/);
  }
});

test("staging workflow cannot target production or a generic hosted runner", async () => {
  const workflow = await readFile(
    new URL(".github/workflows/staging-gates.yml", repositoryRoot),
    "utf8",
  );

  assert.match(workflow, /environment:\s+staging/);
  assert.match(workflow, /runs-on:\s*\[self-hosted, linux, x64, crm-staging\]/);
  assert.match(workflow, /CONFIRM_TARGET -ne "staging"/);
  assert.match(workflow, /\["ConfirmTarget"\]\s*=\s*"staging"/);
  assert.match(workflow, /CandidateRetrievalModelImage/);
  assert.match(workflow, /PreviousRetrievalModelImage/);
  assert.match(workflow, /packages: read/);
  assert.doesNotMatch(workflow, /docker\/login-action@/);
  assert.match(workflow, /docker login ghcr\.io/);
  assert.match(workflow, /--password-stdin/);
  assert.match(workflow, /GHCR_USERNAME: \$\{\{ github\.actor \}\}/);
  assert.match(workflow, /GHCR_TOKEN: \$\{\{ secrets\.GITHUB_TOKEN \}\}/);
  assert.match(workflow, /DOCKER_CONFIG: \$\{\{ runner\.temp \}\}\/crm-staging-docker-config/);
  assert.match(workflow, /docker logout ghcr\.io/);
  assert.match(workflow, /if: \$\{\{ always\(\) && \(steps\.verify_dispatch_commit\.outcome == 'success' \|\| steps\.verify_prefetch_source\.outcome == 'success'\) \}\}/);
  assert.doesNotMatch(workflow, /if: \$\{\{ always\(\) \}\}/);
  assert.doesNotMatch(workflow, /ubuntu-latest/);
  assert.doesNotMatch(workflow, /environment:\s+production/);
});

test("published image evidence binds available GHCR RepoDigests to one source commit", async () => {
  const evidence = JSON.parse(
    await readFile(
      new URL("release/images/mvp-production-gates.json", repositoryRoot),
      "utf8",
    ),
  );

  assert.match(evidence.source_sha, /^[0-9a-f]{40}$/);
  assert.match(
    evidence.application_images.backend.reference,
    /^ghcr\.io\/cp11-gh\/crm-backend@sha256:[0-9a-f]{64}$/,
  );
  assert.match(
    evidence.application_images.frontend.reference,
    /^ghcr\.io\/cp11-gh\/crm-frontend@sha256:[0-9a-f]{64}$/,
  );
  assert.match(
    evidence.application_images.retrieval_model.reference,
    /^ghcr\.io\/cp11-gh\/crm-retrieval-model-service@sha256:[0-9a-f]{64}$/,
  );
  assert.equal(evidence.evidence_status, "final_main_images_published");
  assert.equal(evidence.final_main_publish_required, false);
  assert.equal(evidence.production_release, false);
});
