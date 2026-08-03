# Git 工作流治理规范

> 状态：活文档
> 适用范围：本仓库（starmap-team/starmap）所有分支、提交、PR 与 CI 门禁

## 目标

三条不可退让的底线：

1. `main` 始终是最终领头分支，任何时刻可发布、可演示；
2. 所有变更经 PR 进入 `main`，禁止直接推送工作提交；
3. 提交历史可读、可追溯、可回滚（原子提交 + Conventional Commits）。

## 1. 分支模型

| 分支 | 角色 | 生命周期 |
|---|---|---|
| `main` | 唯一最终领头分支，受保护 | 永久 |
| `<type>/<slug>` | 主题开发分支（见 §2） | 短命：合并即删 |
| `develop`（可选） | 集成暂存分支，仅在多线并行需要汇合点时启用 | 长期，但必须定期经 PR 并入 `main`，不得长期领先 |

约束：

- 允许存在**一个**领先于 `main` 的开发分支（主题分支或 `develop`）；不允许多个游离长期分支。
- 本地 `main` 只做 `origin/main` 的镜像（pull / fast-forward），不在其上直接提交。
- 历史遗留前缀（`stageN-*`、`backup-*`、`codex/*`）只读保留或清理，禁止新建。
- 已合并的远程分支合并后立即删除；本地备份分支（`backup-*`）不得推送远程。

## 2. 分支命名

格式：`<type>/<kebab-case-slug>`，`type` 与提交类型一致（§3）：

```
feat/data-truth-panel
fix/rate-limit-429
refactor/sse-pipeline-consolidation
chore/ci-context-sync
docs/git-governance
test/e2e-browser-suite
```

- 可内嵌 Issue 号：`fix/123-login-crash`
- slug 用小写短横线，≤5 个词，能一眼看出目的

## 3. 提交规范（Conventional Commits）

格式：

```
<type>(<scope>): <description>

<body — 可选，解释 why 而非 what>

<footer — Closes #N / Refs #N / BREAKING CHANGE: ...>
```

**type 白名单**：

| type | 用途 |
|---|---|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 不改行为的重构 |
| `perf` | 性能优化 |
| `test` | 仅测试 |
| `docs` | 仅文档 |
| `chore` | 构建、依赖、仓库卫生 |
| `ci` | CI 配置 |
| `revert` | 回滚 |

**scope**：模块名，如 `backend`、`frontend`、`crawler`、`contracts`、`infra`、`repo`、`governance`，或业务域（`matching`、`pipeline`）。

**description**：祈使句、首字母小写（英文）、结尾无句号、整行 ≤72 字符。中英文均可，但同一提交内保持一致。

**粒度**：

- 一个提交只做一件事，且单独可编译、可过测试；
- 功能代码与其配套测试放在同一提交；
- 禁止夹带无关格式化或顺手重构（单独成 commit）。

**关联 Issue**：修复类提交 footer 写 `Closes #N`，相关但不关闭写 `Refs #N`；squash 合并时由 PR 编号自动补充 `(#N)`。

## 4. PR 与合并策略

标准流程：

```
主题分支 → push -u → gh pr create → CI 四项全绿 → 审查 → 合并 → 删除分支
```

- PR 标题等同规范提交标题；正文使用仓库模板 `.github/pull_request_template.md`（含契约、数据、验证、回滚四节，逐项勾选）。
- **合并策略**：
  - 默认 **squash merge**（单主题 PR）；
  - PR 内提交已全部原子化且各自合规时，可用 **rebase merge** 保留历史；
  - 禁止普通 merge commit（`develop` 回合 `main` 除外）。
- 合并后同步删除远程分支。
- PR 超过 5 天无人审查：主动催办；30 天无活动：关闭并在评论说明。

## 5. 推送权限与分支保护

`main` 启用 GitHub Branch Protection，配置以本节为事实源，与 `ci.yml` 的 job 名保持同步：

| 项 | 配置 |
|---|---|
| 直接推送 | 禁止（仅 PR） |
| Required status checks | `契约校验`、`后端 lint + typecheck + test`、`前端 lint + typecheck + test + build`、`爬虫 compile + test`；strict 模式（合并前先同步 main） |
| PR 审查 | 必需；至少 1 人 approve；新推送自动 dismiss 旧审查 |
| 评论解决 | 审查评论必须全部 resolved 方可合并 |
| force push / 删除分支 | 禁止 |
| 管理员豁免 | `enforce_admins=false`——仅为单人维护期的应急通道，日常管理员同样走 PR 流程 |

单人维护期豁免：无第二审查人时，维护者可在 CI 四项全绿后自审合并，但必须在 PR 正文完成模板自查清单。团队扩充后收紧为强制 1 人 approve（取消管理员豁免）。

## 6. CI 门禁规范

**强制门禁（阻塞合并）**——`.github/workflows/ci.yml` 四个 job：

1. **契约校验**（最先跑）：`starmap-contracts/validate.py`，契约优先原则的机器化；
2. **后端**：Ruff + mypy + pytest（覆盖率门禁 70%）+ FastAPI 导出与 openapi.yaml 一致性比对；
3. **前端**：从契约 `gen:api` 生成类型 → ESLint → vue-tsc → Vitest → build；
4. **爬虫**：compileall + pytest（跳过需 PostgreSQL 的集成测试）。

**可选门禁**——`docker-smoke`（Docker 全栈冒烟）：

- 仅在 `workflow_dispatch`（手动）或每日定时（UTC 02:00）触发，**不阻塞 PR**；
- 验收标准：全栈 compose 启动成功、后端 `/health` 200、前端首页可达；
- 失败不阻塞但须在 24h 内排查（每日集成纪律）；
- 若未来升级为强制门禁，必须同步更新：`ci.yml` 触发条件、`main` 分支保护 contexts、本文件 §5 与 §6。

**通用纪律**：

- PR 不得使任何强制检查由绿转红后合并；
- 安全审计步骤（pip-audit / npm audit）当前为 `continue-on-error`，属观察期；转阻塞前需先修订本文件；
- 文档变更另受 `doc-lint.yml` 检查（新鲜度脚本）。

## 7. 代码审查规范

审查顺序：安全 → 正确性 → 测试 → 可读性。

| 严重级 | 含义 | 合并裁决 |
|---|---|---|
| CRITICAL | 安全漏洞 / 数据丢失风险 | 阻止，必须修复 |
| HIGH | Bug / 重大质量问题 | 合并前应修复 |
| MEDIUM | 可维护性问题 | 建议修复 |
| LOW | 风格建议 | 可选 |

红线检查项（任一命中即 CRITICAL）：硬编码密钥、未校验用户输入、SQL 拼接、无迁移的模型变更、契约外 API 变更。

## 8. 版本与发布

- 语义化版本 `vX.Y.Z`；tag 仅在 `main` 上且 CI 全绿后创建；
- `gh release create vX.Y.Z --generate-notes`，生成后人工校订 changelog。

## 9. 违规处理

| 情形 | 处置 |
|---|---|
| 误直推 `main` | `git revert` 或补 PR 追认，**禁止** force push 抹痕 |
| 误提交密钥 | 立即轮换密钥 → `git filter-repo` 清洗历史 → 通知所有协作者重克隆 |
| 误提交大文件/产物 | 从历史移除并补 `.gitignore`，在 PR 中说明 |
| 分支保护与 `ci.yml` job 名漂移 | 以 `ci.yml` 为事实源，同步保护配置并复核本文件 §5 |

## 附录：日常操作速查

```bash
# 开发
git checkout main && git pull --ff-only
git checkout -b feat/<slug>
# ...原子提交...
git push -u origin feat/<slug>
gh pr create --fill   # 按模板补全

# 合并（CI 绿 + 审查通过后）
gh pr merge <N> --squash --delete-branch   # 或 --rebase

# 本地 main 回正
git checkout main && git pull --ff-only
```
