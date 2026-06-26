# 星图(StarMap) —— 岗位能力演化子系统设计文档

> 文档版本：v1.0 | 日期：2026-06-23 | 基于 50 条真实 JD 评测数据设计

---

## 目录

- [一、概述与设计目标](#一概述与设计目标)
- [二、真实数据分析](#二真实数据分析)
- [三、系统架构设计](#三系统架构设计)
- [四、核心算法设计（融合 §7.1-7.3）](#四核心算法设计融合-71-73)
- [五、API 接口设计](#五api-接口设计)
- [六、数据库设计](#六数据库设计)
- [七、数据流与处理管线](#七数据流与处理管线)
- [八、测试策略](#八测试策略)
- [九、实现路线图](#九实现路线图)

---

## 一、概述与设计目标

### 1.1 子系统定位

岗位能力演化子系统是星图系统**模块B（既有岗位能力动态更新）** 的核心实现，同时服务于**模块A（新岗位发现）** 的演化验证环节。该系统负责：

- 追踪岗位技能需求随时间的变化（增/删/改）
- 检测新兴技能的涌现信号
- 基于多源证据生成可信的演化路径
- 为前端演化看板提供时序数据

### 1.2 设计依据

本设计文档基于以下输入：

| 输入 | 说明 |
|------|------|
| `evaluation/real_eval_report/system_real_llm.jsonl` | 50 条真实 LLM 抽取的 JD 结构化数据（eval 数据集） |
| `docs/星图-项目设计文档v2.0.md` §7.1 | 多源交叉验证的数据信任度模型 |
| `docs/星图-项目设计文档v2.0.md` §7.2 | 基于本体约束的幻觉防控机制 |
| `docs/星图-项目设计文档v2.0.md` §7.3 | 岗位演进路径推荐 |

### 1.3 核心设计目标

| 目标 | 量化指标 | 验证方式 |
|------|---------|----------|
| 差分检测准确率 | F1 ≥ 0.85 | 人工标注 30 组新旧快照对比 |
| 涌现检测召回率 | 对已知涌现技能召回 ≥ 0.80 | 回测历史数据中的已知涌现事件 |
| 演化路径合理性 | 人工评审通过率 ≥ 80% | 随机抽 20 条路径由 3 位领域专家评分 |
| 端到端延迟 | 单岗位演化分析 < 30s | Celery 任务监控 |

---

## 二、真实数据分析

### 2.1 数据集概览

`system_real_llm.jsonl` 包含 50 条经 LLM 结构化抽取的 JD 记录，覆盖新一代信息技术领域的主要岗位方向：

```
总记录数：50 条
有效记录：49 条（jd-005 为空噪声记录，已标记）
岗位类别分布：
  ├─ 后端开发：14 条
  ├─ 前端/移动端：7 条
  ├─ AI/ML：5 条
  ├─ 数据：5 条
  ├─ 管理/产品：3 条
  └─ 专业领域：16 条
```

### 2.2 技能频次分析

从 49 条有效 JD 中统计技能出现频次（含 required + bonus），Top 20 如下：

| 排名 | 技能 | 出现次数 | 跨岗位数 | 作为必备 | 作为加分 |
|------|------|---------|---------|---------|---------|
| 1 | Git | 38 | 35 | 30 | 8 |
| 2 | Python | 20 | 17 | 15 | 5 |
| 3 | SQL | 17 | 15 | 14 | 3 |
| 4 | Docker | 16 | 14 | 10 | 6 |
| 5 | Redis | 15 | 14 | 11 | 4 |
| 6 | Linux | 14 | 12 | 12 | 2 |
| 7 | PostgreSQL | 11 | 10 | 9 | 2 |
| 8 | Kubernetes | 10 | 9 | 3 | 7 |
| 9 | TypeScript | 9 | 7 | 5 | 4 |
| 10 | REST API | 9 | 8 | 6 | 3 |
| 11 | JavaScript | 8 | 7 | 4 | 4 |
| 12 | Apache Kafka | 6 | 5 | 1 | 5 |
| 13 | GraphQL | 5 | 3 | 1 | 4 |
| 14 | PyTorch | 5 | 5 | 4 | 1 |
| 15 | Apache Spark | 5 | 4 | 3 | 2 |
| 16 | MongoDB | 5 | 5 | 1 | 4 |
| 17 | CI/CD | 5 | 5 | 3 | 2 |
| 18 | Elasticsearch | 4 | 4 | 1 | 3 |
| 19 | Airflow | 4 | 4 | 2 | 2 |
| 20 | TensorFlow | 4 | 3 | 1 | 3 |

### 2.3 数据质量问题识别

对 50 条数据逐条审计，发现以下质量问题（直接对应 §7.2 幻觉防控的设计输入）：

| 问题类型 | 示例 | 数量 |
|---------|------|------|
| 空记录 | jd-005：所有字段为空/null | 1 |
| 技能重复（required 内） | SQL/gRPC/C# 重复 | 4 |
| 跨类重复（required ∩ bonus） | Spring Boot/JavaScript/GraphQL/CI/CD | 6 |
| 跨类重复（bonus 内） | Tokio/JavaScript | 3 |

**总计**：50 条中有 **12 条（24%）** 存在数据质量问题。这验证了 §7.2 三层防线设计的必要性。

### 2.4 新兴技能涌现信号

| 技能 | 出现次数 | 关联岗位 | 涌现判断依据 |
|------|---------|---------|-------------|
| RAG | 2 | AI 算法、Prompt 工程 | 2024-2025 年新兴，与 LLM 应用落地同步 |
| LangChain | 1 | AI 算法 | LLM 应用框架，2024 年起爆发 |
| ChromaDB | 1（bonus） | Prompt 工程 | 向量数据库新秀 |
| WebAssembly | 2（bonus） | 前端架构师、Rust 开发 | 前端高性能计算趋势 |
| Flutter | 2 | Android(bonus)、专职 Flutter | 跨端方案持续增长 |

---

## 三、系统架构设计

### 3.1 演化子系统在总架构中的位置

```
L7 交互展示层
    └─ EvolutionDashboard.vue
L6 业务编排层
    └─ EvolutionOrchestrator
L5 智能算法层
    ├─ EvolutionEngine (TrendDetector/EmergenceFinder/DiffEngine/PathRecommender)
    ├─ TrustScorer (§7.1)
    └─ HallucinationGuard (§7.2)
L4 知识计算层
    ├─ GraphBuilder / GraphQuerier / OntologyManager
L3 数据服务层
    └─ Neo4j / PostgreSQL / ChromaDB / Redis
```

### 3.2 核心数据流

```
Celery Beat → EvolutionOrchestrator → EvolutionEngine
  → load_snapshot(T1, T2)
  → diff(旧, 新)
  → trust_score(变更)
  → halluc_check(新技能)
  → save_changelog() → update_graph()
  → emit audit event to compliance_log
```

---

## 四、核心算法设计（融合 §7.1-7.3）

### 4.1 差分检测引擎（DiffEngine）

```
新增必备 = R2 - R1
删除必备 = R1 - R2
保留必备 = R1 ∩ R2
晋升为必备 = 新增必备 ∩ B1
降级为加分 = 新增加分 ∩ R1
```

### 4.2 信任度模型（§7.1）

```
TrustChange(C) = w1*SourceCount + w2*TemporalContinuity + w3*CrossValidation + w4*ManualReview
w1=0.35, w2=0.25, w3=0.25, w4=0.15
TrustDecay(T) = Trust(T0) * exp(-0.15 * Δt)
```

### 4.3 幻觉防控（§7.2）三层防线

```
防线1: 本体白名单（精确匹配+语义匹配≥0.85）
防线2: 多源验证（≥3独立来源，跨度≥4周）
防线3: 置信度分级（≥0.8→verified / ≥0.5→pending / <0.5→high_risk）
额外: LLM-as-judge（SUPPORTED/UNSUPPORTED/AMBIGUOUS）
```

### 4.4 EVOLVES_TO 关系发现（§7.3）

```
1. 构建岗位-时间-技能三维矩阵
2. 对每个岗位对计算 Jaccard 相似度
3. 过滤：sim > 0.6, evidence_count ≥ 3, 时序方向正确
4. 建立 EVOLVES_TO 关系持久化到 Neo4j
```

### 4.5 涌现技能检测

```
z = (f(t) - μ) / σ
if z > 2.0 AND f(t) > 3 AND 独立来源 ≥ 3: 标记为 emerging
elif z > 1.5: 标记为 rising
```

---

## 五、API 接口设计

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/evolution/analyze` | POST | 触发岗位演化分析 |
| `/api/v1/evolution/changelog/{position}` | GET | 获取演化变更记录 |
| `/api/v1/evolution/paths/{position}` | GET | 获取演化路径推荐 |
| `/api/v1/evolution/emerging-skills` | GET | 获取涌现技能列表 |
| `/api/v1/evolution/snapshots` | POST/GET | 快照管理 |
| `/api/v1/evolution/review-queue` | GET/POST | 人工审核队列 |
| `/api/v1/evolution/trends/{position}` | GET | 技能热度趋势（看板） |
| `/api/v1/evolution/cii-history/{position}` | GET | CII 通胀指数历史 |

---

## 六、数据库设计

### 6.1 新增 PostgreSQL 表

- `evolution_snapshot` — 演化快照表
- `evolution_changelog` — 演化变更日志表
- `evolution_path` — 演化路径表
- `skill_timeseries` — 技能时序统计表

### 6.2 Neo4j EVOLVES_TO 增强

```cypher
(:Position)-[:EVOLVES_TO {
  direction, skill_overlap, key_gaps, avg_months,
  evidence_count, trust_score, first_detected
}]->(:Position)
```

---

## 七、数据流与处理管线

- **定期管线**：Celery Beat 每周日凌晨 2:00 触发，8 步全流程
- **按需管线**：API 手动触发，同流程
- **涌现监控**：每日凌晨 4:00，Z-score + HDBSCAN 深度分析

---

## 八、测试策略

- 8 项单元测试（DiffEngine/TrustScorer/HalluGuard/PathRecommender）
- 4 项集成测试（全岗位差分/涌现回测/端到端/审核闭环）
- 准确率评估：30 组标注数据，F1 ≥ 0.85

---

## 九、实现路线图

| Phase | 周次 | 交付 |
|-------|------|------|
| Phase 1 | W1-W2 | 基础框架（Snapshot/Changelog 模型 + DiffEngine） |
| Phase 2 | W3-W4 | 信任度+幻觉防控集成 |
| Phase 3 | W5-W6 | 演化路径推荐 + EVOLVES_TO |
| Phase 4 | W7-W8 | API + Celery 管线 |
| Phase 5 | W9-W10 | 集成测试 + 调优 |

### 文件规划

```
backend/app/core/evolution/
├── diff_engine.py
├── trend_detector.py
├── emergence_finder.py
├── path_recommender.py
├── trust_integration.py
├── hallucination_guard.py
├── snapshot_manager.py
└── orchestrator.py
```

---

## 附录 B：设计决策记录

| ID | 决策 | 理由 |
|----|------|------|
| EVO-001 | 快照采用季度粒度 | 月度波动大，季度更稳定 |
| EVO-002 | 差分最低 5 条/窗口 | 低于 5 条统计意义不足 |
| EVO-003 | 新技能三层防线+LLM-judge | 防幻觉污染 |
| EVO-004 | 去重优先级：归一化→跨类→类内→空记录 | 先统一再比对 |
| EVO-005 | EVOLVES_TO 最小信任度 0.6 | 低于 0.6 证据不足 |
| EVO-006 | Z-score 阈值 2.0 | 95% 置信区间 |