# Blueprint: StarMap 项目计划书修订 v2.1 + docs 单一计划文档收敛

> 生成日期：2026-08-03
> 模式：git + gh（已检测：git repo ✅ / gh auth ✅ / 账号 Li3379）
> 当前分支：`chore/enterprise-git-governance`（⚠️ 工作区有大量无关未提交变更，见 Invariants）

## 目标（One-liner）

把 `docs/星图-项目设计文档v2.0.md` 修订为 **v2.1**（落实"反爬平台放弃 + 无反爬平台实时爬取 + 英文数据中文体现 + 评估固定同一批数据"四项决策），归档旧版计划文档，确保 `docs/` 下**只存在唯一一份项目计划书**。

## 上下文摘要（所有 Step 共享）

- **修订依据**（已确认的决策方向）：
  - **D17 数据源翻转**：主战场源改为 5 海外远程平台（v2ex/arbeitnow/jobicy/weworkremotely/himalayas）+ 拉勾 Apify + ESCO + 掘金公开 API；BOSS/猎聘/智联（反爬/付费墙）**明确放弃**
  - **D18 中英文映射层**：英文爬取数据入图前必须中文化（字典映射优先 + LLM 翻译兜底 + 归一化对齐）；注意 `backend/app/core/extraction/translation.py` 已存在（untracked），计划书描述需与其对齐或声明为目标设计
  - **D19 实时爬取口径**：拒绝"种子+公开数据集"软方案；演示与生产数据来自**周更实时爬虫**
  - **D20 评估口径**：Golden Set 冻结版本，每次评估使用**同一批数据**，保证可复现；爬虫周更不改变评估集
- **证据来源**：
  - `docs/archive/reports/2026-08-03/plan-vs-implementation/README.md`（总账）
  - `docs/archive/reports/2026-08-03/plan-vs-implementation/crawler-compliance.md`（爬虫专项，含数据源矩阵）
- **当前 docs/ 计划书类文件清单**：
  - `docs/星图-项目设计文档v2.0.md`（114 KB，实测约 1877 行）← 唯一 md 计划书
  - `docs/星图StarMap-项目设计文档（含配图）.docx` ← 历史 docx
  - `docs/design/星图StarMap-项目设计文档（含配图）v3.0.docx` ← 历史 docx
  - `docs/design/星图StarMap-毕业设计成果.docx` ← **成果文档，非计划书，不移动**
- **全局 Invariants（每步之后必须成立）**：
  1. 不 `git add -A` / 不 `git commit -a`——工作区存在大量无关变更，只允许暂存本 blueprint 明确列出的路径
  2. 不修改 `backend/` `frontend/` `crawler/` 任何代码（本 blueprint 纯文档）
  3. 不删除任何文件——旧版本一律 `git mv` 进 `docs/archive/plans/`
  4. 活文档（`docs/README.md`、`AGENTS.md`）不写易漂移的硬数字（治理规则）

## 依赖图

```
Step 1（起草 v2.1 全文）────┐
                            ├──► Step 3（归档旧版 + 收敛）──► Step 4（交叉引用 + 门禁）──► Step 5（提交）
Step 2（归档区准备，可并行）─┘
```

| Step | 依赖 | 可并行 | 模型档位 |
|---|---|---|---|
| 1 起草 v2.1 | 无 | 与 Step 2 并行 | 强（长文档修订） |
| 2 归档区准备 | 无 | 与 Step 1 并行 | 快（机械操作） |
| 3 归档旧版 + 唯一性收敛 | 1, 2 | — | 快 |
| 4 交叉引用 + 文档门禁 | 3 | — | 默认 |
| 5 提交 + 报告 | 4 | — | 快 |

---

## Step 1 — 起草 `docs/星图-项目设计文档v2.1.md` 全文

**模型档位**：强（约 1877 行文档的精确修订，上下文重）
**预计产物**：1 个新文件 `docs/星图-项目设计文档v2.1.md`（约 1900-2100 行）

### Context Brief（冷启动可读）

你在 StarMap 仓库（`c:\Users\LiShuai\Desktop\Agents\starmap`）。任务是基于现有 v2.0 计划书产出 v2.1 修订全文。v2.0 是赛题 XH-202621（科大讯飞发榜）的项目设计文档，17 章 + 附录，实测约 1877 行。修订原因是爬虫现实约束：BOSS/猎聘/智联反爬不可行，需换源到无反爬平台，并新增英文数据中文化要求。

### 任务清单

1. 完整读取 `docs/星图-项目设计文档v2.0.md`（分段读完，约 1877 行；行数以 `Get-Content` 实测为准）
2. 读取证据报告的"数据源矩阵"与"偏差清单"章节：`docs/archive/reports/2026-08-03/plan-vs-implementation/crawler-compliance.md` §2（数据源覆盖）、§10（关键偏差清单）
3. 检查 `backend/app/core/extraction/translation.py` 是否已存在及其接口（只读，用于 §5.5 措辞对齐；若存在写"已实现初版"，不存在写"待实现"）
4. 以 v2.0 为底稿产出 v2.1 全文（Write 新文件，不改 v2.0），修订点如下：

| 位置 | 修订内容 |
|---|---|
| 文档头部 | 版本 v2.0 → **v2.1**；进度状态刷新；新增"文档状态：数据源策略修订版"；头部的硬指标数字（如 `F1=0.8767`）按治理规则改为"以 evaluation/ 最新评估报告为准"表述 |
| §1.5 数据概览 | 数据源描述更新（移除 BOSS/猎聘口径，改为无反爬平台矩阵）；不写死会漂移的数字，写"以 evaluation/ 与 Neo4j 实测为准" |
| §3.2 L2 数据融合层 | **D5 决策替换为 D5'**：3 源异构 = ESCO（结构化）+ 5 海外远程平台与拉勾 Apify（半结构化，英文→中文映射后入图）+ 掘金公开 API（非结构化）；新增"反爬平台处置声明"（BOSS/猎聘/智联放弃，理由：反爬升级 + 合规成本） |
| §5 新增 5.5 节 | **中英文映射层**：Step1 字典映射（ESCO 中英对照 + `docs/ontology/` 翻译表）→ Step2 LLM 翻译兜底（星火，`translated_by=llm` 标记，可审核）→ Step3 中文归一化（接入 §6.2 别名+向量）；数据流图：英文 JD → 映射层 → 清洗 → 抽取 → 图谱 |
| §6.4 清洗去重 | SimHash 阈值口径：声明计划默认 10，实现侧当前 3（`--simhash-threshold` 可调），列入待对齐项 |
| §10.1 测试数据 | ≥500 JD 来源改为"5 海外平台周更 + 拉勾 Apify + ESCO 锚点"；**只删除**"BOSS直聘、拉勾、猎聘"三平台并排的旧句，拉勾以 Apify 形态保留在新来源列表中 |
| §14.6 评估防作弊 | 新增 D20：**Golden Set 冻结 v1.0，每次评估使用同一批数据**；爬虫周更不改变评估集；评估对象 = 抽取/归一化/匹配能力 |
| §15.3 爬取合规 | 保留 robots/QPS/公开数据/合规日志；新增"反爬平台已停止采集"声明；新增"英文数据必须经映射层中文化后入图" |
| §16.2 时序策略 | `[real_archive]` 定义改为"海外平台周更历史累积"；保留 inferred_consensus / constructed |
| 附录 D | 追加 **D17（数据源翻转）/ D18（中英文映射层）/ D19（实时爬取口径）/ D20（评估同一批数据）**，格式与 D1-D16 一致（编号/主题/章节/决策内容/理由） |
| 文末修订说明 | 追加 v2.1 修订说明段落（一段，列 4 项决策） |

5. 保持未涉及章节**逐字不变**（surgical：每处改动可追溯到 D17-D20）

### 验证

- `rg -c "D17|D18|D19|D20" docs/星图-项目设计文档v2.1.md` ≥ 8（ASCII 模式，可靠）
- `rg -n "BOSS" docs/星图-项目设计文档v2.1.md` 命中处必须处于"放弃/停止采集"语境（中文语境判定用 rg，不用 Select-String——PowerShell 5.1 对无 BOM UTF-8 的中文模式匹配有假阴性）
- `rg -c "中英文映射" docs/星图-项目设计文档v2.1.md` ≥ 3
- 文件行数在 **1800-2150** 之间（v2.0 实测 1877 行，忠实修订只增不减章节）
- v2.0 文件未被修改（`git status` 中 v2.0 无变更）

### 退出标准

v2.1 全文落盘、4 项决策全部体现、验证命令全过。

### 回滚

删除新建的 v2.1 文件即可，无其他副作用。

---

## Step 2 — 归档区准备（可与 Step 1 并行）

**模型档位**：快
**预计产物**：`docs/archive/plans/` 目录 + `README.md` 索引

### Context Brief

为旧版计划书建立归档位置。StarMap 文档治理规则：一次性/历史文档进 `docs/archive/`。注意 `docs/archive/plans/` **已存在**且含既有历史文件（先 Ls 清点），本步骤只做幂等补充。

### 任务清单

1. Ls 清点 `docs/archive/plans/` 既有文件
2. 目录不存在时才创建（已存在则跳过）
3. 写入/更新 `docs/archive/plans/README.md`：说明此目录存放历史版本计划书（只读存档，唯一权威计划见 `docs/` 根当前版本），版本清单表须**同时覆盖既有历史文件与本次归档的 3 个文件**

### 验证

`Test-Path docs/archive/plans/README.md` 为 True。

### 退出标准 / 回滚

目录与索引存在；回滚 = 删除目录。

---

## Step 3 — 归档旧版计划书 + docs 唯一性收敛

**模型档位**：快
**依赖**：Step 1、Step 2

### Context Brief

旧版计划书移入归档，保证 `docs/` 下只剩一份项目计划书（v2.1）。用 `git mv` 保留历史。**绝不删除文件**。

### 任务清单

1. `git mv "docs/星图-项目设计文档v2.0.md" "docs/archive/plans/星图-项目设计文档v2.0.md"`
2. `git mv "docs/星图StarMap-项目设计文档（含配图）.docx" "docs/archive/plans/"`
3. `git mv "docs/design/星图StarMap-项目设计文档（含配图）v3.0.docx" "docs/archive/plans/"`
4. 保留 `docs/design/星图StarMap-毕业设计成果.docx`（成果文档非计划书）
5. 更新 `docs/archive/plans/README.md` 索引为实际落位文件名
6. **唯一性核验**：`docs/` 根与 `docs/design/` 下不得再存在文件名含"项目设计文档/项目计划书"的文件（归档区除外）

### 验证

- `git -c core.quotepath=false status --short -- docs/` 显示 3 条 R（rename；quotepath=false 避免中文路径显示为八进制转义）+ 新 v2.1（untracked/added）
- 归档区 3 个历史文件存在；`docs/星图-项目设计文档v2.1.md` 是唯一根级计划书

### 退出标准

docs/ 活跃区只剩 1 份计划书；git mv 全部成功（无残留原路径文件）。

### 回滚

`git mv` 反向移回。

---

## Step 4 — 交叉引用修复 + 文档门禁

**模型档位**：默认
**依赖**：Step 3

### Context Brief

文档搬家后修复活文档引用，并跑项目文档门禁脚本。引用修复仅限**活文档**（README/AGENTS/governance/architecture），历史报告（docs/archive/）不改。

**已知事实（审查实测，冷启动者直接采信）**：
- `docs/README.md` 与 `AGENTS.md` 当前**零引用** v2.0 计划书 → 本步骤是"新增条目"，不是"修复死链"
- 全仓非归档的旧文件名命中只有 2 处，均为**预期命中，不处理**：
  - `scripts/check-docs.ps1:64` —— 门禁脚本的 stale-reference 清单故意条目
  - `docs/pencil-tools/eval_mockups.cjs:60` —— docs 下的工具代码，不属于活文档
- ⚠️ **门禁陷阱**：`check-docs.ps1` 对活文档按字符串匹配 `docs/星图-项目设计文档v2.0.md` 即判失败。**任何活文档不得出现该旧路径字符串**；旧路径仅可出现在 `docs/archive/` 内（门禁豁免区）

### 任务清单

1. 扫描确认：`rg -n "项目设计文档v2.0|项目设计文档（含配图）" --glob "!docs/archive/**" --glob "!plans/**" --glob "!scripts/**" --glob "!*.cjs"` → 预期 **0 命中**（若有命中，仅处理 docs/ 下的 .md 活文档）
2. 在 `docs/README.md` 文档入口表**新增** v2.1 条目（唯一计划书），历史版本注明"见 docs/archive/plans/"（措辞不得包含旧路径完整字符串，用"归档目录内历史版本"表述）
3. 运行门禁：`powershell -File scripts/check-docs.ps1`（本机无 pwsh，直接用 Windows PowerShell；脚本失败时记录原因，不修无关项）

### 验证

- 步骤 1 的 rg 扫描 0 命中
- `docs/README.md` 含 v2.1 条目且不含旧路径字符串（`rg "项目设计文档v2.0" docs/README.md` 为 0）
- `check-docs.ps1` 通过（或仅报告与本变更无关的既有问题）

### 退出标准

活跃文档无死链指向旧计划书；门禁结论记录在案。

### 回滚

引用改动均为小 patch，git checkout 对应文件即可。

---

## Step 5 — 提交 + PR（可选）

**模型档位**：快
**依赖**：Step 4

### Context Brief

按项目 Git 约定提交：分支 `docs/*`，commit 格式 `type(scope): description`。⚠️ 当前工作区有大量无关未提交变更（来自 `chore/enterprise-git-governance` 分支上的其他工作）——**只暂存本 blueprint 产物路径**，禁止 `git add -A`。

### 任务清单

1. 与用户确认提交策略（默认：在当前分支只提交 docs 变更；若用户要求新分支 `docs/plan-revision-v2-1`，需先确认如何处理工作区无关变更——建议 `git worktree` 或等用户清理，**不做 stash**）
2. 精确暂存（⚠️ **禁止 `git add -u docs/`**——docs/ 下有约 10 个无关的已修改跟踪文件如 `docs/architecture/pipeline.md`、`docs/standards/*`，会被一并误伤）：
   ```
   git add "docs/星图-项目设计文档v2.1.md" "docs/archive/plans/README.md" docs/README.md
   ```
   （3 条 rename 已由 Step 3 的 `git mv` 自动入栈，无需再 add）
3. 暂存清单精确断言——`git -c core.quotepath=false diff --cached --name-status` 输出必须**恰好等于**：
   - `A  docs/星图-项目设计文档v2.1.md`
   - `R  docs/星图-项目设计文档v2.0.md → docs/archive/plans/...`
   - `R  docs/星图StarMap-项目设计文档（含配图）.docx → docs/archive/plans/...`
   - `R  docs/design/星图StarMap-项目设计文档（含配图）v3.0.docx → docs/archive/plans/...`
   - `A  docs/archive/plans/README.md`（或 M，若既有）
   - `M  docs/README.md`
   出现任何额外路径 → `git reset` 该路径后重验
4. 提交：`docs(plan): 修订项目计划书至 v2.1（D17-D20 数据源策略）并归档旧版`
5. 若用户要求 PR：`gh pr create`，正文附 D17-D20 摘要与证据报告链接

### 验证

`git -c core.quotepath=false show --stat HEAD` 只包含上述 6 个 docs/ 路径；`git status` 中非本 blueprint 的变更（含 docs/ 内无关修改）原样保留未提交。

### 退出标准

提交完成且 diff 范围干净；向用户报告最终 docs/ 计划书唯一性状态。

### 回滚

`git reset --soft HEAD~1`（保留文件）。

---

## 反模式清单（执行时对照）

| 反模式 | 本计划中的防线 |
|---|---|
| `git add -A` / `git add -u docs/` 把无关变更带进提交 | Step 5 精确路径暂存 + `diff --cached --name-status` 清单精确断言 |
| 删除历史 docx | 只用 git mv，不 rm |
| v2.1 丢失 v2.0 章节 | Step 1 验证行数区间 + 未涉及章节逐字保留 |
| 在活文档写死 F1/节点数等硬数字 | §1.5 措辞用"以实测为准" |
| 顺手修改 translation.py 等代码 | 全局 Invariant：纯文档变更（含 docs/ 下的 .cjs/.ps1 代码文件也不改） |
| 修改 docs/archive 历史报告 | 只读证据，不改 |
| 活文档写入旧计划书路径字符串触发门禁 | Step 4 门禁陷阱声明 + 旧路径仅限归档区 |

## 计划变更记录（mutation log）

| 日期 | 变更 | 原因 |
|---|---|---|
| 2026-08-03 | v1 初稿经对抗性审查后修订：修正 v2.0 行数口径（2346→1877 实测）；Step 5 移除 `git add -u docs/` 改为精确暂存+清单断言；Step 4 引用扫描预期改为"0 命中+新增条目"；证据章节引用 §12→§10；验证命令中文模式改 rg；Step 2 幂等化；补门禁陷阱防线与 §10.1 措辞澄清 | 审查实测：v2.0 实际 1877 行；docs/ 存在 10 个无关已修改文件；README/AGENTS 零引用 v2.0；check-docs.ps1 有 stale 字符串门禁 |

## 计划变更协议

任何 Step 拆分/跳过/重排需在本文件追加变更记录（日期 + 变更 + 原因），并在最终提交信息中提及。