# StarMap 模块功能拆解与联动分析

> 基于 codegraph 828 文件索引 + 浏览器 12 模块语义巡检（2026-08-14/15）。
> 分层纪律：`api/v1`（路由）→ `services`（服务）→ `core`（业务核心）→ `models/schemas`（数据）；
> 存储：PostgreSQL（业务主源）/ Neo4j（图谱）/ Redis（token/限流/SSE）/ Chroma（向量）。

---

## 总览：12 前端模块 ↔ 后端链路

| 前端模块 | 路由 | API 前缀 | 服务层 | 核心层 | 主存储 |
|---|---|---|---|---|---|
| 全景图谱 | `/` | `/graph` | graph_overview / graph_service | — | Neo4j + PG |
| 岗位列表 | `/positions` | `/positions` | position_repository | — | PG |
| 数据流水线 | `/pipeline` | `/pipeline` | pipeline_service | orchestrator / engine / stages | PG + Neo4j + Celery |
| 数据源管理 | `/datasources` | `/datasources` | datasource_service | source_quality_sync | PG |
| 匹配诊断 | `/match` | `/match` | match_service | matching/scorer + path_builder | PG + Chroma |
| JD 抽取 | `/extract` | `/extract` | extraction_service | jd_extract + llm_client + normalize | PG + LLM |
| 闭环演示 | `/loop` | `/loop` | loop_service | loop_orchestrator + loop/steps | PG + Neo4j |
| 学习中心 | `/learning` | `/learning` | learning_service | learning/path_engine | PG |
| 数据大屏 | `/dashboard` | `/dashboard` | dashboard_service | dashboard/sse_broadcaster | PG + Redis(SSE) |
| 演化看板 | `/evolution` | `/evolution` | evolution_service | evolution/*（diff/emergence/trust） | PG + Neo4j |
| 图谱质量 | `/quality` | `/quality` | quality_service | quality_monitor + trust | PG + Neo4j |
| 管理后台 | `/admin` | `/admin/*` | admin_*_service | — | PG + Redis |

---

## 三大业务闭环联动

### 闭环 A：JD → 图谱（数据流水线）
```
/extract UI → POST /extract/jd → jd_extract(LLM 抽取+归一化+反幻觉) → PG 写入
  → 内容审核 /admin/review-items（pending_review → approve 即入图）
  → graph_writer 投影 Neo4j（Position/Skill/REQUIRES）
  → 全景图谱 /graph/overview 读 Neo4j 计数；岗位列表 /positions 读 PG（单一真理源）
```
**联动要点**：PG 是业务主源，Neo4j 是查询投影——两库计数一致性由 graph_sync 阶段对账
（C-1 漂移监控）；审核动作通过 `sync_approved_position_to_graph` 实时同步入图。

### 闭环 B：简历 → 匹配 → 学习
```
上传简历 → /match/diagnose → match_service(技能对比) → 差距分析 → 学习路径
  → /learning 推荐（path_engine 依据图谱需求生成）
  → Chroma 语义检索辅助技能对齐
```
**联动要点**：匹配依赖 `skill_records`（PG）与图谱需求边（Neo4j）；`match_threshold`/路径
相似度阈值在 config 统一管理（运行时 safe_update 白名单）。

### 闭环 C：快照 → 演化 → 审核 → 写回
```
定时快照 → evolution/diff_engine 差分 → emergence_finder 新兴技能
  → trust_scorer（§6.2 四因子）→ trust≥0.5 自动 approved / <0.5 pending
  → 演化审核（/admin 演化变更）→ write_back 写回 PG + 删 Neo4j 关系
  → 演化看板 + 质量页直方图（EntityTrustScorer 同口径）
```
**联动要点**：演化链路与质量链路共用 `EntityTrustScorer`（质量页直方图与演化 trust 同源）；
`review_audit_log` 记录审核动作供 audit_pass_rate 计算。

---

## 关键横切能力

| 能力 | 实现 | 影响模块 |
|---|---|---|
| 认证 | auth_service（JWT）+ dev_token 守门（production 强制） | 全部 |
| 限流 | Redis 固定窗口 + 内存兜底（config rate_limit_*） | 全部 |
| 实时推送 | SSE broadcaster（Redis pub/sub）+ 前端 useSSE 轮询兜底 | 大屏/流水线 |
| LLM 降级链 | DashScope→SparkX→MiMo→DeepSeek→讯飞→Ollama | 抽取/翻译/推荐/演化 |
| 反幻觉 | LLM 自验证 + SKILL_ALIAS 词典后过滤 | 抽取（信任度） |
| 契约 | openapi.yaml ↔ schemas/ 双端校验 + JSON Schema 导出 | 前后端 |

---

## 模块间数据依赖（联动风险点）

1. **流水线 → 质量**：quality_monitor 读 `pipeline_runs` 失败数（近 24h 窗口告警）+ `data_source` 质量分
2. **抽取 → 审核 → 图谱**：`pending_review` 计数跨 3 处（质量页/流水线 KPI/admin 队列）同源对齐
3. **演化 → 质量**：`avg_skill_trust` 来自 Neo4j `Skill.trust_score`（metrics 模块统一口径）
4. **学习 → 图谱**：path_engine 需求来自 Neo4j REQUIRES 边；`weekly_new_nodes` 双端一致
5. **部署 → 认证**：生产守卫（CORS/SSL/Neo4j TLS/seed 拒绝）在 config.py 统一 fail-fast
