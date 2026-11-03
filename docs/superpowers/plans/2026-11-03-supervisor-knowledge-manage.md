# 客服主管管理部门知识库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 主管可管理所属客服部全部有效店铺的知识库，跨店铺权限仍按资源归属验证。

**Spec:** [2026-11-03-supervisor-knowledge-manage-design.md](../specs/2026-11-03-supervisor-knowledge-manage-design.md)

## Global Constraints

- 普通客服、Agent 配置、消息发送权限不变。
- 既有知识库 CSRF、幂等、审计、审批与跨店铺 404 规则不变。
- 迁移可回滚；测试放在 `src/tests/`。

## Review Focus

- 多店铺主管：部门内第二家店铺可管理知识。
- 部门外店铺：即使有另一个角色的店铺访问权，不能写知识。
- 撤权：主管角色或部门成员关系撤销后不能写。
- 资源 ID：更新、删除、审核时不能跨店操作。
- 列表：主管只读取获授权部门店铺，普通客服不获得管理权。

### Task 1: 店铺级知识权限与迁移

**Files:** `src/backend/app/auth/store_access.py`、`src/backend/migrations/versions/051_supervisor_knowledge_manage.py`、`src/tests/backend/auth_security/test_supervisor_knowledge_access.py`

- [ ] 先写失败行为测试：主管在部门内两店有 `knowledge.manage`，部门外无；撤销角色/成员资格后无；普通客服无。
- [ ] 运行该测试并确认因当前行为失败。
- [ ] 扩展 `allowed_store_ids_for_permission(session, user, permission_code)` 的知识权限范围；迁移将已有 `knowledge.manage` 授予主管并提供逆迁移。
- [ ] 重跑测试通过；核对迁移升级与回滚。
- [ ] 提交本任务代码与测试。

### Task 2: 知识资源写路径按权限码校验

**Files:** `src/backend/app/knowledge_base/service.py`、`src/backend/app/knowledge_base/document_service.py`、相关 `src/tests/backend/knowledge_base/` 行为测试。

- [ ] 先写失败行为测试：创建、更新和审批只允许 `knowledge.manage` 对应店铺，跨店资源为 404。
- [ ] 运行该测试并确认失败。
- [ ] 将知识写路径的通用店铺检查改为 `knowledge.manage` 的目标店铺检查，读取路径使用 `knowledge.view`；不改变写入业务规则。
- [ ] 重跑知识库与权限回归测试，通过后提交。

### Task 3: 文档、门禁与集成

**Files:** `docs/architecture/API.md`、`docs/product/PRODUCT.md`、`docs/tasks/TASKS.md`、本次 IR/TR/RR 与索引。

- [ ] 同步主管知识库权限及范围，登记任务和证据。
- [ ] 运行适用的格式、类型、后端权限及知识库测试、迁移检查；记录真实结果和未运行项。
- [ ] 审查差异与安全边界，提交证据，按仓库门禁创建 PR 并合入目标主线。

本计划不包含 staging 或 production 部署。
