import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { frontendRoot } from "../helpers/paths.mjs";

const read = (path) => readFile(new URL(path, frontendRoot), "utf8");

test("Phase 4 dashboard has an accessible chart and table fallback", async () => {
  const source = await read("app/dashboard/page.tsx");
  assert.match(source, /Conversation trend line chart/);
  assert.match(source, /会话趋势折线图/);
  assert.match(source, /查看数据表/);
  assert.match(source, /View data table/);
  assert.match(source, /渠道分布/);
  assert.match(source, /Channel distribution/);
  assert.match(source, /实时预警/);
  assert.match(source, /Live alerts/);
});

test("settings pages cover stores channels and team", async () => {
  const sources = await Promise.all([
    read("app/settings/stores/page.tsx"),
    read("app/settings/channels/page.tsx"),
    read("app/settings/team/page.tsx"),
  ]);
  assert.match(sources[0], /createStore/);
  assert.match(sources[0], /Store list/);
  assert.match(sources[1], /契约级 Mock/);
  assert.match(sources[1], /Store authorizations/);
  assert.match(sources[2], /disableTeamMember/);
  assert.match(sources[2], /deleteTeamMember/);
  assert.match(sources[2], /status-badge/);
  assert.match(sources[2], /永久删除/);
  assert.match(sources[2], /Account management/);
});

test("Phase 4 English mode covers Agent forms and workspace SSE content", async () => {
  const [agent, workspace] = await Promise.all([
    read("app/agents/page.tsx"),
    read("app/workspace/page.tsx"),
  ]);
  assert.match(agent, /Allowed tools/);
  assert.match(agent, /Save operations configuration/);
  assert.match(workspace, /AI reply suggestion/);
  assert.match(workspace, /Suggestion inserted; review it before sending/);
  assert.match(workspace, /Transfer to human/);
});

test("workspace ignores stale detail, updates read state, and clears filtered-out selection", async () => {
  const source = await read("app/workspace/page.tsx");
  assert.match(source, /let isCurrentRequest = true/);
  assert.match(source, /return \(\) => \{ isCurrentRequest = false; \}/);
  assert.match(source, /item\.id === selectedId \? \{ \.\.\.item, unread_count: 0 \}/);
  assert.match(source, /setSelectedId\(\(current\) => data\.items\.some\(\(item\) => item\.id === current\)/);
});

test("application shell exposes a retryable authentication error state", async () => {
  const source = await read("components/AppShell.tsx");
  assert.match(source, /setAuthError/);
  assert.match(source, /setAuthRetry\(\(value\) => value \+ 1\)/);
  assert.match(source, /暂时无法进入管理台/);
});

test("Agent tool codes use readable Chinese labels", async () => {
  const agent = await read("app/agents/page.tsx");
  for (const label of ["查询订单", "查询物流", "查询客户资料", "修改收货地址", "发送优惠券", "转人工", "发送平台消息"]) {
    assert.match(agent, new RegExp(label));
  }
  assert.match(agent, /name=\{tool\}/);
});

test("interactive filters and compact fields meet the 44px touch target", async () => {
  const css = await read("app/globals.css");
  assert.match(css, /\.filter\s*\{[^}]*min-height:\s*44px/);
  assert.match(css, /\.compact-field\s*\{[^}]*min-height:\s*44px/);
  assert.doesNotMatch(css, /\.compact-field\s*\{[^}]*min-height:\s*40px/);
});

test("SSE uses cookie CSRF transport and abort support", async () => {
  const [api, workspace] = await Promise.all([
    read("lib/api.ts"),
    read("app/workspace/page.tsx"),
  ]);
  assert.match(api, /X-CSRF-Token/);
  assert.match(api, /credentials: "include"/);
  assert.match(api, /signal: AbortSignal/);
  assert.match(api, /TextDecoder\("utf-8"\)/);
  assert.match(api, /replaceAll\("\\r\\n", "\\n"\)/);
  assert.match(api, /terminalReceived/);
  assert.match(api, /reader\.cancel/);
  assert.match(api, /AI 建议响应格式无效，请重试/);
  assert.match(workspace, /cancelSuggestion/);
  assert.match(workspace, /已取消生成/);
  assert.match(workspace, /aria-live="polite"/);
});

test("management shell follows the prototype information architecture", async () => {
  const source = await read("components/AppShell.tsx");
  for (const label of ["数据看板", "客服工作台", "知识库", "智能营销", "Agent 管理", "系统配置"]) {
    assert.match(source, new RegExp(label));
  }
  assert.match(source, /@phosphor-icons\/react/);
  assert.doesNotMatch(source, /className="topbar"/);
});

test("knowledge and marketing pages implement the prototype while keeping live APIs", async () => {
  const [knowledge, marketing] = await Promise.all([
    read("app/knowledge/page.tsx"),
    read("app/marketing/page.tsx"),
  ]);
  assert.match(knowledge, /knowledge-layout/);
  assert.match(knowledge, /category_id/);
  assert.match(knowledge, /editor-modal/);
  assert.match(marketing, /campaign-grid/);
  assert.match(marketing, /marketing-report/);
  assert.match(marketing, /getDashboardMetrics/);
});

test("knowledge layers are interactive, URL-backed, and protected from stale responses", async () => {
  const [knowledge, css] = await Promise.all([
    read("app/knowledge/page.tsx"),
    read("app/globals.css"),
  ]);
  assert.match(knowledge, /selectedLayer/);
  assert.match(knowledge, /query\.set\("layer", selectedLayer\)/);
  assert.match(knowledge, /setSelectedLayer\(layer\.key\)/);
  assert.match(knowledge, /loadRequestId/);
  assert.match(css, /\.tree-layer-title\.active/);
  assert.match(css, /@media \(max-width: 1399px\)[\s\S]*\.prototype-page-header > \.prototype-title[^}]*flex: 1 0 100%/);
});
