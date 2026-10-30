import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

import { frontendRoot } from "../helpers/paths.mjs";

const sourceUrls = {
  agent: new URL("app/agents/page.tsx", frontendRoot),
  api: new URL("lib/api.ts", frontendRoot),
  appShell: new URL("components/AppShell.tsx", frontendRoot),
  css: new URL("app/globals.css", frontendRoot),
  knowledge: new URL("app/knowledge/page.tsx", frontendRoot),
  marketing: new URL("app/marketing/page.tsx", frontendRoot),
  workspace: new URL("app/workspace/page.tsx", frontendRoot),
  customerSidebar: new URL("components/CustomerSidebar.tsx", frontendRoot),
};

function readRequiredSource(sourceName) {
  const sourceUrl = sourceUrls[sourceName];
  assert.equal(
    existsSync(sourceUrl),
    true,
    `Required frontend source is missing: ${sourceUrl.pathname}`,
  );
  return readFileSync(sourceUrl, "utf8");
}

test("Phase 3 required management route sources exist", () => {
  for (const routeName of ["workspace", "knowledge", "marketing", "agent"]) {
    assert.equal(
      existsSync(sourceUrls[routeName]),
      true,
      `Required management route is missing: ${sourceUrls[routeName].pathname}`,
    );
  }
});

test("Phase 3 write operations send idempotency keys", () => {
  const apiSource = readRequiredSource("api");
  assert.match(apiSource, /Idempotency-Key/);
  assert.match(apiSource, /crypto\?\.randomUUID/);
  assert.match(apiSource, /updateKnowledgeEntry/);
  assert.match(apiSource, /updateCampaign/);
  assert.match(apiSource, /updateShippingAddress/);
  assert.match(apiSource, /issueCoupon/);
  assert.match(apiSource, /transferSession/);
});

test("Phase 3 list state and language are persisted", () => {
  const knowledgeSource = readRequiredSource("knowledge");
  const marketingSource = readRequiredSource("marketing");
  const appShellSource = readRequiredSource("appShell");
  assert.match(knowledgeSource, /search.*status.*page/);
  assert.match(marketingSource, /store_id.*page/);
  assert.match(appShellSource, /document\.documentElement\.lang/);
});

test("file import leaves multipart content type to the browser", () => {
  const apiSource = readRequiredSource("api");
  assert.match(apiSource, /init\.body instanceof FormData/);
  assert.match(apiSource, /!isForm/);
});

test("customer sidebar keeps high-risk actions unavailable and coupons draft-only", () => {
  const workspaceSource = readRequiredSource("workspace");
  const sidebarSource = readRequiredSource("customerSidebar");
  assert.match(workspaceSource, /<dialog aria-label=\{en \? "Close conversation" : "关闭会话"\}/);
  assert.doesNotMatch(workspaceSource, /window\.confirm/);
  assert.doesNotMatch(sidebarSource, /issueCoupon|updateShippingAddress|sendMessage/);
  assert.match(sidebarSource, /onDraft\(content\)/);
});

test("knowledge and marketing pages expose loading empty error and AI waiting states", () => {
  const knowledgeSource = readRequiredSource("knowledge");
  const marketingSource = readRequiredSource("marketing");
  for (const source of [knowledgeSource, marketingSource]) {
    assert.match(source, /LoadingState/);
    assert.match(source, /EmptyState/);
    assert.match(source, /ErrorState/);
  }
  assert.match(marketingSource, /waiting_ai/);
});

test("AI marketing drafts require an explicit operator review before any later send", () => {
  const apiSource = readRequiredSource("api");
  const marketingSource = readRequiredSource("marketing");
  assert.match(apiSource, /ai_draft_content/);
  assert.match(apiSource, /ai_review_status/);
  assert.match(apiSource, /reviewMarketingDraft/);
  assert.match(marketingSource, /waiting_review/);
  assert.match(marketingSource, /reviewMarketingDraft/);
  assert.match(marketingSource, /window\.confirm/);
  assert.match(marketingSource, /仅记录审核结论，不会发送消息或发放优惠券/);
  assert.match(apiSource, /reviewMarketingDraft[^\n]+idempotencyKey/);
  assert.match(marketingSource, /reviewMarketingDraft\(item\.id, decision, createIdempotencyKey\(\)\)/);
  assert.match(apiSource, /const stableInit = withStableIdempotencyKey\(init\)/);
  assert.match(apiSource, /rawRequest\(path, stableInit\)/);
});

test("knowledge page exposes BGE vectorization progress and failed retry", () => {
  const apiSource = readRequiredSource("api");
  const knowledgeSource = readRequiredSource("knowledge");
  assert.match(apiSource, /KnowledgeVectorizationStatus/);
  assert.match(apiSource, /getKnowledgeVectorizationStatus/);
  assert.match(apiSource, /retryKnowledgeVectorization/);
  assert.match(knowledgeSource, /BAAI\/bge-m3/);
  assert.match(knowledgeSource, /vectorizationStatus/);
  assert.match(knowledgeSource, /entry\.vectorization_status === "failed"/);
});

test("knowledge publication requires typed semantic approval and stays non-automatic", () => {
  const apiSource = readRequiredSource("api");
  const knowledgeSource = readRequiredSource("knowledge");
  assert.match(apiSource, /KnowledgeStatementType/);
  assert.match(apiSource, /KnowledgeCustomerScope/);
  assert.match(apiSource, /KnowledgePublicationApproval/);
  assert.match(knowledgeSource, /name="statement_type"/);
  assert.match(knowledgeSource, /name="customer_scope"/);
  assert.match(knowledgeSource, /entry\.statement_type === "unknown"/);
  assert.match(knowledgeSource, /FAQ 不会因此获得自动回复权限/);
  assert.match(knowledgeSource, /window\.confirm/);
});

test("knowledge category tree supports parent editing without mobile overflow", () => {
  const apiSource = readRequiredSource("api");
  const knowledgeSource = readRequiredSource("knowledge");
  const cssSource = readRequiredSource("css");
  assert.match(apiSource, /createKnowledgeCategory[\s\S]*parent_id/);
  assert.match(knowledgeSource, /name="parent_id"/);
  assert.match(knowledgeSource, /collectDescendantIds/);
  assert.match(cssSource, /\.category-tree-item[\s\S]*minmax\(0, 1fr\)/);
  assert.match(cssSource, /@media \(max-width: 767px\)[\s\S]*\.category-tree-item/);
  assert.match(cssSource, /\.stack-form \.field[^}]*min-width: 0/);
  assert.match(cssSource, /\.form-row[^}]*minmax\(0, 1fr\)/);
});

test("knowledge and marketing data rows wrap actions without page overflow", () => {
  const cssSource = readRequiredSource("css");
  assert.match(cssSource, /\.data-row[^}]*min-width: 0/);
  assert.match(cssSource, /\.data-row > :not\(\.row-actions\)[^}]*min-width: 0/);
  assert.match(cssSource, /\.row-actions[^}]*flex: 0 1 auto[^}]*flex-wrap: wrap/);
  assert.match(cssSource, /@media \(max-width: 1199px\)[\s\S]*\.marketing-layout \.data-row[^}]*flex-direction: column/);
  assert.match(cssSource, /@media \(max-width: 767px\)[\s\S]*\.data-row > \.row-actions[^}]*width: 100%/);
});

test("async management forms keep a stable form reference across awaits", () => {
  const knowledgeSource = readRequiredSource("knowledge");
  const marketingSource = readRequiredSource("marketing");
  assert.doesNotMatch(knowledgeSource, /event\.currentTarget\.reset\(\)/);
  assert.doesNotMatch(marketingSource, /event\.currentTarget\.reset\(\)/);
  assert.equal((knowledgeSource.match(/submittedForm\.reset\(\)/g) ?? []).length, 2);
  assert.equal((marketingSource.match(/submittedForm\.reset\(\)/g) ?? []).length, 1);
  assert.match(knowledgeSource, /categorySubmitting/);
  assert.match(knowledgeSource, /entrySubmitting/);
  assert.match(marketingSource, /saving/);
  assert.match(knowledgeSource, /role="status"/);
});

test("protected routes quietly handle expected authentication errors", () => {
  const apiSource = readRequiredSource("api");
  const appShellSource = readRequiredSource("appShell");
  const knowledgeSource = readRequiredSource("knowledge");
  const marketingSource = readRequiredSource("marketing");
  assert.match(apiSource, /class ApiError extends Error/);
  assert.match(apiSource, /error\.status === 401/);
  assert.match(appShellSource, /isAuthenticationError\(caught\)/);
  assert.match(appShellSource, /console\.error\("当前用户状态校验失败"/);
  assert.match(knowledgeSource, /!isAuthenticationError\(caught\)/);
  assert.match(marketingSource, /!isAuthenticationError\(caught\)/);
});

test("Agent configuration edits model and seven-section prompt but keeps automated sending unavailable", () => {
  const agentSource = readRequiredSource("agent");
  const apiSource = readRequiredSource("api");
  const sharedPrompt = readFileSync(new URL("../../../frontend/components/AgentPromptFields.tsx", import.meta.url), "utf8");
  assert.match(agentSource, /AgentPromptFields/);
  assert.match(sharedPrompt, /七段式系统提示词/);
  assert.match(agentSource, /发布版本/);
  assert.match(agentSource, /model_provider/);
  assert.match(agentSource, /AgentToolCatalog/);
  assert.match(apiSource, /\/agents\/tool-catalog/);
  assert.match(apiSource, /\/agents/);
  assert.doesNotMatch(agentSource, /name="llm_model"/);
  assert.doesNotMatch(agentSource, /name="auto_reply_threshold"/);
});
