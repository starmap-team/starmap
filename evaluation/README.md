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
python evaluation/run_baseline.py
python evaluation/run_resume_baseline.py
python evaluation/simulate_llm_eval.py
python evaluation/run_real_eval.py
```

真实评估需要有效的 LLM 凭据和可复现的运行元数据。`run_llm_eval.py` 与 `run_real_eval.py` 的语义不同，发布指标前必须说明使用的入口、模型、prompt 版本、数据集 commit 和时间。

## 指标

抽取评估使用 precision、recall、F1 和结构字段评分。质量门槛与业务配置以评估代码和当前需求为准；不要从旧报告复制 F1 作为当前结果。

## 规则

- baseline、模拟 LLM、真实 LLM 结果必须分开报告。
- 不手工编辑生成结果来"修复"指标。
- 新算法提交前至少运行不需要外部服务的 baseline。
- 需要保留的报告移入 `docs/archive/reports/<date>/evaluation/`，当前目录只保留评估代码、数据集和使用说明。