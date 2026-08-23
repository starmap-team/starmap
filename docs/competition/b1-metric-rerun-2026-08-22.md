# B1 指标权威重跑报告

> **Issue**: [#90](https://github.com/starmap-team/starmap/issues/90)
> **分支**: `b1-metric-rerun` (基于 `ui/upload-ux-polish`)
> **执行人**: @manice2005
> **执行时间**: 2026-08-22 ~ 2026-08-23
> **LLM 管线**: 阿里云百炼 DashScope `qwen-plus`
> **CI 门禁**: `accuracy_gate >= 0.90`

---

## 一、结果总览

| 指标 | 样本数 | F1 | Precision | Recall | 门禁 | 状态 |
|------|--------|----|-----------|--------|------|------|
| **JD 解析** | 110 | **0.9622** | 0.9725 | 0.9568 | >=0.90 | PASS |
| **简历提取** | 50 | **0.9158** | 0.9315 | 0.9007 | >=0.90 | PASS |
| 人岗匹配 | 432 | — | — | — | >=0.90 | 跳过（需 Neo4j+PG 图谱环境） |

### 置信区间（Bootstrap 95% CI）

| 指标 | 下限 | 均值 | 上限 | 样本 |
|------|------|------|------|------|
| JD F1 | 0.9516 | 0.9622 | 0.9713 | 110 |
| JD Precision | 0.9639 | 0.9725 | 0.9815 | 110 |
| JD Recall | 0.9421 | 0.9568 | 0.9698 | 110 |

> 简历评测样本量 50，未做 Bootstrap CI。F1=0.9158 稳定高于门禁 0.90。

---

## 二、与历史记录对比

| 日期 | JD F1 | 简历 F1 | LLM | 备注 |
|------|-------|---------|-----|------|
| 2026-08-17 | 0.938 | — | DashScope qwen-plus | 上一轮达标记录 |
| 2026-08-20 | 0.7569 | — | MiMo（连接错误） | **假失败**：LLM connection error 导致大量样本 fallback 降级 |
| **2026-08-22** | **0.9622** | **0.9158** | **DashScope qwen-plus** | **本次权威重跑** |

### 假失败根因

8-20 的 F1=0.7569 并非模型能力不足，而是 LLM API key 失效（讯飞 Spark 全部 `AppIdNoAuthError`），导致大量样本触发规则降级抽取，拉低整体指标。

本次重跑使用有效的 `DASHSCOPE_API_KEY`，降级链首选阿里云百炼 `qwen-plus`，110 样本 + 50 样本全部走真实 LLM 管线，0 失败。

---

## 三、JD 解析详情（110 样本）

### F1 分布

| 等级 | 区间 | 数量 | 占比 |
|------|------|------|------|
| Excellent | >=0.90 | 99 | 90.0% |
| Good | >=0.70 | 10 | 9.1% |
| Fair | >=0.50 | 1 | 0.9% |
| Poor | <0.50 | 0 | 0% |

### 错误分析

- **总错误数**: 169（110 样本中）
- **幻觉 (false positive)**: 73 次（43%）
- **漏抽 (false negative)**: 95 次（56%）
- **required/bonus 误分类**: 1 次（1%）

最差样本 Top 5：

| ID | 岗位 | 幻觉 | 漏抽 | 误分类 | 总计 |
|----|------|------|------|--------|------|
| jd-019 | 安全工程师 | 3 | 6 | 0 | 9 |
| jd-003 | AI算法工程师 | 3 | 2 | 0 | 5 |
| jd-063 | 网络安全工程师 | 2 | 3 | 0 | 5 |
| jd-065 | 网络安全工程师 | 2 | 3 | 0 | 5 |
| jd-011 | NLP工程师 | 2 | 2 | 0 | 4 |

> 安全/网络安全类岗位漏抽较多，Prompt 对安全领域技能召回不够充分，建议后续在 Prompt 中补充安全领域关键词上下文。

---

## 四、简历提取详情（50 样本）

- **样本数**: 50
- **F1**: 0.9158
- **Precision**: 0.9315
- **Recall**: 0.9007
- **门禁**: >=0.90 -> PASS
- **抽取错误样本**: 无

> 简历提取走真实 `extract_from_jd` 管线（与 `/resume/upload` 同路径），非关键字 baseline。

---

## 五、评测环境

| 项 | 值 |
|----|-----|
| 代码基线 | `ui/upload-ux-polish` 分支（139 commits，领先 main） |
| LLM Provider | Aliyun DashScope (百炼) |
| LLM Model | `qwen-plus` |
| LLM API | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 降级链 | DashScope -> 规则降级（本次未触发降级） |
| 反幻觉 | 启用 |
| 技能归一化 | 启用（579 别名组） |
| 向量归一化 | 未启用 |
| Python | 3.13.12 |
| 评测脚本 | `evaluation/run_real_eval.py` / `evaluation/run_resume_eval.py` |
| 运行位置 | `E:\java1\starmap-b1`（git worktree） |

---

## 六、产出文件清单

| 文件 | 路径 |
|------|------|
| JD 评测报告 | `evaluation/real_eval_report/evaluation_report.md` |
| JD 逐样本结果 | `evaluation/real_eval_report/evaluation_results.json` |
| JD 系统输出 | `evaluation/real_eval_report/system_real_llm.jsonl` |
| JD 错误分析 | `evaluation/real_eval_report/error_analysis.md` |
| JD 元数据 | `evaluation/real_eval_report/evaluation_meta.json` |
| JD 质量门禁 | `evaluation/real_eval_report/quality_gate.json` |
| 简历评测报告 | `evaluation/baseline_report/resume_report.md` |
| **本总报告** | `docs/competition/b1-metric-rerun-2026-08-22.md` |

---

## 七、结论

1. **JD 解析 F1 = 0.9622 [0.9516, 0.9713]**，较 8-17 的 0.938 提升 2.4 个百分点，CI 下限远超门禁 0.90。
2. **简历提取 F1 = 0.9158**，通过门禁。
3. **8-20 假失败根因已确认**：LLM key 失效导致降级抽取，非模型能力问题。
4. **匹配评测待补**：需 Neo4j + PostgreSQL 图谱环境（550 岗位/916 技能），建议 A0 合并部署后在服务器上运行。
5. **两项已跑指标全部 PASS**，可作为赛项评测的权威数字。
