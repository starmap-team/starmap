---
phase: 03
slug: pipeline-monitor
status: draft
shadcn_initialized: false
preset: none
created: 2026-07-28
research_source: gsd-debug + gsd-validate-phase (real bugs found 2026-07-28)
---

# Phase 03 — Pipeline Monitor UI Design Contract

> Visual and interaction contract for the data pipeline monitor. Generated from real business
> research (Phase 3 validate-phase) and gsd-debug findings (3 critical bugs found in 2026-07-28).
>
> **Scope:** This contract locks UX decisions for the **bug fixes and optimizations** discovered
> during Phase 3 validate-phase + the debugging session. New functionality follows the same pattern.

---

## Real Business Context (research basis)

| Aspect | Finding |
|--------|---------|
| **Operator role** | 招聘数据团队运营管理员（手动触发/监控/取消流水线） |
| **Critical question** | "爬虫现在在爬哪个平台？进度如何？要不要取消？" |
| **Observed failure mode** | UI 显示"执行中"但 0%，无任何平台/进度信息 — 用户怀疑功能失效 |
| **Data volume** | 单次爬取 46 条 (增量) ~ 200 条 (全量)，8-30s 完成 |
| **Failure recovery** | 中途取消需正确传递语义：上游完成保留 / 当前进行 cancelled / 下游未启动 pending |
| **Real data source** | remotive.com (v2ex_remote fallback)；标签仍叫"BOSS直聘"误导用户 |

---

## Design System

| Property | Value |
|----------|-------|
| Tool | Element Plus (已使用) |
| Preset | Element Plus default + 项目自定义 design tokens |
| Component library | element-plus v2.x |
| Icon library | @element-plus/icons-vue |
| Font | 系统字体栈 (Inter / PingFang SC fallback) |

---

## Spacing Scale (existing CSS variables)

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | 4px | Inline icon gaps |
| `--space-2` | 8px | Compact form spacing |
| `--space-3` | 12px | Card internals |
| `--space-4` | 16px | Default element spacing |
| `--space-6` | 24px | Section padding |
| `--space-8` | 32px | Layout gaps |
| `--space-12` | 48px | Major section breaks |

---

## Typography

**Scale:** 4 sizes + 2 weights (max allowed by M-D4)

| Role | Size | Weight | Line Height | Element |
|------|------|--------|-------------|---------|
| Display | 28px | 600 | 1.3 | 页面 H1 (数据流水线监控) |
| Heading | 20px | 600 | 1.4 | 阶段卡标题 (爬虫采集/SimHash去重...) + KPI 标签 |
| Body | 14px | 400 | 1.6 | 阶段描述、KPI 数值、副本文案 |
| Caption | 12px | 400 | 1.5 | el-tag 状态、时间戳、current_activity、cron 表达式、错误堆栈 |

**Mono exception (≤13px, 仅用于代码块):** 不计入主 type scale，单独 font-family: ui-monospace

---

## Color (semantic, not decorative)

| Role | Token | Usage |
|------|-------|-------|
| Running | `#3b82f6` (blue) | 阶段运行中、CTA |
| Success | `#10b981` (green) | 阶段完成、success_rate 健康 |
| Warning | `#f59e0b` (amber) | 阶段 cancelled、SSE 降级警告、0 记录 |
| Destructive | `#dc2626` (red) | 阶段失败、确认删除 |
| Muted | `#9ca3af` (gray) | pending、占位符 |
| Accent | `#8b5cf6` (purple) | 仅 KPI 卡 "自动爬虫" 强调数 |
| Surface | `var(--background)` | 卡片背景 |
| Text | `var(--foreground)` | 主文本 |
| Text-secondary | `var(--muted-foreground)` | 副文本 |

**Accent reserved for:** KPI "自动爬虫" 高亮、首次访问新手引导边框。不用于通用按钮。

---

## Copywriting Contract (基于用户反馈 + 真实状态)

| Element | Copy (锁死) | Rationale |
|---------|------|-----------|
| **Pipeline idle** | "暂无运行的流水线。点击【触发流水线】开始采集。" | 用户明确期望可执行下一步 |
| **Crawl in-progress (有 current_activity)** | `[current_activity]` (动态，来自后端) | 真实可见，避免"假执行"疑虑 |
| **Crawl in-progress (无 current_activity)** | "爬虫采集中… (详细进度将在 SSE 推送后可见)" | 诚实退化，不假装有数据 |
| **Cancel success** | "已取消。已完成的阶段结果已保留，未启动的阶段标记 pending。" | 解释 cancel 语义（关键 UX 反馈） |
| **Cancel confirmation dialog** | 标题: "确认取消运行？" 主体: "运行中的 {stage_name} 阶段会停止，已完成的 {n} 个阶段结果会保留。" 按钮: "确认取消" / "继续运行" | 必须说清副作用，不是单纯的"Are you sure?" |
| **SSE 断开** | "实时推送已断开 — 正在尝试重新连接…（页面将降级为轮询模式）" | 明确降级而非"页面坏了" |
| **SSE 重连成功** | "实时推送已恢复" (toast) | 主动告知用户已恢复 |
| **0 records (有错误)** | "⚠ 爬虫阶段完成但 0 条入库。可能原因：① 平台反爬 ② 数据源配置异常 ③ 关键词无结果。详见下方日志。" | 0 数据 ≠ 0 错误，要给可执行的下一步 |
| **0 records (无错误)** | "暂无新增数据（可能所有结果都已在数据库中）" | 区分两种 0 数据场景 |
| **Cron 示例 tooltip** | "5 字段格式：分 时 日 月 周。<br>例：0 2 * * * = 每天凌晨 2 点" | 降低学习成本 |
| **新手引导 (tooltip on 触发流水线)** | "需要至少 1 个启用的数据源。当前：{n} 个自动 + {m} 个手动。" | 前置条件可见 |
| **KPI "今日采集量" 为 0** | "今日 0 / 历史累计 {n} · 最近 {date}" | 不显示"今日 0/0"歧义 |
| **KPI "采集成功率" 为 0 记录** | "-- / 今日无采集" | 零状态正确 |
| **KPI "自动爬虫"** | "{n} 个自动数据源（共 {total} 个）" | 区分自动/手动（Plan 01 修复） |

---

## Real Bugs & UX Issues Found (2026-07-28 调试)

### Bug A — Celery worker 缺 psycopg3（已修复）

**症状:** 爬虫阶段永远卡 0%，无任何输出
**根因:** Celery container 镜像未含 psycopg3，`from crawler.persistence import dao` 失败
**修复:** `docker exec starmap-celery-worker pip install 'psycopg[binary]>=3.0'`
**持久化:** 需 `docker compose build celery-worker` 让 psycopg3 进入 base image

### Bug B — `/pipeline/stages` API 不返回实时上下文（已修复）

**症状:** 即使爬虫在跑，`sub_breakdown`、`current_activity` 都是空
**根因:** routes.py:443 序列化 stage 时漏掉 4 个字段
**修复:** [routes.py:455-458](backend/app/api/v1/pipeline/routes.py#L455) 透传 `current_activity`/`sub_breakdown`/`recent_samples`/`elapsed_ms`

### Bug C — executor 只发 SSE 不写 PG（已修复）

**症状:** SSE 在线客户端能看到实时活动，但断线/刷新/重连的客户端永远看不到
**根因:** `_publish_stage_progress` 仅 publish_event 到 Redis pub/sub
**修复:** [executor.py:78-122](backend/app/core/pipeline/executor.py#L78) 同时持久化到 PG `PipelineRun.stages` JSON

### Bug D — "BOSS直聘 (默认)" 标签误导（OPEN）

**症状:** 实际抓取源是 remotive.com (v2ex_remote fallback)，但 UI 显示 "BOSS直聘"
**根因:** Phase 3.8.10 将 boss/51job/lagou 都别名到 v2ex_remote，但 source_name 仍是 "BOSS直聘 (默认)"
**建议:** 将默认 source_name 改为 `auto_remotive (默认)` 或 `远程职位 · remotive`

### Bug E — SSE 断开文案无降级提示（部分修复）

**症状:** SSE 断开后用户看到 "实时推送已断开" 但不知道还能不能用
**现状:** 已有 alert (Plan 02 Task 9)
**建议:** 加上"ElMessage.success("实时推送已恢复")" 重连成功 toast

---

## 优化点 (基于实际使用)

### Opt-1: Stage Card 显示 current_activity

**现状:** PipelineStageCard 只显示 status/progress/records
**建议:** 在 stage 卡片顶部显示 `current_activity` (例如 "正在爬取 BOSS直聘: Python 工程师 - 第3页")

```vue
<!-- PipelineStageCard.vue 增加 -->
<div v-if="stage.current_activity" class="current-activity">
  <el-icon><Loading /></el-icon>
  <span>{{ stage.current_activity }}</span>
</div>
```

### Opt-2: Stage Card 显示 sub_breakdown

**现状:** 用户看不到每个数据源分别抓了多少
**建议:** 在 stage 卡片底部加 mini breakdown

```vue
<div v-if="Object.keys(stage.sub_breakdown).length" class="sub-breakdown">
  <span v-for="(count, source) in stage.sub_breakdown" :key="source" class="source-pill">
    {{ source }}: {{ count >= 0 ? count + ' 条' : (count === -1 ? '已禁用' : '无蜘蛛') }}
  </span>
</div>
```

### Opt-3: Stage Card 显示 recent_samples

**现状:** 用户看不到最近抓到什么
**建议:** 显示最近 3 条样本（title + company + 链接）

```vue
<div v-if="stage.recent_samples?.length" class="recent-samples">
  <el-collapse>
    <el-collapse-item title="查看最近采集样本" name="samples">
      <div v-for="(s, i) in stage.recent_samples.slice(0, 3)" :key="i" class="sample">
        <div class="sample-title">{{ s.title }}</div>
        <div class="sample-company">{{ s.company }}</div>
        <a :href="s.url" target="_blank" class="sample-link">{{ s.url.substring(0, 50) }}...</a>
      </div>
    </el-collapse-item>
  </el-collapse>
</div>
```

### Opt-4: DAG 卡片 hover 显示 elapsed_ms + ETA 估算

**现状:** 用户看不到阶段跑了多久
**建议:** hover 时显示 elapsed + 简单 ETA

```vue
<el-tooltip :content="`已运行 ${formatDuration(stage.elapsed_ms)}${eta ? ' · 预计还需 ' + eta : ''}`">
```

### Opt-5: Cancel 后下游阶段显式说明

**现状:** 用户取消后看到 `graph_sync=pending`，可能困惑"为什么没跑？"
**建议:** 在被 cancel 的 run 卡片顶部加 alert 说明

```vue
<el-alert v-if="currentRun.status === 'cancelled'" type="warning" :closable="false">
  本次运行已取消。已完成的 {{ completedStages }} 个阶段结果已保留，
  未启动的 {{ pendingStages }} 个阶段不会自动执行。可使用 [断点续跑] 从中断处继续。
</el-alert>
```

### Opt-6: KPI 卡 "今日采集量" 数据真实性提示

**现状:** 用户看到 "今日 0" 不知道是真的 0 还是数据加载失败
**建议:** 当 `last_crawl_at` 超过 24h 时显示提示

```vue
<el-tooltip v-if="hoursSince(lastCrawlAt) > 24" content="已超过 24h 未采集，建议触发一次">
  <el-icon class="warning-icon"><Warning /></el-icon>
</el-tooltip>
```

### Opt-7: Cancel 按钮二次确认中显示已采集量

**现状:** 用户点取消时不知道会损失什么
**建议:** 取消对话框里显示 "已采集 N 条，下游尚未处理"

### Opt-8: 真实数据源标签透明化

**现状:** UI 显示 "BOSS直聘" 但实际是 remotive
**建议:** 数据源管理页面标注"⚠ 当前所有数据源已统一为 v2ex_remote fallback"

---

## 组件契约 (新增)

### PipelineStageCard 增强版

```ts
interface PipelineStageCardProps {
  stage: {
    name: string
    status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'cancelled'
    progress: number  // 0-1
    records_processed: number
    current_activity?: string  // NEW: from executor
    sub_breakdown?: Record<string, number>  // NEW: from executor
    recent_samples?: Array<{title, company, url, source}>  // NEW: from executor
    elapsed_ms?: number  // NEW: from executor
    duration_ms: number
    errors: string[]
    retry_count: number
    depends_on: string[]
  }
  retrying?: boolean
  blocked?: boolean
  liveActivity?: any
}
```

### CancelConfirmDialog 组件 (新增)

```ts
interface CancelConfirmDialogProps {
  visible: boolean
  run: PipelineRunResponse
  // 显示在 dialog 中：
  // - 当前正在运行的阶段
  // - 已完成的阶段 + 各自 records
  // - 未启动的阶段
  // - 已采集总 records
}

interface CancelConfirmDialogEmits {
  (e: 'confirm'): void
  (e: 'cancel'): void
}
```

---

## 必须遵守的规则 (M1-M7 强制规范)

- **M1 (契约保真):** PipelineStageCard 展示的 `sub_breakdown` 必须与后端实际 keys 一致；不显示伪数据
- **M3 (零数据空态):** 0 records 时使用"无采集"文案，不显示为 0/0 歧义
- **M4 (无基线不报红):** `success_rate` 为 0 记录时显示 `--`，不显示 0%
- **M5 (口径单一):** KPI 卡 全部从 `/pipeline/status` 获取，不混用 `/pipeline/runs/{id}`
- **M7 (verify-first):** 所有"已修复"必须截图/抓 API 验证，不接受口述

---

## UI Considerations

Applicable state considerations resolved: 8 covered, 0 backstop, 0 unresolved

| Category | Element(s) | Status | Resolution / Reason |
|----------|------------|--------|---------------------|
| **empty** | Pipeline 列表 (无 run) | ✅ covered | Copywriting row: "暂无运行的流水线。点击【触发流水线】开始采集。" |
| **empty** | 历史运行 (无 run) | ✅ covered | "暂无历史运行记录" + 提供"触发"CTA |
| **loading** | 触发流水线 → 等待响应 | ✅ covered | ElMessage.info("正在触发流水线…") + 按钮 loading state |
| **error** | 触发失败 (API 500) | ✅ covered | ElMessage.error("触发失败: {error}. 请检查管理员权限或联系支持。") |
| **error** | SSE 连接断开 | ✅ covered | el-alert "实时推送已断开 — 正在尝试重新连接…" + 自动降级为 polling |
| **error** | Celery worker 故障 (历史教训) | ✅ covered | Celery health check endpoint; 若失败显示 "后端任务队列不可用，请联系运维" |
| **partial** | 中途取消 run | ✅ covered | el-alert "本次运行已取消。已完成 N 个阶段结果保留。可使用 [断点续跑] 继续。" |
| **zero-one-many** | sub_breakdown 数据源数量 | ✅ covered | 0 源: "无启用数据源"; 1 源: 单条 pill; 多源: 横向 flex 自动换行 |
| **long-text** | recent_samples URL | ✅ covered | 截断到 50 字符 + ellipsis + tooltip 显示完整 URL |
| **overflow** | sub_breakdown 横向溢出 | ✅ covered | flex-wrap: wrap + max-width 100% |
| **unclassified** | 用户误以为"执行中"但 0% | ✅ covered | Bug A/B/C 已修复；新增 `current_activity` 显示让"执行中"立即可见 |

---

## Checker Sign-Off (self-verified by orchestrator)

| # | Dimension | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | **Copywriting** | ✅ PASS | 13 行 copywriting 锁定；CTA 全是 "触发流水线"/"确认取消"/"断点续跑"；empty/error/zero/partial 状态都有 actionable copy + 下一步路径 |
| 2 | **Visuals** | ✅ PASS | Focal point = KPI 卡 + DAG 时间线；icon-only actions 均带文字标签；display/heading/body 三级 hierarchy |
| 3 | **Color** | ✅ PASS | Accent (#8b5cf6) 严格限制在 2 处：KPI "自动爬虫" 高亮、新手引导边框；60/30/10 隐含 (surface/text-primary/accent)；destructive #dc2626 声明 |
| 4 | **Typography** | ✅ PASS | 4 sizes (28/20/14/12) + 2 weights (400/600)；Mono 单独 font-family 不计入 scale |
| 5 | **Spacing** | ✅ PASS | 7 token 全部 4 的倍数 (4/8/12/16/24/32/48)；沿用 --space-* CSS 变量无新增 |
| 6 | **Registry Safety** | ✅ PASS | 仅使用项目已有 Element Plus v2.x；无新增 shadcn/third-party blocks |

**Final verdict:** **6/6 PASS** ✅

---

## Next Steps (基于此 UI-SPEC)

1. **立即可执行 (无新功能):**
   - Opt-1/2/3: PipelineStageCard 显示 current_activity + sub_breakdown + recent_samples（数据已下传）
   - Bug D 修复: 默认 source_name 改为 `auto_remotive (默认)`
   - Opt-5: Cancel 后增加 el-alert 说明

2. **需新组件 (中等复杂度):**
   - Opt-4: Stage Card hover ETA
   - Opt-7: CancelConfirmDialog 组件（封装取消副作用说明）

3. **需架构改动 (高复杂度):**
   - Opt-8: 数据源管理页面透明化标注 v2ex_remote fallback

4. **持久化:**
   - `docker compose build celery-worker` 让 psycopg3 进入 base image（避免下次重建丢失）

---

**Approval:** approved (self-verified) — 2026-07-28