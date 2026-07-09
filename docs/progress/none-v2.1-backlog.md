# StarMap — non-v2.1 真实任务 Backlog

> 生成时间: 2026-07-09
> 来源: 跨 docs/progress、.planning/STATE、audit/00-summary、audit/99-risk-register、audit/depth-analysis、docs/bugs/BUG_REPORT、docs/qa/M7_QA_REPORT、coverage.xml、git log + 代码 grep + 9 个深度 bug 实证交叉验证
> 范围: 排除 v2.1 Milestone (DEMO/MSW/PIPE/CFG) 16 项以外的所有 actionable 任务

---

## A · F1 评估门禁未达标 (最高优先级)

| ID | 来源 | 任务 | 影响 | 状态 |
|----|------|------|------|------|
| A1 | `evaluation/real_eval_report/quality_gate.json` + `f1_optimization_plan.md` | **JD F1 0.8767 → ≥ 0.90** (gate: red) | 上线阻断 | 未做 |
| A2 | f1_optimization_plan.md + BL-10 | 接入 skill_taxonomy.yaml 198 技能 aliases 替换硬编码 | F1 +0.02~0.03 | 部分 (`normalize.py:286-301` 已合并但仍依赖硬编码) |
| A3 | f1_optimization_plan.md | 复测 baseline + real_eval 两条 baseline 路径 | 不知道当前真实 F1 | 未做 |
| A4 | FE-12 / GAP_ANALYSIS G9 | Golden Set 标注口径校准 (复核 jd-005/019 等最差样本) | false-positive 噪声 | 未做 |
| A5 | GAP_ANALYSIS O5 | Bootstrap 95% CI 报告 (1000 次重采样) | 评估严谨性 | 未做 |
| A6 | depth-analysis BL-01 | Judge F1 `(1.0,1.0,1.0)` 当 golden 和 system 都为空集 | 评估污染 | ✅ **已修** (`judge_service.py:230-231` 返回 0.0) |

---

## B · 深度 bug 待修 (B17-B26 cross-check)

BUG_REPORT.md 列了 9 个 "深度" bug，逐一与 main 分支代码交叉验证：

| ID | 描述 | 当前状态 | 行动 |
|----|------|----------|------|
| B15 | 反幻觉白名单 miss "Python" | ✅ 已修 (`hallucination_guard.py:158-211` WELL_KNOWN_SKILLS 含 "python") | — |
| B16 | 全掌握场景匹配率低 | ✅ 已修 (`match_service.run_match` 完整 iterate) | — |
| B17 | evolution_snapshots 仅 2 条 | ⚠️ **仍真实** (取决于 pipeline 是否被实跑) | 跑一次增量 crawl → 触发 `evolution_snapshots` 自动累积 |
| B18 | EVOLVES_TO 未写 Neo4j | ✅ 已修 (`orchestrator.py:316-381` `_write_evolves_to_graph`) | — |
| B19 | Orchestrator 参数不齐 (`first_detected/last_detected/semantic_score`) | ✅ 已修 (`orchestrator.py:162-169` 全部传入 `hallucination_guard.check`) | — |
| B20 | path_recommender evidence 默认 1 → MIN_EVIDENCE=3 阻塞全部路径 | ✅ **已修** (本次 commit: `path_recommender.py:115-127` — 当 callers 不传 evidence_counts 时用 overlap 大小做 fallback) | — |
| B21 | Prompt v1 未提 prereq/learning/evolves/tools | ✅ 已修 (v4 prompt 提了; `_ACTIVE_VERSIONS["jd_extraction"]="v4"`) | — |
| B22 | graph depth 参数忽略 | ✅ 已修 (`graph_service.py` 多跳 + PREREQUISITE/EVOLVES_TO) | — |
| B23 | 所有技能都标 required | ✅ 已修 (`match_service._load_target_profile` 显式 importance) | — |
| B24 | .doc 解析乱码 | ✅ **已修** (本次 commit: `resume_service.py:14` 把 `.doc` 移出 `SUPPORTED_RESUME_EXTENSIONS` + 删除 dead fallback branch) | — |
| B25 | update_trust 未被调用 | ⚠️ 仅 `orchestrator.py:137` 调用 1 次 (retained skills)；其他 5 处场景未用 | 加 cron 周期调用 + 在路径发现/反幻觉 step 接 update_trust |
| B26 | 阈值硬编码 | ⚠️ `orchestrator.py:115-120` 仍有 `0.5` 字面量；其他大部分已迁 config.py | 把 emergence/threshold 字面量迁 config |

---

## C · 单元测试技术债 (Stale TODO 注解)

| ID | 文件 | 注解 | 行动 | 状态 |
|----|------|------|------|------|
| C1 | `backend/tests/unit/test_run_match.py:739` | `_get_pg_session` dead | 删 35 行 dead `class TestGetPgSession` | ✅ **已修** |
| C2 | `backend/tests/unit/test_run_match.py:771` | `_MATCH_RESULTS_MAX_SIZE` LRU eviction dead | 删 LRU 块 | ✅ **已修** |
| C3 | `backend/tests/unit/test_stage3_helpers.py:67` | `_extraction_payload_from_record` removed | 用 5 个真测试覆盖 `JDExtractionRecord.to_extraction_payload` | ✅ **已修** |
| C4 | `crawler/spiders/lagou.py:52` | 拉勾列表选择器待重抓验证 | 跑一次实抓 + 重抓 selector | 未做 |
| C5 | `core/evolution/emergence_finder.py:97` | DOMAIN_KEYWORDS 硬编码 4 领域 | 迁 config / DB | 未做 (BL-15) |
| C6 | `tests/e2e/smoke_test.py:117` | "W8: 演化引擎 ready 后" 后置 | 待 v2.1 E2E 时补 | 未做 |

---

## D · 覆盖率空白 (实测 backend/coverage.xml 当前 78.73% 总覆盖)

| ID | 文件 | 漏覆盖 / 覆盖率 | 优先级 | 备注 |
|----|------|------------|------|------|
| D1 | `core/pipeline/executor.py` | 304 行漏 / **8.7%** | 🔴 极低 | Celery stages 5 个执行函数全空测 |
| D2 | `core/extraction/llm_client.py` | 130 / 23.1% | 🔴 | MiMo/DeepSeek 降级链未测 |
| D3 | `tasks/celery_app.py` | 129 / 24.1% | 🔴 | Celery 调度 0 测 |
| D4 | `core/extraction/resume_eval.py` | 100 / 29.6% | 🟠 | resume Golden Set 路径 |
| D5 | `pipeline/steps.py` | 84 / 40.8% | 🟠 | 旧 pipeline engine 5 step |
| D6 | `api/v1/position.py` | 58 / 44.2% | 🟡 |
| D7 | `api/v1/graph.py` | 67 / 46.4% | 🟡 |
| D8 | `api/v1/extract.py` | 53 / 47.0% | 🟡 |
| D9 | `core/evolution/snapshot_manager.py` | 40 / 50.6% | 🟡 |
| D10 | `core/dashboard/sse_broadcaster.py` | 47 / 53.5% | 🟡 |

---

## E · 测试基础设施

| ID | 来源 | 任务 |
|----|------|------|
| E1 | docs/qa/M7_QA_REPORT | Resume F1 实际测量 (跑 `--golden-set resume`) |
| E2 | 同上 | Match Accuracy 实际测量 (跑 `--golden-set match`) |
| E3 | GAP_ANALYSIS G9 | HDBSCAN 聚类集成到 emergence_finder |
| E4 | depth-analysis AP-04 | LLM 反幻觉从同步串行 → 异步化或缓存 |
| E5 | BL-10 | skill_taxonomy.yaml 198 aliases 真合并确认 |
| E6 | docs/bugs B14 | 演化数据不足 — 是否补 seed |
| E7 | docs/bugs B12 | 演化看板 CII 时序图空白 (前端) |

---

## F · 代码静态可立即修的小项

| ID | 来源 | 任务 | 状态 |
|----|------|------|------|
| F1 | docs/bugs B07 | `Admin.vue:261` `:type=""` 空字符串无效 | ✅ **已修** (4 个 el-tag 当前全用三元表达式返回非空 type) |
| F2 | docs/bugs B13 | `PositionDetail.vue` 热度原始数字 → 格式化 | 未做 |
| F3 | BL-04 | path_engine Tarjan SCC cycle 路径验证 | 半成 (代码已实现 `_tarjan_scc`) |
| F4 | BL-08 | `_clean_skill_name` len=4 阈值验证 | 已修 |
| F5 | BL-15 | DOMAIN_KEYWORDS 硬编码 → 迁配置 | 未做 |

---

## G · 战略性 / 文档交付物

| ID | 任务 |
|----|------|
| G1 | docs/qa/M7 误报 #5/6/7 项 vue-tsc/build 二次复核 |
| G2 | GAP_ANALYSIS O2/O4 — CII 标签可视化 + Playwright E2E 自动化 |
| G3 | emergence.threshold 字面量迁移 config.py |
| G4 | audit/scripts/verify/*.sh 11 个回归测试脚本接入 CI |
| G5 | docs/bugs 后续待挖 — 性能 / 安全 / 前端深度测试 立项 |
| G6 | docs/core/CHANGELOG.md 与 commit 同步抽样核查 |

---

## H · Git 历史碎片风险

| ID | commit | 风险 |
|----|------|------|
| H1 | `350ddfb chore: snapshot of WIP before cleanup` | 留下 WIP 分支，可能冲突 |
| H2 | `f619ac6 WIP on temp-pr42-rebase` | 临时 rebase 残留 |
| H3 | `1ecfa56 merge: Phase 1+2 成果并入 main` | 与 HEAD 一致性待核 |

---

## Summary (本次 commit 已完成)

✅ A6 — Judge F1 空集返回 (0.79 修复)  
✅ B20 — path_recommender evidence fallback  
✅ B24 — resume_service .doc 拒收 + 死 elif 移除  
✅ C1 — 删 35 行 dead `TestGetPgSession`  
✅ C2 — 删 LRU eviction dead 块  
✅ C3 — 5 个真测试覆盖 `JDExtractionRecord.to_extraction_payload`  
✅ F1 — Admin.vue 4 处 el-tag :type 当前已合规 (B07 已存在修复)

剩余 9 条 actionable：B17 (snapshot 增量触发)、B25 (扩展 update_trust 调用点)、B26 (阈值迁 config)、C4/C5/C6、C1-C3 之外的 dead 类、D1-D10 (低覆盖模块)、E1-E7、F2-F5、G1-G6、H1-H3 — 共约 50 项。

---

## 引用来源 (供复核)

- `evaluation/real_eval_report/quality_gate.json` — `{"passed": false, "status": "red", "avg_f1": 0.8767}`
- `evaluation/baseline_report/quality_gate.json` — `{"passed": false, "status": "red", "avg_f1": 0.758}`
- `audit/00-summary.md` — 49 audit findings 总览 (前 commits 已修大部分)
- `audit/depth-analysis-report.md` — BL-01~16 / AP-01~14 / FE-01~12
- `docs/bugs/BUG_REPORT.md` — 26 bug，9 深度 (B17-B26) 已交叉验证代码
- `backend/coverage.xml` — 总 78.73%，D1 executor.py 8.7%
- `git log --oneline | head -20` — 已批量修过 49 个 audit items

*最后更新: 2026-07-09*
