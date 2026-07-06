# Phase 1 SPEC: 核心Bug修复

**Phase:** 1 of 6
**Goal:** 修复所有运行时错误，将内存存储迁移到持久化，消除安全漏洞
**Created:** 2026-07-03

## Deliverables

### D1: 运行时错误修复 (RUNTIME)
- **RUNTIME-01**: `status_aggregator.py` 第151行引用 `EvolutionSnapshot.snapshot_at` → 修正为 `snapshot_date`（模型实际列名）
- **RUNTIME-02**: `loop_orchestrator.py` Step3 `sync_from_pipeline` 未实现 → 实现 `graph_service.sync_from_pipeline(run_id)` 从 pipeline_runs 提取数据写入 Neo4j
- **RUNTIME-03**: `match_service.py` 第102行 `__import__("json")` → 顶部 `import json`

### D2: 内存存储持久化 (PERSIST)
- **PERSIST-01**: `match_service._MATCH_RESULTS` (max 1000, 内存) → PostgreSQL match_results 表读写
- **PERSIST-02**: `loop_orchestrator._LOOP_RESULTS` (max 200, 内存) → 新建 loop_results 表或复用 pipeline_runs
- **PERSIST-03**: `admin._demo_audit_queue` (内存) → PostgreSQL review_queue 表（模型已存在）

### D3: 安全修复 (SEC)
- **SEC-01**: `admin.py` 图谱节点CRUD Cypher字符串拼接 → 参数化查询
- **SEC-02**: `config.py` 默认密码 `starmap123456` / `dev_secret` → 移至 .env，源码中用占位符

## Ambiguity Assessment

| Dimension | Score | Notes |
|-----------|-------|-------|
| Scope clarity | 0.05 | 8个需求全部明确，无歧义 |
| Technical approach | 0.10 | sync_from_pipeline实现方案需确认 |
| Dependencies | 0.05 | 无外部依赖，仅内部代码修改 |
| Acceptance criteria | 0.05 | 每个需求有明确验证方式 |
| **Overall** | **0.06** | ✅ 远低于0.20门禁 |

## Acceptance Criteria

1. `pytest` 全部通过，0 AttributeError
2. 重启后端后 match_results / loop_results / review_queue 数据不丢失
3. Cypher 查询全部参数化（grep验证无字符串拼接）
4. 源码中无明文密码（grep验证）
5. 后端 ruff check 0 errors
6. 后端测试覆盖率 ≥ 60%
