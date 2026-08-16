# StarMap 评估套件

`evaluation/` 保存领域 Golden Set、可重复 baseline、模拟 LLM 评估和真实 LLM 评估入口。生成报告是运行产物，不是质量现状的永久声明。

## 数据集

| 文件 | 范围 |
|---|---|
| `golden_set.jsonl` | JD 抽取 |
| `golden_set_resume.jsonl` | 简历抽取 |
| `golden_set_match.jsonl` | 人岗匹配 |
| `golden_set_pipeline.jsonl` | 流水线场景 |

标注规则见 [annotation_guideline.md](annotation_guideline.md)。修改 Golden Set 时应保留版本和评审记录，并防止真值泄漏到被评估管线。

## 入口

```bash
python evaluation/run_baseline.py            # JD 抽取（规则 baseline，F1≈0.93）
python evaluation/run_resume_baseline.py     # 简历抽取（规则 baseline，F1≈0.78，不达标）
python evaluation/run_resume_eval.py         # 简历抽取（真实 LLM 管线，赛项 P0-2）
python evaluation/run_match_baseline.py      # 人岗匹配（真实匹配引擎，赛项 P0-1）
python evaluation/simulate_llm_eval.py
python evaluation/run_real_eval.py           # JD 抽取（真实 LLM）
```

真实评估需要有效的 LLM 凭据和可复现的运行元数据。`run_llm_eval.py` 与 `run_real_eval.py` 的语义不同，发布指标前必须说明使用的入口、模型、prompt 版本、数据集 commit 和时间。

## 指标口径（赛项 XH-202621 三个 ≥90% 指标）

| 指标 | runner | 口径 | 判定 |
|---|---|---|---|
| JD 解析准确率 | `run_baseline.py`（规则）/ `run_real_eval.py`（LLM） | 对 golden JD 提取技能集合，与标注集合算 **F1**（precision/recall 合并） | F1 ≥ 0.90 |
| 简历提取准确率 | `run_resume_baseline.py`（规则）/ `run_resume_eval.py`（LLM） | 对 golden 简历提取技能集合，与标注集合算 **F1** | F1 ≥ 0.90 |
| 人岗匹配准确率 | `run_match_baseline.py` | 逐条调用真实匹配引擎，判定 match_score 是否落在 golden 期望区间 **且** should_match 方向一致 | 区间命中率 ≥ 0.90 |

口径要点：

- **匹配准确率**采用"区间命中 + 方向一致"二元判定（见 `run_match_baseline.py`），
  不是单一 F1 —— 赛项"匹配准确率≥90%"用可解释的区间校准口径。
- 规则 baseline 与真实 LLM 结果**必须分开报告**，且发布指标以真实管线
  （`run_real_eval.py` / `run_resume_eval.py`）为准，规则 baseline 仅作下限参考。
- 匹配评测暴露的图谱画像问题（岗位 required 技能含跨 JD 噪声，如 Axon/Ktor
  混入「后端工程师」）属于数据质量项，修复后重跑 `run_match_baseline.py` 即刷新数字。

## 指标

抽取评估使用 precision、recall、F1 和结构字段评分。质量门槛与业务配置以评估代码和当前需求为准；不要从旧报告复制 F1 作为当前结果。

## 规则

- baseline、模拟 LLM、真实 LLM 结果必须分开报告。
- 不手工编辑生成结果来"修复"指标。
- 新算法提交前至少运行不需要外部服务的 baseline。
- 需要保留的报告移入 `docs/archive/reports/<date>/evaluation/`，当前目录只保留评估代码、数据集和使用说明。