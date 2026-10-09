# 贡献指南（CONTRIBUTING）

> 状态：活文档
> 适用范围：向本仓库提交代码、文档、数据与配置的全部变更
> 权威来源：分支与提交规则以 [`docs/governance/git-workflow.md`](docs/governance/git-workflow.md) 为准，本文档只做入口与速查

## 一、5 分钟搭起开发环境

```bash
git clone https://github.com/starmap-team/starmap.git && cd starmap
cp .env.example .env          # 填入真实值；.env 不入库
pre-commit install            # 安装提交前钩子

cd backend  && poetry install # Python 依赖
cd ../frontend && npm ci      # 前端依赖
npm run gen:api               # 生成 src/api/schema.ts（该文件为生成物，不入库）
```

完整本地栈（含 Neo4j / Redis / Postgres）用 `docker-compose.dev.yml`；生产编排为 `docker-compose.prod.yml`。部署相关见 [`docs/architecture/deploy-from-zero.md`](docs/architecture/deploy-from-zero.md)。

## 二、提交前必须通过

| 检查 | 命令 |
|---|---|
| Python lint / format | `pre-commit run --all-files`（ruff，仅 `backend/`） |
| 后端测试 | `cd backend && poetry run pytest` |
| 后端单文件 | `cd backend && poetry run pytest tests/unit/<target>.py -q` |
| 前端类型检查 | `cd frontend && npm run typecheck` |
| 前端测试 | `cd frontend && npm run test` |
| 前端 lint | `cd frontend && npm run lint` |
| 契约同步 | `python starmap-contracts/validate.py` |

提交前钩子另外包含三类硬门禁：**gitleaks**（检出密钥即失败）、**check-added-large-files**（单文件 >500KB 失败）、**detect-private-key**。eslint 与 vue-tsc 为 `manual` 阶段，需显式运行。

## 三、分支与 PR

- `main` 与 `deploy/production` **均为受保护分支**，任何变更必须经 PR，禁止直接推送。
- 主题分支命名 `<type>/<kebab-case-slug>`，例如 `fix/rate-limit-429`；合并后即删。
- `deploy/production` 的合并方式：**只允许 squash 或 rebase**（merge commit 已禁用），且需 **1 人 review**、**不豁免管理员**、**禁止 force-push**。
- 提交信息用 Conventional Commits：`type(scope): 中文简述`，`type` 取 `feat` / `fix` / `docs` / `chore` / `test` / `refactor`。
- 原子提交：一次提交只做一件事，附带能说明"为什么"的正文。

## 四、绝不入库的内容

| 类别 | 说明 |
|---|---|
| `.env*` | 真实配置；只允许 `*.example` 模板。仓库已开启**密钥扫描 + 推送保护**，含密钥的推送会被服务端直接拒绝 |
| 大二进制 | 交付用 PDF / PPT / 视频 / 打包 zip，见 `.gitignore` 中的交付物政策（提交材料由云盘单独提供） |
| 生成物 | `frontend/src/api/schema.ts`、构建产物、缓存目录 |
| 工具与调试产物 | AI 工具工作区目录、一次性诊断输出、散落临时文件；根目录不放临时脚本（放 `scripts/` 或 `tmp` 类目录并加 ignore） |

## 五、写文档的规矩

- 项目规范集中在 [`docs/standards/`](docs/standards/)（00-总纲 → 07-devops 分层），改动前先读对应章节。
- 模块内的 `AGENTS.md` 只补充局部边界（`OVERVIEW` / `WHERE TO LOOK` / `CONVENTIONS` / `ANTI-PATTERNS`），不复制 README、不记录 Sprint 或临时状态；规范见 [`docs/standards/03-crawler/02-AGENTS-md-规范.md`](docs/standards/03-crawler/02-AGENTS-md-规范.md)。
- 引用文件用**当前存在的路径**；不要留下指向已删除脚本、已归档报告或工具工作区的链接。
- 不把工作流状态（AI 工具规划目录、阶段编号、调试会话名）写进代码注释或文档正文——对读者不构成信息。
- 文档治理细则见 [`docs/governance/documentation.md`](docs/governance/documentation.md)。

## 六、依赖与漏洞

Dependabot 自动安全更新已关闭，依赖漏洞需人工评估：

```bash
gh api repos/starmap-team/starmap/dependabot/alerts?state=open \
  --jq '.[] | "\(.security_advisory.severity)\t\(.dependency.package.name)"'
```

升级依赖时同步更新 `backend/poetry.lock` 或 `frontend/package-lock.json`，并在 PR 说明影响面（尤其 `frontend` 的 axios / vitest 族与 `backend` 的 anyio 等运行时依赖）。

## 七、安全事件

密钥泄漏按 [`docs/security/secret-rotation-playbook.md`](docs/security/secret-rotation-playbook.md) 处置；JWT 相关见 [`docs/security/jwt-rotation-playbook.md`](docs/security/jwt-rotation-playbook.md)。注意 `deploy/production` **禁止 force-push**——**凭据类提交必须在首次推送前处理干净**，推送之后无法以任何合规方式从历史中移除。

## 八、速查索引

| 我想…… | 先读 |
|---|---|
| 了解系统全貌 | [`docs/architecture/overview.md`](docs/architecture/overview.md) |
| 上手（新人） | [`docs/guides/onboarding.md`](docs/guides/onboarding.md) |
| 改后端领域逻辑 | `docs/standards/01-backend/` |
| 改前端页面 | `docs/standards/02-frontend/` |
| 改爬虫 | [`crawler/README.md`](crawler/README.md)、`docs/standards/03-crawler/` |
| 改 API 契约 | [`starmap-contracts/README.md`](starmap-contracts/README.md)、`docs/standards/04-contracts/` |
| 跑评测 | [`evaluation/README.md`](evaluation/README.md)、`docs/standards/05-evaluation/` |
| 改 CI / 部署 | `docs/standards/07-devops/`、[`docs/architecture/public-deployment-runbook.md`](docs/architecture/public-deployment-runbook.md) |
| 找文档总入口 | [`docs/README.md`](docs/README.md) |
