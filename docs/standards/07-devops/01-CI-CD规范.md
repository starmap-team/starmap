# CI/CD 规范

## 当前工作流

- `ci.yml`：contracts -> backend/frontend/crawler；Docker smoke 在 scheduled/manual 事件运行。
- `doc-lint.yml`：文档结构、链接和失效引用检查。

## 规则

- API 契约校验先于依赖它的构建。
- 后端执行 Ruff、mypy、pytest 和 FastAPI/contract 路径一致性。
- 前端重新生成类型后执行 lint、typecheck、test、build。
- crawler 执行 compile 和不依赖外部数据库的测试。
- 阈值、版本和命令从项目配置读取，不在 workflow 注释复制旧数字。
- 安全审计若允许 continue-on-error，必须有明确治理 owner，不能误称硬门禁。
- Docker smoke 清理资源并输出失败日志。

## 变更

工作流修改同时更新 `.github/AGENTS.md` 和本规范；本地先运行同名命令。