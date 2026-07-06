# Phase 1: 核心Bug修复 — Specification

**Created:** 2026-07-03
**Ambiguity score:** 0.10 (gate: ≤ 0.20)
**Requirements:** 8 locked (3 RUNTIME + 3 PERSIST + 2 SEC)

## Goal

修复所有运行时错误（AttributeError、未实现的TODO、内联import错误），将3处内存存储迁移到PostgreSQL持久化，消除2处安全漏洞（Cypher注入、明文密码）。

## Requirements

### 1. RUNTIME-01: status_aggregator.py snapshot_at → snapshot_date
- **Current:** `EvolutionSnapshot.snapshot_at` 字段不存在，真实字段为 `snapshot_date`。当前代码在运行时抛出 AttributeError。
- **Target:** 将 `status_aggregator.py` 中的 `snapshot_at` 替换为 `snapshot_date`，确保 trend 查询正常。
- **Acceptance:** `GET /api/v1/pipeline/data-quality` 返回 `metrics.trend` 不为空（从 evolution_snapshots 读取真实数据）。

### 2. RUNTIME-02: loop_orchestrator Step3 sync_from_pipeline 实现
- **Current:** ✅ **已完成** — sync_from_pipeline 已在 graph_service.py 实现，loop_orchestrator 已调用。
- **Acceptance:** 验证 `loop_orchestrator._step3_graph_update` 不返回 `DEGRADED`（或 `not yet implemented`）。

### 3. RUNTIME-03: match_service.py 内联 import json
- **Current:** `match_service.py` 中有 `__import__("json")` 内联导入，应改为顶部 `import json`。
- **Target:** 移除 `__import__("json")`，替换为标准 `import json`。
- **Acceptance:** `poetry run ruff check .` 不再警告内联导入。

### 4. PERSIST-01: match_results 内存 → PostgreSQL
- **Current:** `match_service._MATCH_RESULTS` 是进程内 dict（`_MATCH_RESULTS: dict[str, dict] = {}`），重启后丢失。
- **Target:** 将 match_results 写入 `match_results` PostgreSQL 表（已有模型），通过 session query 读取。
- **Acceptance:** 匹配诊断后重启后端，历史匹配结果仍在（`GET /match/results` 返回之前的数据）。

### 5. PERSIST-02: loop_results 内存 → PostgreSQL
- **Current:** `loop_orchestrator._LOOP_RESULTS` 是进程内 dict，重启后丢失。
- **Target:** 将 loop 闭环结果写入 PostgreSQL（已有 pipeline_runs 或新表）。
- **Acceptance:** 闭环演示完成后重启后端，历史闭环结果可查询。

### 6. PERSIST-03: admin._demo_audit_queue 内存 → PostgreSQL
- **Current:** `admin.py` 中的 `_demo_audit_queue` 是进程内列表，使用 review_queue 模型但未持久化。
- **Target:** 写入 `review_queue` PostgreSQL 表。
- **Acceptance:** Admin 审核队列数据在重启后端后不丢失。

### 7. SEC-01: 图谱节点CRUD Cypher注入
- **Current:** `admin.py` 图谱节点 CRUD 使用字符串拼接构建 Cypher 查询，存在注入风险。
- **Target:** 全部改为参数化查询（`$param` 语法）。
- **Acceptance:** 包含特殊字符（如 `'` 或 `"`）的节点名称创建/查询不报错。

### 8. SEC-02: 默认密码移至 .env
- **Current:** `config.py` 中包含明文默认密码（如 neo4j_password 默认值）。
- **Target:** 默认密码仅从 `.env` 读取，代码中不含明文密码值。
- **Acceptance:** `grep -r "starmap123456" app/config.py` 无匹配。

## Acceptance Criteria

- [ ] AC-01: `GET /pipeline/data-quality` 返回 `trend` 数组不为空
- [ ] AC-02: `loop_orchestrator._step3_graph_update` 不返回 `DEGRADED`
- [ ] AC-03: `match_service.py` 中无 `__import__("json")`
- [ ] AC-04: 匹配诊断后重启后端，`GET /match/results` 仍返回之前的数据
- [ ] AC-05: 闭环演示后重启后端，历史闭环结果可查询
- [ ] AC-06: Admin 审核队列重启后不丢失
- [ ] AC-07: 节点名包含 `'` 的图谱CRUD操作正常
- [ ] AC-08: `config.py` 中无明文密码硬编码

## Boundaries

**In scope:**
- 3 处运行时错误修复
- 3 处内存→数据库持久化
- 2 处安全修复

**Out of scope:**
- ❌ 匹配引擎图谱驱动（Phase 2 MATCH-*）
- ❌ Pipeline 硬编码消除（Phase 2 PIPE-HC-*）
- ❌ 前端功能闭环（Phase 3）
- ❌ 数据流贯通（Phase 4）
- ❌ 样式统一（Phase 5）
- ❌ 架构重构（Phase 6）

## Execution Plan (Auto-Generated)

### Wave 1: 运行时修复 (RUNTIME)
- Task 1: 修复 status_aggregator.py snapshot_at → snapshot_date
- Task 2: 验证 sync_from_pipeline 已实现
- Task 3: 修复 match_service.py __import__("json")

### Wave 2: 持久化迁移 (PERSIST)
- Task 4: match_results 内存→PostgreSQL
- Task 5: loop_results 内存→PostgreSQL
- Task 6: admin audit_queue 内存→PostgreSQL

### Wave 3: 安全修复 (SEC)
- Task 7: Cypher 注入修复（参数化查询）
- Task 8: 默认密码移至 .env