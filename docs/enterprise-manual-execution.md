# StarMap 企业化治理 — 手动执行手册

> 以下操作需在本地终端（非沙箱）执行。所有命令均在仓库根目录 `C:\Users\LiShuai\Desktop\Agents\starmap` 下运行。

---

## Step 1: 分支清理（删除 5 个 stale 分支）

```bash
# 删除远程分支
git push origin --delete chore/ui-clean-ai-traces-batch2-frontend feat/plan-alignment-batch1 fix/pipeline-import-clean recovery-wip-others ui/upload-ux-polish

# 删除本地分支
git branch -D chore/ui-clean-ai-traces-batch2-frontend feat/plan-alignment-batch1 fix/pipeline-import-clean recovery-wip-others

# 切回 main
git checkout main
git branch -d ui/upload-ux-polish
```

## Step 2: Stash 清理

```bash
git stash drop "stash@{0}"
git stash drop "stash@{0}"
```

## Step 3: 移除 AI 工作截图（从 git 跟踪中移除，磁盘文件保留）

```bash
git rm --cached dashboard-current.png dashboard-domain-current.png dashboard-fixed.png dashboard-fixed2.png match-banner-fixed.png match-banner-polished.png position-detail-fixed.png positions-filter-with-unclassified.png positions-filter-with-unclassified-2.png
```

## Step 4: 暂存所有新文件并提交

```bash
git add LICENSE .github/CODEOWNERS SECURITY.md docs/enterprise-repo-audit-2026-08-18.md .gitignore

git commit -m "chore(enterprise): 企业级仓库治理 — LICENSE/CODEOWNERS/SECURITY.md + .gitignore 增强 + AI截图清理 + 治理报告"
```

## Step 5: 推送到远程

```bash
git push origin main
```

## Step 6（可选）: 安装 gitleaks pre-commit hook

```bash
# 需要先安装 gitleaks: https://github.com/gitleaks/gitleaks
# 然后在 .pre-commit-config.yaml 中添加:

# - repo: https://github.com/gitleaks/gitleaks
#   rev: v8.18.4
#   hooks:
#     - id: gitleaks

# 或使用 detect-secrets:
# pip install detect-secrets
# detect-secrets scan > .secrets.baseline
```

---

## 已完成的文件变更清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `LICENSE` | 新增 | MIT 许可证 |
| `.github/CODEOWNERS` | 新增 | PR 审查责任人 |
| `SECURITY.md` | 新增 | 安全漏洞报告流程 |
| `docs/enterprise-repo-audit-2026-08-18.md` | 新增 | 完整治理审计报告 |
| `.gitignore` | 修改 | 追加 AI 工作截图排除规则 |
