# 清理批次索引

本索引是 `docs/operations/cleanup/` 下清理批次的派生视图；批次记录与 JSON manifest 是事实源。

| Batch ID | Task ID | State | Scope | Retention until | Updated | Record |
|---|---|---|---|---|---|---|
| CLEANUP-20260916-001 | MAINT-CLEANUP-20260916-001 | VERIFIED_UNUSED | 根目录本地生成残留 | 2026-09-23T14:00:00+08:00 | 2026-09-16 | [记录](CLEANUP-20260916-001.md) |
| CLEANUP-20260916-002 | MAINT-CLEANUP-20260916-002 | VERIFIED_UNUSED | 旧后端测试根 pytest 缓存 | 2026-09-23T18:05:00+08:00 | 2026-09-16 | [记录](CLEANUP-20260916-002.md) |
| CLEANUP-20260921-003 | MAINT-CLEANUP-20260921-003 | QUARANTINED | 入口服务器 `/root` CRM 备份与退役残留 | 备份永久保留；隔离物不早于 2026-09-28T14:37:17+08:00 | 2026-09-21 | [记录](CLEANUP-20260921-003.md) |
