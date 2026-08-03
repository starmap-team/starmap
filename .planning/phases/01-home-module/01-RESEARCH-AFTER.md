# Phase 1 (Home 全景图谱) 完成后 — Research 收集

**Date:** 2026-07-26
**Mode:** research-only (--research-phase 1)
**Purpose:** 收集 Phase 1 执行后所有发现，供 Phase 2-12 执行时使用

---

## 1. 状态总览

### Phase 1 (Home) — ✅ 已完成

| Task | 状态 | 证据 |
|------|------|------|
| Task 1-2: 验证源码分析+设计 | ✅ | `docs/archive/home-source-analysis.md` (13 个问题) |
| Task 3: 前后端联调修复 | ✅ | KPI 修复, Map 响应式, 错误处理, Home.spec.ts |
| Task 4: Home.spec.ts 测试 | ✅ | 9/9 passed (4 原 + 5 新) |
| 输出 SUMMARY | ✅ | `.planning/phases/01-home-module/01-01-SUMMARY.md` |

### Phase 2 (Position 岗位列表) — 计划存在，未执行

- `.planning/phases/02-position-module/02-01-PLAN.md` (30KB, 4 tasks)
- 建议执行: `/gsd-execute-phase 2`

### Phase 3 (Pipeline 数据流水线) — 计划存在，未执行

- `.planning/phases/03-pipeline-monitor/03-01-PLAN.md` (32KB) + RESEARCH.md
- 含 SSE / DAG / 僵尸 pipeline / 监控相关 task
- 建议执行: `/gsd-execute-phase 3`

### Phase 4-12 — 未计划

按 v5.0 milestone:
- Phase 4: 数据源管理 (DataSources.vue)
- Phase 5: 匹配诊断 (MatchDiagnosis.vue) — **与架构修复冲突，需要重新规划**
- Phase 6: JD抽取 (ExtractJD.vue)
- Phase 7: 闭环演示 (LoopDemo.vue)
- Phase 8: 学习中心 (LearningCenter.vue)
- Phase 9: 数据大屏 (DataDashboard.vue)
- Phase 10: 演化看板 (EvolutionDashboard.vue)
- Phase 11: 图谱质量 (QualityDashboard.vue)
- Phase 12: 管理后台 (Admin.vue)

---

## 2. 跨 Phase 通用发现

### 2.1 基础设施层（已完成修复）

| 修复 | 验证 | 影响 Phase |
|------|------|------------|
| Redis 认证 | `redis-cli ping` → PONG | 所有需认证的 API |
| SSE 限流白名单 | curl 200 | Pipeline / Dashboard |
| SSE 连接数限制 (10→25) | 90 errors → 0 | Pipeline / Dashboard |
| Vite 错误遮罩 | hmr.overlay: false | 所有页面 |
| 3d-force-graph 安装 | package.json 存在 | Graph3D.vue (Home/Quality) |
| Vite 容器缓存问题 | 已知遗留，P3 修复 | 所有页面（间歇性） |

### 2.2 架构层（Phase 5 方案 B 完成）

| Step | 状态 | 验证 |
|------|------|------|
| Step 1: Neo4j 字段映射 | ✅ | Neo4j 56 = PG 56 |
| Step 2: 写路径同步 MERGE | ✅ | `_sync_neo4j_on_audit` 重写 |
| Step 3: 定时 reconcile | ✅ | cron_scanner_loop 集成 |
| Step 4: 健康度监控 | ✅ | `/admin/data-truth` 返回 health |

**关键变化**：Neo4j 现在是 PG 的只读投影，**任何 phase 都不应该假设 Neo4j 有独立数据**。

### 2.3 数据真相表

新增端点: `GET /api/v1/admin/data-truth`
返回字段: rows (5 指标) + health (orphan/sync/reconcile)
前端: 管理后台"数据源诊断"tab (Phase 12)

**所有 phase 都应遵守**：不要展示"Neo4j 节点数"和"PG approved 数"让用户自己对比 — 统一显示其中一个并在 tooltip 解释。

### 2.4 验证规范

`.planning/VERIFY_FIRST_METHODOLOGY.md` 已建立：
1. 修复前写验收标准（截图 + API + DB）
2. 改代码后重启容器
3. 截图验证
4. 记录到记忆

---

## 3. Phase 2-12 优先级建议

### 立即执行（用户报告影响）

1. **Phase 3 (Pipeline)** — 用户在第一轮就报告了僵尸流水线问题
   - 含 zombie run 检测（部分已修）
   - DAG 显示（部分已修）
   - **未验证**：PipelineMonitor.spec.ts 测试

2. **Phase 12 (Admin)** — 含数据源诊断（已建）
   - 验证管理后台所有 tab 工作
   - 含 batch approve/reject 验证

### 中优先级

3. **Phase 2 (Position)** — 岗位列表
4. **Phase 4 (DataSources)** — 数据源管理
5. **Phase 9 (DataDashboard)** — 数据大屏
6. **Phase 6 (ExtractJD)** — JD抽取
7. **Phase 7 (LoopDemo)** — 闭环演示
8. **Phase 8 (LearningCenter)** — 学习中心

### 低优先级（功能相对独立）

9. **Phase 10 (Evolution)** — 演化看板
10. **Phase 11 (Quality)** — 图谱质量

---

## 4. 已知遗留问题（跨 Phase）

| 严重度 | 问题 | 归属 Phase |
|--------|------|------------|
| P0 | Vite 容器缓存损坏 — 间歇性 Internal Server Error | 基础设施 |
| P1 | Neo4j 关系边数 vs dashboard 差 196 | 5-architecture 后续 |
| P1 | Neo4j Tool/KnowledgeArea/Industry 节点未与 PG 同步 | 5-architecture 后续 |
| P1 | `name_cn` 字段在 PG 全空 | 业务数据回填 |
| P2 | 旧的 `name_cn` 字段在 Neo4j 已建（70+ 节点） | 5-architecture 后续 |
| P2 | review-items API 翻页未传 limit | 12 (Admin) |
| P3 | `_sse_attach` 集成 — 事件流验证 | 3 (Pipeline) |

---

## 5. 验证脚本模板（已用）

`.planning/VERIFY_FIRST_METHODOLOGY.md` 提供标准流程。Phase 2+ 执行时：

```bash
# 1. 重启后端
docker restart starmap-backend
sleep 15

# 2. 重启前端
docker stop starmap-frontend && docker rm starmap-frontend
docker compose -f docker-compose.dev.yml up -d --no-deps frontend
sleep 20
# 可能需要重新安装 3d-force-graph
docker exec starmap-frontend sh -c "npm install 3d-force-graph@1.80.0 --save"

# 3. 截图
mcp__playwright__browser_navigate(url)
mcp__playwright__browser_take_screenshot(filename, fullPage)

# 4. 验证 console errors
mcp__playwright__browser_console_messages(level: error)
```

---

## 6. 建议下一步

按优先级：

1. **立即**: 执行 `/gsd-execute-phase 3` (Pipeline)，含 zombie run + DAG 验证
2. **紧随**: 执行 `/gsd-execute-phase 12` (Admin)，含数据源诊断 + 内容审核
3. **然后**: 执行 `/gsd-execute-phase 2` (Position 岗位列表)
4. **再后**: 顺序执行 Phase 4-11

每个 phase 都用 verify-first 方法论：
- 修复前写验收标准
- 改代码后重启 + 截图
- 记录到记忆 + STATE.md

---

## 7. 关键记忆引用

- `starmap-verify-first-methodology.md` — 修复验证规范
- `starmap-architecture-audit.md` — 三端架构评估
- `browser-e2e-test-fixes.md` — 浏览器测试修复历史
- `starmap-data-investigation-2026-07-25.md` — 70/56/39 口径问题调查
- `starmap-data-consistency-audit.md` (Phase 4) — KPI 口径扫描

---

**Status:** research complete
**Next action:** 用户选择 Phase 2/3/12 中的一个执行