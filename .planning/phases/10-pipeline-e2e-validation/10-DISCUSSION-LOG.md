# Phase 10 Discussion Log

**Phase:** 10-pipeline-e2e-validation
**Date:** 2026-07-10
**Mode:** default (text-mode user)

## Selected Gray Areas

User selected all 4 phase-specific gray areas for discussion:

1. **G1: Playwright 安装方式** (PIPE-01)
2. **G2: PROXY_LIST 解析与 fallback** (PIPE-02)
3. **G3: Pipeline 触发方式** (PIPE-03)
4. **G4: E2E 冒烟验证范围** (PIPE-04)

## Discussion Detail

### G1 — Playwright 安装方式
**Options presented:**
- (a) `mcr.microsoft.com/playwright/python:v1.49.0-jammy` 官方镜像
- (b) Python slim base + `pip install playwright && playwright install`
- (c) Claude discretion (让 planner 评估)

**Trade-off table:**
| 方案 | 体积 | 可复现 | 构建速度 | 维护成本 |
|---|---|---|---|---|
| 官方镜像 | 大 (~1.5GB) | 高（镜像自带） | 快（无 install 步骤） | 低 |
| pip install | 中 | 中（依赖 pip 镜像） | 慢（首次 install 联网） | 中 |
| Claude 自由 | n/a | n/a | n/a | n/a |

**User selection:** (a) **官方 mcr.microsoft.com 镜像 + 锁定 Chromium 版本 v1.49.0-jammy**

**Locked decision: D-01** — `backend/Dockerfile.dev` 的 celery-worker 服务改用官方 Playwright 镜像 base

### G2 — PROXY_LIST 加载策略
**Options presented:**
- (a) 逗号分隔 + round-robin + 无代理直连
- (b) 逐项试用 + 失败熔断 + 熔断窗口期
- (c) 仅预留配置骨架

**Trade-off table:**
| 方案 | 实现复杂度 | 失败容忍度 | 复杂度来源 |
|---|---|---|---|
| round-robin | 低 | 低（不感知失败） | 仅调度 |
| 熔断窗口 | 中 | 高（5 分钟冷却） | 状态 + 调度 |
| 仅骨架 | 最低 | n/a | 仅占位 |

**User selection:** (b) **逐项试用 + 失败熔断 + 熔断窗口期**

**Locked decision: D-02** — PROXY_LIST 解析为 list[ProxyEntry]，熔断状态模块级 dict，5 分钟 ≥3 失败 → 5 分钟冷却

### G3 — Pipeline 触发方式
**Options presented:**
- (a) 容器启动自动跑一次 + API
- (b) API + CLI + README
- (c) API + CLI + 启动 cron

**Trade-off table:**
| 方案 | 新手上手 | 日常工具完整度 | 实施复杂度 |
|---|---|---|---|
| 自动 + API | 一键启动 | 中 | 中 |
| API + CLI + README | 低（需查文档） | 高 | 低 |
| API + CLI + cron | 一键启动 | 高 | 中 |

**User selection:** (c) **API + CLI + 启动 cron 跑一次**

**Locked decision: D-03** —
- `POST /api/v1/pipeline/trigger` 确认存在并测试
- `python -m crawler.run run-pipeline` 新增 CLI
- `PIPELINE_BOOTSTRAP=true` 时 worker 启动 30 秒后一次性入队 pipeline run

### G4 — E2E 冒烟验证范围
**Options presented:**
- (a) 仅 1 条 happy path
- (b) 包含采集质量 + 抽取 + 前端展示
- (c) 加上边界场景 + 负向验证

**Trade-off table:**
| 方案 | 断言数 | 覆盖深度 | CI 耗时 |
|---|---|---|---|
| happy path only | 1 | 浅 | 快 |
| 核心覆盖 | 5 | 中 | 中 |
| 含边界负向 | 7-8 | 深 | 慢 |

**User selection:** (c) **加上边界场景 + 负向验证**

**Locked decision: D-04** —
- crawl ≥5 / dedup 去重 / clean 清洗 / extract ≥10 技能 / graph_sync ≥5 节点 ≥3 关系
- **负向**: PROXY 全失败 → 退化为直连不阻断
- **降级**: 云端 LLM 全缺失 → Ollama 仍能抽取
- **前端**: 真实图谱页加载 ≠ mock 硬编码

## Deferred

User did not raise any new scope-creep ideas during discussion. Suggested deferred items
(already documented in CONTEXT.md):
- 多爬虫并行（lagou/51job）
- 大规模数据采集
- 周期 cron（仅一次性）
- Redis 共享代理熔断
- Proxy 池管理后台

## Outstanding

None — all 4 gray areas resolved in single round. User ready for planning.

---

*Discussion complete: 2026-07-10*
*Next: `/gsd:plan-phase 10`*
