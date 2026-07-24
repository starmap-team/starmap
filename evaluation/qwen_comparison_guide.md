# Qwen/Ollama 对比运行

该文档只说明可选的本地 LLM profile。它不是生产部署指南，也不保证一次运行结果代表当前模型质量。

## 启动

```bash
docker compose -f docker-compose.dev.yml --profile llm up -d ollama ollama-pull
docker logs -f starmap-ollama-pull
curl http://localhost:11434/api/tags
```

## 运行评估

```bash
python evaluation/run_real_eval.py --help
python evaluation/run_llm_eval.py --help
```

运行前确认模型名称、Ollama 地址、输入 Golden Set 和输出目录。不要把真实评估结果写入源码目录；需要保留的结果放入 `docs/archive/reports/<date>/evaluation/`。

## 解释结果

baseline、模拟结果和 Ollama/云端真实结果必须分栏记录 provider、model、prompt 版本、数据集版本和时间。缺少这些元数据的 F1 不应作为项目质量结论。