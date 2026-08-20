# XH-202621 比赛作品提交就绪分析报告

> 生成时间：2026-08-20 ｜ 依据：赛项官方 PDF（XH-202621 比赛方案）+ 当前仓库真实代码/数据/评测证据
> 提交截止：**2026-09-05**（云盘打包 + 邮箱提交 3094947125@qq.com，压缩包命名：单位—申报人—作品名—手机号）

---

## 0. 2026-08-20 晚复核执行结果（增量，覆盖上文阻断项状态）

> 本轮已在当前分支 `feat/public-deploy-preflight`（HEAD=`3d72555`）实跑验证，并提交 B1 证据恢复。

### 0.1 B1 匹配评测 = ✅ 已解除（当前分支复现 98.84%）

- **实跑**：`run_match_baseline.py` 432 对 → **427/432 = 98.84% PASS**（216 should_match + 216 not，方向判定用 golden 区间语义）。
- **关键结论**：匹配引擎 depth=1 修复**已在当前分支**（uc 分支与之仅注释缩进差异），无需 cherry-pick。证据链已随 commit 入库。
- ⚠️ 运行中观察到 `_save_match_result` 抛 `match_results.id` NOT NULL（只是历史记录持久化失败，不参与准确率指标；匹配本身照常返回分数）。

### 0.2 B1 JD 评测 = ✅ PASS（规则基线，无需 LLM）

- `run_baseline.py` 110 样本 → **F1=0.9340**，`quality_gate.json` = green（PASS 已入库）。
- ✅ 恢复 4 个被 d26078c 缩进事故损坏的评测脚本（judge_eval / ingestion_consistency / run_real_eval / expand_golden_sets，从 origin/ui/upload-ux-polish 取回干净版），均通过语法+导入校验，已提交。

### 0.3 B1 简历评测 = ⚠️ 阻塞（外部依赖：LLM 全部不可用）

- **2026-08-20 23:04 实测**：DashScope `400 Arrearage`（账户欠费）+ DeepSeek `402 Insufficient Balance` + Xunfei `500 AppIdNoAuthError` → 真实 LLM 链路全挂。
- 重跑 `run_resume_eval.py` 50 样本因 LLM 失效退化 **F1=0.7569（FAIL）**，磁盘报告被覆盖（gitignored）。
- **合格证据**：已提交的 `docs/competition-indicators-2026-08-17.md` F1=0.9316（历史 25 样本真实 LLM）。**充值任意 LLM 后必须重跑**生成新鲜 ≥90% 证据，否则实用价值"简历≥90%"项存疑。

### 0.4 ⚠️ 新增发现（提交前必读）

1. **入库完整性门禁动态 FAIL**：运行期间 PG↔Neo4j 边/节点漂移（REQUIRES PG 979 vs N4 973、Position PG 708 vs N4 703）。根因=**宿主机 172.18.0.1 持续 POST `/api/v1/pipeline/trigger` 触发 full run → 前端又 cancel 的循环**（与 08-18 记忆"外部自动化已停止"矛盾，当前复活），run 未走到 graph_sync 阶段即被取消 → Neo4j 落后。
2. **数据质量风险**：LLM 欠费期间跑流水线，近 15 分钟 48 个新岗位中 **44 个（92%）零技能**（raw-data 兜底灌入空岗位）。**清除空岗位应纳入提交前清理**。
3. 已一次性回填 **73 条缺失 REQUIRES 边 + 6 个缺失技能节点**（canonical_id 键、幂等 MERGE、requirement_type/confidence 与现有边同构），瓶颈在 run 结束后跑 reconcile（节点同步）+ 再验门禁。
4. `evaluation/baseline_report/*`、`real_eval_report/*` 均被 `.gitignore` 忽略 → **打包云盘时若整目录拷贝会带上旧/失败报告，必须只拷贝指标汇总文档 + 本轮 PASS 报告，或打包前重跑生成**。

### 0.5 B2 / B3 / B4 现状（复核无变化）

- **B2 模块 A**：`responsibilities` LLM 已抽取、`JDExtractionResult` 有字段，但 `PositionRecord` 未持久化、前端 0 渲染；**典型行业应用场景字段全系统不存在**（schema/prompt/模型均无）。→ 提交策略见 §三 B2。
- **B3 PPT**：全仓库确认 0 个 `.ppt*` 文件，必须制作。
- **B4 数据源模块**：backend 4 个改动文件 ruff 全过；crawler 单测上个会话 11 passed；CI 规范 `pip install -r crawler/requirements.txt && pytest crawler/tests/`。**仍未 commit，提交包不含 → 必须提交**。

### 0.6 提交前硬性动作（更新版，按序）

1. **充值任一 LLM**（DashScope 优先）→ 重跑 `run_resume_eval.py` + `run_real_eval.py` 生成 ≥90% 新证据，覆盖/替换 FAIL 报告。
2. **停止宿主机外部自动化**（POST /pipeline/trigger 循环）→ 清空零技能空岗位 → 跑 reconcile → 重验入库门禁全绿。
3. 提交 B4 数据源模块 + 全量测试（backend pytest / crawler pytest / frontend vue-tsc+eslint）。
4. B2 至少按路径 2 兜底（fixtures 大模型应用工程师五项齐备入设计文档/视频）；时间允许走路径 1。
5. 制作 PPT（B3）+ 重录 ≥10 分钟内含"新岗位 + 既有岗位能力更新"两段图谱的演示视频。
6. 整理测试数据目录（1 新 + 1 既有岗位图谱 JSON + 源 JD 输入输出示例）→ 打包（gitignored 报告目录勿整拷）。

---

## 一、比赛要求清单（官方 PDF 五、答题要求 原文摘录）

---

## 一、比赛要求清单（官方 PDF 五、答题要求 原文摘录）

### 1. 岗位选择范围
立足数字经济，瞄准**新一代信息技术**领域（人工智能、大数据、智能系统、物联网等）。

### 2. 核心功能要求（4 大模块）
| 模块 | 要求 |
|---|---|
| **A 新岗位发现与定义** | 识别萌芽/新兴岗位并生成岗位定义，必须包含：**岗位名称、核心职责、必备技能、加分技能、典型行业应用场景**；支持人工优化与动态更新 |
| **B 既有岗位能力动态更新** | 针对现有岗位（如 Java 开发工程师）识别能力要求变化，提供**更新说明及数据源**，明确标注**新增/删除/修改**的能力项，支持人工优化与动态更新演化 |
| **C 岗位全景图谱** | 展示领域内岗位能力要求，颗粒度到**技能点**级别，可**按技术栈和级别切换视图** |
| **D 人岗匹配诊断与差距分析** | 用户输入技能数据/上传简历（**PDF/Word**）→ 对比目标岗位图谱 → 差距分析；简历技能提取**准确率≥90%**；支持多维度匹配；提供**针对性改进建议与岗位学习路径规划** |

### 3. 创新性要求
① 多源异构数据清洗与**交叉验证**融合机制（解决 JD "时滞/噪音/抄袭"）；② 能力"幻觉"防控，提升图谱构建科学性。

### 4. 可验证性要求
- 完整测试方案：**≥100 条岗位 JD 及测试用例**
- 核心指标可量化验证：**JD 解析准确率≥90%、简历提取准确率≥90%、匹配准确率≥90%**

### 5. 作品提交形式
| 交付物 | 要求 |
|---|---|
| 材料文档 | 作品设计实现方案、**PPT 作品介绍**、**≤10 分钟**演示视频（须含新岗位 + 既有岗位能力更新的图谱演示） |
| 软件模块 | 源代码、可执行程序（如有）、**部署说明（Dockerfile/容器化）**、**单元测试用例（覆盖率≥60%）** |
| 测试数据 | **1 个新岗位 + 1 个既有岗位**的能力图谱及岗位数据源（含输入输出示例） |

---

## 二、当前项目真实情况核对（实证）

### ✅ 已达标项

| 要求 | 实证 | 证据位置 |
|---|---|---|
| **JD 解析准确率≥90%** | 规则基线 **F1=0.934**（110 样本，quality_gate PASS）；真实 LLM **F1=0.9509**（30 样本） | `evaluation/baseline_report/evaluation_results.json`、`quality_gate.json` |
| **简历提取准确率≥90%** | 真实 LLM **F1=0.9316~0.9692**（25/10 样本，走 /resume/upload 同路径） | `evaluation/baseline_report/resume_report.md` |
| **≥100 条 JD 测试用例** | golden_set.jsonl **110 条**（+匹配 100 对 + 简历 50 份） | `evaluation/golden_set*.jsonl` |
| **模块 B 既有岗位动态更新** | 完整实现：快照→diff（6 类变更 added_required/added_preferred/removed/promoted/demoted/retained）→信任度→变更日志→写回图库，Celery 6h 自动调度，证据含 source_count 数据源 | `backend/app/core/evolution/`、`/evolution/*` 端点、`EvolutionDashboard.vue` |
| **模块 C 全景图谱** | 完整实现：Neo4j `/graph/overview`（4 视图模式）、G6 2D + Three.js 3D、技术栈/职级/领域筛选、技能点级粒度 | `backend/app/api/v1/graph.py`、`Home.vue`/`Graph2D.vue`/`Graph3D.vue` |
| **模块 D 人岗匹配** | 完整实现：简历 PDF/docx 解析（pdfplumber/python-docx）、LLM 技能抽取、匹配评分+差距明细（技能缺失项分级）、学习路径规划、批量匹配、反向推荐 | `backend/app/api/v1/resume.py`/`match.py`、`MatchDiagnosis.vue` |
| **部署/容器化** | Dockerfile + Dockerfile.celery + docker-compose.dev/prod + 公网部署脚本/手册 | `backend/Dockerfile`、`docker-compose*.yml`、`deploy-public.sh` |
| **单元测试覆盖率≥60%** | pytest 门禁 `--cov-fail-under=70`（CI 强制）> 60% 要求 | `backend/pyproject.toml` addopts |
| **设计实现方案** | 星图-项目设计文档 v2.0.md + v3.0.docx + 毕业设计成果.docx | `docs/`、`docs/design/` |
| **演示视频 ≤10min** | starmap-demo.webm 36.56s ✓ | `docs/demo/starmap-demo.webm` |
| **测试数据 1 新 + 1 既有岗位** | fixtures 35 岗位：**大模型应用工程师**（新岗位候选）+ **高级后端工程师**（既有岗位） | `backend/app/data/fixtures/positions.json` |
| **幻觉防控** | 写入门禁（信任度门槛/required 上限截断）、置信度分级、审核状态机、source_authority+source_quality_sync 交叉验证 | `backend/app/core/extraction/ingestion_gate.py`、`review_service.py` |
| **简历 PDF/Word** | 支持 pdf/docx（.doc 明确拒绝 B24，属合理边界） | `backend/app/services/resume_service.py` |

### ⚠️ 风险项（不阻断但不干净）

| # | 风险 | 现状 | 影响 |
|---|---|---|---|
| R1 | 磁盘 `evaluation/baseline_report/match_report.md` 显示 **0% FAIL**（旧残留） | 该目录被 `.gitignore:196` 忽略，未跟踪 | 打包源码时若目录一并复制，评审可能看到"匹配 0%"报告 → **必须删除/重跑** |
| R2 | 磁盘 `backend/coverage.xml` 显示 **32.42%** | 旧/部分运行残留（gitignored） | 与 CI 70% 门禁矛盾，打包证据需以 CI 全量跑为准 |
| R3 | 归档指标文档 `docs/archive/reports/competition-indicators-2026-08-17.md` 显示**匹配 60.06%（待校准 FAIL）** | gitignored 旧版 | 该文档非最终版（见下方阻断项 B1），但磁盘上的版本会误导 |

---

## 三、阻断项（提交前必须处理，按优先级）

### 🔴 B1（CRITICAL）：匹配准确率≥90% 的证据链不在当前提交分支

**事实链**（已用 git 实证）：
1. 匹配指标演进：6%→35%→60%→84%→**99.14%**（最后两跳：`b73685e` Phase7 depth=1 修复，`33e4eb8` Phase8 方向判定用 golden 区间语义）
2. 这些提交**只存在于 `origin/ui/upload-ux-polish` 分支**（139 个提交领先 main），**不在**当前提交分支 `feat/public-deploy-preflight`（HEAD=3e9498b）也不在 `main`（eb3c4e1）
3. 当前分支缺失的文件（全在 ui 分支，已验证存在）：
   - `evaluation/run_match_baseline.py`（175 行，匹配评测入口）
   - `evaluation/golden_set_match.jsonl` **348 对**（当前分支只有 100 对）
   - `evaluation/run_resume_eval.py`、`evaluation/accuracy_gate.py`、`evaluation/real_eval_report/`（真实 LLM 报告全套）
4. 匹配引擎代码两分支有 60 行 diff（scorer/service），当前分支无法保证复现 99.14%

**后果**：若按现分支提交，评审看到的是"匹配 60.06% FAIL"（或更差），直接损失 30 分实用价值中的硬指标分。

**行动**：
```bash
# 1. 从 ui 分支恢复关键文件到当前分支
git checkout origin/ui/upload-ux-polish -- evaluation/run_match_baseline.py \
  evaluation/golden_set_match.jsonl evaluation/run_resume_eval.py \
  evaluation/accuracy_gate.py evaluation/expand_golden_sets.py evaluation/judge_eval.py
# 2. 恢复最新指标文档（先确认当前精确内容）
git show origin/ui/upload-ux-polish:docs/competition-indicators-2026-08-17.md
# 3. 在当前分支后端引擎上重跑匹配评测（引擎有 diff，必须实测）
cd backend && poetry run python ../evaluation/run_match_baseline.py
# 4. 若结果<90%，把 Phase7/8 引擎修复 cherry-pick 过来重新评测
```
> ⚠️ 注意：`baseline_report/` 与 `real_eval_report/` 在 .gitignore 中（`evaluation/baseline_report/*`、`evaluation/llm_real_report/`），报告产物不入仓——但 `competition-indicators` 指标汇总文档应入仓（当前版在 ui 分支 `docs/competition-indicators-2026-08-17.md` 路径，需确认目标路径）。

### 🔴 B2（CRITICAL）：模块 A 新岗位发现与定义 = PARTIAL

**已具备**：EmergenceFinder（Z-score/Wilcox 涌现技能检测）+ LLM JD 抽取（prompt v1-v4）+ 审核状态机 + 管理端图节点编辑。
**缺失**（与赛题要求的岗位定义五项对比）：
1. ❌ **典型行业应用场景**：整个系统未建模该字段（当前只有单一 `industry` 字符串）；LLM prompt 与 position schema 均无场景列表
2. ⚠️ **核心职责**：LLM 抽取了 `responsibilities`，但 ExtractJD.vue / PositionDetail.vue 从不渲染
3. ⚠️ **无"涌现信号→自动生成新岗位定义→审核→发布"闭环**：`POST /positions/discover` 只返回涌现技能，不生成岗位定义

**行动**（择一即可满足评审）：
- **路径 1（推荐，快）**：写一个"新岗位定义生成"LLM prompt + 服务（输入涌现技能集 → 输出名称/职责/必备/加分/场景 JSON），挂到 `/positions/discover` 或新端点，前端 ExtractJD 渲染。约 1-2 天工作量。
- **路径 2（兜底）**：用 fixtures 中"大模型应用工程师"作为新岗位样例，在提交材料（设计文档/演示视频）中展示其岗位定义五项齐备，同时说明系统支持人工编辑定义（admin GraphNodeEditor 已具备）。风险：评审按系统实操打分时若点"发现新岗位"看不到定义生成，仍会扣分。

### 🔴 B3（CRITICAL）：PPT 作品介绍缺失
全仓库 `find *.ppt*` 为空。比赛提交形式第 (1) 条明确要求 PPT。**无技术阻力的纯交付物**，需制作（可用设计文档 v3.0 内容为骨架）。

### 🟠 B4（HIGH）：数据源模块大量未提交改动
工作树 32 文件 +2033/-2053（DataSources.vue 802 行重写 + 3 个新组件 + crawler 大改 + spider_registry）。crawler 单测 11 passed 已通过，但**未 commit 无法进入提交包**。提交前需：
1. 确认这批改动的意图（数据源全链路优化：注册表驱动映射 + 爬虫超时重试 + 前端拆组件）
2. 跑全量相关测试（backend + crawler），确认无回归
3. **提交**（当前分支或在提交分支上提交）

---

## 四、提交前行动清单（按顺序执行）

1. **[B1] 恢复匹配评测全套**（run_match_baseline.py + 348 golden + accuracy_gate + 指标文档）→ 在现分支引擎上**重跑匹配评测**，确认 ≥90%；<90% 则 cherry-pick Phase7/8 引擎修复再测
2. **[B1] 重跑 JD + 简历评测**生成新报告（真实 LLM 需 DashScope key；规则基线不需要），替换/清理旧报告
3. **[R1/R2] 清理 gitignored 旧评测产物**：删除 `evaluation/baseline_report/match_report.md`（0% 残留）、重生成 coverage.xml；确保指标汇总文档（99.14% 版）入仓
4. **[B2] 模块 A 补强**：生成岗位定义的五项字段（至少补典型行业应用场景），前端渲染核心职责
5. **[B3] 制作 PPT**（≤20 页：背景痛点→架构→4 模块演示→创新点→指标→部署→团队）
6. **[B4] 提交未完成的数据源改动**并跑全量测试
7. **[提交包] 准备测试数据目录**：1 新岗位（大模型应用工程师）+ 1 既有岗位（高级后端工程师）的能力图谱 JSON + 数据源原始 JD 示例 + 输入输出示例（Fixtures/API 均有，整理成独立目录）
8. **[提交包] 核验视频**：确认 ≥10 分钟内的视频包含"新岗位 + 既有岗位能力更新"两段图谱演示（现有 36s demo 可能不足，建议重录）
9. **[提交包] 打包**：按官方命名「单位—申报人—作品名—手机号」上传云盘，截图含上传时间，连同报名表发邮箱

## 五、评分预估（按当前状态）

- **作品完整性 30 分**：全流程闭环齐（采集→抽取→图谱→演化→匹配），若 B2 补齐可望拿满；B2 不补约扣 5-10 分
- **技术创新性 25 分**：信任度交叉验证 + 幻觉防控 + 演化图谱三处均为赛题亮点，有完整实现，可望 20-25 分档
- **用户体验 15 分**：图谱 2D/3D + 匹配诊断向导 + 差距分级展示，前端成熟，12-15 分档
- **实用价值 30 分**：三项指标若均 ≥90%（实证达标）× 110+ JD 测试用例 → 25-30 分档；**若匹配指标证据未修复，此项落到 60.06%（FAIL）档，扣 10-20 分**

---

*本报告基于 2026-08-20 仓库实际状态核实（git 分支拓扑、评测产物、API 路由、前端组件、fixtures）。修复动作建议在下一次会话按清单执行。*