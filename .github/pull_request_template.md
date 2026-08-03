## 变更说明

<!-- 说明做了什么、为什么，以及用户可观察行为。 -->

## 变更类型

- [ ] 功能
- [ ] Bug 修复
- [ ] 重构
- [ ] API 契约
- [ ] 数据模型/迁移
- [ ] 文档/治理
- [ ] 依赖/基础设施

## 影响范围

<!-- 列出后端、前端、crawler、contracts、数据、部署等受影响边界。 -->

## 契约与数据

- [ ] 不涉及公共 API；或已先更新 `starmap-contracts/openapi.yaml`
- [ ] 不涉及 Pydantic Schema；或已导出 JSON Schema 并生成前端类型
- [ ] 不涉及数据库结构；或已新增并验证 Alembic migration
- [ ] PG/Neo4j 投影和数据兼容性已说明

## 验证

- [ ] 后端 Ruff / mypy / pytest（适用范围）
- [ ] 前端 lint / typecheck / test / build（适用范围）
- [ ] 契约校验与类型生成（适用范围）
- [ ] E2E / 手工场景（适用范围）
- [ ] `pwsh -File scripts/check-docs.ps1`（文档变化）

验证结果与未执行项：

<!-- 粘贴命令摘要；说明因环境/凭据未运行的检查。 -->

## 风险与回滚

<!-- 迁移、数据写入、兼容性、部署或安全风险；给出回滚/恢复路径。 -->