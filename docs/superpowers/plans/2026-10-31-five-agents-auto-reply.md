# 五类 Agent 模板与自动回复预演 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 五个共享模板可用，商品工具只返回有货商品，店铺多 Agent 自动回复在本地形成待审阅草稿，staging 实测后清理合成数据。

**Architecture:** 复用现有模板生命周期和动态 Agent 路由；商品过滤留在共用平台投影与 Agent 详情边界；店铺预演策略驱动现有入站任务和正式多 Agent 链路，禁止自动平台发送。

**Tech Stack:** FastAPI、SQLAlchemy/PostgreSQL、LangChain `@tool`、Next.js/TypeScript、pytest、Playwright。

**Spec:** `docs/superpowers/specs/2026-10-31-five-agents-auto-reply.md`

## Global Constraints

- `BASE_SHA=59233e0f880cab1750b9f8868e655dfb1fd466f5`; merge target `origin/main`。
- 真实外发和生产发布不在本轮测试；自动回复预演默认关闭，不扩大已有单店人工发送权限。
- 测试源码、fixture 和临时输出只在 `src/tests/`；本轮合成数据清理，五个共享模板保留。

## Review Focus

- 商品库存未知、混合有货/无货 SKU 与分页不能泄露缺货规格。
- 切换店铺、撤销权限、停用 Agent 后，排队任务不能读取/发送越权内容。
- 同一入站消息重投不得重复任务或重复建议；模型失败不计为兜底三轮。
- 发布模板不能复制跨店文件 ID；未审批文件不能被 Agent 引用。
- 物流更新普通买家问题与真正新节点必须分开，重复节点不产生通知。

### Task 1: 商品有货投影

**Files:** `src/backend/app/agents/tools/product_facts.py`、`src/backend/app/workspace/sidebar.py`、`src/tests/backend/agent/test_agent_business_tools.py`、`src/tests/backend/domain/test_workspace_catalog_availability.py`。

- [ ] 写混合 SKU、零/未知库存、下架与详情翻页失败用例并确认 RED。
- [ ] 在搜索候选与详情的共同边界只暴露上架且正库存的商品和 SKU，维持平台总量与当前页匹配数的区别。
- [ ] 运行受影响 pytest、Ruff 和 mypy，检查工作台既有商品入口兼容。

### Task 2: 五模板与路由语义

**Files:** `app/agents/management/templates/*`、`app/agents/management/{schemas,service,models}.py`、`app/agents/orchestration/{router,service}.py`、迁移（若需）、`src/tests/backend/agent/`、`src/tests/integration/postgres/`。

- [ ] 写业务/事件/兜底用途、模型路由及同会话第三轮按买家语言输出固定内容（英文原文、中文固定版本、不自由改写）的失败用例。
- [ ] 配置用途随模板发布和店铺 Agent 发布冻结；普通问题先路由所有本店业务 Agent，兜底后置，物流事件走通知链路，失败不累计。
- [ ] 创建四个新模板的可重复配置清单；保留并核对原订单物流模板，七段提示词、工具和逐店知识槽完整。
- [ ] 运行模板、路由、记忆、迁移和隔离数据库验证。

### Task 3: 店铺多 Agent 自动回复预演

**Files:** `app/agents/management/` 下策略模型/服务/路由、`app/integrations/service.py`、`app/chat/worker.py`、`app/chat/service.py`、前端 Agent 配置页/API 类型、迁移、`src/tests/`。

- [ ] 写策略默认关闭、授权/CSRF/乐观锁/审计、入站幂等、撤权、无 Agent 与无外发的失败用例。
- [ ] 实现店铺级预演开关，任务调用现有正式多 Agent 运行并保存坐席可读结果；不将草稿当作买家消息，不触发平台发送。
- [ ] Agent 设置页展示准确的预演状态与开关，工作台显示已复核待审阅建议；前后端契约与浏览器测试。
- [ ] 本地用合成数据验证双 Agent 路由、工具、知识、结果和零外发；运行全量受影响静态/单元/集成/构建测试。

### Task 4: 一次交付、真实验收与清理

**Files:** `docs/tasks/TASKS.md`、当前产品/API/AI/部署/质量文档、IR/TR/RR、`release/evidence/staging/`。

- [ ] 汇总本地所有失败后统一修复；最终候选复测、审查、安全与回滚检查，按适用 CI 或零步骤本地替代门禁合并。
- [ ] 对固定提交构建镜像、私有备份、双预检、手动部署一次；健康、迁移与原开关状态核对。
- [ ] 在 TikTok US 测试店铺逐模板完成预览及工作台 AI 建议真实测试，核对实际工具轨迹和知识引用；物流新节点使用专用预演；中英文及门禁负例覆盖。
- [ ] 清理并核对本轮合成 Agent、文件、会话和策略，保留五个共享模板及原业务数据；定稿低敏证据、任务状态和恢复摘要。
