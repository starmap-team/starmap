# Phase 1 PLAN: 核心Bug修复

**Phase:** 1 of 6
**Created:** 2026-07-03
**Status:** Ready for execution

## Execution Waves

### Wave 1: 运行时错误修复 (独立，可并行)

#### Plan 1-1: status_aggregator snapshot_at 修复
- **File**: `backend/app/core/pipeline/status_aggregator.py`
- **Change**: 第151行 `EvolutionSnapshot.snapshot_at` → `EvolutionSnapshot.snapshot_date`
- **Verify**: `pytest tests/ -k status` 通过

#### Plan 1-2: match_service json import 修复
- **File**: `backend/app/services/match_service.py`
- **Change**: 删除第102行 `__import__("json")` → 顶部添加 `import json`
- **Verify**: `ruff check app/services/match_service.py` 通过

#### Plan 1-3: sync_from_pipeline 实现
- **File**: `backend/app/services/graph_service.py` (新增函数)
- **File**: `backend/app/core/pipeline/loop_orchestrator.py` (调用新函数)
- **Implementation**:
  1. `graph_service.py` 新增 `sync_from_pipeline(run_id: str)`:
     - 查询 `jd_extraction_records` 中 `pipeline_run_id == run_id` 的记录
     - 调用 `graph_writer.batch_write_extractions(records)` 写入 Neo4j
     - 返回 `{"synced": True, "nodes_written": N, "edges_written": M}`
  2. `loop_orchestrator.py` Step3 调用 `sync_from_pipeline`:
     - 替换当前的 `{"synced": False, "note": "not yet implemented"}`
     - 添加 try/except：Neo4j 写入失败不影响其他步骤
- **Verify**: 闭环演示 Step3 不再降级

### Wave 2: 内存存储持久化 (依赖 Wave 1)

#### Plan 1-4: match_results 持久化
- **File**: `backend/app/services/match_service.py`
- **Change**:
  1. `_MATCH_RESULTS` 内存缓存保留作为读缓存
  2. `_persist_match_result()` 改为写入 PostgreSQL match_results 表
  3. `get_match_result()` 改为先查缓存，miss 时查 PG
  4. 启动时从 PG 恢复缓存（可选，非必须）
- **Verify**: 匹配后查询 `SELECT count(*) FROM match_results` > 0

#### Plan 1-5: loop_results 持久化
- **File**: `backend/app/models/pipeline_models.py` (新增 LoopResult 模型)
- **File**: `backend/alembic/versions/` (新增迁移 008)
- **File**: `backend/app/core/pipeline/loop_orchestrator.py`
- **Change**:
  1. 新增 `LoopResult` 模型：id, run_id, steps_json(JSONB), status, error_log, created_at, completed_at
  2. Alembic 迁移 008 创建 loop_results 表
  3. `_LOOP_RESULTS` 内存存储 → PG 写入
  4. `get_loop_status()` 从 PG 读取
- **Verify**: 闭环运行后重启，loop 结果不丢失

#### Plan 1-6: review_queue 持久化
- **File**: `backend/app/api/v1/admin.py`
- **Change**:
  1. `_demo_audit_queue` 内存列表 → 查询 review_queue 表
  2. 审核操作（approve/reject）→ UPDATE review_queue 表
  3. 初始化时从 PG 加载待审核项
- **Verify**: 重启后端后审核队列不丢失

### Wave 3: 安全修复 (独立)

#### Plan 1-7: Cypher 参数化
- **File**: `backend/app/api/v1/admin.py`
- **Change**: 第504/529/555行字符串拼接 Cypher → 参数化查询
  - `f"MATCH (n:{label}) WHERE n.name = '{name}'"` → `"MATCH (n:$label) WHERE n.name = $name"` + params
  - 注意：Neo4j 不支持节点标签参数化，需用白名单验证 + 字符串拼接标签，属性值参数化
- **Verify**: `ruff check` + `pytest` 通过

#### Plan 1-8: 密码安全
- **File**: `backend/app/config.py`
- **File**: `.env.example`
- **Change**:
  1. `neo4j_password` 默认值 `"starmap123456"` → `"CHANGE_ME_IN_ENV"`
  2. `postgres_uri` 默认值含密码 → 改为从组件构建，密码默认 `"CHANGE_ME_IN_ENV"`
  3. `secret_key` 默认 `"dev_secret"` → `"CHANGE_ME_IN_ENV"`
  4. `.env.example` 更新注释说明
  5. 添加 `@model_validator` 启动时检查非占位符（仅非 dev 模式）
- **Verify**: `grep -r "starmap123456" app/` 返回空

## Dependency Graph

```
Wave 1 (并行):  Plan 1-1 ─┐
                Plan 1-2 ─┤
                Plan 1-3 ─┘
                         │
Wave 2 (串行):  Plan 1-4 ─→ Plan 1-5 ─→ Plan 1-6
                         │
Wave 3 (并行):  Plan 1-7 ─┐
                Plan 1-8 ─┘
```

## Verification Checklist

- [ ] `pytest` 全部通过
- [ ] `ruff check app/` 0 errors
- [ ] 重启后端后 match_results 数据不丢失
- [ ] 重启后端后 loop_results 数据不丢失
- [ ] 重启后端后 review_queue 数据不丢失
- [ ] `grep -r "starmap123456" app/` 返回空
- [ ] `grep -r "snapshot_at" app/core/pipeline/status_aggregator.py` 返回空
- [ ] 闭环演示 Step3 不再降级
- [ ] Cypher 查询无字符串拼接属性值
