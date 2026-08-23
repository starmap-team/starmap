# 简历提取准确率评测报告（真实 LLM 管线）

- **样本数**: 50
- **Precision**: 0.9315
- **Recall**: 0.9007
- **F1**: 0.9158
- **门禁**: ≥90% → ✅ PASS

> 评测走真实 LLM 抽取管线（extract_from_jd，与 /resume/upload 同路径），
> 非关键字 baseline。对比 run_resume_baseline.py（关键字 F1≈0.78）。

## 抽取错误样本

- 无
