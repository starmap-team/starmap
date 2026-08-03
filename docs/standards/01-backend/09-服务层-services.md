# Services 层规范

## 职责

`backend/app/services/` 负责路由和 core 之间的业务编排、数据访问、认证/审核、图查询与 PG->Neo4j 投影。

## 规则

- 使用 `resources.py` 和依赖注入共享 engine/driver/client。
- 图查询使用 `graph_service.py` 等现有服务；PG->Neo4j 使用 `graph_projector.py`/sync 服务。
- `neo4j_service.py` 已不存在，不得在文档或新代码恢复该平行入口。
- PostgreSQL 记录先提交，再 best-effort 投影；失败可观察、可重试。
- 服务返回领域/Schema 友好的值，不把 ORM、driver record 或 provider response 直接暴露给 API。
- 对用户资源执行所有权/角色检查。
- 外部调用配置 timeout、重试和可审计错误。

## 变更

新增服务前确认没有现有领域 owner。多个服务共享逻辑时抽到明确领域模块，不创建无边界的 helpers。
