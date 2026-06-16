# 评测模块

**负责人**: R7 姜文彬（流D QA评估）

## 文件说明

| 文件 | 用途 |
|------|------|
| `judge_eval.py` | LLM-as-judge裁判评估+F1指标计算 |
| `golden_set.jsonl` | 5条Golden标注样本（JD抽取标准答案） |

## 评估指标

- **技能F1**: 基于集合的精确率/召回率/F1（大小写不敏感，自动trim）
- **加权总分**: F1(0.5) + 岗位名称(0.15) + 经验(0.15) + 学历(0.20)
- **质量门禁**: F1≥0.90绿色 / ≥0.85黄色 / ≥0.80橙色 / <0.80红色

## 使用方式

```python
from evaluation.judge_eval import evaluate_batch, check_quality_gate

# 批量评估
metrics = evaluate_batch(
    golden_file="evaluation/golden_set.jsonl",
    system_file="data/output/jd_output.jsonl",
    output_file="data/output/eval_result.json"
)

# 检查门禁
gate = check_quality_gate(metrics)
print(gate)  # {"passed": True/False, "status": "green"/"red", ...}
```
