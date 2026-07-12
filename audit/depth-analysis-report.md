# StarMap 非审计维度深度分析报告

**日期**: 2026-07-08
**与修复工作流的分工**: 修复代理处理安全审计 49 项(C1-C4/H2-H17/M1-M22/L1-L10)，本报告覆盖审计**不会触及**的三个维度：业务逻辑、架构性能、功能拓展

---

## 一、业务逻辑发现 (16 项)

### P0 — 逻辑缺陷

| # | 模块 | 问题 | 影响 | 建议 |
|---|------|------|------|------|
| BL-01 | `judge_service.py:229` | F1 计算：golden 和 system 都为空集时返回 (1.0, 1.0, 1.0) | 空匹配被误判为完美匹配，污染评估指标 | 空集对空集应返回 N/A 或跳过，不应计为 F1=1.0 |
| BL-02 | `jd_extract.py:248-264` | Pydantic 验证失败时 fallback 逻辑手动重建 `JDExtractionResult`，但不处理 `tools`/`prerequisites`/`learning_resources`/`evolves_to` | LLM 返回异常结构时丢失 4 个关键字段，下游依赖这些字段的匹配/路径模块可能出错 | 完整 fallback 所有字段，或记录 warning 并返回空结果 |
| BL-03 | `scorer.py:118-119` | `_semantic_similarity` 对所有 candidate 做 O(n) 遍历，且 SequenceMatcher 本身 O(n²) | 大量技能时匹配评分 O(n³)，target_skills=50 + person_skills=50 时可感知卡顿 | 预计算 person_skills 的 canonical name 索引，skip 自身；对 >20 技能用 Bloom filter 预筛 |

### P1 — 算法问题

| # | 模块 | 问题 | 影响 | 建议 |
|---|------|------|------|------|
| BL-04 | `path_engine.py:312-316` | 拓扑排序检测到环时 fallback 直接返回原始 key 顺序，忽略依赖关系 | 学习路径中前置技能可能排在后面，用户先学高级再学基础 | 用 SCC (强连通分量) 压缩环为超级节点，再做拓扑排序 |
| BL-05 | `path_engine.py:200-235` | 学习时长估算 `multiplier = 0.5 + proficiency_gap`，无实测数据支撑 | 估算偏差大，用户看到"2-3周"实际需要2个月 | 引入历史学习数据校准，或至少按技能类别区分基础系数 |
| BL-06 | `service.py:185-221` | CII 通胀修正排序 key 为 `(proficiency_score, source_count)` 但 proficiency 默认"熟悉"=0.65 对大多数技能相同 | 降级几乎完全依赖 source_count，低来源数但实际重要的技能可能被误降 | 加入技能在行业中的稀缺度/重要性权重 |
| BL-07 | `emergence_finder.py:188-200` | Z-score 对 history_len < 2 直接返回 STABLE，但 history_len=2 时方差极不稳定 | 新技能早期信号被忽略，2 个数据点时 z-score 可被单个异常值主导 | history_len < 5 时使用 Wilson score interval 或贝叶斯估计替代 |
| BL-08 | `jd_extract.py:277-289` | `_clean_skill_name` 循环剥离后缀直到稳定，但 `len(name) >= 3` 阈值可能误切 | "渗透测试"→"渗透"(3字,不会切)、"安全攻防"→"安全"(3字,不会切)；但"分布式系统架构"→"分布式系统"(6字,会切后缀)→"分布式"(6→3字,会切!) → 误切 | 提高最小长度阈值到 4，或使用白名单技能名跳过清理 |

### P2 — 数据一致性

| # | 模块 | 问题 | 影响 | 建议 |
|---|------|------|------|------|
| BL-09 | `service.py:383-423` | `_save_match_result` 用 raw SQL + `CAST(...AS jsonb)` 但 match_results 表可能缺少 cii 列 | 新增 cii 字段后如果数据库迁移未执行，所有匹配结果持久化静默失败 | 使用 ORM 模型代替 raw SQL，或加 Alembic 迁移 |
| BL-10 | `normalize.py` vs `prompt.py` | 归一化别名表硬编码 191 组，但 v3/v4 Prompt 引导提取更多中文技能名 | 归一化覆盖率不足导致评估 F1 偏低（已知 0.8767→0.90 缺口的主因） | 将 `skill_taxonomy.yaml` (198 技能) 别名接入，预期 F1 +0.02~0.03 |
| BL-11 | `judge_service.py:293-304` | 批量评估 system 无对应 sample 时当空集处理，F1=0 | 单条样本失败拉低整体 avg_f1，但实际是数据对齐问题而非模型问题 | 缺失 sample 应标记为 "skipped" 而非 F1=0 |
| BL-12 | `scorer.py:136` | `recall_score = 0.5*exact + 0.3*fuzzy + 0.2*semantic` 权重无验证 | 三个分数量纲不同（exact∈{0,1}, fuzzy∈[0,1], semantic∈[0,1]），加权无理论依据 | 做消融实验验证最优权重，或改为 cascading 逻辑 |

### P3 — 边界条件

| # | 模块 | 问题 | 影响 | 建议 |
|---|------|------|------|------|
| BL-13 | `cache.py:52-56` | profile_cache 全局 TTL，一次过期清空所有岗位缓存 | 多岗位同时请求时缓存雪崩，全部回源 | 改为 per-key TTL |
| BL-14 | `path_engine.py:331` | `phase_hours_budget = weekly_hours * 2` 固定 2 周预算 | 每阶段固定 2 周，但有些技能需要 6 周，会被拆到 3 个阶段 | 按技能时长自适应分组 |
| BL-15 | `emergence_finder.py:97-121` | `DOMAIN_KEYWORDS` 硬编码 4 个领域，无法扩展 | 新行业（如"新能源""医疗AI"）无法被识别 | 从配置文件或数据库加载领域关键词 |
| BL-16 | `prompt.py:362` | `_ACTIVE_VERSIONS["jd_extraction"] = "v1"` 但 v3/v4 已有更好 recall | v1 是保守版本，F1 最差但却是默认激活版 | 基于 A/B 测试数据激活 v4 |

---

## 二、架构与性能发现 (14 项)

### P1 — 性能瓶颈

| # | 类别 | 问题 | 影响 | 建议 |
|---|------|------|------|------|
| AP-01 | 性能 | `path_engine.py` 全局缓存 `_prereqs_cache`/`_skill_hours_cache` 是进程级变量，多 worker 各持一份 | worker 1 加载的缓存 worker 2 无法复用；重启丢失 | 迁移到 Redis 共享缓存 |
| AP-02 | 性能 | `cache.py:MatchCache` 是线程级单例，uvicorn 多 worker 模式下各自独立 | 1000 条结果缓存 × N worker = N×1000 内存开销 | 优先查 Redis，本地只做 LRU 热数据 |
| AP-03 | 性能 | `scorer.py` 每次匹配对每个 target skill 遍历所有 person skills | 50 target × 50 person = 2500 次 SequenceMatcher，每次 O(n²) | 预构建 BK-tree 或使用编辑距离预筛 |
| AP-04 | 性能 | `llm_client.py` 每次抽取调用 2 次 LLM（抽取 + 反幻觉） | 延迟翻倍（MiMo ~55s/次 → 总 ~110s），成本翻倍 | 反幻觉改为异步/可选，或缓存常见 hallucinated skills 黑名单 |

### P2 — 架构风险

| # | 类别 | 问题 | 影响 | 建议 |
|---|------|------|------|------|
| AP-05 | 架构 | Neo4j 和 PostgreSQL 数据可能不同步（graph_writer 写 Neo4j，ORM 写 PG） | 匹配引擎三级 fallback (repo→graph→pg) 正是因为数据可能不一致 | 引入统一写入事务或 CDC 同步机制 |
| AP-06 | 架构 | `resources.py` 全局 `AppResources` 单例，无连接池大小配置 | 默认 SQLAlchemy pool_size=5，uvicorn 4 worker × 高并发 → 连接耗尽 | 在 `get_async_engine()` 配置 pool_size/max_overflow |
| AP-07 | 架构 | SSE `event_stream` 无连接数限制，每个客户端一个 pubsub | 100 个 SSE 客户端 = 100 个 Redis pubsub 连接 + 100 个长连接 | 添加 MAX_SSE_CLIENTS 限制，超限返回 503 |
| AP-08 | 架构 | Celery tasks (`tasks/celery_app.py`) 缺少幂等性保证 | 重试时 pipeline 阶段可能重复执行 | 使用 `task_acks_late=True` + 幂等性 key |
| AP-09 | 可扩展 | `DOMAIN_KEYWORDS` 和 `authority_scores` 硬编码在代码中 | 新增数据源/领域需改代码重启 | 迁移到数据库或配置文件 |

### P3 — 可观测性

| # | 类别 | 问题 | 影响 | 建议 |
|---|------|------|------|------|
| AP-10 | 可观测 | loguru 无结构化输出，日志无法被 ELK/Loki 高效查询 | 排查线上问题靠 grep | 配置 `logger.add(sink, serialize=True)` JSON 输出 |
| AP-11 | 可观测 | 无业务指标追踪（匹配延迟、抽取成功率、LLM 降级率） | 无法量化服务质量 | 添加 Prometheus metrics 或自定义指标中间件 |
| AP-12 | 可观测 | LLM 降级链无追踪（MiMo→DeepSeek→Xunfei→Qwen） | 不知道降级频率和原因 | 每次降级记录 event，暴露 `/metrics` 端点 |
| AP-13 | 可观测 | A/B 测试结果无自动统计 | `prompt.py` 有 A/B 测试框架但无效果分析闭环 | 添加 `GET /admin/ab-test/{name}/results` 统计端点 |
| AP-14 | 性能 | `normalize.py` 别名表在模块加载时从 YAML 解析，每次请求查字典 | 191 组别名查 O(1)，可接受；但 `normalize_by_vector` 每次调 ChromaDB | 向量归一化结果加 Redis 缓存 |

---

## 三、功能拓展机会 (12 项)

### P0 — 必须有

| # | 类别 | 建议 | 价值 | 难度 | 依赖 |
|---|------|------|------|------|------|
| FE-01 | 算法 | **激活 v4 Prompt + 增强归一化别名表**：当前 F1=0.8767 未达门禁 0.90，f1_optimization_plan.md 明确指出归一化增强可 +0.02~0.03 | F1 达标→可上线 | 低 | 无 |
| FE-02 | 功能 | **Prompt A/B 测试效果统计闭环**：已有 A/B 框架但无结果端点，无法判断 v1 vs v4 孰优 | 数据驱动的 Prompt 迭代 | 低 | FE-01 |
| FE-03 | 数据 | **用户反馈回流机制**：匹配结果"是否准确"投票→加权更新匹配权重 | 匹配质量持续提升 | 中 | 用户系统 |

### P1 — 应该有

| # | 类别 | 建议 | 价值 | 难度 | 依赖 |
|---|------|------|------|------|------|
| FE-04 | 功能 | **反向匹配**：根据用户技能推荐适合的岗位（当前只有岗位→技能单向） | 求职者核心需求 | 中 | 无 |
| FE-05 | 功能 | **个人技能档案页**：用户管理自己的技能树+熟练度 | 匹配诊断的数据源 | 中 | 用户系统 |
| FE-06 | 算法 | **匹配评分权重消融实验**：当前 0.5*exact+0.3*fuzzy+0.2*semantic 无验证 | 优化匹配准确度 | 低 | 无 |
| FE-07 | UX | **学习进度追踪+打卡**：当前学习路径只生成不追踪 | 用户留存 | 中 | FE-05 |
| FE-08 | 算法 | **技能生命周期追踪**：新兴→上升→成熟→衰退全周期可视化 | 演化看板增强 | 中 | 时间序列数据积累 |

### P2 — 可以有

| # | 类别 | 建议 | 价值 | 难度 | 依赖 |
|---|------|------|------|------|------|
| FE-09 | UX | **多岗位对比匹配**：同时对比 2-3 个岗位的技能缺口 | 职业规划决策支持 | 中 | 无 |
| FE-10 | 算法 | **时间序列预测**(ARIMA/Prophet)替代 Z-score 静态比较 | 新兴技能预测更前瞻 | 高 | 历史数据积累 |
| FE-11 | 集成 | **Webhook 推送**替代轮询获取 pipeline 结果 | 实时性 + 降低服务器负载 | 中 | 无 |
| FE-12 | 数据 | **Golden Set 标注口径校准**：安全/产品经理等非标岗位 golden 质量存疑 | 评估基线准确性 | 低 | 人工审核 |

---

## 四、优先级路线图

### 立即可做（1-2 天，零依赖）

| # | 行动 | 预期收益 |
|---|------|---------|
| FE-01 | 激活 v4 Prompt + 补齐归一化别名表 | F1 0.8767 → ≥0.90 |
| BL-16 | `_ACTIVE_VERSIONS["jd_extraction"]` 改为 "v4" | 同上 |
| FE-02 | 添加 A/B 测试结果统计端点 | 数据驱动迭代 |
| FE-06 | 匹配评分权重消融实验 | 验证/优化匹配 |

### 本周可做（3-5 天）

| # | 行动 | 预期收益 |
|---|------|---------|
| BL-01 | Judge F1 空集处理改为 skip | 评估指标更准确 |
| BL-02 | Pydantic fallback 补全所有字段 | 下游模块数据完整 |
| BL-13 | profile_cache 改 per-key TTL | 消除缓存雪崩 |
| AP-06 | 配置数据库连接池 | 避免高并发连接耗尽 |
| AP-07 | SSE 连接数限制 | 防止资源耗尽 |

### 本月可做（1-2 周）

| # | 行动 | 预期收益 |
|---|------|---------|
| AP-01/02 | 缓存迁移到 Redis | 多 worker 共享 |
| FE-04 | 反向匹配 API | 核心求职功能 |
| FE-12 | Golden Set 标注校准 | 评估基线准确 |
| BL-04 | 拓扑排序环检测改进 | 学习路径合理性 |
| AP-10/11 | 结构化日志 + 业务指标 | 可观测性 |

---

## 五、与修复工作流的协同

| 修复工作流 | 本报告重叠 | 本报告互补 |
|-----------|-----------|-----------|
| Phase 1 Fix Critical (C1-C4) | 无 | 无 |
| Phase 2 Fix High (H2-H17) | 部分 AP-06/07 可能在 H 类中 | 业务逻辑 BL-01~16 全部独立 |
| Phase 3 Fix Medium (M1-M22) | AP-09 (硬编码配置) 可能在 M 类中 | 架构性能 AP-01~05 全部独立 |
| Phase 4 Fix Low (L1-L10) | AP-10 (结构化日志) 可能在 L 类中 | 功能拓展 FE-01~12 全部独立 |
| Phase 5 Verify | 无 | FE-01 (F1 达标验证) 可作为 Verify 补充 |

**核心结论**: 修复工作流解决"安全合规"，本报告解决"业务正确+性能+增长"。两者正交互补，不冲突。
