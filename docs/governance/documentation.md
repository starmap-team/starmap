# 文档治理规范

> 状态：活文档
> 适用范围：仓库内所有人工与自动生成文档

## 目标

文档必须能回答"现在如何工作"，或明确说明"这是何时的历史记录"。禁止让一次性报告、旧计划或手写指标与当前代码竞争权威性。

## 文档类型

| 类型 | 位置 | 维护方式 |
|---|---|---|
| 活文档 | `docs/architecture/`、`guides/`、`governance/`、`standards/`、`ontology/`、`reference/` | 随行为、接口或约定变更同步更新 |
| 模块文档 | 模块旁的 `README.md` / `CONTRIBUTING.md` | 只描述本模块边界和操作入口 |
| 契约文档 | `starmap-contracts/` | OpenAPI/Schema 变更流程维护 |
| 工作流状态 | `.planning/` | 由规划工具维护，不作为产品事实源 |
| 历史快照 | `docs/archive/` | 只读保留，文件内标注归档性质和日期 |
| 运行产物 | 被 `.gitignore` 忽略的结果目录 | 默认不提交；需要留证时转入归档 |

## 唯一归属

- 公共架构说明只在 `docs/architecture/`。
- 操作型说明只在 `docs/guides/` 或对应模块 README。
- 强制规则只在`CONTRIBUTING.md` 和 `docs/standards/`。
- 术语只在 `docs/reference/glossary.md`。
- 一次性报告只在 `docs/archive/reports/<date>/`。
- 旧计划、审计和设计稿分别进入 `archive/plans/`、`archive/audits/`、`archive/design/`。

根目录只允许三个 Markdown 入口：`README.md`、`CONTRIBUTING.md`。

以下文件因工具发现或模块自治必须就地保留，不视为违反集中规则：

- 任意目录的 `CONTRIBUTING.md`
- 包、模块或子项目的 `README.md`
- `.github/pull_request_template.md`
- `starmap-contracts/CHANGELOG.md` 和联调说明
- `.planning/` 中的规划器状态

## 内容规则

1. 先读取代码、配置和契约，再更新文档。
2. 活文档不记录测试通过数、覆盖率实测值、端点数、文件数、组件数、行数或"最新迁移编号"。
3. 必须记录阈值时，引用配置事实源，例如"pytest 门禁见 `backend/pyproject.toml`"。
4. 规范性要求用"必须/禁止"；当前状态用可验证陈述；未来方案进入 issue 或归档计划。
5. 相对链接必须可解析；移动文档时同步更新所有引用。
6. 示例命令必须从仓库声明的工具链执行，不引用不存在的脚本或服务。
7. API 字段保留项目约定的 `snake_case`。
8. 归档内容不做"修正文义"式改写，只添加归档标识并修复必要的导航链接。

## 变更触发

以下变更必须同步文档：

- API 路径、请求/响应 Schema 或错误格式变更
- 服务拓扑、端口、环境变量或启动方式变更
- 数据库职责、模型或迁移流程变更
- 目录边界、模块入口或公共命令变更
- 测试门禁与 CI 工作流变更

## 验证

```powershell
pwsh -File scripts/check-docs.ps1
```

校验必须覆盖活文档链接、根目录散落文档、错误的历史报告位置和已知失效引用。归档正文允许保留当时的旧路径与数字，因为它们属于历史证据。