# 数据流水线模块 Debug 闭环报告

**日期**: 2026-07-28
**方法**: 修复 → 测验 → 修复 → 审计 (gsd-debug + ComputerUse)
**范围**: Phase 16 审计发现的 B06/A07 缺陷 + 测验中新发现的 resume_run 事务 Bug

---

## 修复清单

| # | 缺陷 | 严重度 | 根因 | 修复 | 文件 |
|---|------|--------|------|------|------|
| 1 | B06 断点续跑按钮永不显示 | Major | 后端 routes.py 漏传 `recent_failed_run`；前端按钮条件用 `current_run?.status==='failed'`（永不为真） | 后端补传字段 + 前端改用 `recent_failed_run && !is_running` + handleResume 用 `recent_failed_run.id` | routes.py:134, PipelineMonitor.vue:521, usePipelineMonitor.ts:478 |
| 2 | A07 Hero "2 跳过" 与 DAG 不一致 | Minor | stageSummary 未过滤 timeseries（已在 Phase 16 修复，Vite 缓存导致未生效） | 重启 frontend 容器使 `coreNames` 过滤器生效 | usePipelineMonitor.ts:193 (已有) |
| 3 | resume_run 事务回滚 | Major | executor.py `resume_run` 执行 UPDATE 后缺少 `await session.commit()`，session 关闭时回滚 | 添加显式 commit | executor.py:1281 |

---

## 验证结果

### 第一轮 (修复后 API 验证)
```
recent_failed_run: YES id=a2d127cd  ← 后端修复生效
Resume: import BEFORE failed/20errors → AFTER running/0errors  ← commit 修复生效
```

### 第二轮 (ComputerUse UI 验证)
| 验证项 | 结果 |
|--------|------|
| B06 断点续跑按钮显示 | PASS — 橙色按钮可见 |
| A07 Hero/DAG 一致性 | PASS — "5 已完成" = "5/5 阶段已完成" |
| Issue J 数字口径回归 | PASS — "采集 84 条 → 入库 0 条" + "(今日累计)" |
| 断点续跑功能 | PASS — Toast 正确 + 阶段重置 + run→running |

### 第三轮 (端到端生命周期)
| 验证项 | 结果 |
|--------|------|
| 运行中状态 | PASS — Hero "正在执行中" + DAG running |
| 按钮联动 | PASS — 运行中: 续跑隐藏/取消显示; 空闲: 续跑显示/取消隐藏 |
| SSE 实时 | PASS — 绿色指示器 + 断线 8s 自动重连 |
| 运行完成 | PASS — 96s 后 "全部完成"，5/5 阶段 |

---

## 32 项测试用例最终状态 (更新)

- **PASS = 31** (原 29 + B06/B07 修复后通过)
- **SKIPPED = 1**: B08 (当前无 failed 阶段可重试，代码逻辑正确)
- **FAIL = 0**
- **BLOCKED = 0**

---

## 残留观察项 (非阻塞)

| # | 描述 | 严重度 | 建议 |
|---|------|--------|------|
| 1 | sseMode Vue 警告重复 (MainLayout) | Cosmetic | 后续清理 |
| 2 | SSE 初始加载短暂 "连接中断" 后恢复 | Cosmetic | 指数退避已覆盖 |
| 3 | 错误消息英文技术原文 | Minor | 建议后续 Phase 加中文映射层 |

---

## 修改文件汇总

```
backend/app/api/v1/pipeline/routes.py      (+1 line: recent_failed_run 补传)
backend/app/core/pipeline/executor.py      (+1 line: await session.commit())
frontend/src/stores/pipelineRun.ts         (+1 line: interface 增加 recent_failed_run)
frontend/src/pages/PipelineMonitor.vue     (1 line: 按钮条件修改)
frontend/src/composables/usePipelineMonitor.ts (4 lines: handleResume 改用 failedRunId)
```
