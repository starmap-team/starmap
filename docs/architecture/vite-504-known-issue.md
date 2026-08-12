---
title: Vite 6 optimizeDeps + Docker Desktop 匿名卷 → 浏览器端 504
date: 2026-08-13
owner: M1 全景图谱 (Phase 1)
phase: 01-home-module
source: 01-UI-REVIEW.md §"已知环境问题"
severity: P3 (环境问题,非代码缺陷)
status: documented (待环境层修复)
---

# Vite 6 optimizeDeps + Docker Desktop 匿名卷 + Playwright 504 三者纠缠

## 现象

Playwright 加载前端任意页面 → 浏览器控制台报 `504 Outdated Dep: optimizeDeps` → 页面加载后前端 verify 无法完成。

## 根因 (三者纠缠,非孤立)

1. **Vite 6 `optimizeDeps`**:内置 `rerun` 定时器需要在 `node_modules/.vite/deps_temp_*` 临时目录写入
2. **Docker Desktop for Windows 匿名卷写权限**:挂载 `node_modules` 时,匿名卷默认 root 拥有,容器内非 root 用户(appuser)无法写入临时目录
3. **定时器**:Vite 的 `rerun` 定时器在 Docker 启动早期尝试 mkdir → `EACCES: mkdir node_modules/.vite/deps_temp_*` 触发

## 受影响页面

- 全部前端页面 (Vite 共享 dev server)
- 仅本地 Docker Desktop for Windows 环境触发;Linux/macOS Docker 不触发

## 验证失败历史

- 2026-07-27 Phase 13 Step 7 (4 视图后端端点验证) — Playwright 截图缺失,代码逻辑 code review 正确

## 修复方向 (待执行,本 phase 不实施)

1. **修改 Dockerfile**:`RUN chown appuser node_modules/.vite` (需 builder 层写入)
2. **关闭 optimizeDeps**:via `VITE_CACHE_DIR` 环境变量 + `optimizeDeps: { disabled: true }` (损失首次加载快)
3. **Linux/macOS Docker**:作为 CI 默认环境绕开

## Phase 1 当前应对

- verify-first 方法论改为后端 curl 为主 + 必要时手动浏览器截图 (沿 `01-01-TASK3-VERIFICATION.md`)
- Playwright 截图作为 P3 项 backlog,环境修复后补

## 相关

- `.planning/phases/01-home-module/01-UI-REVIEW.md` §"已知环境问题"
- `.planning/phases/01-home-module/01-RESEARCH-AFTER.md` §"2.1 基础设施层"
- Phase 1 Plan 01-04 Task 4 (2026-08-13 落盘)