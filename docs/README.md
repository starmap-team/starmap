# StarMap 文档中心

本目录是项目公共文档的唯一根目录。文档按用途而不是按作者或阶段分类；同一主题只有一个当前入口。

## 当前文档

| 分类 | 位置 | 内容 |
|---|---|---|
| 架构 | `architecture/` | 系统边界、数据存储与运行流水线 |
| 指南 | `guides/` | 入职、开发与部署操作 |
| 治理 | `governance/` | 文档维护规则和例外 |
| 规范 | `standards/` | 可执行的编码、契约、测试与运维规则 |
| 本体 | `ontology/` | 技能分类、本体和映射数据 |
| 参考 | `reference/` | 稳定术语和查询型资料 |
| 交付物 | `design/` | Word/设计成果等交付物；不作为工程实现事实 |
| 工具 | `pencil-tools/` | 设计评估工具及其运行资源 |
| 归档 | `archive/` | 历史报告、计划、审计、设计稿和提示词 |

推荐阅读顺序：

1. [项目 README](../README.md)
2. [入职指南](guides/onboarding.md)
3. [架构总览](architecture/overview.md)
4. [规范索引](standards/README.md)
5. 对应模块旁的 `README.md`

## 真相来源

| 问题 | 权威来源 |
|---|---|
| 如何运行 | 根 `README.md`、Compose 文件、`.env.example` |
| 开发约定 | `CONTRIBUTING.md`、`docs/standards/` |
| API 路径与字段 | `starmap-contracts/openapi.yaml` |
| 后端请求/响应模型 | `backend/app/schemas/` |
| 数据库结构 | SQLAlchemy models + Alembic migrations |
| 当前实现状态 | 当前工作树中的代码和测试结果 |
| 历史决策或验证证据 | `docs/archive/`，仅用于追溯 |

`.planning/` 是工作流状态，不是产品文档；其阶段结论不能覆盖当前代码。模块内 README、契约 CHANGELOG 和测试说明因就地发现需求保留在代码目录中，这些是集中目录规则的明确例外。

## 维护

文档变更遵循 [文档治理规范](governance/documentation.md)。提交前运行：

```powershell
pwsh -File scripts/check-docs.ps1
```