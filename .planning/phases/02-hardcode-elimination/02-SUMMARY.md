# Phase 2 SUMMARY: 后端硬编码消除

**Phase:** 2 of 6
**Completed:** 2026-07-03
**Status:** ✅ VERIFIED

## Deliverables Completed

### D1: 匹配引擎图谱驱动 (MATCH) ✅
- MATCH-01: POSITION_SKILL_PROFILES 硬编码字典已完全删除
- MATCH-02: _load_target_profile() 从 Neo4j 加载（Tier 1: PositionRepository, Tier 2: Neo4j graph）
- MATCH-03: 从 REQUIRES 关系提取 required/bonus（基于 importance 属性）
- MATCH-04: Neo4j 不可用时返回 None → API 返回 404
- MATCH-05: 添加 ChromaDB 语义相似度匹配（阈值 0.85）

### D2: EVOLVES_TO 写入 Neo4j (EVOLVE) ✅
- EVOLVE-01: _save_paths_to_db() 末尾调用 _write_evolves_to_graph()
- EVOLVE-02: 构建 EVOLVES_TO 三元组 (source_pos)-[EVOLVES_TO]->(target_pos)
- EVOLVE-03: 属性: direction, skill_overlap(float), key_gaps, evidence_count, trust_score, similarity
- EVOLVE-04: 调用 graph_writer.write_triples_to_graph()，Neo4j 失败不影响 PG

### D3: 学习路径去硬编码 (LEARN) ✅
- LEARN-01: _load_prerequisites_from_neo4j() 从 Neo4j PREREQUISITE 关系加载，5分钟缓存
- LEARN-02: _load_skill_hours_from_neo4j() 从 Skill 节点属性加载，5分钟缓存
- LEARN-03: 硬编码值保留为 fallback（Neo4j 不可用时）

### D4: 演化趋势真实数据 (TREND) ✅
- TREND-01: /evolution/trends 已移除模拟 CII → 返回空数组+日志提示
- TREND-02: /quality/dashboard 幻觉趋势从真实 skill_timeseries 计算
- TREND-03: days 查询参数已生效（cutoff = now - days）

### D5: Pipeline executor 去硬编码 (PIPE-HC) ✅
- PIPE-HC-01: keyword 从 DataSourceRecord 配置读取
- PIPE-HC-02: max_count 可配置
- PIPE-HC-03: _update_source_after_dedup 不再硬编码 "bosszhipin" → 查询所有 active crawler 源

## Verification Results

| Check | Result |
|-------|--------|
| ruff check app/ | ✅ 0 errors |
| pytest tests/ | ✅ 468 passed, 5 skipped |
| vue-tsc --noEmit | ✅ 0 errors |
| ESLint | ✅ 0 errors, 31 warnings |
| POSITION_SKILL_PROFILES | ✅ 已删除 |
| 模拟CII数据 | ✅ 已移除 |
| "bosszhipin"硬编码 | ✅ 已移除 |

## Files Modified (backend)
- app/services/match_service.py — 图谱驱动匹配 + ChromaDB语义匹配
- app/core/evolution/orchestrator.py — EVOLVES_TO Neo4j写入
- app/core/learning/path_engine.py — Neo4j前置依赖/学时加载 + 5分钟缓存
- app/core/pipeline/executor.py — 去硬编码keyword/source
- app/api/v1/evolution.py — 移除模拟CII + days参数生效
- app/api/v1/quality.py — 幻觉趋势从真实数据计算
- app/api/v1/learning.py — 移除 POSITION_SKILL_PROFILES 引用

## Files Modified (frontend)
- src/components/PipelineStageCard.vue — StageData类型更新 + cancelled状态
- src/pages/PipelineMonitor.vue — waiting→pending, errors类型修复, cancelled支持
