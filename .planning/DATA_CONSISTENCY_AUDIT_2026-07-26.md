---
title: 跨模块数据源一致性深度审计
date: 2026-07-26
---

# 跨模块数据源一致性深度审计

## 审计方法

四层穿透校验：
1. **API 返回值**（curl 直调每个端点）
2. **PostgreSQL 原始数据**（直接 SQL）
3. **Neo4j 原始数据**（Cypher 直查）
4. **前端显示**（Playwright 截图）

每个指标都问："这个数字的口径是什么？"

## 不一致矩阵

| 指标 | API 1 | API 2 | API 3 | PG | Neo4j | 差异根因 |
|------|-------|-------|-------|----|----|---------|
| 岗位总数 | **70** | **56** | **39** | 56 | 70 | 三个数据源不同口径 |
| 技能总数 | **393** | **257** | - | 257 | **259** | Neo4j 比 PG 多 2（已删除节点残留） |
| 关系边数 | - | **1179** | - | - | **1375** | Neo4j 比 dashboard 多 196 |
| 图谱节点总数 | - | **329** | - | - | **313** | Neo4j 比 dashboard 少 16 |
| 流水线总运行 | - | - | - | **7** | - | admin/stats 不显示 |
| 今日采集量 | - | **0** | - | - | - | jd_raw.crawled_at 缺失 |
| 待审核岗位 | - | **50** | 17 | **17** | - | review-items API 翻页未传 |

## 各数字的口径解读

### 岗位 70/56/39 的三重含义
- **70** = Neo4j 图谱节点总数（包括历史所有入库的，可能含废弃/重复）
- **56** = PostgreSQL `position_records` 表总行数（含所有 review_status）
- **39** = PostgreSQL `position_records` 表中 `review_status='approved'` 的行数（用户可见）
- **17** = PostgreSQL `position_records` 表中 `review_status='pending_review'` 的行数

### 技能 393/257/259 的歧义
- **393** = `graph/overview` 返回的 total_skills — **数据源未知，需查代码**
- **257** = `dashboard/overview` 与 PostgreSQL 一致
- **259** = Neo4j 实际节点数（比 PG 多 2 个孤儿节点）

### 关系 1179/1375 的歧义
- **1179** = dashboard 计算的可能去重后的边数
- **1375** = Neo4j 实际边数（含重复和已删除的）

### 流水线运行 7 的分歧
- DB 真实 7 条 pipeline_runs
- `/admin/stats` 不返回 pipeline 相关字段
- `/pipeline/status` 的 `run_counts` 字典不返回总数

## 13 个具体的用户体验问题

### 数据真实性问题（影响用户决策）

1. **岗位数三义**：全景图谱显示 70，岗位列表显示 56，管理后台显示 39+17。用户无法判断哪个是真实数字。
2. **技能数三义**：393 vs 257 vs 259，三个 API 返回三个值。
3. **关系数二义**：1179 vs 1375，dashboard 与 Neo4j 相差 196 条。
4. **孤儿节点**：Neo4j 有 2 个 skill 节点不在 PostgreSQL 中（可能是手动插入或删除未同步）。
5. **边数差异**：196 条边的差异未说明。
6. **今日采集量 = 0**：jd_raw 表 crawled_at 全部为 2026-07-24，没有今天的记录。

### 权限 / 角色问题

7. **数据访问权限**：普通用户能否看 Neo4j 全量（70）？还是只能看 approved（39）？当前 `/positions` API 默认 `approved`，但 `/graph/overview` 返回 70，可能导致普通用户看到不一致。

### UI 体验问题

8. **待审核数字差异**：管理后台内容审核显示 17 条，但 review-items API 返回 50 条（可能是分页参数问题）。
9. **图谱节点数差异**：Neo4j 313 vs dashboard 329，相差 16 个节点。
10. **流水线运行总数缺失**：用户看不到"系统总共跑过几次流水线"。

### 数据同步问题

11. **Neo4j ↔ PG 不同步**：PG 删除岗位后，Neo4j 节点仍存在。
12. **crawled_at 时间戳**：jd_raw 表的 crawled_at 全部是同一天，可能表示新的 crawl 没在更新这个字段。
13. **Pipeline run_counts 字典**：未返回 cancelled 状态的运行数。

## 建议的高优先级 UX 优化

按修复优先级排序：

### P0 — 阻塞用户理解的问题
- **数据源统一标识**：所有页面 KPI 卡片增加"数据源 + 口径" tooltip（已部分实现）
- **统一口径 API**：在 `/api/v1/admin/stats` 中新增 `data_source_breakdown` 字段，明示每个数字的来源

### P1 — 视觉/体验问题
- **页面间数字一致性**：同一概念在不同页面显示同一数字（已 tooltip，但建议统一显示）
- **Neo4j/PG 同步状态**：在管理后台显示"图谱节点 vs 数据库记录"对比

### P2 — 数据完整性
- **孤儿节点清理**：定期清理 Neo4j 中 PG 已删除的节点
- **crawled_at 字段更新**：pipeline crawl 阶段应该更新 jd_raw.crawled_at

### P3 — 性能
- **stats 缓存**：admin/stats 应该加缓存（每分钟一次），避免每次请求全表扫描
- **dashboard 计算优化**：1179 vs 1375 的差异说明有重复计算

## 自发性问题清单（执行时要主动发现的）

按用户要求"自发找出问题"，以下是我应该在审计过程中主动发现的检查项：

1. **缓存与实时数据混用**：dashboard 显示 0 但 Neo4j 有 56 个节点，可能用了 Redis 缓存但 TTL 设置过长
2. **权限边界**：普通用户登录后是否能看 Neo4j 全量？
3. **CORS 配置**：dev 环境的 CORS 配置是否允许 frontend 跨域
4. **认证 token 泄露**：每个 API 是否要求有效 Bearer token？
5. **错误信息泄露**：stack trace 是否返回到前端？
6. **数据库备份**：Neo4j 和 PG 的备份策略
7. **API 版本**：URL 是否带 v1 前缀？
8. **缓存一致性**：Redis 缓存修改后是否失效？

每个发现的 bug 都应该有：截图、API 返回、DB 数据三层证据。