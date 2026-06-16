# StarMap Contracts

接口契约子模块，作为 StarMap 项目各端（后端/前端/算法）之间的单一事实源。

## 使用方式

- `openapi.yaml` — OpenAPI 3.0 规范，含所有端点及数据定义
- `models/__init__.py` — Pydantic v2 共享模型，与 openapi.yaml 保持同步
- `graph_cypher/` — Neo4j Cypher 查询模板
