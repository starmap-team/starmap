# Phase 15: 多源数据聚合 (0 成本实时化)

**Phase:** 15-multi-source-data
**Goal:** 把"伪 BOSS 实时爬取"重塑为"多源免费 API + 用户手动补料"的真实数据闭环，全部 0 成本
**Status:** planning
**Created:** 2026-07-29
**Wave:** 2 (depends on Phase 3 validate-phase 修复)

## 为什么需要这个 Phase

Phase 3 验证暴露的根本问题：
- 当前 `crawler/spiders/v2ex_remote.py` 被错误别名为 bosszhipin/51job/lagou → 用户看到"BOSS 直聘"实际拿到 remotive 数据
- 真 BOSS/拉勾爬取需要付费 proxy（Bright Data $50+/月）+ 持续运维 → 不在用户预算范围
- 用户明确表态："该做的业务还是需要闭环掉"

## 0 成本路径（已实测验证）

| 数据源 | 类型 | 实测可用 | 单次响应 | 覆盖 |
|--------|------|---------|---------|------|
| Remotive API | JSON REST | ✅ HTTP 200 | 0.7s | 英文远程 (36 jobs/页) |
| Arbeitnow API | JSON REST | ✅ HTTP 200 | 3.2s | 英文+少量德文 (110 jobs/页) |
| Jobicy API | JSON REST | ✅ HTTP 200 | 1.0s | 英文远程 |
| WeWorkRemotely RSS | XML | ✅ HTTP 200 | <1s | 英文远程 |
| V2EX jobs node | JSON | ✅ 已用 | <1s | **中文远程** |
| 用户手动 CSV/JSON | upload | ✅ 通用 | — | **任意平台** (运营手动导出) |

## 子计划 (4 个)

| Plan | 标题 | Wave | 工作量 | 依赖 |
|------|------|------|--------|------|
| **15-01** | 多源免费 API Spider 接入 | 1 | 1-2 天 | — |
| **15-02** | CSV/JSON 用户手动导入端点 | 1 | 3-5 天 | — |
| **15-03** | 数据源管理 UI 透明化 | 2 | 1-2 天 | 15-01 |
| **15-04** | 数据源健康度监控 + 自动熔断 | 2 | 3-4 天 | 15-01, 15-02 |

**总工作量:** 8-13 天 (1.5-2.5 周)

## 关键架构决策

1. **每个数据源独立 spider**：不复用 v2ex_remote fallback，5 个独立 `run_sync` 函数
2. **DataSourceRecord.source_type 透明化**：UI 显示 `API 实时` / `RSS 周期` / `CSV 导入` / `爬虫实验`，不再假装是 BOSS
3. **CSV 导入作为中文 JD 唯一现实路径**：用户从 BOSS/拉勾手动导出 → 上传 → 自动入库
4. **自动熔断**：连续 3 次失败的源自动暂停，防止资源浪费

## M1-M7 强制规范应用

- **M1 (UUID保真)**：每个 imported item 必须有 content_hash，避免与爬虫数据冲突
- **M3 (零数据空态)**：导入 0 条时显示"已上传但全部为重复内容"
- **M4 (无基线不报红)**：新源前 7 天不显示 success_rate（无基线）
- **M5 (口径单一)**：健康度只从 data_source_metrics 表读，不混用其他来源
- **M6 (verify-first)**：每个 plan 完成后实测 API + DB + UI 三端一致

## 真实业务闭环图

```
           ┌─────────────────────────────────────────────┐
           │ Phase 15 多源数据闭环                        │
           └─────────────────────────────────────────────┘
                              │
   ┌──────────────┐    ┌─────▼─────────┐    ┌──────────────┐
   │ Remotive API │    │   Pipeline    │    │ Arbeitnow    │
   │ Jobicy API   │───▶│   trigger     │◀───│ WeWorkRemotely│
   │ WWR RSS      │    │   crawl       │    │ V2EX 中文    │
   └──────────────┘    └─────┬─────────┘    └──────────────┘
                              │
                  ┌───────────▼────────────┐
                  │ Health Monitor        │ ◀── 失败率/熔断
                  │ + Auto Circuit Breaker │
                  └───────────┬────────────┘
                              │
                       ┌──────▼──────┐
                       │ Dedup/Clean │ ◀── 已有
                       │ Import     │
                       │ Graph Sync │
                       └──────┬──────┘
                              │
   ┌──────────────┐    ┌──────▼──────┐    ┌──────────────┐
   │ 用户手动导出 │───▶│  /import/jd │───▶│ Neo4j + PG  │
   │ BOSS CSV    │    │  endpoint  │    │ (统一存储)  │
   └──────────────┘    └─────────────┘    └──────────────┘
```

## 不在范围（明确排除）

- ❌ 真 BOSS/拉勾/51job/猎聘爬虫（反爬+合规+成本三重不可行）
- ❌ 用户个人信息抓取（《个保法》风险）
- ❌ 分钟级以下实时（API 限频 5-15 分钟）
- ❌ 第三方数据采购（八爪鱼/亮数据）

## 相关文档

- `.planning/notes/zero-cost-data-strategy.md` — 战略决策
- `.planning/todos/pending/integrate-4-free-apis.md` — T1-T7 子任务
- `.planning/todos/pending/csv-import-endpoint.md` — 导入端点详情
- `.planning/VALIDATION.md` (Phase 3) — Bug D 起源

## 执行建议

按 wave 顺序：
1. Wave 1: 15-01 + 15-02 并行（基础接入 + CSV 导入）
2. Wave 2: 15-03 + 15-04 并行（UI 透明化 + 健康监控）

每完成一个 plan 跑 pytest 验证三端一致。

## Success Criteria

- [ ] 4 个免费 API spider 各自可独立调用
- [ ] POST /api/v1/import/jd 接受 CSV/JSON 并正确入库
- [ ] 数据源管理 UI 显示 4 种 type 标签，移除"BOSS 直聘"误导
- [ ] 连续 3 次失败的源自动暂停（错误类型加权 — Fix M1）
- [ ] 真实数据流程：触发 → 5 源都尝试 → 至少 1 个成功 → 46+ JDs 入库
- [ ] 用户手动上传 CSV → 自动入库 → 数据可匹配
- [ ] **Fix H2**: PII 检测警告（邮箱/手机/身份证）写入 audit log
- [ ] **Fix H1**: 启动探针自动 disable 4xx/5xx 源（如 Himalayas）
- [ ] **Fix M2**: Rate limit 429 时指数退避
- [ ] **Fix M4**: 历史 "BOSS直聘" 数据迁移 + 分离 `last_successful_crawl_at`

## Applied Critical Fixes (来自 self-review)

7 个修复已应用到 PLAN.md (2026-07-29)，详见 [15-REVIEWS.md § Applied Fixes](./15-REVIEWS.md)