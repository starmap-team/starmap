# 信息抽取引擎 (Extraction Pipeline)

**负责人**: R3 杨博文（流B 算法抽取岗）

## 模块结构

```
extraction/
├── __init__.py          # 包导出
├── prompt.py            # Prompt模板管理（4组常量）
├── llm_client.py        # 讯飞星火API异步封装（httpx+tenacity）
├── jd_extract.py        # JD抽取主流程编排
├── normalize.py         # 三步技能归一化引擎
└── graph_writer.py      # Neo4j图谱异步写入
```

## 调用链路

```
extract_from_jd(jd_content)
  → prompt.get_prompt("jd_extraction", ...)    # 填充提示词
  → llm_client.LLMClient.extract_from_jd()     # 调用星火API
  → parse_llm_json_response()                  # 解析JSON
  → JDExtractionResult pydantic校验             # 结构化校验
  → normalize_skill() / batch_normalize_skills() # 三步归一化
  → llm_client.validate_extraction()            # 防幻觉校验
  → graph_writer.write_extraction_to_graph()    # 写入Neo4j
```

## 关键设计

| 层级 | 逻辑 | 容错 |
|------|------|------|
| LLM调用 | 讯飞星火主链路 → Qwen本地兜底 | 3次重试+指数退避 |
| JSON解析 | 自动清理markdown fences、尾逗号 | ValueError抛上层 |
| 技能归一化 | 别名字典→BGE向量搜索→多源校验 | 每层降级，不阻断流程 |
| 防幻觉 | 独立LLM裁判二次校验 | 低可信标记不入图 |

## 环境变量

参见 `.env`:
- `XUNFEI_API_KEY` / `XUNFEI_API_SECRET` / `XUNFEI_APP_ID`（必填）
- `LOCAL_QWEN_ENDPOINT`（可选，兜底模型）
- `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD`
