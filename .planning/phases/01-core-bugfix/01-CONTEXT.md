# Phase 1 CONTEXT: 核心Bug修复

**Phase:** 1 of 6
**Created:** 2026-07-03

## Key Decisions

### DEC-P1-01: sync_from_pipeline 实现方案
**选项A**: 从 pipeline_runs.stages[graph_sync] 提取已写入的数据 → 写入 Neo4j
**选项B**: 从 extraction_records 表查询本次 run 新增的抽取记录 → 调用 graph_writer 批量写入
**决定**: **选项B** — 更可靠，graph_writer 已有完整的批量写入逻辑，直接复用

### DEC-P1-02: loop_results 持久化方案
**选项A**: 新建 loop_results 表
**选项B**: 复用 pipeline_runs 表，增加 loop_type 字段
**决定**: **选项A** — 新建 loop_results 表，结构更清晰，不影响现有 pipeline_runs 查询

### DEC-P1-03: match_results 缓存策略
**选项A**: 完全移除内存缓存，每次从 PostgreSQL 读取
**选项B**: 保留内存缓存作为读缓存，写入时同时写 PG 和缓存
**决定**: **选项B** — 保留缓存提升读取性能，但写入必须双写 PG+缓存，重启时从 PG 恢复

### DEC-P1-04: Cypher 参数化方案
**选项A**: 使用 Neo4j driver 的参数化查询 `session.run(query, params)`
**选项B**: 使用 Pydantic 验证 + 白名单过滤
**决定**: **选项A** — Neo4j driver 原生参数化是标准做法，最安全

### DEC-P1-05: 密码处理方案
**选项A**: config.py 中设空字符串默认值，.env 中必须配置
**选项B**: config.py 中设占位符如 "CHANGE_ME"，启动时检查非占位符
**决定**: **选项B** — 占位符方案更安全，启动时可以验证

## Technical Notes

- match_results 表已存在（Alembic 004），有 id, position_name, user_skills, match_score, matched_skills, missing_skills, created_at 字段
- review_queue 表已存在（extraction_models.py），有 id, skill_name, source, status, reviewer, reviewed_at, created_at 字段
- loop_results 需新建表：id, run_id, steps_json, status, created_at, completed_at
- graph_writer.batch_write_extractions() 已实现完整的 Neo4j 批量写入
