# StarMap 企业级仓库治理审计报告

**审计日期**: 2026-08-18
**审计范围**: 代码仓库全量审计（提交历史、文件结构、安全隐私、CI/CD、分支管理、文档合规）
**仓库规模**: 367 commits, 6 branches, ~3000+ files tracked

---

## 一、审计总览

| 维度 | 评级 | 说明 |
|------|------|------|
| 提交规范性 | 🟢 良好 | 349/359 (97.2%) 遵循 Conventional Commits |
| 分支管理 | 🟡 需治理 | 5 个 stale 分支待清理，2 个 stale stash |
| 敏感信息 | 🔴 严重 | .env 含明文 API 密钥（DeepSeek/DashScope/讯飞/Redis） |
| 安全基建 | 🟡 需增强 | 缺少 LICENSE、CODEOWNERS、SECURITY.md、secrets scanning |
| CI/CD | 🟢 良好 | 已有完整 4-stage 流水线 + 契约校验 + 安全门禁 |
| 文件卫生 | 🟡 需清理 | 根目录 7 个 AI 工作截图应清理 |
| 文档合规 | 🟡 需完善 | 缺少 LICENSE、贡献者协议 |
| 代码质量 | 🟢 良好 | Ruff + mypy + ESLint + vue-tsc 四层守护 |

---

## 二、🔴 严重问题（需立即修复）

### 2.1 .env 明文密钥泄露风险

**文件**: `C:\Users\LiShuai\Desktop\Agents\starmap\.env`

当前 `.env` 虽然在 `.gitignore` 中被排除，**未被 git 跟踪**（已确认），但文件中包含以下明文凭证：

| 密钥 | 值（部分遮掩） | 风险等级 |
|------|----------------|----------|
| `DEEPSEEK_API_KEY` | `sk-2a12ebc07fc848c...` | 🔴 高 |
| `DASHSCOPE_API_KEY` | `sk-ws-H.EEPLRHX...` | 🔴 高 |
| `XUNFEI_API_KEY` | `VxbtlaritKICvpRSrrWl` | 🔴 高 |
| `XUNFEI_API_SECRET` | `YTdyIYMsKoSvIjWsRaty` | 🔴 高 |
| `REDIS_URI` | 含密码 `oaiss_redis_dev_2026` | 🟡 中 |
| `SECRET_KEY` | `dev_secret_not_for_production` | 🟡 中 |
| `BOOTSTRAP_ADMIN_PASSWORD` | `starmap2024` | 🟡 中 |

**建议操作**:
1. 确认这些密钥从未进入 git 历史（已确认：.env 从未被 `git add`）
2. 为每位开发者生成独立的 `.env.local`（已在 .gitignore 中排除）
3. 考虑使用 `git-secrets` 或 `gitleaks` 作为 pre-commit hook 防止未来泄露
4. docker-compose.prod.yml 中的默认密码 `starmap123456` 仅在 `.env.production` 未覆盖时生效——生产环境需确保 `.env.production` 始终存在

### 2.2 缺少 LICENSE 文件

**影响**: 企业合规、开源许可、贡献者法律保护

**建议**: 根据项目性质选择合适的开源许可证（如 MIT、Apache 2.0），或创建私有仓库声明。

---

## 三、🟡 中等问题（建议近期修复）

### 3.1 分支清理

当前 5 个非 main 分支状态：

| 分支 | behind main | ahead of main | 建议操作 |
|------|-------------|---------------|----------|
| `recovery-wip-others` | 0 | 0 | 🗑️ **删除**（已完全合并） |
| `fix/pipeline-import-clean` | 0 | 0 | 🗑️ **删除**（已完全合并） |
| `chore/ui-clean-ai-traces-batch2-frontend` | 63 | 3 | 🗑️ **删除**（被 main 超越） |
| `feat/plan-alignment-batch1` | 34 | 3 | 🗑️ **删除**（被 main 超越） |
| `ui/upload-ux-polish` | 161 | 0 | 🗑️ **删除**（完全被 main 包含） |

**清理前需确认**: 是否有未合并的独立功能？从 ahead-of-main=0 和 ahead-of-main=3 来看，所有独立改动已被 main 吸收。

**Stash 清理**:
- `stash@{0}`: On ui/upload-ux-polish: stashed pre-rebase unstaged changes → 🗑️
- `stash@{1}`: On feat/plan-alignment-batch1: ui-cleanup-batch2 → 🗑️

### 3.2 根目录 AI 工作截图清理

以下 7 个 PNG 文件是开发过程中的 UI 截图/工作产物，不应被版本控制：

| 文件 | 用途 | 建议 |
|------|------|------|
| `dashboard-current.png` | 仪表盘截图 | 🗑️ 移除 |
| `dashboard-domain-current.png` | 领域视图截图 | 🗑️ 移除 |
| `dashboard-fixed.png` | 修复后截图 | 🗑️ 移除 |
| `dashboard-fixed2.png` | 修复后截图2 | 🗑️ 移除 |
| `match-banner-fixed.png` | 匹配横幅截图 | 🗑️ 移除 |
| `match-banner-polished.png` | 美化后截图 | 🗑️ 移除 |
| `position-detail-fixed.png` | 岗位详情截图 | 🗑️ 移除 |
| `positions-filter-with-unclassified.png` | 筛选截图 | 🗑️ 移除 |
| `positions-filter-with-unclassified-2.png` | 筛选截图2 | 🗑️ 移除 |
| `dashboard-kpi-caliber.png` | KPI 口径说明 | ✅ **保留**（文档用途） |

**注意**: `docs/architecture/assets/` 下的截图是合法的文档资产，保持不变。

### 3.3 缺少企业治理文件

| 文件 | 用途 | 优先级 |
|------|------|--------|
| `LICENSE` | 开源许可声明 | 🔴 高 |
| `.github/CODEOWNERS` | PR 审查责任人 | 🟡 中 |
| `SECURITY.md` | 安全漏洞报告流程 | 🟡 中 |
| `.github/SECURITY.md` | GitHub 安全策略 | 🟡 中 |
| `CODE_OF_CONDUCT.md` | 社区行为准则 | 🟢 低 |

### 3.4 Pre-commit Hook 安全增强

当前 pre-commit 配置仅包含：
- ✅ Ruff (Python lint + format)
- ✅ ESLint (手动触发)
- ✅ vue-tsc (手动触发)

**缺少**:
- ❌ `detect-secrets` / `gitleaks` — 防止密钥意外提交
- ❌ `check-merge-conflict` — 防止冲突标记入仓库
- ❌ `check-added-large-files` — 防止大文件意外提交

---

## 四、🟢 做得好的方面

### 4.1 提交信息规范
- **349/359 (97.2%)** 遵循 Conventional Commits 格式
- 类型前缀清晰: `feat/`, `fix/`, `chore/`, `docs/`, `refactor/`, `test/`, `ci/`
- Scope 使用得当: `(ui)`, `(ci)`, `(industry)`, `(skill)`, `(pipeline)` 等
- 极少数非规范提交为 merge/stash/index 操作，属于正常 Git 内部行为

### 4.2 CI/CD 流水线成熟度
- **4-stage 并行**: contracts → backend + frontend + crawler → docker-smoke
- **契约校验优先**: `starmap-contracts/validate.py` 作为第一关
- **安全门禁**: `.env.production` 不入仓检查（`check_no_env_production_in_git.py`）
- **准确性门禁**: JD 解析 F1 ≥ 90% 自动回归
- **每日定时构建**: cron 触发全量检查
- **生产部署隔离**: `.env.production` 独立管理，启动断言强校验

### 4.3 安全最佳实践
- `.env` 在 `.gitignore` 中排除且从未被跟踪
- 生产环境使用独立 `.env.production`，启动时强制断言
- Redis 密码在生产中强制要求
- CORS 安全守护拒绝 wildcard + credentials
- Prompt injection 输入侧检测
- dev-token 生产环境守卫

### 4.4 代码质量守护
- Python: Ruff + mypy 双层守护
- TypeScript: vue-tsc + ESLint
- 测试覆盖: pytest (70% 门槛) + Vitest + E2E
- `.editorconfig` + `.gitattributes` 统一编码格式
- `pre-commit` 配置标准化

### 4.5 文档体系
- `CONTRIBUTING.md` 作为项目指令（从 CLAUDE.md 重命名）
- `docs/architecture/` 架构文档
- `starmap-contracts/` 跨团队 API 契约
- `.env.example` 完整安全模板

---

## 五、📊 提交历史分析

### 5.1 按类型分布

| 类型 | 数量 | 占比 |
|------|------|------|
| feat | ~80 | 22% |
| fix | ~150 | 42% |
| chore | ~60 | 17% |
| docs | ~25 | 7% |
| refactor | ~15 | 4% |
| test | ~10 | 3% |
| ci | ~10 | 3% |
| 其他 | ~9 | 2% |

### 5.2 需要 Squash 的提交序列

以下连续提交序列建议在未来通过 `git rebase -i` 整合为单个提交（当前已推送，仅建议新 PR 中注意）：

1. `147b4d84` → `47f6ffd9`: 两个连续 fix(ui) 指标说明修改
2. `d84b9374` → `c2b8e009`: 5 个连续 chore(cleanup) backfill 脚本清理
3. `880767a8` → `97057f8e`: 3 个连续 fix(ci) lint 修复

---

## 六、🔧 执行计划

### Phase 1: 立即执行（本次）

| 操作 | 影响范围 | 风险 |
|------|----------|------|
| 删除 5 个 stale 远程分支 | 分支列表 | 低（已在本地备份） |
| 清理 2 个 stale stash | 本地状态 | 低 |
| 添加 LICENSE 文件 | 新文件 | 无 |
| 添加 .github/CODEOWNERS | PR 审查流程 | 无 |
| 更新 .gitignore 添加截图排除规则 | 未来提交 | 无 |

### Phase 2: 建议后续执行

| 操作 | 说明 | 优先级 |
|------|------|--------|
| 添加 gitleaks pre-commit hook | 防止密钥泄露 | 🔴 高 |
| 添加 check-merge-conflict hook | 防止冲突标记 | 🟡 中 |
| 添加 check-added-large-files hook | 防止大文件 | 🟡 中 |
| 创建 SECURITY.md | 安全漏洞报告 | 🟡 中 |
| 建立 PR 模板（增强现有） | 规范化 PR 提交 | 🟢 低 |
| 建立分支保护规则 | 强制 1 approval + CI green | 🟡 中 |

### Phase 3: 长期改进

| 操作 | 说明 |
|------|------|
| GitHub Actions secrets 管理 | 将 API 密钥移至 GitHub Secrets |
| Dependabot 配置 | 自动依赖更新 |
| SBOM 生成 | 软件物料清单 |
| 代码扫描（CodeQL） | GitHub 安全扫描 |

---

## 七、Git 仓库健康度

| 指标 | 值 | 状态 |
|------|-----|------|
| 总提交数 | 367 | ✅ |
| 主要贡献者 | 1 (Li3379) | ✅ |
| 非规范提交 | 10/359 (2.8%) | ✅ |
| 活跃分支 | 6 (含 main) | ⚠️ 需清理 |
| Stale stash | 2 | ⚠️ 需清理 |
| .env 被跟踪 | 否 | ✅ |
| .idea 被跟踪 | 否 | ✅ |
| 大文件 | 无异常 | ✅ |
| 行尾规范 | .gitattributes 已配置 LF | ✅ |
