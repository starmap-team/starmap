---
title: StarMap 三端数据架构企业级合规性评估
date: 2026-07-26
status: audit
---

# 三端数据架构企业级合规性评估

## 当前架构概览

```
┌─────────────────────────────────────────────────────────┐
│  前端 (Vue 3) — 18 个页面                                  │
└──────────────┬──────────────────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
┌──────▼──────┐ ┌───────▼────────┐
│ /api/v1/*   │ │ /api/v1/*       │
│ PostgreSQL  │ │ Neo4j           │
│ (SSOT 标)    │ │ (投影缓存)        │
│ + Redis    │ │                  │
└─────────────┘ └──────────────────┘
```

文档 **声称** 的架构：
- PostgreSQL = 唯一真相源（SSOT）
- Neo4j = 只读投影（派生缓存）
- Redis = 缓存 + 限流 + SSE

**实际运行** 的架构：
- PostgreSQL = 业务主数据
- Neo4j = 图谱节点（**独立写入源**，不是从 PG 投影）
- Redis = 限流 + 实时事件

---

## 企业级数据架构标准（参考）

### 1. CQRS（Command Query Responsibility Segregation）
- 写操作：单一源（PG）
- 读操作：可能多个优化副本（Neo4j、Redis、ElasticSearch）
- **关键**：副本必须由写源派生，不能独立写入

### 2. Event Sourcing / Outbox Pattern
- 写 PG → 发出事件 → 异步投影到 Neo4j
- 失败重试 + 死信队列
- 保证最终一致性

### 3. Read Replica Synchronization
- 写路径：PG only
- 同步路径：PG → outbox → consumer → Neo4j
- 验证路径：reconcile job 定期跑

### 4. Schema 单一性
- 所有数据源用相同的字段名
- 单一字段名（如 `name`）不应在不同表中表示不同含义

---

## 当前架构 vs 企业级标准 差距分析

| 维度 | 企业级标准 | 当前实现 | 差距 |
|------|-----------|---------|------|
| **SSOT 唯一性** | PG 是唯一写源 | PG 和 Neo4j 都独立写 | ❌ 严重 |
| **同步机制** | Outbox + 异步投影 | `apply_change()` 函数存在但**无人调用** | ❌ 严重 |
| **重对账** | `reconcile_all()` 定期跑 | 函数存在但**无人调用** | ❌ 严重 |
| **字段一致性** | 跨源字段名一致 | Neo4j 用 `name_cn`，PG 的 `name_cn` 全空 | ❌ 严重 |
| **数据闭环** | 写 → 事件 → 投影 → 验证 | Neo4j 有 70 个节点但 PG 只有 56 条 | ❌ 严重 |
| **监控** | 同步延迟、孤儿计数 | 无任何监控 | ⚠️ 中 |
| **Caching** | Redis cache invalidation on write | Cache 10 分钟但 PG 写入不主动失效 | ⚠️ 中 |

---

## 当前架构的根本问题

### 问题 1：Neo4j 不是投影，是独立数据源
**证据**：
- Neo4j 有 70 个 Position 节点
- PG `position_records` 只有 56 条
- 14 个 Neo4j 节点的 `name` 在 PG 找不到
- Neo4j 有 58 个节点的 `name_cn`，但 PG 的 `name_cn` 全是 NULL

**这说明 Neo4j 是被人手动写入或从另一个数据源导入**，而不是从 PG 投影的。

### 问题 2：GraphProjector 服务定义了但未使用
**证据**：
- `apply_change()` — 0 个调用方
- `apply_batch()` — 0 个调用方（只在 `reconcile_all` 内部用）
- `reconcile_all()` — 0 个调用方

**服务完整定义但业务代码没有触发同步**。这意味着设计意图是好的，但实现断裂。

### 问题 3：字段映射不一致
- Neo4j Position 用 `name` 存中文（"大模型应用工程师"）
- PG Position 用 `name` 存英文（"Senior Python Engineer"）+ `name_cn` 存中文（但全空）

**两个数据库对"名字"的理解不同**，导致比对失败。

### 问题 4：数据真理表存在但没接 API
- `/admin/data-truth` 是新建的诊断端点
- 但其他 API 仍然各自选源，没有强制统一

---

## 三套备选方案对比

### 方案 A：Neo4j 是真理源（Graph-First）
**适用场景**：图谱是核心业务，PG 只是审核元数据

**优点**：
- 图谱查询性能好（Neo4j 原生）
- 关系遍历自然

**缺点**：
- 需要重新实现 PG 的所有字段约束
- 审计流（review_status）需要在 Neo4j 里实现
- 数据迁移复杂

### 方案 B：PG 是真理源，Neo4j 是只读投影（当前文档声称的方案）
**适用场景**：审计/合规是核心业务，图谱是辅助

**优点**：
- PG 的事务和约束成熟
- 审计流简单

**缺点**：
- 必须实现同步机制（当前缺失）
- 图谱查询需要 JOIN

### 方案 C：CQRS + Outbox（企业级标准）
**适用场景**：读写分离，多副本最终一致

**实现要求**：
1. 所有写操作走 PG，PG 写事务中插入 outbox 事件
2. 单独的 consumer 进程读取 outbox → 投影到 Neo4j
3. 定时 reconcile job 检查 Neo4j 与 PG 一致性
4. 监控：同步延迟、孤儿计数、失败重试

**优点**：
- 写源唯一（PG）
- 读副本可扩展（Neo4j、ES、Redis）
- 失败可恢复（outbox + 重试）
- 企业级标准

---

## 建议：方案 B 的轻量级版本

理由：
1. 当前架构已经按 PG 是 SSOT 的方向设计了
2. GraphProjector 服务已经定义好了 `apply_change` 和 `reconcile_all`
3. 只需要"接通"同步机制 + 修复字段映射

### 实施步骤

#### Step 1: 修复字段映射（紧急）
- Neo4j 投影时只同步 PG 的字段
- 统一字段名：Neo4j Position 用 `name`（不带 _cn），用 PG 现有数据
- 删除 Neo4j 的 `name_cn` 字段（或只作为派生属性）

#### Step 2: 接入同步机制（核心）
- 写路径：所有 `position_records` / `skill_records` 的 INSERT/UPDATE 之后，调用 `projector.apply_change()`
- 失败重试：outbox 表 + 单独 worker

#### Step 3: 定时 reconcile
- 每天凌晨 3 点跑 `projector.reconcile_all()`
- 检查结果写入 `audit_events` 表

#### Step 4: 监控
- 增加 `/admin/data-truth` 的"同步健康度"指标
- 孤儿节点数 > 0 → 触发 P1 级别告警

### 不推荐的方案
- **方案 A**：成本太高，需要重写大量代码
- **方案 C**：完整 outbox + worker 是大工程，6 个月工作量

---

## 结论

**当前架构不符合企业级数据规范**，但已经走在正确的路上：
- ✅ GraphProjector 服务设计正确
- ✅ `/admin/data-truth` 端点存在（让用户看到差异）
- ❌ 同步机制未接通
- ❌ 字段映射不一致
- ❌ 监控缺失

**最小修复路径**（方案 B 轻量版）：
1. 修复字段映射（P0，立即）
2. 接入 apply_change 到写路径（P0，立即）
3. 添加定时 reconcile（P1，1 周内）
4. 完善监控（P2，长期）

总工作量约 **3-5 人天**。