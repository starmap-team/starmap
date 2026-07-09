# Phase 8: 后端清理与配置 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-07-09
**Phase:** 08-backend-cleanup
**Areas discussed:** Demo数据处置, reset-demo与Admin按钮, LLM校验严格度, 健康检查详情粒度, demo脚本归档方式

---

## Demo 数据处置 (DEMO-01)

### review_queue auto-seed 处置

| Option | Description | Selected |
|--------|-------------|----------|
| 完全移除 | 完全移除 _DEMO_REVIEW_SEED 和 auto-seed，空表返回空列表。需演示数据时手动跑归档脚本 | ✓ |
| opt-in 环境变量 | 保留 seed 代码，但用 SEED_DEMO_DATA=true 环境变量保护，默认关闭 | |
| Claude决定 | Claude 来决定 | |

**User's choice:** Claude决定
**Notes:** Claude 推荐完全移除（D-01）。理由：v2.1 目标是真实数据，任何 demo 数据路径都与此矛盾；env flag 增加配置面违背 DEC-003 简洁原则；DEMO-06 归档脚本供开发手动运行。

### data_sources 表数据定性

| Option | Description | Selected |
|--------|-------------|----------|
| 算真实配置 | 站点是真实爬取目标，保留表数据，仅归档 seed 脚本。爬虫照常读 DataSourceRecord | ✓ |
| 算demo数据清空 | 清空 data_sources 表，爬虫走 fallback 默认值 | |
| Claude决定 | Claude 来决定 | |

**User's choice:** Claude决定
**Notes:** Claude 决定算真实配置（D-02）。理由：BOSS/拉勾/51Job 正是 SOURCE_SITE_MAP 真实目标，config.py authority_scores 有真实评分；清空表逼爬虫走 fallback 是退化。

---

## reset-demo 与 Admin 按钮 (DEMO-02)

| Option | Description | Selected |
|--------|-------------|----------|
| 删端点+删按钮 | 删端点 + 前端删除"重置演示数据"按钮及 useAdminReset.ts | ✓ |
| 按钮改为触发Pipeline | 删端点，前端按钮改为"触发Pipeline采集" | |
| dev标志保护端点 | 端点用 APP_ENV=development 标志保护，生产禁用 | |
| Claude决定 | Claude 来决定 | |

**User's choice:** 删端点+删按钮（推荐）
**Notes:** 前端按钮移除属 DEMO-02 协调清理（非 Phase 9 MSW 工作）。PipelineMonitor 已有"立即执行"按钮无需替代。需同步删 schema.ts 的 resetDemoData 类型和 openapi.yaml 的 /admin/seed/reset。

---

## LLM 校验严格度 (CFG-01/02)

| Option | Description | Selected |
|--------|-------------|----------|
| 全部仅warning | 开发 warning（Ollama本地可降级）。生产也仅 warning 不阻止启动 | ✓ |
| 生产阻止启动 | 开发 warning，生产要求至少一个云端 LLM key 否则 RuntimeError | |
| Claude决定 | Claude 来决定 | |

**User's choice:** 全部仅warning（推荐）
**Notes:** Ollama 本地模型始终可降级，无云端 key 不致命；与 DB 密码不同（DB 密码缺失是硬依赖）。CFG-02 DB 密码校验已存在于 config.py:124-167，本阶段仅确认。CFG-03 .env.example 补 MIMO/DEEPSEEK/PROXY 字段由 Claude 决定（D-07）。

---

## 健康检查详情粒度 (CFG-04)

| Option | Description | Selected |
|--------|-------------|----------|
| 仅连接 ping | 只 ping 4 个服务连接状态 | |
| ping + 配置状态 | ping 4 服务 + 显示各 LLM key 是否已配置 + demo 数据是否存在 | ✓ |
| Claude决定 | Claude 来决定 | |

**User's choice:** Claude决定
**Notes:** Claude 决定 ping + 配置状态（D-05）。仅 ping 不足以解释"LLM 为何不工作"。增加 LLM key 布尔（不泄露值）+ demo 数据指示，直接服务真实数据切换排查。无 auth 保护（与 /health 一致，SEC-03 未来范畴）。

---

## demo 脚本归档方式 (DEMO-04)

| Option | Description | Selected |
|--------|-------------|----------|
| 原地注释 | 保留原位，文件头加 # ARCHIVE 注释。路径不变，模块调用不 break | ✓ |
| 移至archive目录 | 移至 scripts/archive/，路径变 scripts.archive.xxx，需更新引用 | |
| Claude决定 | Claude 来决定 | |

**User's choice:** 原地注释（推荐）
**Notes:** 最小侵入，避免 break docstring 和模块引用。DEMO-03 同步清理 quality.py:557 和 expand_graph.py:719 的推荐文本。

---

## Claude's Discretion

- D-01: review_queue auto-seed 完全移除（用户选"Claude决定"）
- D-02: data_sources 表数据视为真实配置保留（用户选"Claude决定"）
- D-05: /health/detail 返回 ping + LLM key 布尔 + demo 指示（用户选"Claude决定"）
- D-07: .env.example 补全 LLM/PROXY 字段并标注降级链优先级
- LLM key 校验 warning 文案、demo 数据检测查询、quality.py recommendation 替换文案
- 是否一并归档根目录 scripts/ 下非 _demo 后缀的 seed 脚本（seed_jd_data.py 等）

## Deferred Ideas

- 现有 DB 中已存在的 demo 行清理（review_queue/pipeline_runs demo 记录）-- 属 Phase 10 数据层
- data_sources 表 GitHub/ESCO 两条非爬虫源是否清空 -- 留 Phase 10 评估（可能服务 ESCO 技能映射 import）
- SEC-03 身份验证系统 -- /health/detail 无 auth 是临时方案，完整 auth 属未来里程碑
- LLM key 轮换/密钥管理 -- CFG-01 仅启动校验，轮换属密钥管理范畴
- demo 脚本彻底删除（非归档）-- 推 v2.2+ 确认无依赖后
- seed_chroma.py 等非 _demo seed 脚本归档 -- 若服务真实功能则不归档
