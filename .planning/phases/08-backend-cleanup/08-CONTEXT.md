# Phase 8: 后端清理与配置 - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning

<domain>
## Phase Boundary

移除后端 demo/auto-seed 数据生成逻辑 + 配置 LLM/DB 启动校验 + 增强健康检查端点 + 归档 demo 脚本。这是 v2.1"真实数据切换"的第一层：让后端不再生成或推荐假数据，并让配置缺失在启动时可见。**不涉及**前端 MSW 关闭（Phase 9）、不涉及 Pipeline 实际采集（Phase 10）、不重写已有架构（DEC-003）、不新增 API 字段类型（DEC-004，仅删 demo 端点这一例外）。

前置状态（**不在本阶段重做**）：
- ✅ DB 密码启动校验已存在于 `config.py:124-167`（`model_validator` 检测 `CHANGE_ME_IN_ENV`，生产 raise RuntimeError，开发 logger.warning）-- CFG-02 大部分已实现，本阶段仅确认/扩展
- ✅ `_DEMO_AUDIT_QUEUE` 内存审核队列已在 Phase 1 迁移至 PostgreSQL `review_queue` 表（PERSIST-03）
- ✅ 6 个死端点已在 Phase 5 删除（CLEANUP-01）
- ✅ `data_sources` 表已有 5 个站点记录（BOSS/拉勾/51Job/GitHub/ESCO），爬虫从 `DataSourceRecord.config` 读取

本阶段 5 个真正灰色地带（仅实现决策，不重做）：
1. review_queue auto-seed 处置（完全移除 vs opt-in 标志）
2. data_sources 表数据定性（demo 数据 vs 真实配置）
3. reset-demo 端点删除与前端 Admin 按钮协调
4. LLM key 校验严格度（仅 warning vs 生产阻止）
5. demo 脚本归档方式（移文件 vs 原地注释）

</domain>

<decisions>
## Implementation Decisions

### G1 Demo 数据处置（DEMO-01/03/04）
- **D-01 (Claude discretion):** **完全移除 `_DEMO_REVIEW_SEED` 常量和 auto-seed 逻辑**--review_queue 空表时返回空列表，不再自动插入 4 条假审核项。理由：v2.1 目标是真实数据，任何 demo 数据路径都与此矛盾；env flag（SEED_DEMO_DATA）会增加配置面违背 DEC-003 简洁原则；DEMO-06 归档脚本供开发手动运行
- **D-02 (Claude discretion):** **`data_sources` 表 5 个站点记录视为真实配置保留**--不清空表数据，仅归档 `seed_datasources_demo.py` 脚本。理由：BOSS/拉勾/51Job 正是爬虫 `SOURCE_SITE_MAP` 映射的真实目标，`config.py` 的 `authority_scores` 有真实评分；清空表会逼爬虫走 fallback 默认值，是退化而非真实数据
- **D-06:** **demo 脚本原地归档**--保留原位，文件头加 `# ARCHIVE: 非生产用，仅开发演示` 注释，不移动文件，保持 `python -m scripts.seed_xxx` 调用路径不变（最小侵入，避免 break docstring 和模块引用）
- **DEMO-03 处理:** `quality.py:557` 的 `recommendations.append("...建议运行 seed_expansion_data_demo.py 扩充")` 改为建议触发 pipeline run；`expand_graph.py:719` 的 print 同步清理

### G2 reset-demo 与 Admin 按钮（DEMO-02）
- **D-03:** **删端点 + 删前端按钮**--删除 `/admin/seed/reset` 和 `/reset-demo` 端点及 `ResetDemoResponse` 模型；前端删除"重置演示数据"按钮、`useAdminReset.ts` composable、`datasource.ts` 的 `resetToDemo()` action 及 schema.ts 中 `resetDemoData` 类型。前端按钮移除属 DEMO-02 协调清理（非 Phase 9 的 MSW 工作）。PipelineMonitor 已有"立即执行"按钮（PIPE-FE-05 Phase 3），无需替代

### G3 LLM 校验严格度（CFG-01/02）
- **D-04:** **LLM key 校验仅 warning，开发/生产都不阻止启动**--理由：Ollama 本地模型始终可用作降级（Docker Compose 已含 Ollama + Qwen2.5-7B），无云端 key 不致命；与 DB 密码不同（DB 密码缺失是硬依赖，无法连接数据库）。校验逻辑加到 `config.py` 的 `model_validator`，检测 MIMO_API_KEY/DEEPSEEK_API_KEY/XUNFEI_API_KEY 至少一个非空，否则 logger.warning
- **CFG-02 现状:** DB 密码校验已存在于 `config.py:124-167`，本阶段仅确认 SECRET_KEY/NEO4J_PASSWORD/POSTGRES_PASSWORD 三项覆盖完整，无需重写

### G4 .env 模板（CFG-03）
- **D-07 (Claude discretion):** `.env.example` 补全 MIMO_API_KEY/DEEPSEEK_API_KEY/PROXY_LIST 字段，标注降级链优先级 MiMo(主用)->DeepSeek->Xunfei->Ollama(本地兜底)。保留现有 XUNFEI 三字段，新增 MIMO/DEEPSEEK 两字段及注释

### G5 健康检查详情（CFG-04）
- **D-05 (Claude discretion):** **`/health/detail` 返回 ping + 配置状态**--4 服务 ping 状态（Neo4j/PostgreSQL/Redis/Ollama）+ 3 个 LLM key 配置布尔值（MIMO/DEEPSEEK/XUNFEI，仅 true/false 不泄露 key 值）+ demo 数据存在指示（review_queue 是否含 auto-seed 行、pipeline_runs 是否含 demo run）。不返回任何 key 值。无 auth 保护（与现有 `/health` 一致，无 auth 系统属 SEC-03 未来范畴）

### Claude's Discretion
- LLM key 校验的具体 warning 文案（建议：列出未配置的供应商名，提示降级到 Ollama）
- `/health/detail` 的 demo 数据检测查询（建议：count review_queue where status=pending + count pipeline_runs，<5 视为 demo 残留）
- `quality.py:557` recommendation 替换文案（建议：改为"图谱技能数偏少，建议触发 pipeline run 采集真实数据"）
- 是否同时清理 `scripts/seed_jd_data.py`/`seed_position_skill_records.py`/`seed_skill_timeseries.py`/`seed_hardcoded_profiles.py`（根目录 scripts/ 下的非 _demo 后缀 seed 脚本）--建议一并加 ARCHIVE 注释，统一处置

### 验证指标（硬性）
- **D-08:** **启动校验可观测**--后端启动时 LLM key 未配置输出 WARNING 日志（可在日志中验证）
- **D-09:** **`/health/detail` 返回 200 且包含 4 服务 + 3 LLM key + demo 指示字段**
- **D-10:** **`pytest` 全部通过**（admin/quality/config 相关测试需同步更新，不回归）
- **D-11:** **`ruff check` + `mypy app` 通过**（删端点后 schema.ts 重新 gen:api 或手动同步）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目级决策
- `.planning/PROJECT.md` - 项目定义、v2.1 真实数据切换目标、DEC-001~006、DEC-011
- `.planning/REQUIREMENTS.md` §Phase 8 - 8 个需求（DEMO-01~04, CFG-01~04）
- `.planning/ROADMAP.md` §Phase 8 - 成功标准、关键文件
- `.planning/STATE.md` - 当前状态、DEC-001~011 已锁定决策

### 前序阶段决策（不重做）
- `.planning/phases/06-arch-refactor/06-CONTEXT.md` - Phase 6 架构重构决策（了解 db/session.py、pipeline 拆分现状）
- `.planning/phases/04-dataflow/04-CONTEXT.md` - Phase 4 数据流决策（D-08 真实计算为准，不引入 mock，与 v2.1 目标一致）
- `.planning/codebase/CONCERNS.md` - SEC-01/02（密码明文、内存审核队列）、TD-01（硬编码配置）-- v2.1 直接解决这些遗留

### 后端配置与校验（核心改造目标）
- `backend/app/config.py` - `Settings` 类 + `model_validator`（D-04 LLM 校验加在此；CFG-02 DB 密码校验已存在 L124-167）
- `backend/app/core/extraction/llm_client.py` - LLM 降级链 MiMo->DeepSeek->Xunfei->Ollama，`call_llm_with_fallback()` 入口
- `backend/app/api/v1/health.py` - 现有 `/health` 端点，D-05 新增 `/health/detail` 的位置

### Demo 数据清理目标（DEMO-01/02/03）
- `backend/app/api/v1/admin.py:78` - `_DEMO_REVIEW_SEED` 常量（D-01 删除）
- `backend/app/api/v1/admin.py:179-193` - auto-seed 逻辑（D-01 删除）
- `backend/app/api/v1/admin.py:308-327` - `/seed/reset` + `/reset-demo` 端点 + `ResetDemoResponse`（D-03 删除）
- `backend/app/api/v1/admin.py:73-75` - `ResetDemoResponse` 模型定义（D-03 删除）
- `backend/app/api/v1/quality.py:557` - 推荐 seed 脚本的文本（DEMO-03 改文案）
- `backend/scripts/expand_graph.py:719` - 推荐 seed 脚本的 print（DEMO-03 清理）

### Demo 脚本归档目标（DEMO-04）
- `backend/scripts/seed_pipeline_runs_demo.py` - D-06 加 ARCHIVE 注释
- `backend/scripts/seed_expansion_data_demo.py` - D-06 加 ARCHIVE 注释
- `backend/scripts/seed_datasources_demo.py` - D-06 加 ARCHIVE 注释
- `backend/scripts/seed_cross_domain_demo.py` - D-06 加 ARCHIVE 注释
- `scripts/seed_demo_data.py` - D-06 加 ARCHIVE 注释
- `backend/scripts/seed_chroma.py` - 非 _demo 后缀，评估是否一并归档
- `scripts/seed_jd_data.py`/`seed_position_skill_records.py`/`seed_skill_timeseries.py`/`seed_hardcoded_profiles.py` - 根目录 scripts/ seed 脚本，Claude 酌情一并加 ARCHIVE 注释

### 前端协调清理（DEMO-02 联动）
- `frontend/src/composables/useAdminReset.ts` - D-03 删除整个文件
- `frontend/src/stores/datasource.ts:205` - `resetToDemo()` action（D-03 删除）
- `frontend/src/api/schema.ts:163/168/1226` - `resetDemoData` 类型 + `/admin/seed/reset` path（D-03 删或重新 gen:api）
- `frontend/src/pages/Admin.vue` - "重置演示数据"按钮（D-03 删除）

### 测试与验证
- `backend/tests/unit/test_quality_api.py` - quality API 测试，DEMO-03 改文案后需同步
- `backend/tests/unit/test_stage3_api.py` - admin/pipeline API 测试，删端点后需同步
- `backend/tests/conftest.py` - pytest fixtures 复用

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `config.py` 的 `model_validator`（L124-167）-- D-04 LLM 校验逻辑直接在此扩展，复用现有 `CHANGE_ME_IN_ENV` 检测 pattern
- `loguru` logger（全后端统一）-- D-04 warning 用现有 logger，无需新依赖
- `app/services/resources.py` 的 `AppResources` 单例-- D-05 `/health/detail` 复用现有 pg_engine/redis_client/neo4j driver 做 ping
- Ollama 容器（docker-compose.dev.yml:175）-- D-04 降级保障，LLM key 缺失时 Ollama 可用

### Established Patterns
- **配置校验 pattern:** `model_validator(mode="after")` + 敏感字段集合 + `_UNCONFIGURED` 占位值检测 + 生产 raise / 开发 warning（config.py 已确立，D-04 沿用）
- **服务降级 pattern:** Neo4j/LLM 不可用时返回默认值（0/空）不中断（ARCHITECTURE.md L219-220），`/health/detail` 的 ping 失败应返回 false 而非抛异常
- **端点删除 pattern:** Phase 5 已删 6 个死端点（CLEANUP-01），D-03 删 reset-demo 沿用同样流程（删路由 + 删 schema + 同步前端）
- **契约优先:** CLAUDE.md 约定 API 变更先改 openapi.yaml 再 gen:api--删端点需同步 openapi.yaml 或确认 schema.ts 手动更新

### Integration Points
- `backend/app/config.py` `model_validator` -- D-04 LLM key 校验插入点
- `backend/app/api/v1/health.py` -- D-05 新增 `/health/detail` 路由
- `backend/app/api/v1/admin.py` -- D-01/D-03 删除 demo 代码
- `frontend/src/pages/Admin.vue` -- D-03 删除按钮（前端协调）
- `.env.example` -- D-07 补全 LLM/PROXY 字段

</code_context>

<specifics>
## Specific Ideas

- D-04 校验文案示例：`⚠️ 以下 LLM 供应商未配置 API key：MIMO_API_KEY, DEEPSEEK_API_KEY。将降级使用本地 Ollama（质量较低）。如需高质量抽取，请在 .env 中配置至少一个云端 LLM key。`
- D-05 `/health/detail` 响应结构示例：`{"services": {"neo4j": "ok", "postgres": "ok", "redis": "ok", "ollama": "ok"}, "llm_keys": {"mimo": false, "deepseek": false, "xunfei": false}, "demo_data": {"review_queue_seeded": false, "pipeline_runs_count": 0}}`
- D-05 demo 数据检测：`review_queue` 中 status=pending 且 entity_name 在 `_DEMO_REVIEW_SEED` 名称集合内的记录数；`pipeline_runs` 总数 <5 视为可能含 demo run（seed_pipeline_runs_demo 生成 15 条）
- D-03 删端点后，`starmap-contracts/openapi.yaml` 中 `/admin/seed/reset` 定义需同步删除（契约优先约定）
- D-06 ARCHIVE 注释格式：`# ARCHIVE: 非生产用，仅开发演示。v2.1 真实数据切换后不再推荐运行。` 置于文件 docstring 之后

</specifics>

<deferred>
## Deferred Ideas

- **现有 DB 中已存在的 demo 行清理（review_queue/pipeline_runs 的 demo 记录）**-- D-01 已明确不在 Phase 8 范围（属 Phase 10 数据层或手动 truncate）；删代码不删数据
- **data_sources 表的 GitHub/ESCO 两条非爬虫源**-- GitHub/ESCO 不是 `SOURCE_SITE_MAP` 的爬虫目标，是否清空这两条留 Phase 10 评估（可能用于 ESCO 技能映射 import，非 crawl）
- **SEC-03 身份验证系统**-- `/health/detail` 无 auth 保护是临时方案；完整 auth 系统属未来里程碑
- **LLM key 轮换/管理**-- CFG-01 仅做启动校验，key 轮换属密钥管理范畴，超出 v2.1
- **demo 脚本彻底删除（非归档）**-- D-06 选择保留归档注释，彻底删除推 v2.2+ 确认无依赖后
- **`seed_chroma.py` 等非 _demo seed 脚本的归档**-- Claude 酌情处理，但若它们服务真实功能（向量库初始化）则不归档

</deferred>

---

*Phase: 08-backend-cleanup*
*Context gathered: 2026-07-09*
