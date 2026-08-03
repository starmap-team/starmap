# Phase 15 种子 — 实时中文数据采集与真实呈现（explore 产出）

**Type:** explore seed → 待 `/gsd-plan-phase 15`（或 `/gsd-new-phase`）正式立项
**Date:** 2026-07-27 · **决策路径（用户选定）:** 定时+按需 + 英文源翻译（非真流式）
**方法:** DB 取证 + Serena 代码追踪 + `/docs` 设计文档比对

## 1. 已确认现状（三重取证）

| 维度 | 事实 | 证据 |
|---|---|---|
| 岗位来源 | 34/56 = `system:fixture`；8 = 抽取；14 空白 | `position_records.created_by` |
| 真实爬取 | 仅一次性 46 JD（remotive 36 + v2ex 10，7/24 同秒）；**Boss/拉勾/ESCO = 0、从未爬** | `jd_raw.source_site`；`data_sources.total_records=0,last_crawl_at=NULL` |
| 抽取加数 | 模块可用（46→8 岗位），但**无调度/无触发** | 无 `pipeline_schedules` 行 |
| 自动转中文 | **无**：`name_cn` 56/56 全空；`extraction/` 无翻译模块 | `name_cn` 全 NULL；目录无 translate |
| 设计意图 | 目标 ≥500 条 BOSS/拉勾/猎聘（中文源，天然中文→**设计未规划翻译**）；**明确“❌ 不做实时流式，批+定时(Beat 6h/cron)+按需”**；多平台=TODO，且 BOSS 也未跑 | `星图-项目设计文档v2.0.md` L88/102/261/1543；`pipeline_deep_analysis.md` L445 |

**根因结论：** 非“缺翻译”，而是“设计预期的中文源爬虫根本没跑” → 库里只剩种子+一次性英文抓取。用户目标=对旧设计的**升级**（旧设计既不要流式也不要翻译）。

## 2. 选定路径（覆盖旧设计两条决策：no-streaming / no-translation）

- **采集 = 定时(cron)+按需触发**（非字面流式）：中文站 Boss/拉勾/猎聘 经 Apify 或本地 spider + WAF/反爬降级；建 `pipeline_schedules` 定期跑 + 页面“立即采集”按需触发。
- **英文源翻译 = 新增**：抽取阶段对英文 JD 用 LLM 翻译 `title`/`industry`→`name_cn`（中文源则直接映射，免翻译）。
- **前端真实体现**：列表/详情/数据源页显示 `source`/`last_crawl_at`/采集状态，让用户知晓数据新旧与出处。

## 3. 需求（待登记 REQUIREMENTS.md：DATA-SRC-01..04 + I18N-01）

- **DATA-SRC-01** 中文招聘爬虫可运行并产出数据：Boss/拉勾/猎聘 至少 1 源端到端跑通（Apify token 或本地 spider + WAF 降级），`data_sources.total_records>0` 且 `last_crawl_at` 更新。
- **DATA-SRC-02** 调度+按需：`pipeline_schedules` 支持 cron 定期 + 页面按需触发；crawl→extract→import→graph_sync 全链路自动。
- **DATA-SRC-03** 抽取实时入库：新爬 JD 经抽取模块自动产生 position/skill 并投影图谱，前端可见新增。
- **DATA-SRC-04** 前端真实呈现：列表/详情/数据源页可见 `source`、`last_crawl_at`、采集/运行状态；空/旧数据有诚实提示。
- **I18N-01** 英文源自主转中文：抽取时对英文 `title`/`industry` 生成 `name_cn`（LLM），中文源直接映射；前端优先展示 `name_cn`，无中文时打“英文原文”标签（已有）。

## 4. verify-first 验收标准（每项三层取证）
- 每需求：API 返回 + PG/Neo4j 真实计数 + 浏览器截图 三者一致方算通过。
- DATA-SRC-01：触发某源采集后，`jd_raw` 该 `source_site` 行数↑、`data_sources.last_crawl_at` 非空、`total_records`↑。
- I18N-01：英文 JD 抽取后对应 `position_records.name_cn` 非空且为中文；前端卡片不再显示裸英文（除非翻译失败的降级标签）。
- DATA-SRC-04：截图含“数据来源/最近采集时间”且与 DB `last_crawl_at` 一致。

## 5. 风险 / 待 plan 阶段 spike
- BOSS/拉勾 强反爬/WAF：需可行性 spike（Apify 成本 vs 本地 stealth）；若不可行，降级到可稳定源 + 标注。
- LLM 翻译成本/质量：批量翻译 title/industry 的 token 成本与抽检策略。
- 调度幂等/去重：simhash 去重已存在，需验证重复抓取不产生重复岗位。

## 6. 路由
- 下一步：`/gsd-plan-phase 15`（本种子已就绪，plan 可直接消费 §3/§4）；执行沿用 verify-first。
- 依赖：无前置 phase 阻塞；与 Phase 13 一致性审计正交。