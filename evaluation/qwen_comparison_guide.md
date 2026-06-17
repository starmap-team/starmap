# Qwen2.5-7B 对比评测指南

## 1. 启动 Ollama + Qwen2.5-7B

```bash
# 启动 Ollama 服务（含自动拉取模型）
docker-compose -f docker-compose.dev.yml up -d ollama

# 检查模型是否拉取完成
docker logs starmap-ollama-pull -f

# 验证 API 可用
curl http://localhost:11434/api/tags
```

## 2. 测试连接

```bash
cd backend
poetry run python ../scripts/test_qwen_ollama.py
```

## 3. 运行对比评测

编辑 `.env`，确保 `QWEN_MODEL_PATH=http://ollama:11434`，然后运行评测：

```bash
# 使用讯飞星火
poetry run python -c "
from evaluation.judge_eval import evaluate_batch, generate_evaluation_report
metrics = evaluate_batch('evaluation/golden_set.jsonl', 'evaluation/system_xunfei.jsonl')
print(f'Xunfei F1: {metrics.avg_f1}')
"

# 使用 Qwen2.5-7B（设置 LLM_BACKEND=qwen）
LLM_BACKEND=qwen poetry run python evaluation/run_baseline.py
```

## 4. 预期对比

| 维度 | 讯飞星火 v3.5 | Qwen2.5-7B (本地) |
|------|---------------|-------------------|
| 延迟 | ~1-3s (网络) | ~5-15s (本地 GPU) |
| 成本 | 按量付费 | 免费 |
| 稳定性 | 依赖网络 | 本地无网络风险 |
| F1 预期 | ≥0.90 | ≥0.85 |
| 适用场景 | 线上生产 | 开发调试/离线评测 |

## 5. 架构说明

```
backend → llm_client.py
            ├── call_xunfei_llm()     # 主力：讯飞星火 API
            └── call_llm_with_fallback()  # 降级：Qwen2.5-7B via Ollama
                     └── http://ollama:11434/v1/chat/completions
```

Qwen2.5-7B 作为自动降级（fallback），当讯飞 API 不可用时自动切换。
