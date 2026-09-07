# Phase 4 P4-10 M04 BGE 模型服务性能测试报告

## 1. 测试基本信息

| 项目 | 内容 |
| --- | --- |
| Phase | Phase4 |
| 任务编号 | P4-10；关联 Phase2 P2-03、P2-07 |
| 模块编号 | M04 |
| 模块名称 | BGE 本地检索模型服务 |
| 被测主责 Agent | AIAgent开发工程师Agent |
| 被测协作 Agent | 全栈开发工程师Agent、架构师Agent |
| 测试执行 Agent | 测试工程师 Agent |
| 关联实施记录 | `共享记忆文档/实施记录/Phase2-P2-03-AIAgent开发工程师Agent-BGE混合检索与重排序-002.md`、`共享记忆文档/实施记录/Phase2-P2-04-全栈开发工程师Agent-BGE知识库运行面适配-001.md` |
| 测试类型 | 性能测试、压力测试、回归测试 |
| 执行日期 | 2026-08-21 |
| 测试结论 | 通过 |

## 2. 测试目标与门禁

验证 RTX 4060 8 GB 单实例部署下：

- 批量 32 向量化和候选 20 重排序不会 OOM。
- 50 个并发 HTTP 请求全部成功。
- P95 和任务拆解要求的 P99 均小于 5 秒。
- 记录端到端吞吐、冷启动和显存峰值。
- 服务日志中无 CUDA OOM、模型加载失败或致命堆栈。

## 3. 环境与方法

| 项目 | 实际环境 |
| --- | --- |
| GPU | NVIDIA GeForce RTX 4060，8188 MB |
| 模型 | BGE-M3 1024 维 + bge-reranker-large，固定 Revision |
| 推理依赖 | Torch 2.13.0+cu130、Transformers 5.5.4、FP16 |
| 部署 | Docker Compose + `docker-compose.gpu.yml`，单 Worker、单模型实例 |
| 并发客户端 | 64 连接池，50 个请求同时发起 |
| Embedding 负载 | 每请求 1 条短文本 |
| Reranker 负载 | 每请求 20 个候选，覆盖生产候选上限 |
| 延迟口径 | 客户端端到端 wall clock，nearest-rank 百分位 |
| 原始证据 | `测试工程师/evidence/bge-capacity-gpu-gate-20260821.json`、`bge-gpu-runtime-20260821.json` |

模型服务内部使用推理锁保护 8 GB 显存，因此并发请求会受控排队；报告中的尾延迟包含排队时间。显存由宿主机独立采样，避免在容器内高频启动采样工具干扰推理。

## 4. 批量和 OOM 结果

| 场景 | 结果 | 状态 |
| --- | --- | --- |
| Embedding batch=32 | 返回 32 个 1024 维有限向量 | 通过 |
| Reranker candidates=20 | 返回 20 个有限分数 | 通过 |
| 50 并发请求失败数 | Embedding 0；Reranker 0 | 通过 |
| OOM/致命日志匹配 | 0 | 通过 |
| 峰值显存 | 3697/8188 MB，45.15% | 通过 |
| 峰值剩余显存 | 4491 MB | 通过 |

## 5. 50 并发性能结果

| 指标 | Embedding | Reranker（20 候选/请求） | 门禁 |
| --- | ---: | ---: | --- |
| 成功/总请求 | 50/50 | 50/50 | 全部成功 |
| 总耗时 | 0.3807 s | 1.9817 s | 记录 |
| 吞吐 | 131.35 RPS | 25.23 RPS | 记录 |
| 平均延迟 | 214.68 ms | 1037.15 ms | 记录 |
| P50 | 215.24 ms | 1025.69 ms | 记录 |
| P95 | 363.69 ms | 1878.94 ms | `< 5000 ms`，通过 |
| P99 | 375.22 ms | 1966.59 ms | `< 5000 ms`，通过 |
| 最大延迟 | 375.22 ms | 1966.59 ms | `< 5000 ms`，通过 |

## 6. 冷启动结果

冷启动口径为：镜像与固定模型资产已经存在于本机，但模型服务进程未运行；从 GPU Compose 强制重建并启动服务，到健康检查返回 `healthy`。

| 指标 | 实际结果 | 门禁 | 状态 |
| --- | ---: | ---: | --- |
| 服务进程冷启动 | 24.256 s | `< 180 s`（Compose start period） | 通过 |
| 启动后设备 | NVIDIA GeForce RTX 4060 | 必须为 CUDA GPU | 通过 |
| 启动后健康状态 | healthy | healthy | 通过 |

该数字不包含首次下载约 4.6 GB 模型权重或首次构建镜像，因此不能外推为全新服务器的首次部署耗时。

## 7. 无效对照轮次说明

测试中曾仅传入 `--profile gpu` 而未叠加 `docker-compose.gpu.yml`，PyTorch 实际报告 `cuda_available=False`，形成 CPU 对照文件 `bge-capacity-gate-20260821.json`。该轮 P95 明显变慢，已标记 `valid_for_gpu_gate=false`，不参与任何 GPU 生产结论。

发现配置问题后，使用以下正式口径重新执行并通过：

```text
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml --profile ai ...
```

## 8. 回归与运行安全

| 验证 | 结果 | 状态 |
| --- | --- | --- |
| GPU Compose 配置 | 7 个服务可解析 | 通过 |
| 模型服务健康 | healthy | 通过 |
| PyTorch 设备 | NVIDIA GeForce RTX 4060 | 通过 |
| 全量 pytest | 88 passed，2 skipped | 通过 |
| Ruff/mypy/锁文件 | 全部通过 | 通过 |
| 锁定依赖漏洞审计 | 123 个包无已知漏洞或不良状态 | 通过 |

## 9. 缺陷关闭与结论

| 编号 | 原状态 | 本次证据 | 当前状态 |
| --- | --- | --- | --- |
| R-AI-BGE-004（容量部分） | P0，未完成 | 50 并发、P95/P99、吞吐、冷启动和 OOM 全部完成 | 已关闭 |
| OBS-M04-001 | P1，待处理 | batch=32、候选=20、50 并发和显存峰值完成 | 已关闭 |

**RTX 4060 8 GB 单实例 BGE 模型服务性能与容量门禁通过。** 当前固定负载下 50 并发零失败，P95/P99 小于 5 秒，冷启动小于 180 秒，峰值显存 3697 MB，未发现 OOM。

本结论适用于当前固定模型 Revision、FP16、单 Worker、候选上限 20 和短查询负载。生产上线后仍应持续监控尾延迟、队列长度、显存和错误率；变更批量、候选长度、Worker 数或 GPU 型号时重新执行容量测试。
