# Phase 2 SPEC: 后端硬编码消除

**Phase:** 2 of 6
**Goal:** 消除所有硬编码数据源，让系统从Neo4j图谱动态加载，确保52个岗位全部可匹配

## Deliverables

### D1: 匹配引擎图谱驱动 (MATCH) — 5 items
- MATCH-01: 删除 POSITION_SKILL_PROFILES 硬编码字典（8个岗位）
- MATCH-02: _load_target_profile() 改为从 Neo4j 加载
- MATCH-03: 从 REQUIRES 关系提取 required/bonus（基于 importance 属性）
- MATCH-04: Neo4j 不可用时返回 404（不再 fallback 硬编码）
- MATCH-05: 技能匹配增加语义相似度（ChromaDB 向量检索）

### D2: EVOLVES_TO 写入 Neo4j (EVOLVE) — 4 items
- EVOLVE-01: orchestrator._save_paths_to_db() 末尾添加 Neo4j 写入
- EVOLVE-02: 构建 EVOLVES_TO 三元组
- EVOLVE-03: 属性: direction, skill_overlap, key_gaps, evidence_count, trust_score
- EVOLVE-04: 调用 graph_writer.write_triples_to_graph()

### D3: 学习路径去硬编码 (LEARN) — 3 items
- LEARN-01: DEFAULT_PREREQUISITES → 从 Neo4j PREREQUISITE 关系加载
- LEARN-02: _BASE_HOURS → 从 Neo4j Skill 节点属性加载
- LEARN-03: 学习路径时间线组件 JSON → 格式化 UI

### D4: 演化趋势真实数据 (TREND) — 3 items
- TREND-01: /evolution/trends 移除模拟CII → 返回空+提示
- TREND-02: /quality/dashboard 幻觉趋势从真实timeseries计算
- TREND-03: days 查询参数不再被忽略

### D5: Pipeline executor 去硬编码 (PIPE-HC) — 3 items
- PIPE-HC-01: keyword 从 DataSourceRecord 读取
- PIPE-HC-02: max_count 可配置
- PIPE-HC-03: _update_source_after_dedup 不硬编码 "bosszhipin"

## Acceptance Criteria

1. 52个岗位全部可匹配（grep验证无硬编码Profile）
2. MATCH (a:Position)-[r:EVOLVES_TO]->(b:Position) RETURN count(r) > 0
3. /evolution/trends 无模拟CII数据
4. /quality/dashboard 幻觉趋势从真实数据计算
5. Pipeline crawl keyword 从配置读取
6. ruff check + pytest 全部通过
