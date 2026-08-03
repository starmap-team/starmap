# 数据流水线模块前后端联通审计 — 测试用例与审计标准

**范围**: Phase 3 (Pipeline Monitor) + Phase 16 (Pipeline Audit) 全部前端功能
**方法**: 前端 UX 操作 → API 请求 → 后端响应 → 前端反馈 闭环验证
**日期**: 2026-07-28

---

## 一、前后端 API 契约映射

| # | 前端操作 | API 端点 | 后端路由 | 认证 |
|---|----------|----------|----------|------|
| 1 | 页面加载 → 状态概览 | GET /pipeline/status | routes.py:68 | Bearer |
| 2 | 运行历史列表 | GET /pipeline/runs | routes.py:145 | Bearer |
| 3 | 运行详情 | GET /pipeline/runs/{id} | routes.py:174 | Bearer |
| 4 | 触发流水线 | POST /pipeline/trigger | routes.py:211 | Admin |
| 5 | 取消运行 | POST /pipeline/runs/{id}/cancel | routes.py:187 | Bearer |
| 6 | 重试阶段 | POST /pipeline/runs/{id}/retry | routes.py:234 | Admin |
| 7 | 强制推进 | POST /pipeline/runs/{id}/force-advance | routes.py:248 | Admin |
| 8 | 强制重置 | POST /pipeline/runs/{id}/force-reset | routes.py:306 | Admin |
| 9 | 断点续跑 | POST /pipeline/runs/{id}/resume | routes.py:351 | Admin |
| 10 | 阶段状态 | GET /pipeline/stages | routes.py:401 | Bearer |
| 11 | 数据质量 | GET /pipeline/data-quality | routes.py:492 | Bearer |
| 12 | 数据源列表 | GET /pipeline/datasources | routes.py:527 | Bearer |
| 13 | SSE 实时事件 | GET /pipeline/events | routes.py:542 | SSE Token |
| 14 | 轮询降级 | GET /pipeline/events-poll | routes.py:575 | SSE Token |
| 15 | 定时调度 CRUD | GET/POST/PUT/DELETE /pipeline/schedules | routes.py:599+ | Admin |
| 16 | 配置读写 | GET/PUT /pipeline/config | routes.py (尾部) | Admin |

---

## 二、审计标准 (5 维度)

### D1: API 联通性
- 每个前端操作必须触发对应 API 调用
- 响应状态码 2xx → 前端正向反馈 (ElMessage.success)
- 响应状态码 4xx/5xx → 前端错误提示 (ElMessage.error + 具体消息)
- 网络超时 → 前端 loading 消失 + 错误提示

### D2: 数据一致性
- 前端展示的字段值 = API 响应 JSON 中的对应字段
- 数字口径: Hero(采集/入库) vs KPI(今日累计) vs DAG(单阶段单次) 语义清晰
- 阶段状态: 前端标签映射 (completed→已完成, running→运行中, failed→失败, skipped→已跳过)

### D3: UX 反馈闭环
- 每个用户操作有即时视觉反馈 (loading/toast/状态变化)
- 异步操作有成功/失败两条路径的反馈
- 危险操作有确认对话框 (取消运行、强制重置)
- SSE 断连有提示 + 自动重连 + 恢复 toast

### D4: 状态机正确性
- Pipeline Run: pending → running → completed/failed/cancelled
- Stage: pending → running → completed/failed/skipped/cancelled
- 前端按钮可见性与 run 状态一致 (running 时显示取消, failed 时显示续跑)
- 终态后不可再触发操作 (cancelled/completed 无取消按钮)

### D5: 容错与降级
- SSE 失败 → 自动降级 polling → 恢复后切回 SSE
- API 不可用 → 页面不白屏，显示错误状态
- 后端返回 null/缺失字段 → 前端 fallback (progress=null→100%)

---

## 三、测试用例 (32 项)

### 模块 A: 页面加载与数据展示 (8 项)

| TC | 操作 | 预期 API | 预期 UX | 审计维度 |
|----|------|----------|---------|----------|
| A01 | 打开 /pipeline | GET status + stages + data-quality + datasources | 骨架屏→数据填充，无白屏 | D1,D3 |
| A02 | 检查 KPI "今日采集量" | status.today_crawl_volume | 数字 + "(今日累计)" 标注 | D2 |
| A03 | 检查 KPI "采集成功率" | status.success_rate | 百分比或 "--" (无采集时) | D2 |
| A04 | 检查 KPI "自动爬虫" | status.active_data_sources | 数字 + "N个自动数据源 (共M个)" | D2 |
| A05 | 检查 Hero 卡片 | stages[].records_processed | "采集 N 条 → 入库 M 条, 累计耗时 Xs" | D2 |
| A06 | 检查 DAG 5 阶段 | stages[] | 每阶段: 名称+状态标签+进度条+记录数+耗时 | D2 |
| A07 | 阶段完成数一致性 | stages[] | Hero 完成数 = DAG 完成数 (仅核心 5 阶段) | D2 |
| A08 | 数据质量面板 | GET data-quality | 质量分数 + 告警列表 | D1 |

### 模块 B: 触发与控制 (8 项)

| TC | 操作 | 预期 API | 预期 UX | 审计维度 |
|----|------|----------|---------|----------|
| B01 | 点击"触发流水线" | — | 弹出对话框: 全量/增量 + 5 阶段复选 | D3 |
| B02 | 选增量+仅crawl→启动 | POST trigger {run_type, selected_stages} | Toast "流水线已触发（增量，1 个阶段）" | D1,D3 |
| B03 | 触发后状态变化 | SSE event | Hero "正在执行中" + 阶段 running | D4 |
| B04 | 运行中点击"取消运行" | POST runs/{id}/cancel | 确认框→Toast "已取消" + 状态 cancelled | D1,D3,D4 |
| B05 | 卡死时"强制推进" | POST runs/{id}/force-advance | Toast 成功 + 阶段状态变化 | D1,D3 |
| B06 | 卡死时"强制重置" | POST runs/{id}/force-reset | 确认框→Toast + 状态重置 | D1,D3,D4 |
| B07 | 失败后"断点续跑" | POST runs/{id}/resume | Toast "从失败阶段继续" + 状态 running | D1,D3,D4 |
| B08 | 失败阶段"重试" | POST runs/{id}/retry {stage_name} | Toast "阶段已重新调度" | D1,D3 |

### 模块 C: SSE 实时与降级 (6 项)

| TC | 操作 | 预期 API | 预期 UX | 审计维度 |
|----|------|----------|---------|----------|
| C01 | 页面加载 SSE 连接 | GET events?token=xxx | 指示器 "SSE 实时" 绿色 | D1 |
| C02 | 运行中阶段进度更新 | SSE stage_update | 进度条动态递增 + 记录数实时变化 | D2,D3 |
| C03 | 模拟 SSE 断连 (kill 后端) | — | 指示器变红 + "连接中断" + 自动重连 | D5 |
| C04 | SSE 恢复 | GET events (重连) | Toast "实时推送已恢复" + 指示器恢复 | D3,D5 |
| C05 | 连续失败→polling 降级 | GET events-poll | 数据继续更新 (轮询模式) | D5 |
| C06 | 首次加载 token 过期 | 401 → refresh → reconnect | 短暂提示后自动恢复，无需用户干预 | D5 |

### 模块 D: 定时调度与配置 (5 项)

| TC | 操作 | 预期 API | 预期 UX | 审计维度 |
|----|------|----------|---------|----------|
| D01 | 打开定时调度对话框 | GET schedules | 列表显示已有调度 | D1 |
| D02 | 创建调度 | POST schedules | Toast "已创建" + 列表刷新 | D1,D3 |
| D03 | 手动触发调度 | POST schedules/{id}/trigger | Toast 成功 + 流水线开始 | D1,D3 |
| D04 | 删除调度 | DELETE schedules/{id} | 确认框→列表移除 | D1,D3 |
| D05 | 修改配置 | PUT config | Toast 成功 + 配置生效 | D1,D3 |

### 模块 E: 容错与边界 (5 项)

| TC | 操作 | 预期 API | 预期 UX | 审计维度 |
|----|------|----------|---------|----------|
| E01 | 后端不可用时加载页面 | 连接拒绝 | 错误提示，不白屏 | D5 |
| E02 | completed 阶段 progress=null | stages[].progress=null | 显示 100% (fallback) | D2,D5 |
| E03 | 触发失败 (403 非管理员) | POST trigger → 403 | Toast "触发失败：权限不足" | D1,D3 |
| E04 | 错误消息展示 | stages[].errors | 去重显示 + "×N" 徽章，无 raw Traceback | D2 |
| E05 | 空数据状态 (无运行历史) | runs=[] | 空态提示，不报错 | D3 |

---

## 四、已知风险点 (从代码分析发现)

| # | 风险 | 影响 | 建议 |
|---|------|------|------|
| R1 | /pipeline/stages 回退展示最近 failed run | 用户刚成功触发后看到旧失败状态 | 产品复核 UX 策略 |
| R2 | 错误消息为英文技术原文 | 非技术用户无法理解 | 后端添加中文映射层 |
| R3 | SSE token 通过 URL query 传递 | 日志中可能泄露 token | 评估 short-lived SSE token |
| R4 | force-advance/force-reset 无二次确认 | 误操作可能破坏运行状态 | 前端已有确认框 (已验证) |
| R5 | 批量操作无 rate limit | 快速连续触发可能创建多个 run | 后端添加 cooldown |

---

## 五、测试执行策略

### 自动化覆盖
- **已有**: test_pipeline_e2e.py (6), test_pipeline_api.py (886行), phase16-audit.spec.ts (5), sse-reconnect.spec.ts (2)
- **补充**: 本文 TC 中 B04-B08 (控制操作) 和 E01-E05 (容错) 建议补充 Playwright e2e

### 手动验证
- C03/C04 (SSE 断连恢复) 需 Docker stop/start 模拟
- R1 (stages 回退策略) 需产品确认

### 通过标准
- D1 (联通性): 16/16 端点 2xx 可达
- D2 (一致性): 数字口径三处语义清晰
- D3 (UX 反馈): 每个操作 ≤500ms 有视觉反馈
- D4 (状态机): 按钮可见性与 run 状态 100% 一致
- D5 (容错): 后端不可用时不白屏
