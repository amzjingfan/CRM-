# Task 1 实施报告：环境隔离的 TikTok OAuth 回调

- Phase：Rootless staging deployment
- 任务编号：Task 1
- 主责 Agent：全栈开发工程师 Agent（协作 Agent：无）
- 修改文件：
  - `CRM智能聊天系统/backend/app/shared/config/settings.py`
  - `CRM智能聊天系统/backend/tests/test_real_runtime_config.py`

## 修改内容

新增 production/staging OAuth 回调常量及 `TIKTOK_OAUTH_FIXED_REDIRECT_URIS` 环境映射：integration 与 production 使用 `https://www.hophorsefit.com/v1/integrations/tiktok/oauth/callback`，staging 使用 `https://staging.hophorsefit.com/v1/integrations/tiktok/oauth/callback`。保留 `TIKTOK_OAUTH_FIXED_REDIRECT_URI` 作为 production 兼容别名。真实环境校验现在按 `app_env` 进行精确匹配。

测试覆盖各环境合法回调以及 staging/production 互换回调的拒绝行为。

## 验证结果

- `python -m pytest tests/test_real_runtime_config.py tests/test_tiktok_oauth.py -q`：106 passed
- `python -m ruff check app/shared/config/settings.py tests/test_real_runtime_config.py`：All checks passed
- `git diff --check`：通过

## concerns

无任务范围内遗留问题。真实平台 OAuth、Scope、Token 刷新和平台侧撤销仍属于后续目标环境门禁，不在本任务范围内。
