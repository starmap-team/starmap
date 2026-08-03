---
gsd_state_version: 4.0-snapshot
milestone: post-v3.0
milestone_name: 文档治理 + 流水线 P0 修复 双轨 sprint
status: active
last_updated: 2026-07-20T00:00:00.000Z
last_activity: 2026-07-20 — fresh-snapshot write
supersedes: .planning/STATE.md(2026-07-14,v3.0 100% claim 现已不准确)
scope: 2026-07-16 ~ 2026-07-20 active window
branch: feat/frontend-type-migration
---

# Project State — v4-active-sprint Snapshot

> **本文件**:`.planning/STATE.md.v4-active-sprint.md`
> **与 `STATE.md` 关系**:`STATE.md`(2026-07-14 写,声称 v3.0 100% 完成)目前 dirty
> 评估中;本文件不替代它,而是**为当前活跃工作**额外补一份快照,避免误读 v3.0 完成。
> **谁该读**: sprint 内的算法组/后端组/前端组;不在 v3.0 ~ 现 sprint 范围的可忽略。

---

## 1. 当前活跃 sprint(2026-07-16 ~ 2026-07-20)

### 1.1 时间窗与分支
- **起点**:2026-07-16(commit `163ca6d` audit closure 当日)
- **终点**:活跃中(2026-07-20)
- **分支**:`feat/frontend-type-migration`(KB 旧值 `fix/all-26-bugs` 已过时)
- **HEAD**:`0810d35 chore: cleanup temp scripts, docs, and gitignore`

### 1.2 提交数
- 自 2026-07-16 起:**25+ commits**(截至 2026-07-20)
- 自 2026-07-14(v3.0 声称完成)起:**30+ commits**
- 近 30 天:**412 commits**

### 1.3 双轨并行

| 轨道 | 主导人 | 主要活动 | 提交代表 |
|---|---|---|---|
| **轨道 A: 文档治理** | Li3379(以及当前 session agent) | 文档与代码同步;49 项审计关闭;AGENTS.md 重写 | `163ca6d`, `6ec0278`, `1d19a12`, `ea107e2`, `5571c36` |
| **轨道 B: 流水线 P0 修复** | 后端组 | Celery event loop / jd_raw 表 / graph_sync 三件 | `docs/fix_plan_p0_2026-07-20.md`(本日新写) |
| **轨道 C: 前端 type 迁移** | 前端组 | 类型化 schema.ts + eslint 0 警告 + vitest 233 pass | `ea107e2`, `625130e`, `182b62b` |
| **轨道 D: 安全硬化** | 后端组 | IDOR / Cypher injection / debug telemetry / 数据 PII | `2c27908`, `d75c415`, `7b3e257`, `08a6cc2`, `98e1d9f` |

---

## 2. 已关闭(本 sprint 内)

### 2.1 49 项安全审计(`163ca6d`)
- AUTH-01 全站鉴权、AUTHZ-01 admin 守卫、SEC-01 .env 密钥清除、API-01 HTTPS、
  DATA-01 PII、INJ-01/03/05 注入硬化、AUTH-03/04 鉴权语义、AUTHZ-05 配置 admin、
  W1-T2 dev opt-in、API-05 SSE 限制、SEC-10/LOG-04 就绪响应、DATA-05 soft-delete、
  DEP-01~04 依赖 pin、API-01 nginx TLS+、SEC-04 mypy

### 2.2 类型与 CI
- `ea107e2` stage3 type migration(eslint 48 警告清零)
- `625130e` stage5 auth test 覆盖
- `182b62b` vitest 加进 CI
- `1d19a12` golden_set 计数对齐

### 2.3 安全续作
- `2c27908` IDOR use uid
- `d75c415` Cypher injection guard
- `08a6cc2` reset token 不再泄露
- `7b3e257` debug telemetry 清除
- `98e1d9f` Redis 限流 + in-memory fallback

### 2.4 其他
- `16ef331` MSW 死依赖清除
- `f5f797a` useAuthBootstrap 接线
- `b093008` git history 缩减 -36%
- `0810d35` temp 脚本/文档清理

---

## 3. 进行中(本 sprint,活跃工作)

### 3.1 流水线 P0 修复(轨道 B)
来自 `docs/fix_plan_p0_2026-07-20.md`:
- **PIPE-P0-1**:Celery event loop(`backend/app/tasks/celery_app.py` 改造,~20 行)
- **PIPE-P0-2**:jd_raw 表(`crawler/persistence/database.py` + `dao.py`,~10 行)
- **PIPE-P0-3**:graph_sync 阶段从未跑(依赖 PIPE-P0-1)

### 3.2 evolution 重构(轨道 A 边界)
脏状态标记 6 个 evolution 文件 D:
- `diff_engine.py` / `hallucination_guard.py` / `orchestrator.py` /
  `path_recommender.py` / `snapshot_manager.py` / `trust_integration.py`

`__init__.py` / `emergence_finder.py` / `AGENTS.md` 处于 M 状态。重构尚未合并。

### 3.3 AGENTS.md 体系收敛(轨道 A)
6 个 AGENTS.md 文件 dirty:`backend/app/api/v1/` / `core/` / `core/evolution/` /
`core/extraction/` + `.github/`。等待 WIP 重构合并后再统一更新。

### 3.4 dirty 工作区总览(20+ 文件)
未提交改动按主题分组:
- 后端代码:`auth.py` / `datasource.py` / `evolution.py` / `extract.py` / `graph.py` /
  `judge.py` / `learning.py` / `loop.py` / `match.py` / `position.py` / `resume.py` /
  `router.py` / `pipeline/{routes,schemas,serializers}.py`
- 早期迁移:`001_initial_migration.py` / `002` / `003` / `004` / `008` /
  `20260616_01_initial_baseline.py`
- 配置:`.gitignore`(182 行 diff) / `alembic.ini`(根 + backend 双份)
- 文档:`README.md` / `.planning/PROJECT.md`
- Dockerfile:`Dockerfile.celery` / `Dockerfile.dev`

---

## 4. 未关闭 backlog(sprint 外,需后续 PR)

来自 `docs/standards/99-appendix/04-审计关闭-2026-07-16.md §4`:
- P0-10 / API 路径前缀冲突
- P1-17 / dev compose `depends_on` healthy
- P5-39 / match/resume/pipeline golden 无执行器
- P5-40 / judge LLM-as-judge(决策点)
- P5-43 / 覆盖率门禁 60% 与实际 80.42% 脱节
- P5-47 / openapi.yaml 缺 /auth(契约变更需团队签署)
- P5-51 / change-password 路由设计异味
- P5-52 / 前端错误未展示 detail

---

## 5. 当前 P0 数据流水线族(`99-appendix/01 §0`)

| ID | 标题 | 状态 | 修法行数 | 风险 |
|----|------|------|---------|------|
| PIPE-P0-1 | Celery event loop 错 | 🔴 Open | ~20 | 低 |
| PIPE-P0-2 | `jd_raw` 表不存在 | 🔴 Open | ~10 | 低 |
| PIPE-P0-3 | graph_sync 未跑 | 🔴 Open | 依赖 PIPE-P0-1 | — |

---

## 6. 验证证据(2026-07-20 实测)

| 项 | 命令 | 结果 |
|---|---|---|
| 无 API 密钥泄漏 | `grep -r "sk-[A-Za-z0-9]\{20,\}" .env backend/ frontend/` | 0 命中 |
| OpenAPI 端点扩量 | `grep -c '^  /' starmap-contracts/openapi.yaml` | 115(ONBOARDING 写 131, 漂移) |
| pytest 基线 | `163ca6d` 自述 | 1785 passed, 1 pre-existing failure |
| vitest 基线 | `ea107e2` 自述 | 233 pass |
| audit/ 不存在 | `ls audit/` | ENOENT |
| 文档漂移本地检查 | `python scripts/check_doc_freshness.py` | 3 HIGH / 3 INFO / 0 ERROR |

---

## 7. 与其他 STATE 类文档的关系

| 文件 | 描述 | 本文件是否覆盖 |
|---|---|---|
| `STATE.md`(2026-07-14) | v3.0 100% 完成声明 | ❌ 不覆盖(声明已不准) |
| `STATE.md.v4-active-sprint.md`(本文件) | 当前 sprint 快照 | — |
| `.planning/ROADMAP-v2.2.md` | 路线图 | ❌ 不覆盖(范围不同) |
| `docs/standards/99-appendix/01-已知问题清单.md §0` | 当前 P0 | ✅ 同步(本文件 §5) |
| `docs/standards/99-appendix/04-审计关闭-2026-07-16.md` | 已关闭审计 | ✅ 同步(本文件 §2) |

---

## 8. 何时升级/弃用本文件

### 8.1 升级到 v5 的触发
- 上述活跃工作全部合并后(轨道 B/C 关闭)
- 进入下个 sprint 起点

### 8.2 弃用本文件
- 若 `.planning/STATE.md` 重写为 v4-active 并能完整表达当前 sprint,可删除本文件
- 当前不动 `STATE.md`(dirty,待 WIP 合并)

---

## 9. 引用

- **49 项审计关闭**: `docs/standards/99-appendix/04-审计关闭-2026-07-16.md`
- **现行 P0**: `docs/standards/99-appendix/01-已知问题清单.md §0`
- **当前 P0 修复计划**: `docs/fix_plan_p0_2026-07-20.md`
- **流水线深度分析**: `docs/pipeline_deep_analysis.md`
- **寻路**: `docs/standards/00-总纲/00-寻路-LANDING.md`
- **本地检查脚本**: `scripts/check_doc_freshness.py`
- **CI 检查**: `.github/workflows/doc-lint.yml`
- **历史 v3.0 声明**: `.planning/STATE.md`(已不准)